"""MediKiosk NER service (plan T3.7) — thin FastAPI wrapper over the
deterministic rule-based extractor. No ML, no network: same-process,
same-dictionary output every time.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from medikiosk_ner.extractor import extract_entities

app = FastAPI(title="MediKiosk NER", version="0.1.0")


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "ner"}


@app.post("/extract")
def extract(req: ExtractRequest):
    try:
        return extract_entities(req.text)
    except Exception as e:  # pragma: no cover — extractor is total over str
        raise HTTPException(500, f"extraction failed: {e}") from e