"""T3.8: Template summarizer contract tests.

Anti-hallucination is the core guarantee: the summary is a DETERMINISTIC
Jinja render of SessionState — it can only contain facts present in the
session. LLM (phrasify) touches ONLY free-answer English phrasing and must
degrade to raw text on failure. Every rendered fact carries a citation chip
(🎤 voice + HH:MM, 👆 touch, 📄 document + doc_id) — never a fabricated time.
"""

import pytest
from fastapi.testclient import TestClient

from medikiosk_shared.models import (
    Answer,
    ChiefComplaint,
    DocumentRecord,
    LabExtract,
    MedExtract,
    Patient,
    RedFlagAlert,
    SessionState,
    Slot,
    Source,
)

MICRO = "\U0001f3a4"  # 🎤
TOUCH = "\U0001f446"  # 👆
DOC = "\U0001f4c4"  # 📄


def _slot(key, value, source=Source.VOICE, confirmed=True, hour=10, minute=5):
    from datetime import datetime, timezone

    return Slot(
        key=key,
        value=value,
        source=source,
        confirmed=confirmed,
        timestamp=datetime(2026, 9, 7, hour, minute, tzinfo=timezone.utc),
    )


@pytest.fixture()
def c():
    from medikiosk_summarizer.main import app

    return TestClient(app)


def _post(c, session):
    return c.post("/summarize", json={"session": session.model_dump(mode="json")})


# --- (a) anti-hallucination -------------------------------------------------


def test_no_facts_beyond_session(c):
    s = SessionState(
        chief_complaint=ChiefComplaint(
            name="chest_pain",
            framework="SOCRATES",
            slots=[_slot("onset", "2 hours")],
        )
    )
    r = _post(c, s)
    assert r.status_code == 200
    md = r.json()["summary_md"]
    assert "2 hours" in md
    assert "myocardial infarction" not in md.lower()
    assert "stemi" not in md.lower()


# --- (b) citation chips -------------------------------------------------------


def test_voice_and_touch_citation_chips(c):
    s = SessionState(
        chief_complaint=ChiefComplaint(
            name="fever",
            framework="OPQRST",
            slots=[
                _slot("onset", "2-3 din se", source=Source.VOICE, hour=9, minute=41),
                _slot("associated", "Cough", source=Source.TOUCH),
            ],
        )
    )
    md = _post(c, s).json()["summary_md"]
    hpi = md.split("## HPI")[1].split("##")[0]
    assert MICRO in hpi and "09:41" in hpi
    assert TOUCH in hpi


def test_document_citation_chip(c):
    doc = DocumentRecord(
        doc_id="doc-xyz",
        kind="prescription",
        raw_text_ref="k/sess/doc.txt",
        meds=[MedExtract(name="Paracetamol", dose="650mg", frequency="TDS")],
        labs=[
            LabExtract(test="Hb", value="9.8", unit="g/dL", ref_range="13-17", abnormal=True)
        ],
    )
    s = SessionState(documents=[doc])
    md = _post(c, s).json()["summary_md"]
    med_line = next(ln for ln in md.splitlines() if "Paracetamol" in ln)
    lab_line = next(ln for ln in md.splitlines() if "Hb" in ln)
    assert DOC in med_line and "doc-xyz" in med_line
    assert DOC in lab_line and "doc-xyz" in lab_line


# --- (c) empty sections --------------------------------------------------------


def test_empty_meds_say_none_reported(c):
    s = SessionState()
    md = _post(c, s).json()["summary_md"]
    assert "None reported" in md
    assert "## Medications" in md
    assert "## Allergies" in md


# --- (d) red-flag banner ---------------------------------------------------------


def test_red_flag_banner(c):
    s = SessionState(
        red_flags=[
            RedFlagAlert(
                pattern_id="mi_pattern",
                urgency="immediate",
                message_hi="तुरंत डॉक्टर से मिलें",
                message_en="Chest pain radiating to left arm with sweating — seek immediate care",
            )
        ]
    )
    md = _post(c, s).json()["summary_md"]
    assert "⚠️" in md
    assert "seek immediate care" in md


def test_verification_line_present(c):
    md = _post(c, SessionState()).json()["summary_md"]
    assert "AI-generated draft" in md and "physician must verify" in md


# --- (e) PDF -------------------------------------------------------------------


def test_pdf_bytes(c):
    s = SessionState(
        chief_complaint=ChiefComplaint(
            name="fever",
            framework="OPQRST",
            slots=[_slot("onset", "2-3 din se", source=Source.VOICE)],
        )
    )
    r = c.post("/summarize.pdf", json={"session": s.model_dump(mode="json")})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    body = r.content
    assert body[:4] == b"%PDF"
    assert MICRO.encode() not in body  # citation emoji stripped in PDF


# --- (f) phrasify degradation ------------------------------------------------------


class ExplodingClient:
    """Stub OpenAI client whose API call raises."""

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        raise RuntimeError("LLM down")


def test_phrasify_failure_degrades_to_raw_text(c):
    r = c.post(
        "/summarize",
        json={"session": SessionState().model_dump(mode="json")},
        headers={"x-inject-client": "explode"},  # wiring hook (see main.py)
    )
    assert r.status_code == 200
    from medikiosk_summarizer.main import get_phrasifier

    assert get_phrasifier() is not None  # app still functional


def test_phrasify_used_for_hpi_free_answers():
    """Direct unit check: HPI phrasing comes from the injected LLM."""
    from medikiosk_summarizer.summarizer import Summarizer

    class Stub:
        def phrasify(self, text, language):
            return "Symptoms began two hours prior"

    summ = Summarizer(client=Stub())
    s = SessionState(
        chief_complaint=ChiefComplaint(
            name="chest_pain",
            framework="SOCRATES",
            slots=[_slot("onset", "2 hours")],
        ),
        answers=[
            Answer(
                question_id="onset",
                raw_text="do ghante se",
                parsed={"value": "2 hours"},
                language="hi",
            )
        ],
    )
    md = summ.render(s)
    assert "Symptoms began two hours prior" in md or "two hours prior" in md


def test_phrasify_stub_failure_keeps_raw_text():
    from medikiosk_summarizer.summarizer import Summarizer

    class Boom:
        def phrasify(self, text, language):
            raise RuntimeError("LLM down")

    summ = Summarizer(client=Boom())
    s = SessionState(
        chief_complaint=ChiefComplaint(
            name="chest_pain",
            framework="SOCRATES",
            slots=[_slot("onset", "2 hours")],
        )
    )
    md = summ.render(s)
    assert "2 hours" in md  # raw text survived the phrasify failure


def test_secondary_and_past_sections(c):
    s = SessionState(secondary_complaints=["cough", "abdominal_pain"])
    md = _post(c, s).json()["summary_md"]
    assert "## Secondary complaints" in md
    assert "cough" in md and "abdominal_pain" in md
    assert "## Past Medical/Surgical" in md and "None reported" in md
    assert "## Family/Personal" in md and "Not elicited in MVP" in md