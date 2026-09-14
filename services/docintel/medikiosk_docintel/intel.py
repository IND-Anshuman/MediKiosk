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

from medikiosk_shared.models import (
    ClinicalSafetyAlert,
    DocumentRecord,
    LabExtract,
    MedExtract,
)

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
    with open(DATA_DIR / "drug_interactions.json", encoding="utf-8-sig") as f:
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


# ---- check_allergies & contraindications -------------------------------------
@lru_cache(maxsize=1)
def _load_contraindications() -> dict:
    with open(DATA_DIR / "drug_contraindications.json", encoding="utf-8-sig") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_allergies() -> dict:
    with open(DATA_DIR / "drug_allergies.json", encoding="utf-8-sig") as f:
        return json.load(f)["allergy_classes"]


def check_allergies(meds: list[MedExtract], allergies: list[str]) -> list[ClinicalSafetyAlert]:
    """Flag critical alerts when prescribed/active meds clash with patient allergies."""
    if not allergies or not meds:
        return []
    allergy_data = _load_allergies()
    alerts: list[ClinicalSafetyAlert] = []

    # Map normalized allergy keywords to classes and specific drugs
    normalized_allergies = [a.lower().strip() for a in allergies if a and a.strip()]

    for med in meds:
        m_name = med.name.lower().strip()
        for allergen in normalized_allergies:
            # 1. Direct drug name match
            if allergen in m_name or m_name in allergen:
                alerts.append(
                    ClinicalSafetyAlert(
                        category="allergy",
                        severity="critical",
                        title=f"Allergy Clash: {med.name}",
                        detail=f"Patient has documented allergy to {allergen}; prescribed medication {med.name} may trigger severe hypersensitivity.",
                        source_entities=[med.name, allergen],
                    )
                )
                continue

            # 2. Allergy class match
            for cls_key, cls_info in allergy_data.items():
                # check if reported allergen matches class name or key
                class_matched = (
                    cls_key in allergen
                    or allergen in cls_key
                    or allergen in cls_info["name"].lower()
                )
                if class_matched:
                    # check if med is in this class
                    if any(member in m_name for member in cls_info["members"]):
                        alerts.append(
                            ClinicalSafetyAlert(
                                category="allergy",
                                severity="critical",
                                title=f"Allergy Clash: {med.name} ({cls_info['name']})",
                                detail=f"Patient is allergic to {cls_info['name']}. {med.name} belongs to this class: {cls_info['note']}",
                                source_entities=[med.name, allergen],
                            )
                        )
    return alerts


def check_contraindications(
    meds: list[MedExtract],
    conditions: list[str],
    age: int | None = None,
    sex: str | None = None,
) -> list[ClinicalSafetyAlert]:
    """Flag contraindications between active medications, conditions, and demographics."""
    if not meds:
        return []
    rules = _load_contraindications()
    alerts: list[ClinicalSafetyAlert] = []
    med_names = {m.name.lower().strip() for m in meds}

    # Normalize conditions
    norm_conditions = {c.lower().strip().replace("-", "_").replace(" ", "_") for c in conditions if c}

    # Condition-based contraindications
    for item in rules.get("contraindications", []):
        d = item["drug"].lower()
        c = item["condition"].lower()
        if any(d in m for m in med_names):
            if any(c in cond or cond in c for cond in norm_conditions):
                matched_med = next(m for m in med_names if d in m)
                alerts.append(
                    ClinicalSafetyAlert(
                        category="contraindication",
                        severity=item["severity"],
                        title=f"Contraindication: {matched_med} in {c.replace('_', ' ').title()}",
                        detail=item["note"],
                        source_entities=[matched_med, c],
                    )
                )

    # Demographic-based rules (pediatric / geriatric)
    for rule in rules.get("demographic_rules", []):
        d = rule["drug"].lower()
        if any(d in m for m in med_names):
            matched_med = next(m for m in med_names if d in m)
            if age is not None:
                if "age_max" in rule and age <= rule["age_max"]:
                    alerts.append(
                        ClinicalSafetyAlert(
                            category="demographic",
                            severity=rule["severity"],
                            title=f"Pediatric Safety Warning: {matched_med} (Age {age})",
                            detail=rule["note"],
                            source_entities=[matched_med, f"age_{age}"],
                        )
                    )
                if "age_min" in rule and age >= rule["age_min"]:
                    alerts.append(
                        ClinicalSafetyAlert(
                            category="demographic",
                            severity=rule["severity"],
                            title=f"Geriatric Safety Warning: {matched_med} (Age {age})",
                            detail=rule["note"],
                            source_entities=[matched_med, f"age_{age}"],
                        )
                    )
    return alerts


def evaluate_clinical_safety(
    meds: list[MedExtract],
    conditions: list[str] | None = None,
    allergies: list[str] | None = None,
    age: int | None = None,
    sex: str | None = None,
) -> list[ClinicalSafetyAlert]:
    """Unified safety screening combining interactions, allergies, and contraindications."""
    alerts: list[ClinicalSafetyAlert] = []

    # 1. Allergies
    if allergies:
        alerts.extend(check_allergies(meds, allergies))

    # 2. Contraindications & Demographics
    alerts.extend(check_contraindications(meds, conditions or [], age, sex))

    # 3. Drug-drug interactions
    interactions = check_interactions(meds)
    for inter in interactions:
        alerts.append(
            ClinicalSafetyAlert(
                category="interaction",
                severity=inter["severity"],
                title=f"Drug Interaction: {inter['a'].title()} + {inter['b'].title()}",
                detail=inter["note"],
                source_entities=[inter["a"], inter["b"]],
            )
        )

    # Priority sorting: critical -> major -> moderate -> advisory
    order = {"critical": 0, "major": 1, "moderate": 2, "advisory": 3}
    alerts.sort(key=lambda a: order.get(a.severity, 4))
    return alerts


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