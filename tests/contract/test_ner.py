"""T3.7: rule-based NER service contract (pure dictionary + regex, no ML).

NEVER invent entities: no-match text must yield empty lists.
"""

import pytest
from fastapi.testclient import TestClient

from medikiosk_ner.main import app
from medikiosk_ner.extractor import extract_entities


@pytest.fixture()
def c():
    return TestClient(app)


def test_healthz(c):
    assert c.get("/healthz").status_code == 200


def test_extract_endpoint_shape(c):
    r = c.post("/extract", json={"text": "Tab Aspirin 75mg OD"})
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"drugs", "labs"}


def test_aspirin_dose_frequency():
    out = extract_entities("Tab Aspirin 75mg OD for 5 days")
    assert out["drugs"], "aspirin must be found"
    med = out["drugs"][0]
    assert med["name"] == "aspirin"
    assert med["dose"] == "75mg"
    assert med["frequency"] == "OD"


def test_dose_case_insensitive_and_lower_unit():
    out = extract_entities("Paracetamol 500 MG TDS")
    med = out["drugs"][0]
    assert med["name"] == "paracetamol"
    assert med["dose"] == "500mg"
    assert med["frequency"] == "TDS"


def test_numeric_frequency_1_0_1():
    out = extract_entities("Metformin 500mg 1-0-1")
    med = out["drugs"][0]
    assert med["frequency"] == "1-0-1"


def test_hba1c_value_and_range():
    out = extract_entities("HbA1c 8.5 % (4.0-6.0)")
    assert out["labs"] == [
        {"test": "hba1c", "value": "8.5", "unit": "%", "ref_range": "4.0-6.0"}
    ]


def test_lab_without_range_uses_dictionary_unit():
    out = extract_entities("Hemoglobin 10.2 g/dL")
    assert out["labs"] == [
        {"test": "hemoglobin", "value": "10.2", "unit": "g/dL", "ref_range": None}
    ]


def test_devanagari_synonym_hit():
    out = extract_entities("मेटफॉर्मिन 500 mg BD")
    med = out["drugs"][0]
    assert med["name"] == "metformin"
    assert med["dose"] == "500mg"
    assert med["frequency"] == "BD"


def test_never_invents_on_nonsense():
    out = extract_entities("zzq xxv plk qwrt 12345")
    assert out == {"drugs": [], "labs": []}


def test_empty_text_returns_empty():
    assert extract_entities("") == {"drugs": [], "labs": []}


def test_endpoint_rejects_missing_text(c):
    r = c.post("/extract", json={})
    assert r.status_code == 422