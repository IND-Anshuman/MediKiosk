"""T3.5: Real LLM slot-filler (OpenAILLM) + prompt hygiene (plan AD-3).

AD-3 (critical): the composed LLM prompt must NEVER contain patient PII —
no patient name, no ABHA number. Only the utterance text + slot schema
travel to the remote LLM. Also locked: malformed JSON degrades to {}.
"""

import json
import os
from types import SimpleNamespace

import pytest

from medikiosk_dialogue.openai_llm import OpenAILLM


class RecordingStub:
    """Stub OpenAI client: records what it was asked, returns canned JSON."""

    def __init__(self, response: str = '{"choice": "Sharp/stabbing"}'):
        self.calls: list[dict] = []
        self._response = response

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content=self._response)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class ExplodingStub:
    """Returns garbage that breaks JSON parsing."""

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        msg = SimpleNamespace(content="not json at all {")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _session_like_context():
    """A SessionState-like context that WOULD leak PII if the caller were naive."""
    return {
        "patient": {"name": "Ravi Kumar", "abha": "14-3344-5566-7788"},
        "session_id": "sess-abc123",
        "chief_complaint": "chest_pain",
    }


def test_prompt_hygiene_no_name_no_abha():
    """AD-3: composed messages must not contain patient name or ABHA."""
    stub = RecordingStub()
    llm = OpenAILLM(client=stub)
    llm.extract(
        text="डो दिन से दर्द है",
        slot_schema={"question_id": "character", "type": "single_choice"},
        language="hi",
        context=_session_like_context(),
    )
    assert stub.calls, "stub client was never called"
    sent = json.dumps(stub.calls[0], ensure_ascii=False)  # whole request payload
    assert "Ravi Kumar" not in sent
    assert "14-3344-5566-7788" not in sent
    assert "sess-abc123" not in sent
    # the utterance and schema DID travel
    assert "डो दिन से दर्द है" in sent
    assert "character" in sent


def test_extract_parses_choice():
    stub = RecordingStub('{"choice": "Sharp/stabbing"}')
    llm = OpenAILLM(client=stub)
    out = llm.extract(
        text="tez dard", slot_schema={"question_id": "character"}, language="hi"
    )
    assert out == {"choice": "Sharp/stabbing"}
    kwargs = stub.calls[0]
    assert kwargs["temperature"] == 0
    assert kwargs["model"] == llm.model


def test_malformed_json_returns_empty_dict():
    llm = OpenAILLM(client=ExplodingStub())
    out = llm.extract(text="anything", slot_schema={}, language="hi")
    assert out == {}


def test_extract_on_stub_failure_returns_empty_dict():
    class Boom:
        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            raise RuntimeError("network down")

    llm = OpenAILLM(client=Boom())
    assert llm.extract(text="x", slot_schema={}, language="hi") == {}


def test_live_llm_opt_in():
    """Real API call only when RUN_LIVE_LLM is exported; skipped otherwise."""
    if not os.getenv("RUN_LIVE_LLM"):
        pytest.skip("set RUN_LIVE_LLM=1 for the live OpenAI call")
    llm = OpenAILLM()
    out = llm.extract(
        text="do din se bukhar hai",
        slot_schema={"question_id": "onset", "type": "free_text"},
        language="hi",
    )
    assert isinstance(out, dict)