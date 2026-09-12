"""DialogueEngine (plan T3.4 v2).

v1 bugs fixed here:
  - AD-9: NO in-process session dict. All state flows through a SessionStore
    (Redis in prod, any impl in tests). Engine restarts resume cleanly.
  - C-10: multi_choice answered with touch_indices: list[int] -> list value.
  - AD-10: low ASR confidence (< 0.75, passed in by the caller) triggers a
    confirmation echo; confirm-yes promotes the slot, confirm-no re-asks.
  - Red-flag matching runs after every answer using the ontology's
    list-intersection matcher over ALL confirmed slots.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from medikiosk_ontology.loader import Ontology, Question, load_ontology
from medikiosk_shared.models import (
    Answer,
    ChiefComplaint,
    RedFlagAlert,
    SessionState,
    Slot,
    Source,
)

CONFIRM_THRESHOLD = 0.75

# other_problems touch options map to chief complaint keys (index-aligned
# with each complaint's other_problems options — kept in one place).
OTHER_PROBLEMS_MAP: dict[str, list[str]] = {
    "chest_pain": ["fever", "cough", "headache", "abdominal_pain", "comorbidity", None],
    "fever": ["cough", "abdominal_pain", "gi", "comorbidity", None],
    "abdominal_pain": ["fever", "cough", "headache", "chest_pain", "comorbidity", None],
    "cough": ["fever", "headache", "abdominal_pain", "chest_pain", "comorbidity", None],
    "headache": ["fever", "cough", "abdominal_pain", "chest_pain", "comorbidity", None],
}


class LLM(Protocol):
    def extract(self, *, text: str, slot_schema: dict, language: str) -> dict: ...


class SessionStore(Protocol):
    def save(self, state: SessionState) -> None: ...
    def load(self, session_id: str) -> SessionState | None: ...


class DialogueEngine:
    def __init__(self, ontology: Ontology, llm: LLM, store: SessionStore):
        self.ontology = ontology
        self.llm = llm
        self.store = store

    # -- session lifecycle ---------------------------------------------------

    def start_session(self, *, chief_complaint: str, language: str = "hi") -> str:
        state = SessionState(
            language=language,
            chief_complaint=ChiefComplaint(
                name=chief_complaint,
                framework=self.ontology.chief_complaints[chief_complaint].framework,
                slots=[],
            ),
        )
        self.store.save(state)
        return state.session_id

    def load(self, session_id: str) -> SessionState:
        state = self.store.load(session_id)
        if state is None:
            raise KeyError(f"unknown session {session_id}")
        return state

    # -- question flow ---------------------------------------------------------

    def next_question(self, session_id: str) -> Question | None:
        state = self.load(session_id)
        defn = self.ontology.chief_complaints[state.chief_complaint.name]
        asked = {s.key for s in state.chief_complaint.slots}
        for q in defn.questions:
            if q.id not in asked:
                return q
        return None  # complete

    def answer(
        self,
        session_id: str,
        *,
        raw_text: str | None = None,
        touch_indices: list[int] | None = None,
        language: str = "hi",
        asr_confidence: float | None = None,
        confirm: bool | None = None,
    ) -> dict[str, Any]:
        """Answer the current question. Returns {red_flag, next, confirm, re_asking}."""
        state = self.load(session_id)
        defn = self.ontology.chief_complaints[state.chief_complaint.name]

        # --- confirmation-echo handling (AD-10) -----------------------------
        pending = [s for s in state.chief_complaint.slots if not s.confirmed]
        if confirm is not None and pending:
            slot = pending[-1]
            if confirm:
                slot.confirmed = True
                self.store.save(state)
                return self._respond(state)
            # confirm-no: drop unconfirmed slot; question will be re-asked
            state.chief_complaint.slots.remove(slot)
            self.store.save(state)
            return {**self._respond(state), "re_asking": True}

        q = self.next_question(session_id)
        if q is None:
            return self._respond(state)  # nothing to answer

        # --- parse the answer -------------------------------------------------
        parsed: Any
        if touch_indices:
            opts = defn_questions_options(defn, q, language)
            if isinstance(touch_indices, int):  # defensive: client sent bare int
                touch_indices = [touch_indices]
            chosen = [opts[i] for i in touch_indices]
            parsed = chosen if q.type == "multi_choice" else chosen[0]
            source, confidence = Source.TOUCH, 1.0
        else:
            text = (raw_text or "").strip()
            schema = {"question_id": q.id, "type": q.type, "options": q.touch_options_en}
            extracted = self.llm.extract(text=text, slot_schema=schema, language=language)
            choice = extracted.get("choice")
            # snap free-text to a known option when unambiguous (echo-safe)
            if isinstance(choice, str) and choice not in (q.touch_options_en + q.touch_options_hi):
                choice = _fuzzy_snap(choice, q)
            parsed = choice if choice is not None else text
            source, confidence = Source.VOICE, (asr_confidence if asr_confidence is not None else 0.9)

        needs_confirm = (
            source == Source.VOICE
            and asr_confidence is not None
            and asr_confidence < CONFIRM_THRESHOLD
        )
        slot = Slot(
            key=q.id,
            value=parsed,
            source=source,
            confidence=confidence,
            confirmed=not needs_confirm,
        )
        state.chief_complaint.slots.append(slot)
        state.answers.append(
            Answer(
                question_id=q.id,
                raw_text=raw_text or "",
                parsed={"value": parsed},
                language=language,
            )
        )

        # --- secondary complaints from other_problems ------------------------
        if q.id == "other_problems" and touch_indices:
            mapping = OTHER_PROBLEMS_MAP.get(state.chief_complaint.name, [])
            for i in touch_indices:
                if i < len(mapping) and mapping[i]:
                    if mapping[i] not in state.secondary_complaints:
                        state.secondary_complaints.append(mapping[i])

        self.store.save(state)
        resp = self._respond(state)
        if needs_confirm:
            resp["confirm"] = {"heard": raw_text, "question_id": q.id}
        return resp

    # -- red flags -------------------------------------------------------------

    def check_red_flag(self, session_id: str) -> RedFlagAlert | None:
        state = self.load(session_id)
        confirmed_slots = {s.key: s.value for s in state.chief_complaint.slots if s.confirmed}
        rf = self.ontology.match_red_flag(
            chief_complaint=state.chief_complaint.name, slots=confirmed_slots
        )
        if rf is None:
            return None
        if any(a.pattern_id == rf.pattern_id for a in state.red_flags):
            return next(a for a in state.red_flags if a.pattern_id == rf.pattern_id)
        alert = RedFlagAlert(
            pattern_id=rf.pattern_id,
            urgency=rf.urgency,
            message_hi=rf.message_hi,
            message_en=rf.message_en,
        )
        state.red_flags.append(alert)
        self.store.save(state)
        return alert

    # -- internals ---------------------------------------------------------------

    def _respond(self, state: SessionState) -> dict[str, Any]:
        rf = self.check_red_flag(state.session_id)
        nq = self.next_question(state.session_id)
        return {
            "red_flag": rf.model_dump() if rf and rf.pattern_id not in {
                a.pattern_id for a in state.red_flags[:-1]
            } else None,
            "next_question": nq.model_dump() if nq else None,
            "confirm": None,
            "re_asking": False,
        }


def defn_questions_options(defn, q: Question, language: str) -> list[str]:
    opts = q.touch_options_hi if language == "hi" else q.touch_options_en
    return opts if opts else q.touch_options_en


def _fuzzy_snap(choice: str, q: Question) -> str:
    """Snap LLM output to a known touch option (en or hi) by substring."""
    low = choice.lower()
    for opt in q.touch_options_en + q.touch_options_hi:
        if low in opt.lower() or opt.lower() in low:
            return opt
    return choice


# ── HTTP service layer (plan v2: independent FastAPI service, port 8003) ────
# Mechanically simple: build engine against Redis + a swappable LLM, expose
# /healthz, /dialogue/start, /dialogue/answer. Session state stays in the
# store between requests (AD-9: no in-process dict).

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="medikiosk-dialogue")

_engine = None


class SessionStoreImpl:
    """Redis-backed SessionStore (AD-9). Matches the SessionStore protocol."""

    def __init__(self) -> None:
        import redis

        self.r = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
        self._ttl = 60 * 60 * 4  # sliding 4h, matches API gateway

    def save(self, state: SessionState) -> None:
        self.r.set(f"session:{state.session_id}", state.model_dump_json(), ex=self._ttl)

    def load(self, session_id: str) -> SessionState | None:
        raw = self.r.get(f"session:{session_id}")
        if not raw:
            return None
        return SessionState.model_validate_json(raw)


def get_engine():
    global _engine
    if _engine is None:
        onto = load_ontology(Path(os.getenv("ONTOLOGY_DIR", "packages/ontology/data")))
        if os.getenv("LLM_BACKEND", "stub") == "openai":
            from medikiosk_dialogue.openai_llm import OpenAILLM
            llm: LLM = OpenAILLM()
        else:
            from medikiosk_dialogue import stub_llm
            llm = stub_llm.StubLLM()
        _engine = DialogueEngine(onto, llm, SessionStoreImpl())
    return _engine


@app.get("/healthz")
def healthz():
    return {"ok": True}


class StartReq(BaseModel):
    chief_complaint: str
    language: str = "hi"


@app.post("/dialogue/start")
def start(req: StartReq):
    e = get_engine()
    if req.chief_complaint not in e.ontology.chief_complaints:
        raise HTTPException(422, f"unknown chief complaint: {req.chief_complaint}")
    sid = e.start_session(chief_complaint=req.chief_complaint, language=req.language)
    nq = e.next_question(sid)
    return {"session_id": sid, "next_question": nq.model_dump() if nq else None}


class AnswerReq(BaseModel):
    session_id: str
    raw_text: str | None = None
    touch_indices: list[int] | None = None
    language: str = "hi"
    asr_confidence: float | None = None
    confirm: bool | None = None


@app.post("/dialogue/answer")
def answer(req: AnswerReq):
    e = get_engine()
    try:
        resp = e.answer(
            req.session_id,
            raw_text=req.raw_text,
            touch_indices=req.touch_indices,
            language=req.language,
            asr_confidence=req.asr_confidence,
            confirm=req.confirm,
        )
    except KeyError:
        raise HTTPException(404, f"unknown session {req.session_id}")
    return resp