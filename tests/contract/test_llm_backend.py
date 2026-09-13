"""LLM backend selection — one OpenAI-compatible config for any provider.

The project talks to any OpenAI-compatible endpoint (OpenAI, Featherless,
Groq, Together, local vLLM/Ollama) through the SAME three variables:
  OPENAI_API_KEY   — the credential
  OPENAI_BASE_URL  — the endpoint (omit for api.openai.com)
  OPENAI_MODEL     — the model id
No provider-specific variables exist.
"""
from __future__ import annotations

import json


def test_custom_base_url_used_when_set(monkeypatch):
    """Featherless-style config: key + base URL + model, all via OPENAI_*. """
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    monkeypatch.delenv("FEATHERLESS_BASE_URL", raising=False)
    monkeypatch.delenv("FEATHERLESS_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fl-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.featherless.ai/v1")
    monkeypatch.setenv("OPENAI_MODEL", "fl-model")

    from medikiosk_dialogue.openai_llm import OpenAILLM

    llm = OpenAILLM()
    assert llm.client.api_key == "fl-key"
    assert "featherless" in str(llm.client.base_url or "")
    assert llm.model == "fl-model"


def test_default_openai_when_no_base_url(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
    monkeypatch.setenv("OPENAI_MODEL", "oa-model")

    from medikiosk_dialogue.openai_llm import OpenAILLM

    llm = OpenAILLM()
    assert llm.client.api_key == "oa-key"
    assert llm.model == "oa-model"


def test_default_model_when_nothing_set(monkeypatch):
    for v in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
              "FEATHERLESS_API_KEY", "FEATHERLESS_BASE_URL", "FEATHERLESS_MODEL"):
        monkeypatch.delenv(v, raising=False)

    from medikiosk_dialogue.openai_llm import OpenAILLM

    assert OpenAILLM().model == "gpt-4o-mini"


def test_no_key_degrades_gracefully(monkeypatch):
    for v in ("OPENAI_API_KEY", "FEATHERLESS_API_KEY"):
        monkeypatch.delenv(v, raising=False)

    from medikiosk_dialogue.openai_llm import OpenAILLM

    llm = OpenAILLM()
    assert llm.client is None  # no client built
    assert llm.extract(text="x", slot_schema={}, language="en") == {}


def test_extract_never_leaks_api_key(monkeypatch):
    """The API key lives only in the client; extract() sends schema+text (AD-3)."""
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.featherless.ai/v1")
    monkeypatch.setenv("OPENAI_MODEL", "m1")

    captured: dict = {}
    import medikiosk_dialogue.openai_llm as mod

    class FakeCompletions:
        def create(self, **kw):
            captured["kw"] = kw
            return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": '{"choice": "ok"}'})})]})()

    fake_client = type("F", (), {"chat": type("Ch", (), {"completions": FakeCompletions()})})
    llm = mod.OpenAILLM(client=fake_client)
    llm.model = "m1"
    llm.extract(text="user says hi", slot_schema={"x": 1}, language="en")

    sent = json.dumps(captured["kw"])
    assert "super-secret-key" not in sent
    assert "user says hi" in sent