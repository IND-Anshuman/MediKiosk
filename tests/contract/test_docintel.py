"""T3.10: docintel contract — classify, extract_date, flag_labs,
check_interactions, build_timeline, and the full /process pipeline.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from medikiosk_docintel.intel import (
    build_timeline,
    check_interactions,
    classify,
    extract_date,
    flag_labs,
)
from medikiosk_shared.models import DocumentRecord, LabExtract, MedExtract


# ---------- classify ----------

def test_classify_prescription():
    assert classify("Rx\nTab Paracetamol 650mg TDS") == "prescription"
    assert classify("Prescription Dr. Sharma") == "prescription"


def test_classify_lab_report():
    assert classify("Lab Report\nHemoglobin 10.2 g/dL") == "lab"
    assert classify("Investigation report: HbA1c 8.5%") == "lab"


def test_classify_discharge():
    assert classify("Discharge Summary — advised rest and follow-up") == "discharge"


def test_classify_unknown():
    assert classify("random note about weather") == "unknown"


# ---------- extract_date ----------

def test_extract_date_slash_format():
    assert extract_date("Visited on 14/03/2025") == date(2025, 3, 14)


def test_extract_date_day_month_ambiguity_resolves_dd_mm():
    # 14/03 → day 14 > 12, unambiguous dd/mm
    assert extract_date("14/03/25") == date(2025, 3, 14)


def test_extract_date_dotted():
    assert extract_date("Date: 05.04.2025") == date(2025, 4, 5)


def test_extract_date_devanagari_prefix():
    assert extract_date("दिनांक: 12/01/2025") == date(2025, 1, 12)


def test_extract_date_absent_returns_none():
    assert extract_date("no date here, just meds") is None
    # bare year or 1-2 digit fragments must NOT be guessed into a date
    assert extract_date("year 2025 intake") is None


# ---------- flag_labs ----------

def test_flag_hb_low_female():
    labs = [LabExtract(test="hemoglobin", value="6.5", unit="g/dL")]
    out = flag_labs(labs, age=30, sex="female")
    assert out[0].abnormal is True


def test_flag_hb_normal_female():
    labs = [LabExtract(test="hemoglobin", value="12.5", unit="g/dL")]
    out = flag_labs(labs, age=30, sex="female")
    assert out[0].abnormal is False


def test_flag_defaults_adult_band():
    labs = [LabExtract(test="hemoglobin", value="6.5", unit="g/dL")]
    out = flag_labs(labs)  # no age/sex → adult default
    assert out[0].abnormal is True


def test_flag_unknown_test_left_alone():
    labs = [LabExtract(test="mysteryine", value="99", unit="x")]
    out = flag_labs(labs, age=30, sex="male")
    assert out[0].abnormal is False


# ---------- check_interactions ----------

def test_aspirin_warfarin_flagged():
    meds = [MedExtract(name="aspirin"), MedExtract(name="warfarin")]
    hits = check_interactions(meds)
    assert any(
        h["a"] == "aspirin" and h["b"] == "warfarin" and h["severity"] == "major"
        for h in hits
    )


def test_no_interaction_returns_empty():
    meds = [MedExtract(name="cetirizine"), MedExtract(name="paracetamol")]
    assert check_interactions(meds) == []


def test_interaction_match_is_case_insensitive():
    meds = [MedExtract(name="Aspirin"), MedExtract(name="WARFARIN")]
    assert check_interactions(meds)


# ---------- build_timeline ----------

def _doc(d, day=None, kind="prescription"):
    return DocumentRecord(
        doc_id=d, kind=kind, extracted_date=day, raw_text_ref=f"raw/{d}.txt"
    )


def test_timeline_dated_ascending():
    docs = [
        _doc("b", date(2025, 3, 2)),
        _doc("a", date(2025, 1, 5)),
        _doc("c", date(2025, 2, 1)),
    ]
    order = [rec.doc_id for rec, _lbl in build_timeline(docs)]
    assert order == ["a", "c", "b"]


def test_timeline_undated_first_labeled():
    docs = [
        _doc("b", date(2025, 3, 2)),
        _doc("u1"),
        _doc("a", date(2024, 12, 1)),
        _doc("u2"),
    ]
    out = build_timeline(docs)
    labels = [lbl for _, lbl in out]
    ids = [rec.doc_id for rec, _lbl in out]
    assert ids[:2] == ["u1", "u2"], "undated docs group first, in input order"
    assert labels[:2] == ["Undated", "Undated"]
    assert labels[2:] == ["2024-12-01", "2025-03-02"]


# ---------- /process pipeline ----------

@pytest.fixture()
def c():
    from medikiosk_docintel.main import app

    return TestClient(app)


def test_healthz(c):
    assert c.get("/healthz").status_code == 200


def test_process_prescription_text(c):
    r = c.post(
        "/process",
        json={
            "doc_id": "doc-1",
            "text": "Rx\nDate: 14/03/2025\nTab Aspirin 75mg OD\nTab Warfarin 5mg HS",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["doc_id"] == "doc-1"
    assert body["kind"] == "prescription"
    assert body["extracted_date"] == "2025-03-14"
    names = {m["name"] for m in body["meds"]}
    assert {"aspirin", "warfarin"} <= names
    assert any(i["severity"] == "major" for i in body["interactions"])
    assert body["raw_text_ref"]


def test_process_lab_text_flags_abnormal(c):
    r = c.post(
        "/process",
        json={
            "doc_id": "doc-2",
            "text": "Lab Report\nDate: 05.04.2025\nHemoglobin 6.5 g/dL\nHbA1c 8.5 % (4.0-6.0)",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "lab"
    hbs = [lab for lab in body["labs"] if lab["test"] == "hemoglobin"]
    assert hbs and hbs[0]["abnormal"] is True
    a1c = [lab for lab in body["labs"] if lab["test"] == "hba1c"]
    assert a1c and a1c[0]["ref_range"] == "4.0-6.0"


def test_process_undated_keeps_none_and_sorts_first(c):
    r = c.post(
        "/process",
        json={"doc_id": "doc-3", "text": "Rx\nTab Paracetamol 650mg TDS"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["extracted_date"] is None
    # timeline over [this doc] trivially puts the undated doc first
    tl = build_timeline([DocumentRecord.model_validate(body)])
    assert [lbl for _, lbl in tl] == ["Undated"]


def test_process_with_safety_alerts_and_allergies(c):
    r = c.post(
        "/process",
        json={
            "doc_id": "doc-4",
            "text": "Rx\nTab Amoxicillin 500mg TDS\nTab Propranolol 40mg BD",
            "allergies": ["penicillin"],
            "conditions": ["asthma"],
            "age": 45,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "safety_alerts" in body
    alerts = body["safety_alerts"]
    assert any(a["category"] == "allergy" and "amoxicillin" in a["title"].lower() for a in alerts)
    assert any(a["category"] == "contraindication" and "propranolol" in a["title"].lower() for a in alerts)