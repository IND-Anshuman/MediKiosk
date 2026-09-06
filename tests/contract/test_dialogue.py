"""T3.4: Dialogue engine contract tests (plan v2).

Locks the v2 behaviors that fix v1's bugs:
  - SessionStore-backed (AD-9): survives engine restart; no in-process dict
  - multi_choice multi-tap (C-10): touch_indices list -> list value
  - confirmation echo (AD-10): low ASR confidence -> confirm step
  - red-flag check after every answer with list-intersection semantics
  - secondary complaints captured via other_problems question
"""

from pathlib import Path

import pytest

from medikiosk_ontology.loader import load_ontology
from medikiosk_shared.models import SessionState

ONTO = load_ontology(Path("packages/ontology/data"))


class StubLLM:
    """Deterministic slot extraction from Hindi text."""

    def extract(self, *, text: str, slot_schema: dict, language: str) -> dict:
        if "do din" in text:
            return {"choice": "2-3 din se"}
        if "tez" in text:
            return {"choice": "Sharp/stabbing"}
        return {"choice": text.strip() or "unparsed"}


class FakeStore:
    """In-memory SessionStore for tests (same protocol as RedisSessionStore)."""

    def __init__(self):
        self.data: dict[str, SessionState] = {}

    def save(self, state: SessionState) -> None:
        self.data[state.session_id] = state

    def load(self, session_id: str) -> SessionState | None:
        return self.data.get(session_id)


@pytest.fixture()
def eng():
    from medikiosk_dialogue.main import DialogueEngine

    return DialogueEngine(ONTO, llm=StubLLM(), store=FakeStore())


class TestBasicFlow:
    def test_starts_with_onset_question(self, eng):
        sid = eng.start_session(chief_complaint="chest_pain", language="hi")
        q = eng.next_question(sid)
        assert q.id == "onset"

    def test_voice_answer_advances(self, eng):
        sid = eng.start_session(chief_complaint="fever", language="hi")
        eng.answer(sid, raw_text="do din se bukhar hai", language="hi")
        q = eng.next_question(sid)
        assert q.id == "peak_temp"

    def test_touch_answer_uses_index(self, eng):
        sid = eng.start_session(chief_complaint="fever", language="hi")
        eng.answer(sid, touch_indices=[2], language="hi")  # "2-3 din se"
        slots = {s.key: s.value for s in eng.load(sid).chief_complaint.slots}
        assert slots["onset"] == "2-3 din se"

    def test_multi_tap_yields_list_value(self, eng):
        sid = eng.start_session(chief_complaint="chest_pain", language="en")
        # walk to 'associated' (multi_choice): onset, location, character, radiation
        for _ in range(4):
            eng.answer(sid, touch_indices=[0], language="en")
        eng.answer(sid, touch_indices=[0, 1], language="en")  # Sweating + SOB
        slots = {s.key: s.value for s in eng.load(sid).chief_complaint.slots}
        assert slots["associated"] == ["Sweating", "Shortness of breath"]

    def test_interview_completes(self, eng):
        sid = eng.start_session(chief_complaint="fever", language="hi")
        while eng.next_question(sid) is not None:
            eng.answer(sid, touch_indices=[0], language="hi")
        assert eng.next_question(sid) is None


class TestConfirmEcho:
    def test_low_confidence_triggers_confirm(self, eng):
        sid = eng.start_session(chief_complaint="fever", language="hi")
        resp = eng.answer(
            sid, raw_text="do din se bukhar", language="hi", asr_confidence=0.4
        )
        assert resp["confirm"] is not None
        assert resp["confirm"]["heard"] == "do din se bukhar"
        # slot pending, not confirmed
        state = eng.load(sid)
        assert state.chief_complaint.slots[-1].confirmed is False

    def test_confirm_yes_promotes(self, eng):
        sid = eng.start_session(chief_complaint="fever", language="hi")
        eng.answer(sid, raw_text="do din se", language="hi", asr_confidence=0.4)
        resp = eng.answer(sid, confirm=True)
        assert resp["confirm"] is None
        assert eng.load(sid).chief_complaint.slots[-1].confirmed is True

    def test_confirm_no_reasks(self, eng):
        sid = eng.start_session(chief_complaint="fever", language="hi")
        eng.answer(sid, raw_text="galat suna", language="hi", asr_confidence=0.4)
        resp = eng.answer(sid, confirm=False)
        assert resp["re_asking"] is True
        q = eng.next_question(sid)
        assert q.id == "onset"  # same question again
        # pending unconfirmed slot was dropped
        assert all(s.confirmed for s in eng.load(sid).chief_complaint.slots)


class TestRedFlags:
    def test_mi_pattern_fires_mid_interview(self, eng):
        sid = eng.start_session(chief_complaint="chest_pain", language="en")
        # onset, location, character taps then radiation=Left arm(0), associated=Sweating(0)
        eng.answer(sid, touch_indices=[1], language="en")  # Today
        eng.answer(sid, touch_indices=[0], language="en")  # Center of chest
        eng.answer(sid, touch_indices=[0], language="en")  # Crushing
        resp = eng.answer(sid, touch_indices=[0], language="en")  # Left arm
        assert resp["red_flag"] is None  # needs both radiation AND associated
        resp = eng.answer(sid, touch_indices=[0], language="en")  # Sweating
        assert resp["red_flag"] is not None
        assert resp["red_flag"]["urgency"] == "immediate"

    def test_no_false_positive(self, eng):
        sid = eng.start_session(chief_complaint="chest_pain", language="hi")
        eng.answer(sid, touch_indices=[3], language="hi")
        eng.answer(sid, touch_indices=[3], language="hi")
        eng.answer(sid, touch_indices=[3], language="hi")
        resp = eng.answer(sid, touch_indices=[3], language="hi")  # Back / stays
        assert resp["red_flag"] is None


class TestPersistence:
    def test_survives_engine_restart(self, eng):
        sid = eng.start_session(chief_complaint="fever", language="hi")
        eng.answer(sid, touch_indices=[1], language="hi")

        from medikiosk_dialogue.main import DialogueEngine

        eng2 = DialogueEngine(ONTO, llm=StubLLM(), store=eng.store)
        q = eng2.next_question(sid)
        assert q.id == "peak_temp"  # continued where it left off

    def test_engine_has_no_inprocess_state(self, eng):
        assert not hasattr(eng, "state")  # AD-9 regression guard


class TestSecondaryComplaints:
    def test_other_problems_appends(self, eng):
        sid = eng.start_session(chief_complaint="fever", language="hi")
        while eng.next_question(sid) is not None:
            q = eng.next_question(sid)
            if q.id == "other_problems":
                eng.answer(sid, touch_indices=[0, 1], language="hi")  # Cough, Abdominal
            else:
                eng.answer(sid, touch_indices=[0], language="hi")
        assert set(eng.load(sid).secondary_complaints) == {"cough", "abdominal_pain"}