"""OCR backend selection: PaddleOCR local OR vision-LLM (Featherless/OpenAI).

Using the vision LLM means the OCR service needs NO paddleocr model — the
container stays lean; the image is sent to an OpenAI-compatible vision model
(Featherless base URL + key). Selection via OCR_BACKEND=paddle|vision.
"""
from __future__ import annotations

import pytest


def test_vision_ocr_adapter_exists():
    from medikiosk_ocr import vision_ocr
    assert hasattr(vision_ocr, "ocr_bytes")


def test_vision_ocr_calls_llm_with_image(monkeypatch):
    from medikiosk_ocr import vision_ocr as mod

    captured = {}
    class FakeCompletions:
        def create(self, **kw):
            captured["kw"] = kw
            return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "Aspirin 75mg"})})]})()
    fake_client = type("F", (), {"chat": type("Ch", (), {"completions": FakeCompletions()})})
    monkeypatch.setattr(mod, "_get_client", lambda: fake_client)
    monkeypatch.setenv("OPENAI_API_KEY", "fl-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.featherless.ai/v1")
    monkeypatch.setenv("OCR_BACKEND", "vision")

    text, pages = mod.ocr_bytes(b"fake-image-bytes")
    assert "Aspirin" in text
    assert pages == 1
    # the image must travel as a data URL in the message content
    sent = str(captured["kw"].get("messages", []))
    assert "image" in sent.lower() or "data:" in sent


def test_vision_ocr_no_key_degrades(monkeypatch):
    from medikiosk_ocr import vision_ocr
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # no key -> no client -> error surfaced rather than silent fake
    with pytest.raises(RuntimeError):
        vision_ocr._get_client()