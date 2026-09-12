"""Bhashini/ULCA ASR backend (plan T3.12)."""
from __future__ import annotations

import os
from typing import Literal

import httpx

_BHASHINI_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"


def transcribe(
    audio_bytes: bytes,
    lang: Literal["hi", "en"] = "hi",
    pipeline_id: str | None = None,
) -> tuple[str, str]:
    api_key = os.getenv("BHASHINI_ULCA_API_KEY", "")
    if not api_key:
        raise RuntimeError("BHASHINI_ULCA_API_KEY not set")
    pid = pipeline_id or os.getenv("BHASHINI_ASR_PIPELINE_ID", "")
    if not pid:
        raise RuntimeError("BHASHINI_ASR_PIPELINE_ID not set")
    import base64
    payload = {
        "pipeline_id": pid,
        "data": [base64.b64encode(audio_bytes).decode()],
        "audio": [{"audioContent": base64.b64encode(audio_bytes).decode()}],
        "source_language": lang,
        "target_language": lang,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=30) as c:
        r = c.post(_BHASHINI_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    text = (
        data.get("pipeline_response", [{}])[0]
        .get("output", [{}])[0]
        .get("source", "")
    )
    return text or "", lang
