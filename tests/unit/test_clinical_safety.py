"""Tests for Clinical & Diagnostic Safety Improvements (Contraindications, Allergies, Demographics)."""

import pytest
from medikiosk_docintel.intel import (
    check_allergies,
    check_contraindications,
    evaluate_clinical_safety,
)
from medikiosk_shared.models import (
    ClinicalSafetyAlert,
    DocumentRecord,
    MedExtract,
    Patient,
    SessionState,
)


class TestAllergySafety:
    def test_penicillin_allergy_flags_amoxicillin(self):
        meds = [MedExtract(name="amoxicillin", dose="500mg")]
        allergies = ["penicillin"]
        alerts = check_allergies(meds, allergies)
        assert len(alerts) == 1
        assert alerts[0].category == "allergy"
        assert alerts[0].severity == "critical"
        assert "amoxicillin" in alerts[0].source_entities
        assert "penicillin" in alerts[0].detail.lower()

    def test_direct_drug_allergy_match(self):
        meds = [MedExtract(name="aspirin", dose="75mg")]
        allergies = ["aspirin"]
        alerts = check_allergies(meds, allergies)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        assert "aspirin" in alerts[0].title.lower()

    def test_no_allergy_clash_returns_empty(self):
        meds = [MedExtract(name="paracetamol", dose="650mg")]
        allergies = ["sulfa"]
        alerts = check_allergies(meds, allergies)
        assert alerts == []


class TestContraindicationSafety:
    def test_asthma_with_propranolol_contraindicated(self):
        meds = [MedExtract(name="propranolol", dose="40mg")]
        conditions = ["asthma"]
        alerts = check_contraindications(meds, conditions)
        assert len(alerts) == 1
        assert alerts[0].category == "contraindication"
        assert alerts[0].severity == "critical"
        assert "bronchoconstriction" in alerts[0].detail.lower()

    def test_peptic_ulcer_with_diclofenac_contraindicated(self):
        meds = [MedExtract(name="diclofenac", dose="50mg")]
        conditions = ["peptic_ulcer"]
        alerts = check_contraindications(meds, conditions)
        assert len(alerts) == 1
        assert alerts[0].severity == "major"
        assert "ulceration" in alerts[0].detail.lower()

    def test_renal_impairment_with_metformin_contraindicated(self):
        meds = [MedExtract(name="metformin", dose="500mg")]
        conditions = ["renal_impairment"]
        alerts = check_contraindications(meds, conditions)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        assert "lactic acidosis" in alerts[0].detail.lower()


class TestDemographicSafetyRules:
    def test_pediatric_aspirin_warning(self):
        meds = [MedExtract(name="aspirin", dose="150mg")]
        alerts = check_contraindications(meds, conditions=[], age=7)
        ped = [a for a in alerts if a.category == "demographic"]
        assert len(ped) == 1
        assert ped[0].severity == "critical"
        assert "reye" in ped[0].detail.lower()

    def test_geriatric_beers_criteria_alprazolam(self):
        meds = [MedExtract(name="alprazolam", dose="0.5mg")]
        alerts = check_contraindications(meds, conditions=[], age=72)
        ger = [a for a in alerts if a.category == "demographic"]
        assert len(ger) == 1
        assert ger[0].severity == "major"
        assert "beers criteria" in ger[0].detail.lower()
        assert "falls" in ger[0].detail.lower()

    def test_geriatric_beers_criteria_tramadol(self):
        meds = [MedExtract(name="tramadol", dose="50mg")]
        alerts = check_contraindications(meds, conditions=[], age=68)
        ger = [a for a in alerts if a.category == "demographic"]
        assert len(ger) == 1
        assert "delirium" in ger[0].detail.lower()


class TestUnifiedClinicalSafetyEvaluation:
    def test_multi_hazard_prioritization(self):
        # Patient: 70yo with asthma & penicillin allergy, taking amoxicillin, propranolol, and tramadol
        meds = [
            MedExtract(name="amoxicillin"),
            MedExtract(name="propranolol"),
            MedExtract(name="tramadol"),
        ]
        alerts = evaluate_clinical_safety(
            meds=meds,
            conditions=["asthma"],
            allergies=["penicillin"],
            age=70,
        )
        assert len(alerts) >= 3
        # Critical items must be sorted first
        assert alerts[0].severity == "critical"
        categories = {a.category for a in alerts}
        assert {"allergy", "contraindication", "demographic"} <= categories


class TestSummarizerSafetyIntegration:
    def test_summary_renders_dynamic_allergies_and_safety_alerts(self):
        from medikiosk_summarizer.summarizer import Summarizer
        from medikiosk_shared.models import ChiefComplaint

        session = SessionState(
            patient=Patient(name="Ram Lal", age=68, allergies=["penicillin", "sulfa"]),
            chief_complaint=ChiefComplaint(name="chest_pain", framework="SOCRATES"),
            secondary_complaints=["asthma"],
            documents=[
                DocumentRecord(
                    doc_id="doc-1",
                    meds=[MedExtract(name="amoxicillin"), MedExtract(name="propranolol")],
                    raw_text_ref="raw/1.txt",
                )
            ],
        )

        summarizer = Summarizer()
        rendered = summarizer.render(session)

        # Check dynamic allergies
        assert "## Allergies" in rendered
        assert "- penicillin" in rendered
        assert "- sulfa" in rendered
        assert "None reported" not in rendered.split("## Allergies")[1].split("##")[0]

        # Check safety alerts section
        assert "## CLINICAL SAFETY ALERTS & CONTRAINDICATIONS" in rendered
        assert "Allergy Clash" in rendered
        assert "Contraindication" in rendered
