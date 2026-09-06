"""T3.1: ASR service contract (faster-whisper, utterance-level).

Stubbed _transcribe → CI runs model-free. GPU test is opt-in via RUN_GPU_TESTS.
"""

import os

import pytest
from fastapi.testclient import TestClient

from medikiosk_asr.main import app


@pytest.fixture()
def c():
    return TestClient(app)


def test_healthz(c):
    assert c.get("/healthz").status_code == 200


def test_transcribe_stubbed(monkeypatch, c):
    import medikiosk_asr.main as m

    monkeypatch.setattr(
        m, "_transcribe", lambda b: ("namaste doctor", "hi", 0.92)
    )
    r = c.post(
        "/transcribe", files={"audio": ("x.wav", b"RIFF-fake", "audio/wav")}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "namaste doctor"
    assert body["language"] == "hi"
    assert body["confidence"] == pytest.approx(0.92)


def test_transcribe_rejects_bad_mime(c):
    r = c.post("/transcribe", files={"audio": ("x.txt", b"nope", "text/plain")})
    assert r.status_code == 415


@pytest.mark.skipif(not os.getenv("RUN_GPU_TESTS"), reason="needs faster-whisper model")
def test_real_english_clip(c):
    with open("tests/fixtures/audio/english_hello.wav", "rb") as f:
        data = f.read()
    r = c.post("/transcribe", files={"audio": ("x.wav", data, "audio/wav")})
    assert "hello" in r.json()["text"].lower()