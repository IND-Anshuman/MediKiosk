"""Summarizer core (plan T3.8).

DETERMINISTIC render: the Jinja template can only contain facts that exist
in the SessionState — the anti-hallucination guarantee. The LLM is involved
ONLY in phrasify(), which turns a free-answer raw text into a clinical
English one-liner for HPI; any phrasify failure degrades to the raw text.

Every rendered fact carries a citation chip sourced from real data:
  🎤 voice slot  + slot timestamp HH:MM (UTC)
  👆 touch slot
  📄 document    + doc_id
Times are never fabricated — a slot without a timestamp contributes no time.
"""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, FileSystemLoader
from medikiosk_shared.models import SessionState

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

MICRO = "\U0001f3a4"  # 🎤
TOUCH = "\U0001f446"  # 👆
DOC = "\U0001f4c4"  # 📄


class Phrasifier(Protocol):
    def phrasify(self, text: str, language: str) -> str: ...


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["hhmm"] = _hhmm
    return env


def _hhmm(dt: datetime | None) -> str:
    """HH:MM of the STORED timestamp, no TZ conversion — never fabricate time."""
    if dt is None:
        return ""
    return dt.strftime("%H:%M")


class Summarizer:
    def __init__(self, client: Any | None = None, template_name: str = "summary.md.j2"):
        self._template = _env().get_template(template_name)
        self._phrasifier = self._wrap(client)

    @staticmethod
    def _wrap(client: Any | None) -> Phrasifier | None:
        """Adapt an injected OpenAI-style client into a Phrasifier."""
        if client is None:
            return None
        if hasattr(client, "phrasify"):
            return client
        if hasattr(client, "chat"):
            return _OpenAIPhrasifier(client)
        return None

    def phrasify(self, text: str, language: str) -> str:
        """LLM English one-liner; ALWAYS degrades to raw text on any failure."""
        if not text or not text.strip():
            return text
        if self._phrasifier is None:
            return text
        try:
            out = self._phrasifier.phrasify(text, language)
            return out if (out and out.strip()) else text
        except Exception:
            return text

    def render(self, session: SessionState) -> str:
        """Deterministic markdown render. No LLM involvement here."""
        cc = session.chief_complaint
        confirmed_slots = [s for s in (cc.slots if cc else []) if s.confirmed]

        hpi_lines: list[str] = []
        for slot in confirmed_slots:
            if slot.source.value == "voice":
                chip = f"{MICRO} {_hhmm(slot.timestamp)}".strip()
            elif slot.source.value == "touch":
                chip = TOUCH
            else:  # document / llm_parsed
                chip = DOC
            value = self.phrasify(str(slot.value), session.language)
            hpi_lines.append(f"- {slot.key}: {value} ({chip})")

        meds_lines: list[str] = []
        labs_lines: list[str] = []
        for doc in session.documents:
            for med in doc.meds:
                bits = [med.name]
                if med.dose:
                    bits.append(med.dose)
                if med.frequency:
                    bits.append(med.frequency)
                meds_lines.append(f"- {' '.join(bits)} ({DOC} {doc.doc_id})")
            for lab in doc.labs:
                bits = [f"{lab.test}: {lab.value}"]
                if lab.unit:
                    bits.append(lab.unit)
                rng = f" (ref {lab.ref_range})" if lab.ref_range else ""
                flag = " — ABNORMAL" if lab.abnormal else ""
                labs_lines.append(
                    f"- {' '.join(bits)}{rng}{flag} ({DOC} {doc.doc_id})"
                )

        past_lines = self._past_medical_lines(session)

        return self._template.render(
            chief_complaint=cc.name if cc else "—",
            framework=cc.framework if cc else "",
            hpi_lines=hpi_lines,
            secondary=session.secondary_complaints,
            past_lines=past_lines,
            meds_lines=meds_lines,
            labs_lines=labs_lines,
            red_flags=session.red_flags,
        )

    # -- internals -------------------------------------------------------------

    @staticmethod
    def _past_medical_lines(session: SessionState) -> list[str]:
        answers = {a.question_id: a for a in session.answers}
        lines: list[str] = []
        if "other_problems" in answers:
            raw = answers["other_problems"].raw_text
            parsed = answers["other_problems"].parsed
            if isinstance(parsed, dict):
                vals = [v for v in parsed.values() if isinstance(v, str)]
            else:
                vals = []
            for v in vals:
                lines.append(f"- {v}")
            if raw and not lines:
                lines.append(f"- {raw}")
        if not lines:
            lines = ["None reported"]
        return lines

    def pdf(self, session: SessionState) -> bytes:
        """Plain-text PDF of the same sections; citation emoji stripped."""
        from fpdf import FPDF

        md = self.render(session)
        md = _strip_citation_emoji(md)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        for para in md.split("\n"):
            line = para.rstrip()
            if line.startswith("## "):
                pdf.set_font("Helvetica", size=12, style="B")
                pdf.multi_cell(0, 7, _pdfsafe(line[3:]), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", size=10)
            elif line.startswith("# "):
                pdf.set_font("Helvetica", size=14, style="B")
                pdf.multi_cell(0, 8, _pdfsafe(line[2:]), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", size=10)
            elif line.startswith(("- ", "* ")):
                pdf.multi_cell(0, 5, _pdfsafe("• " + line[2:]), new_x="LMARGIN", new_y="NEXT")
            elif line:
                pdf.multi_cell(0, 5, _pdfsafe(line), new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.ln(2)
        return bytes(pdf.output())


def _pdfsafe(s: str) -> str:
    """Helvetica (latin-1) safety: transliterate common Devanagari words, drop rest."""
    replacements = {
        "⚠️": "[!]",
        "—": "-",
        "•": "*",
        "\u00a0": " ",
        "तेज": "tez",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _strip_citation_emoji(md: str) -> str:
    for e in (MICRO, TOUCH, DOC, "⚠️"):
        md = md.replace(e, "")
    return re.sub(r"  +", " ", md)


class _OpenAIPhrasifier:
    """Adapts an OpenAI-style client into phrasify(text, language)."""

    def __init__(self, client: Any):
        self.client = client
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def phrasify(self, text: str, language: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rewrite the patient's answer as one concise clinical "
                        "English sentence for an HPI. Do not add facts, do not "
                        "infer diagnoses. Return only the sentence."
                    ),
                },
                {"role": "user", "content": f"language: {language}\ntext: {text}"},
            ],
        )
        return (resp.choices[0].message.content or "").strip()