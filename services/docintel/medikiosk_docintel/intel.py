"""Document intelligence rules (plan T3.10, AD-7 Module B).

Pure functions over OCR text / structured extracts:
  classify(text)                      -> kind
  extract_date(text)                  -> date | None   (never guesses)
  flag_labs(labs, age, sex)           -> labs with abnormal set from
                                          data/reference/lab_reference_ranges.json
  check_interactions(meds)            -> pairs from drug_interactions.json
  build_timeline(documents)           -> undated-first, dated ascending

All reference data lives in data/reference/*.json (repo-relative), mirroring
the NER service; MEDIKIOSK_DATA_DIR overrides for containers.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from medikiosk_shared.models import DocumentRecord, LabExtract, MedExtract

_REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = (
    Path(os.environ["MEDIKIOSK_DATA_DIR"])
    if "MEDIKIOSK_DATA_DIR" in os.environ
    else _REPO_ROOT / "data" / "reference"
)

Kind = Literal["prescription", "lab", "discharge", "unknown"]

# ---- classify ----------------------------------------------------------------
_RX_KEYWORDS = ("rx", "prescription", "tab ", "cap ", "syp ", "inj ", "खुराक", "गोली")
_LAB_KEYWORDS = ("lab report", "report", "investigation", "pathology", "रिपोर्ट", "जांच", "जाँच")
_DISCHARGE_KEYWORDS = ("discharge summary", "discharge", "advised review", "छुट्टी")

# ---- extract_date ------------------------------------------------------------
# dd/mm/yyyy, dd-mm-yy, dd.mm.yyyy, optionally prefixed by Date/दिनांक.
_DATE_RE = re.compile(
    r"(?:(?:date|dated|दिनांक|दिनांकः)\s*[:\-]?\s*)?"
    r"\b(?P<dd>\d{1,2})[/.\-](?P<mm>\d{1,2})[/.\-](?P<yy>\d{2}|\d{4})\b"
)
_MONTH_NAMES = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}
_DATE_MONTH_NAME_RE = re.compile(
    r"(?:(?:date|dated|दिनांक)\s*[:\-]?\s*)?"
    r"\b(?P<dd>\d{1,2})\s*(?P<mon>[A-Za-z]{3,9})\.?\s*,?\s*(?P<yy>\d{4})\b"
)


def classify(text: str) -> str:
    t = text.lower()
    if any(k in t for k in _DISCHARGE_KEYWORDS):
        return "discharge"
    if any(k in t for k in _LAB_KEYWORDS):
        return "lab"
    if any(k in t for k in _RX_KEYWORDS):
        return "prescription"
    return "unknown"


def extract_date(text: str) -> date | None:
    """First date-like token → date; None when none present. NEVER guesses.

    Ambiguous d/m pairs resolve as dd/mm ONLY when the day is unambiguous
    (day > 12). A bare year or 1-2 digit fragment never becomes a date.
    """
    m = _DATE_RE.search(text)
    if not m:
        m2 = _DATE_MONTH_NAME_RE.search(text)
        if not m2:
            return None
        dd = int(m2.group("dd"))
        mon = _MONTH_NAMES.get(m2.group("mon")[:3].lower())
        if mon_ok(dd, mon := mon):
            return _mk(dd, mon, int(m2.group("yy")))
        return None
    dd, mm, yy = int(m.group("dd")), int(m.group("mm")), int(m.group("yy"))
    if yy < 100:
        yy += 2000
    if dd > 12:  # unambiguous: dd/mm
        return _mk(dd, mm, yy)
    if mm > 12:  # first number must be the month
        return _mk(mm, dd, yy)
    # Both ≤ 12: the leading 'Date:' prefix is the only signal; default dd/mm.
    if m.group(0)[:1].isdigit() or "date" in m.group(0).lower() or "दिनांक" in m.group(0):
        return _mk(dd, mm, yy)
    return _mk(dd, mm, yy)


def _mk(dd: int, mm: int, yy: int) -> date | None:
    try:
        return date(yy, mm, dd)
    except ValueError:
        return None  # impossible date fragments are NOT dates


def mon_ok(dd: int, mon: int | None) -> bool:
    return mon is not None and 1 <= dd <= 31


# ---- flag_labs ---------------------------------------------------------------
def _band(age: int | None, sex: str | None) -> str:
    if sex == "female":
        return "child" if age is not None and age < 12 else "adult_female"
    if sex == "male":
        return "child" if age is not None and age < 12 else "adult_male"
    return "child" if age is not None and age < 12 else "adult_female"


@lru_cache(maxsize=1)
def _load_ranges() -> dict:
    with open(DATA_DIR / "lab_reference_ranges.json", encoding="utf-8") as f:
        return json.load(f)


def flag_labs(labs: list[LabExtract], age: int | None = None, sex: str | None = None) -> list[LabExtract]:
    """Set LabExtract.abnormal against age/sex-banded ranges (default adult band
    when age/sex unknown — plan T3.10). Unknown tests are never flagged."""
    ranges = _load_ranges()
    band = _band(age, sex)
    out = []
    for lab in labs:
        spec = ranges.get(lab.test.lower())
        abnormal = False
        if spec and lab.value:
            try:
                v = float(lab.value)
                lo, hi = spec[band][0], spec[band][1]
                abnormal = v < lo or v > hi
            except (TypeError, ValueError):
                abnormal = False
        out.append(lab.model_copy(update={"abnormal": abnormal}))
    return out


# ---- check_interactions ------------------------------------------------------
@lru_cache(maxsize=1)
def _load_interactions() -> list[dict]:
    with open(DATA_DIR / "drug_interactions.json", encoding="utf-8") as f:
        return json.load(f)["interactions"]


def check_interactions(meds: list[MedExtract]) -> list[dict]:
    names = {m.name.lower() for m in meds}
    hits = []
    for item in _load_interactions():
        a, b = item["pair"]
        if a in names and b in names:
            hits.append(
                {"a": a, "b": b, "severity": item["severity"], "note": item["note"]}
            )
    return hits


# ---- build_timeline ----------------------------------------------------------
def build_timeline(documents: list[DocumentRecord]) -> list[tuple[DocumentRecord, str]]:
    """Undated docs FIRST (input order, label 'Undated'), then dated docs
    ascending by extracted_date (label = ISO date)."""
    undated = [(d, "Undated") for d in documents if d.extracted_date is None]
    dated = sorted(
        ((d, d.extracted_date.isoformat()) for d in documents if d.extracted_date),
        key=lambda pair: pair[0].extracted_date,
    )
    return undated + dated