"""RED-first tests for T1.1 shared models — run BEFORE models.py exists.

Expected initial failure: ModuleNotFoundError: No module named 'medikiosk_shared'
"""

import pytest


class TestPatientIdentity:
    def test_valid_abha_accepted(self):
        from medikiosk_shared.models import Patient

        p = Patient(
            identifiers=[{"system": "abha", "value": "14-3344-5566-7788"}],
            name="Ravi Kumar",
            age=42,
            gender="male",
            language="hi",
        )
        assert p.abha_id == "14-3344-5566-7788"

    def test_malformed_abha_rejected_not_repaired(self):
        from medikiosk_shared.models import Patient

        # Malformed ABHA (bad segment lengths) MUST raise — never normalize.
        with pytest.raises(Exception):
            Patient(identifiers=[{"system": "abha", "value": "123"}], name="X")

    def test_abha_address_form_accepted(self):
        from medikiosk_shared.models import Patient

        p = Patient(identifiers=[{"system": "abha", "value": "ravi@abdm"}])
        assert p.abha_id == "ravi@abdm"

    def test_walkin_with_token_only_roundtrips(self):
        from medikiosk_shared.models import Patient

        p = Patient(
            identifiers=[{"system": "token", "value": "T-0042"}],
            name="Sita Devi",
            age=60,
            gender="female",
        )
        assert p.abha_id is None
        assert p.identifiers[0].system == "token"


class TestSessionState:
    def test_roundtrip_with_secondary_complaints_and_docs(self):
        from medikiosk_shared.models import (
            Answer,
            ChiefComplaint,
            DocumentRecord,
            SessionState,
            Slot,
        )

        s = SessionState(
            session_id="sess-123",
            identifiers=[{"system": "token", "value": "T-0042"}],
            chief_complaint=ChiefComplaint(
                name="fever", framework="OPQRST", slots=[]
            ),
            secondary_complaints=["cough"],
            answers=[
                Answer(
                    question_id="onset",
                    raw_text="3 din se",
                    parsed={"duration": "3 days"},
                    language="hi",
                )
            ],
            documents=[
                DocumentRecord(
                    doc_id="doc-1",
                    kind="lab",
                    page_count=1,
                    extracted_date="2026-08-01",
                    meds=[],
                    labs=[
                        {
                            "test": "Hb",
                            "value": "6.5",
                            "unit": "g/dL",
                            "ref_range": "12.0-15.5",
                            "abnormal": True,
                        }
                    ],
                    raw_text_ref="obj/doc-1",
                )
            ],
        )
        j = s.model_dump_json()
        s2 = SessionState.model_validate_json(j)
        assert s2.session_id == "sess-123"
        assert s2.secondary_complaints == ["cough"]
        assert s2.documents[0].labs[0].abnormal is True
        assert s2.documents[0].extracted_date.year == 2026


class TestRedFlagAndConsent:
    def test_red_flag_alert_fields(self):
        from medikiosk_shared.models import RedFlagAlert

        rf = RedFlagAlert(
            pattern_id="mi_suspect",
            urgency="immediate",
            message_hi="turant doctor",
            message_en="immediate attention",
        )
        assert rf.urgency == "immediate"

    def test_consent_artifact_defaults(self):
        from medikiosk_shared.models import ConsentArtifact

        c = ConsentArtifact(
            session_id="s1",
            scopes=["his_share"],
            audio_signature_path="obj/consent/s1",
        )
        assert c.revoked_at is None
        assert c.signed_at is not None
