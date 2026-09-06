"""T3.9: FHIR R4 bundle builder + ABHA adapter contract tests.

Resource rules: NO fake SNOMED codes — complaint/medication coding is
text-only. Identity: token system 'urn:medikiosk:token', ABHA
'urn:abdm:abha'. Labs: valueQuantity when numeric-parsable, else
valueString; H/L interpretation only when abnormal AND ref_range known.
"""

import json
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from medikiosk_shared.models import (
    ConsentArtifact,
    DocumentRecord,
    Identifier,
    LabExtract,
    MedExtract,
    Patient,
    RedFlagAlert,
    SessionState,
)


@pytest.fixture()
def c():
    from medikiosk_fhir.main import app

    return TestClient(app)


def _post(c, session, path="/bundle"):
    return c.post(path, json={"session": session.model_dump(mode="json")})


def _types(bundle):
    return sorted(r["resource"]["resourceType"] for r in bundle["entry"])


# --- bundle composition -------------------------------------------------------


def test_bundle_has_patient_and_condition(c):
    s = SessionState(
        patient=Patient(
            identifiers=[Identifier(system="token", value="TOK-1")],
            name="Ravi Kumar",
            age=45,
            gender="male",
        ),
        chief_complaint=__import__(
            "medikiosk_shared.models", fromlist=["ChiefComplaint"]
        ).ChiefComplaint(name="chest_pain", framework="SOCRATES"),
    )
    r = _post(c, s)
    assert r.status_code == 200
    bundle = r.json()["bundle"]
    assert bundle["resourceType"] == "Bundle"
    types = _types(bundle)
    assert "Patient" in types and "Condition" in types


def test_token_identifier_when_no_abha(c):
    s = SessionState(identifiers=[Identifier(system="token", value="TOK-9")])
    bundle = _post(c, s).json()["bundle"]
    pats = [r["resource"] for r in bundle["entry"] if r["resource"]["resourceType"] == "Patient"]
    systems = [i["system"] for i in pats[0]["identifier"]]
    assert "urn:medikiosk:token" in systems
    assert "urn:abdm:abha" not in systems


def test_abha_identifier_uses_abdm_system(c):
    s = SessionState(
        patient=Patient(
            identifiers=[
                Identifier(system="token", value="TOK-1"),
                Identifier(system="abha", value="14-3344-5566-7788"),
            ]
        )
    )
    bundle = _post(c, s).json()["bundle"]
    pat = next(r["resource"] for r in bundle["entry"] if r["resource"]["resourceType"] == "Patient")
    by_system = {i["system"]: i["value"] for i in pat["identifier"]}
    assert by_system["urn:abdm:abha"] == "14-3344-5566-7788"
    assert by_system["urn:medikiosk:token"] == "TOK-1"


def test_secondary_complaint_second_condition(c):
    from medikiosk_shared.models import ChiefComplaint

    s = SessionState(
        chief_complaint=ChiefComplaint(name="fever", framework="OPQRST"),
        secondary_complaints=["cough", "abdominal_pain"],
    )
    bundle = _post(c, s).json()["bundle"]
    conds = [r["resource"] for r in bundle["entry"] if r["resource"]["resourceType"] == "Condition"]
    texts = {c2["code"]["text"] for c2 in conds}
    assert len(conds) == 3
    assert {"fever", "cough", "abdominal_pain"} <= texts


def test_condition_code_is_text_only_no_snomed(c):
    from medikiosk_shared.models import ChiefComplaint

    s = SessionState(
        chief_complaint=ChiefComplaint(name="fever", framework="OPQRST")
    )
    bundle = _post(c, s).json()["bundle"]
    cond = next(r["resource"] for r in bundle["entry"] if r["resource"]["resourceType"] == "Condition")
    assert cond["code"]["text"] == "fever"
    assert "coding" not in cond["code"]  # NO fabricated SNOMED


def test_lab_value_quantity_when_numeric(c):
    doc = DocumentRecord(
        doc_id="doc-lab",
        kind="lab",
        raw_text_ref="k/x",
        labs=[
            LabExtract(test="Hb", value="9.8", unit="g/dL", ref_range="13-17", abnormal=True),
            LabExtract(test="Widal", value="S. typhi O 1:80", abnormal=False),
        ],
    )
    s = SessionState(documents=[doc])
    bundle = _post(c, s).json()["bundle"]
    obs = [r["resource"] for r in bundle["entry"] if r["resource"]["resourceType"] == "Observation"]
    hb = next(o for o in obs if "Hb" in o["code"]["text"])
    widal = next(o for o in obs if "Widal" in o["code"]["text"])
    assert hb["valueQuantity"]["value"] == 9.8
    assert hb["valueQuantity"]["unit"] == "g/dL"
    # H only because abnormal AND ref_range present
    assert hb["interpretation"][0]["coding"][0]["code"] == "H"
    assert "interpretation" not in widal
    assert widal["valueString"] == "S. typhi O 1:80"


def test_medication_statement_per_doc_med(c):
    doc = DocumentRecord(
        doc_id="doc-rx",
        kind="prescription",
        raw_text_ref="k/y",
        extracted_date=date(2026, 9, 1),
        meds=[__import__("medikiosk_shared.models", fromlist=["MedExtract"]).MedExtract(name="Paracetamol", dose="650mg", frequency="TDS")],
    )
    s = SessionState(documents=[doc])
    bundle = _post(c, s).json()["bundle"]
    meds = [r["resource"] for r in bundle["entry"] if r["resource"]["resourceType"] == "MedicationStatement"]
    assert len(meds) == 1
    assert "Paracetamol 650mg" in meds[0]["medicationCodeableConcept"]["text"]


def test_document_reference_and_consent(c):
    doc = DocumentRecord(doc_id="doc-d", kind="discharge", raw_text_ref="k/z")
    s = SessionState(
        documents=[doc],
        consent=ConsentArtifact(session_id="sess-x", scopes=["his_share", "storage"]),
    )
    bundle = _post(c, s).json()["bundle"]
    types = _types(bundle)
    assert "DocumentReference" in types
    assert "Consent" in types
    consent = next(r["resource"] for r in bundle["entry"] if r["resource"]["resourceType"] == "Consent")
    assert consent["scope"]["coding"][0]["code"] in {"his_share", "storage", "patient-privacy"}


def test_red_flag_observation(c):
    s = SessionState(
        red_flags=[
            RedFlagAlert(
                pattern_id="mi_pattern",
                urgency="immediate",
                message_hi="तुरंत",
                message_en="chest pain + sweating — immediate",
            )
        ]
    )
    bundle = _post(c, s).json()["bundle"]
    obs = [r["resource"] for r in bundle["entry"] if r["resource"]["resourceType"] == "Observation"]
    assert any("red-flag" in json.dumps(o) for o in obs)


# --- push / outbox --------------------------------------------------------------


def test_push_writes_outbox_without_his_url(c, tmp_path, monkeypatch):
    monkeypatch.delenv("HIS_FHIR_URL", raising=False)
    monkeypatch.setenv("HIS_FHIR_OUTBOX", str(tmp_path))
    s = SessionState(
        identifiers=[Identifier(system="token", value="TOK-OUT")],
        session_id="sess-outbox-test",
    )
    r = _post(c, s, path="/push")
    assert r.status_code == 200
    body = r.json()
    assert body["written"].endswith("sess-outbox-test.json")
    written = json.loads((tmp_path / "sess-outbox-test.json").read_text(encoding="utf-8"))
    assert written["resourceType"] == "Bundle"


def test_push_posts_to_his_when_url_set(c, tmp_path, monkeypatch):
    """Stub httpx server: bundle POSTed when HIS_FHIR_URL is set."""
    monkeypatch.setenv("HIS_FHIR_URL", "http://stub-his.invalid/fhir")
    s = SessionState(session_id="sess-live", identifiers=[Identifier(system="token", value="T")])

    from medikiosk_fhir import main as fmain

    calls = {}

    class FakeResp:
        status_code = 200

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, **kwargs):
            calls["url"] = url
            calls["json"] = kwargs.get("json")
            return FakeResp()

    monkeypatch.setattr(fmain.httpx, "Client", FakeClient)
    r = _post(c, s, path="/push")
    assert r.status_code == 200
    assert calls["url"].startswith("http://stub-his.invalid")
    assert calls["json"]["resourceType"] == "Bundle"
    assert not list(tmp_path.glob("**/*.json"))


# --- ABHA adapters -----------------------------------------------------------------


def test_abha_mock_returns_valid_demo():
    from medikiosk_fhir.adapters.abha_mock import AbhaMock

    out = AbhaMock().verify("14-3344-5566-7788")
    assert out["valid"] is True
    assert out["name"] == "Demo User"


def test_abha_protocol_signature():
    """AbhaAdapter is a Protocol: structural typing check."""
    from medikiosk_fhir.adapters.abha import AbhaAdapter
    from medikiosk_fhir.adapters.abha_mock import AbhaMock

    m = AbhaMock()
    assert isinstance(m, AbhaAdapter)
    assert callable(getattr(m, "verify", None))