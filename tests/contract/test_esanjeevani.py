"""T3.15: eSanjeevani hand-off packet (plan G7).

We do NOT integrate with eSanjeevani (no public API). We produce a
structured summary PDF + QR that a teleconsult doctor can read — assist,
don't compete.
"""
from __future__ import annotations

import pytest


def test_adapter_exists():
    from medikiosk_fhir.adapters.esanjeevani import EsanjeevaniHandoff
    assert hasattr(EsanjeevaniHandoff, "build_packet")


def test_packet_contains_summary_and_qr():
    from medikiosk_fhir.adapters.esanjeevani import EsanjeevaniHandoff
    session = {
        "session_id": "s1",
        "patient": {"name": "Ravi", "age": 42, "gender": "male"},
        "chief_complaint": {"name": "chest_pain", "slots": [{"key": "onset", "value": "2 hours"}]},
        "summary_md": "# Chief Complaint\nChest pain since 2 hours.",
    }
    packet = EsanjeevaniHandoff.build_packet(session)
    assert packet["format"] == "pdf"
    assert "summary" in packet
    assert packet["summary"] == session["summary_md"]
    # QR is present (bytes or empty if qrcode missing)
    assert "qr_payload" in packet
    assert "s1" in packet["qr_payload"]
