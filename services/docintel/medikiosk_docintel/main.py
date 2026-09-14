"""MediKiosk docintel service (plan T3.10) — full document pipeline.

POST /process {text, doc_id} → DocumentRecord-shaped JSON:
classify → extract_date → NER (meds/labs) → flag_labs → interactions.

NOTE: the NER extraction is called via DIRECT IMPORT
(medikiosk_ner.extractor.extract_entities), not over HTTP, so the kiosk demo
runs single-process (plan AD-7: demo deployability on one kiosk box). In a
later deployment phase this becomes a network call behind a queue.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from medikiosk_docintel.intel import (
    build_timeline,
    check_interactions,
    classify,
    evaluate_clinical_safety,
    extract_date,
    flag_labs,
)
# Direct import, NOT http — keeps the demo single-process (see module docstring).
from medikiosk_ner.extractor import extract_entities
from medikiosk_shared.models import DocumentRecord

app = FastAPI(title="MediKiosk DocIntel", version="0.1.0")


class ProcessRequest(BaseModel):
    text: str = Field(min_length=1)
    doc_id: str | None = None
    conditions: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    age: int | None = None
    sex: str | None = None


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "docintel"}


@app.post("/process")
def process(req: ProcessRequest):
    text = req.text
    kind = classify(text)
    extracted_date = extract_date(text)
    ents = extract_entities(text)
    labs = flag_labs(
        [
            # coerce dicts → LabExtract so abnormal-flagging returns typed models
            __import__("medikiosk_shared.models", fromlist=["LabExtract"]).LabExtract.model_validate(l)
            for l in ents["labs"]
        ],
        age=req.age,
        sex=req.sex,
    )
    meds = [
        __import__("medikiosk_shared.models", fromlist=["MedExtract"]).MedExtract.model_validate(m)
        for m in ents["drugs"]
    ]
    interactions = check_interactions(meds)
    safety_alerts = evaluate_clinical_safety(
        meds=meds,
        conditions=req.conditions,
        allergies=req.allergies,
        age=req.age,
        sex=req.sex,
    )
    doc = DocumentRecord(
        doc_id=req.doc_id or f"doc-auto",
        kind=kind,
        extracted_date=extracted_date,
        meds=meds,
        labs=labs,
        raw_text_ref=f"raw/{req.doc_id or 'auto'}.txt",
    )
    timeline = build_timeline([doc])
    return doc.model_dump(mode="json") | {
        "interactions": interactions,
        "safety_alerts": [a.model_dump(mode="json") for a in safety_alerts],
        "timeline_label": timeline[0][1],
    }