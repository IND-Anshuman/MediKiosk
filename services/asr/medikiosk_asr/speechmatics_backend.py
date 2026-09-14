"""Speechmatics API ASR backend (plan T3.1 option B).

Speechmatics v2 REST API — upload audio, get transcript. Multilingual
(Hindi native), so the ASR service needs NO local whisper model when this
backend is chosen: runtime stays lean and languages come from the API.
Key: SPEECHMATICS_API_KEY. Enabled via ASR_BACKEND=speechmatics.
"""
from __future__ import annotations

import json
import os
import time

import httpx

_JOBS_URL = "https://api.speechmatics.com/v2/jobs"


def transcribe(audio_bytes: bytes, lang: str = "hi") -> tuple[str, str]:
    api_key = os.getenv("SPEECHMATICS_API_KEY", "")
    if not api_key:
        raise RuntimeError("SPEECHMATICS_API_KEY not set")
    headers = {"Authorization": f"Bearer {api_key}"}

    config = {
        "type": "transcription",
        "transcription_config": {"language": lang},
    }
    audio_suffix = ".webm" if audio_bytes[:4] == b"\x1aE\xdf\xa3" else ".wav"
    files = [
        ("data_file", (f"audio{audio_suffix}", audio_bytes, "audio/octet-stream")),
        ("config", (None, json.dumps(config), "application/json")),
    ]

    with httpx.Client(timeout=60.0) as c:
        r = c.post(_JOBS_URL, headers=headers, files=files)
        r.raise_for_status()
        job = r.json()
    job_id = job.get("id")
    if not job_id:
        raise RuntimeError("Speechmatics job creation failed (no id)")

    with httpx.Client(timeout=30.0) as c:
        for _ in range(30):
            jr = c.get(f"{_JOBS_URL}/{job_id}", headers=headers)
            jr.raise_for_status()
            payload = jr.json()
            state = payload.get("job", {}).get("status")
            if state == "done":
                transcription = payload.get("transcription", {})
                return _extract_text(transcription), lang
            if state in ("rejected", "failed"):
                raise RuntimeError(f"Speechmatics job failed: {state}")
            time.sleep(2)
    raise RuntimeError("Speechmatics job timed out")


def _extract_text(transcription: dict) -> str:
    texts = [
        alt.get("transcript", "")
        for group in transcription.get("results", [])
        for alt in group.get("alternatives", [])
    ]
    return " ".join(t for t in texts if t).strip()