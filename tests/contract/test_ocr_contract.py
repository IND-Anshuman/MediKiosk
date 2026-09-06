"""T3.6: OCR service contract (paddleocr — lazily imported, Linux-only in dev).

Stubbed _ocr_bytes → tests run model-free on Windows (paddle is Docker-only).
"""

import pytest
from fastapi.testclient import TestClient

from medikiosk_ocr.main import app


@pytest.fixture()
def c():
    return TestClient(app)


def test_healthz(c):
    assert c.get("/healthz").status_code == 200


def test_ocr_stubbed(monkeypatch, c):
    import medikiosk_ocr.main as m

    monkeypatch.setattr(m, "_ocr_bytes", lambda data, lang: ("Rx: paracetamol", 2))
    r = c.post("/ocr", files={"image": ("scan.png", b"\x89PNG-fake", "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "Rx: paracetamol"
    assert body["pages"] == 2


def test_ocr_rejects_bad_mime(c):
    r = c.post("/ocr", files={"image": ("x.txt", b"nope", "text/plain")})
    assert r.status_code == 415


def test_ocr_rejects_empty(c):
    r = c.post("/ocr", files={"image": ("x.png", b"", "image/png")})
    assert r.status_code == 422


def test_real_engine_unavailable_is_503(c, monkeypatch):
    """When paddle is NOT importable (Windows dev), the endpoint says so clearly."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("paddleocr") or name.startswith("paddle"):
            raise ImportError("paddleocr is not installed (Linux/Docker only)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # Force the lazy-import path even if paddle were cached elsewhere.
    r = c.post("/ocr", files={"image": ("x.png", b"\x89PNG-fake", "image/png")})
    assert r.status_code == 503
    assert "paddle" in r.json()["detail"].lower()