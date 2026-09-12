"""T3.12: Bhashini/ULCA ASR/TTS backends — contract tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kw):
        return _FakeResp({
            "pipeline_response": [
                {"output": [{"source": "नमस्ते डॉक्टर", "audioContent": "ZmFrZS1tcDctYnl0ZXM="}]}
            ]
        })


def test_asr_bhashini_backend_exists():
    from medikiosk_asr import bhashini_backend
    assert hasattr(bhashini_backend, "transcribe")


def test_tts_bhashini_backend_exists():
    from medikiosk_tts import bhashini_backend
    assert hasattr(bhashini_backend, "synthesize")


def test_asr_bhashini_transcribe_returns_text_and_lang(monkeypatch):
    import medikiosk_asr.bhashini_backend as mod
    monkeypatch.setenv("BHASHINI_ULCA_API_KEY", "fake-key")
    monkeypatch.setenv("BHASHINI_ASR_PIPELINE_ID", "pipe-1")
    monkeypatch.setattr(mod, "httpx", MagicMock())
    monkeypatch.setattr(mod.httpx, "Client", lambda **_: _FakeClient())

    text, lang = mod.transcribe(b"fake-audio-bytes", lang="hi")
    assert "नमस्ते" in text
    assert lang == "hi"


def test_tts_bhashini_synthesize_returns_bytes(monkeypatch):
    import medikiosk_tts.bhashini_backend as mod
    monkeypatch.setenv("BHASHINI_ULCA_API_KEY", "fake-key")
    monkeypatch.setenv("BHASHINI_TTS_PIPELINE_ID", "pipe-2")
    monkeypatch.setattr(mod, "httpx", MagicMock())
    monkeypatch.setattr(mod.httpx, "Client", lambda **_: _FakeClient())

    audio = mod.synthesize("नमस्ते", lang="hi")
    assert isinstance(audio, bytes)
    assert len(audio) > 0


def test_bhashini_no_key_raises(monkeypatch):
    monkeypatch.delenv("BHASHINI_ULCA_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_ASR_PIPELINE_ID", raising=False)
    from medikiosk_asr import bhashini_backend
    with pytest.raises(RuntimeError):
        bhashini_backend.transcribe(b"fake", lang="hi")
