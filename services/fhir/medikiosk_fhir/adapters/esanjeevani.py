"""eSanjeevani hand-off packet (plan G7).

We do NOT integrate with eSanjeevani (no public third-party API).
Instead, this adapter produces a structured summary PDF + QR code that
a teleconsult doctor on the eSanjeevani side can read — we hand off to
the doctor, not to the platform.
"""
from __future__ import annotations

import io
from typing import Any


class EsanjeevaniHandoff:
    @staticmethod
    def build_packet(session: dict[str, Any]) -> dict[str, Any]:
        summary_text = session.get("summary_md", "No summary available.")
        patient = session.get("patient", {})
        name = patient.get("name", "Unknown")
        age = patient.get("age", "?")
        gender = patient.get("gender", "?")

        # Minimal PDF via reportlab if available, else plain text fallback.
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter)
            styles = getSampleStyleSheet()
            story = [
                Paragraph(f"<b>MediKiosk → eSanjeevani Hand-off</b>", styles["Title"]),
                Paragraph(f"Patient: {name}, {age} yrs, {gender}", styles["Normal"]),
                Paragraph("<b>Clinical Summary:</b>", styles["Heading2"]),
                Paragraph(summary_text.replace("\n", "<br/>"), styles["Normal"]),
            ]
            doc.build(story)
            pdf_bytes = buf.getvalue()
        except Exception:
            pdf_bytes = (
                f"MediKiosk → eSanjeevani Hand-off\n"
                f"Patient: {name}, {age} yrs, {gender}\n"
                f"---\n{summary_text}\n"
            ).encode("utf-8")

        # QR encodes a deep-link back to MediKiosk doctor portal for this session.
        session_id = session.get("session_id", "")
        qr_payload = f"medikiosk://doctor/{session_id}"
        try:
            import qrcode
            img = qrcode.make(qr_payload)
            qr_buf = io.BytesIO()
            img.save(qr_buf, format="PNG")
            qr_bytes = qr_buf.getvalue()
        except Exception:
            qr_bytes = b""

        return {
            "format": "pdf",
            "bytes": pdf_bytes,
            "qr": qr_bytes,
            "qr_payload": qr_payload,
            "summary": summary_text,
        }
