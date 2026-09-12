"""T3.5 addendum: Featherless LLM backend (OpenAI-compatible).

When FEATHERLESS_API_KEY is set, the DialogueEngine's OpenAILLM uses
Featherless's base URL + model instead of OpenAI's. Never sends PII (AD-3).
"""
from __future__ import annotations

import json


def test_featherless_client_used_when_key_present(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "oa-model")  # should be ignored
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fl-key")
    monkeypatch.setenv("FEATHERLESS_MODEL", "fl-model")
    monkeypatch.setenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")

    from medikiosk_dialogue.openai_llm import OpenAILLM

    llm = OpenAILLM()
    assert llm.client.api_key == "fl-key"
    assert "featherless" in str(llm.client.base_url or "")
    assert llm.model == "fl-model"  # FEATHERLESS_MODEL wins over OPENAI_MODEL


def test_openai_client_used_when_no_featherless_key(monkeypatch):
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
    monkeypatch.setenv("OPENAI_MODEL", "oa-model")

    from medikiosk_dialogue.openai_llm import OpenAILLM

    llm = OpenAILLM()
    assert llm.client.api_key == "oa-key"
    assert llm.model == "oa-model"


def test_default_model_fallback_when_neither_key(monkeypatch):
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("FEATHERLESS_MODEL", raising=False)

    from medikiosk_dialogue.openai_llm import OpenAILLM

    assert OpenAILLM().model == "gpt-4o-mini"


def test_extract_never_leaks_api_key(monkeypatch):
    """The API key lives only in the client; extract() sends schema+text."""
    monkeypatch.setenv("FEATHERLESS_API_KEY", "super-secret-fl")
    monkeypatch.setenv("FEATHERLESS_MODEL", "fl-model")

    captured: dict = {}
    import medikiosk_dialogue.openai_llm as mod

    class FakeCompletions:
        def create(self, **kw):
            captured["kw"] = kw
            return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": '{"choice": "ok"}'})})]})()

    fake_client = type("F", (), {"chat": type("Ch", (), {"completions": FakeCompletions()})})
    llm = mod.OpenAILLM(client=fake_client)
    llm.model = "fl-model"
    llm.extract(text="user says hi", slot_schema={"x": 1}, language="en")

    sent = json.dumps(captured["kw"])
    assert "super-secret-fl" not in sent
    assert "user says hi" in sent