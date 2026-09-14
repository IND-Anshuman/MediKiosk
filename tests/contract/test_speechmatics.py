"""ASR backend selection: local faster-whisper OR Speechmatics API.

Speechmatics is OpenAI-quality ASR over HTTP (multilingual, incl. Hindi),
keyed by SPEECHMATICS_API_KEY. Using it means the ASR service needs NO local
model — the container stays lean and the language list is native to the API.
Selection via ASR_BACKEND=local|speechmatics (default local).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from medikiosk_asr import speechmatics_backend as mod


def test_speechmatics_adapter_exists():
    assert hasattr(mod, "transcribe")


def test_speechmatics_transcribe_calls_api(monkeypatch):
    captured = {}

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): return None
        def json(self): return self._p

    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, **kw):
            captured["url"], captured["kw"] = url, kw
            return FakeResp({"id": "job-123"})
        def get(self, url, **kw):
            captured["poll_url"] = url
            return FakeResp({"job": {"status": "done"}, "transcription": {
                "results": [{"alternatives": [{"transcript": "नमस्ते डॉक्टर"}]}]}})

    monkeypatch.setattr(mod, "httpx", MagicMock())
    monkeypatch.setattr(mod.httpx, "Client", lambda **_: FakeClient())
    monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")

    text, lang = mod.transcribe(b"fake-audio-bytes", lang="hi")
    assert "नमस्ते" in text
    assert lang == "hi"
    assert "api.speechmatics.com" in captured["url"]


def test_speechmatics_no_key_raises(monkeypatch):
    monkeypatch.delenv("SPEECHMATICS_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        mod.transcribe(b"x", lang="hi")