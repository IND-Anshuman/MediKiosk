"""Vision-LLM OCR backend — runs OCR via an OpenAI-compatible vision model.

Enabled with OCR_BACKEND=vision (default is local paddleocr). The image is
base64'd into a chat message and the model returns extracted text. Uses the
same OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL config as the LLM
services — so pointing them at Featherless with a vision-capable model id
gives API-only OCR with NO local paddle model (lean container).
"""
from __future__ import annotations

import base64
import os
from typing import Any

from fastapi import HTTPException


def _get_client() -> Any:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OCR vision backend needs OPENAI_API_KEY")
    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL", "") or None)


def ocr_bytes(data: bytes) -> tuple[str, int]:
    """OCR image bytes -> (text, page_count) via a vision-capable LLM."""
    client = _get_client()
    image_b64 = base64.b64encode(data).decode("ascii")
    mime = "image/png"  # docintel sends PNG; service validates mime upstream
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract ALL text from this medical document image verbatim, preserving layout line breaks. Return only the text, no commentary."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                ],
            }
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise HTTPException(422, "OCR vision returned no text")
    return text, 1