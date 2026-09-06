"""MediKiosk ASR service (plan T3.1, AD-1).

Design: utterance-level batching — the CLIENT records a full utterance
(client-side VAD/silence detection), POSTs the complete clip here; this
service transcribes it with faster-whisper (CPU int8) and returns text +
detected language + a confidence score.

Why no server-side streaming: openai-whisper has NO streaming API (v1 plan
bug C-03). Partial transcripts are a v1.1 feature (LocalAgreement-style
sliding window). The demo latency story is carried by pre-baked TTS
questions (AD-2) + instant touch feedback.

Confidence: sigmoid of mean avg_logprob across segments — a calibrated
proxy used by the dialogue engine to trigger the confirmation echo when
< 0.75 (AD-10).
"""

from __future__ import annotations

import math
import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(title="MediKiosk ASR", version="0.1.0")

ALLOWED_MIME = {"audio/wav", "audio/x-wav", "audio/wave", "audio/webm", "audio/ogg", "audio/mpeg"}
CONFIRM_THRESHOLD = 0.75

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            os.getenv("ASR_MODEL", "small"),
            device=os.getenv("ASR_DEVICE", "cpu"),
            compute_type=os.getenv("ASR_COMPUTE", "int8"),
        )
    return _model


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "asr"}


def _transcribe(audio_bytes: bytes) -> tuple[str, str, float]:
    """Transcribe full utterance bytes → (text, language, confidence)."""
    suffix = ".webm" if audio_bytes[:4] == b"\x1aE\xdf\xa3" else ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        model = _get_model()
        segments, info = model.transcribe(
            path,
            language=None,  # auto-detect hi/en
            vad_filter=True,  # trims silence — robust in noisy OPD
            beam_size=1,
        )
        texts, logprobs = [], []
        for seg in segments:
            texts.append(seg.text.strip())
            logprobs.append(seg.avg_logprob)
        text = " ".join(t for t in texts if t).strip()
        confidence = _sigmoid(sum(logprobs) / len(logprobs)) if logprobs else 0.0
        return text, info.language, round(confidence, 3)
    finally:
        os.unlink(path)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    if audio.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"unsupported audio type: {audio.content_type}")
    data = await audio.read()
    if not data:
        raise HTTPException(422, "empty audio")
    text, language, confidence = _transcribe(data)
    return {
        "text": text,
        "language": language,
        "confidence": confidence,
        "needs_confirmation": confidence < CONFIRM_THRESHOLD,
    }