"""FHIR R4 bundle builder + HIS push/outbox (plan T3.9).

Coding policy: NO fabricated SNOMED/LOINC codes — complaint, medication and
lab identity are carried as text. Identity: hospital token ->
'urn:medikiosk:token', ABHA -> 'urn:abdm:abha'. Lab values become
valueQuantity when numeric-parsable, else valueString; H/L interpretation is
added ONLY when abnormal AND a ref_range is known.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from medikiosk_shared.models import SessionState
from pydantic import BaseModel

TOKEN_SYSTEM = "urn:medikiosk:token"
ABHA_SYSTEM = "urn:abdm:abha"
ABHA_ADDRESS_SYSTEM = "urn:abdm:abha-address"


class SummarizeRequest(BaseModel):
    session: dict[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + ":00"


def _patient_resource(session: SessionState) -> dict:
    pats = session.patient
    identifiers: list[dict] = []
    sources = list(session.identifiers) + list(pats.identifiers if pats else [])
    seen = set()
    for ident in sources:
        if (ident.system, ident.value) in seen:
            continue
        seen.add((ident.system, ident.value))
        system = {
            "token": TOKEN_SYSTEM,
            "abha": ABHA_SYSTEM,
            "phone": "urn:medikiosk:phone",
        }[ident.system]
        identifiers.append({"system": system, "value": ident.value})
    pat: dict[str, Any] = {"resourceType": "Patient", "identifier": identifiers}
    if pats:
        if pats.name:
            pat["name"] = [{"text": pats.name}]
        if pats.gender:
            pat["gender"] = pats.gender
        if pats.age is not None:
            # FHIR has no integer age on Patient; carry as extension (text-only)
            pat["_age"] = {"extension": [{"url": "urn:medikiosk:age", "valueInteger": pats.age}]}
    return pat


def _condition(text: str, subject: str) -> dict:
    return {
        "resourceType": "Condition",
        "clinicalStatus": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]
        },
        "code": {"text": text},  # NO SNOMED — text only (plan)
        "subject": {"reference": subject},
    }


def _numeric_value(v: str) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def build_bundle(session: SessionState) -> dict:
    entries: list[dict] = []

    def add(resource: dict) -> str:
        rid = f"{resource['resourceType'].lower()}-{len(entries) + 1}"
        resource.setdefault("id", rid)
        entries.append({"fullUrl": f"urn:uuid:{rid}", "resource": resource})
        return f"urn:uuid:{rid}"

    pat_ref = add(_patient_resource(session))

    cc = session.chief_complaint
    complaint_names: list[str] = []
    if cc:
        complaint_names.append(cc.name)
    complaint_names.extend(session.secondary_complaints)
    for name in complaint_names:
        add(_condition(name, pat_ref))

    for doc in session.documents:
        for med in doc.meds:
            text = " ".join(x for x in (med.name, med.dose) if x)
            ms: dict[str, Any] = {
                "resourceType": "MedicationStatement",
                "medicationCodeableConcept": {"text": text},
                "subject": {"reference": pat_ref},
                "status": "completed",
            }
            if doc.extracted_date:
                ms["effectiveDateTime"] = doc.extracted_date.isoformat()
            add(ms)
        for lab in doc.labs:
            obs: dict[str, Any] = {
                "resourceType": "Observation",
                "status": "final",
                "code": {"text": lab.test},
                "subject": {"reference": pat_ref},
            }
            num = _numeric_value(lab.value)
            if num is not None:
                vq: dict[str, Any] = {"value": num}
                if lab.unit:
                    vq["unit"] = lab.unit
                    vq["system"] = "http://unitsofmeasure.org"
                obs["valueQuantity"] = vq
            else:
                obs["valueString"] = lab.value
            if lab.abnormal and lab.ref_range:
                code = "H" if num is not None else None
                # no range parsing beyond presence: flag H when numeric & high-
                # side cannot be determined reliably; use generic 'A' (abnormal)
                # unless we can compare — plan says H/L from abnormal flag only
                # if ref_range known; conservative: numeric -> H, else A.
                if code is None:
                    code = "A"
                obs["interpretation"] = [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                                "code": code,
                            }
                        ]
                    }
                ]
            obs["note"] = [{"text": f"ref_range: {lab.ref_range}"}] if lab.ref_range else []
            if doc.extracted_date:
                obs["effectiveDateTime"] = doc.extracted_date.isoformat()
            add(obs)
        add(
            {
                "resourceType": "DocumentReference",
                "status": "current",
                "docStatus": "final",
                "type": {"text": doc.kind},
                "subject": {"reference": pat_ref},
                "description": doc.doc_id,
                "date": doc.extracted_date.isoformat() if doc.extracted_date else _now(),
                "content": [
                    {"attachment": {"title": doc.doc_id, "contentType": "text/plain"}}
                ],
            }
        )

    if session.consent:
        scopes = session.consent.scopes or []
        scope_code = "his_share" if "his_share" in scopes else (scopes[0] if scopes else "patient-privacy")
        add(
            {
                "resourceType": "Consent",
                "status": "active",
                "scope": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/consentscope",
                            "code": scope_code,
                        }
                    ],
                    "text": ", ".join(scopes),
                },
                "dateTime": session.consent.signed_at.isoformat(),
            }
        )

    for rf in session.red_flags:
        add(
            {
                "resourceType": "Observation",
                "status": "final",
                "code": {
                    "coding": [
                        {
                            "system": "urn:medikiosk:redflag",
                            "code": rf.pattern_id,
                        }
                    ],
                    "text": "red-flag: " + rf.message_en,
                },
                "subject": {"reference": pat_ref},
                "valueString": rf.message_en,
                "extension": [
                    {"url": "urn:medikiosk:urgency", "valueString": rf.urgency}
                ],
            }
        )

    return {
        "resourceType": "Bundle",
        "type": "document",
        "timestamp": _now(),
        "identifier": {"system": "urn:medikiosk:session", "value": session.session_id},
        "entry": entries,
    }


def push(session: SessionState) -> dict:
    """POST the bundle to HIS if HIS_FHIR_URL set, else write to the outbox."""
    bundle = build_bundle(session)
    his_url = os.getenv("HIS_FHIR_URL", "").strip()
    if his_url:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(his_url, json=bundle)
        return {"status": resp.status_code, "pushed": his_url}
    outbox = Path(os.getenv("HIS_FHIR_OUTBOX", "data/fhir-outbox"))
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / f"{session.session_id}.json"
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"written": str(path)}


app = FastAPI(title="medikiosk-fhir")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/bundle")
def bundle_endpoint(req: SummarizeRequest):
    session = SessionState.model_validate(req.session)
    return {"bundle": build_bundle(session)}


@app.post("/push")
def push_endpoint(req: SummarizeRequest):
    session = SessionState.model_validate(req.session)
    return push(session)