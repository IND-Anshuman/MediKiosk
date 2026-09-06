"""MediKiosk OCR service (plan T3.6, AD-7 Module A).

Digitizes scanned prescriptions/lab reports/discharge summaries into raw text
that docintel (T3.10) classifies and structures.

Engine: PaddleOCR — imported LAZILY inside _ocr_bytes because paddleocr is
Linux-only in this setup (installed in the Docker image, not on Windows dev
machines and not in pyproject deps). Without it the service still imports and
serves /healthz on Windows; POST /ocr answers 503 with a clear message.
"""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(title="MediKiosk OCR", version="0.1.0")

ALLOWED_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/tiff"}


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "ocr"}


def _ocr_bytes(data: bytes, lang: str = "en") -> tuple[str, int]:
    """OCR image bytes → (text, page_count).

    Raises HTTPException(503) when paddleocr is unavailable (Windows dev).
    """
    try:
        from paddleocr import PaddleOCR  # noqa: lazy — Docker-only dep
    except ImportError as e:
        raise HTTPException(
            503,
            "OCR engine unavailable: paddleocr is not installed "
            "(Linux/Docker only in this setup; run the service in its container).",
        ) from e

    ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    import io

    import cv2  # paddleocr's image decoder is cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(422, "unparseable image bytes")
    result = ocr.ocr(img, cls=True)
    pages = len(result) if result else 1
    lines: list[str] = []
    for page in result or []:
        for line in page or []:
            lines.append(line[1][0])  # (box, (text, conf))
    return "\n".join(lines), pages


@app.post("/ocr")
async def ocr(image: UploadFile = File(...), lang: str = "en"):
    if image.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"unsupported image type: {image.content_type}")
    data = await image.read()
    if not data:
        raise HTTPException(422, "empty image")
    text, pages = _ocr_bytes(data, lang)
    return {"text": text, "pages": pages}