"""Bhashini/ULCA TTS backend (plan T3.12)."""
from __future__ import annotations

import os
from typing import Literal

import httpx

_BHASHINI_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"


def synthesize(
    text: str,
    lang: Literal["hi", "en"] = "hi",
    pipeline_id: str | None = None,
) -> bytes:
    api_key = os.getenv("BHASHINI_ULCA_API_KEY", "")
    if not api_key:
        raise RuntimeError("BHASHINI_ULCA_API_KEY not set")
    pid = pipeline_id or os.getenv("BHASHINI_TTS_PIPELINE_ID", "")
    if not pid:
        raise RuntimeError("BHASHINI_TTS_PIPELINE_ID not set")
    payload = {
        "pipeline_id": pid,
        "data": [text],
        "source_language": lang,
        "target_language": lang,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=30) as c:
        r = c.post(_BHASHINI_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    audio_b64 = (
        data.get("pipeline_response", [{}])[0]
        .get("output", [{}])[0]
        .get("audioContent", "")
    )
    if not audio_b64:
        return b""
    import base64
    return base64.b64decode(audio_b64)
