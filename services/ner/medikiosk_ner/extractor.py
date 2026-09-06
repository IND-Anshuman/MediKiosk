"""Rule-based clinical entity extraction (plan T3.7, AD-7 Module B).

Deterministic, zero-ML: longest-dictionary-match over data/reference/drugs.json
and lab_tests.json (case-insensitive, synonym-aware, Hindi Devanagari
synonyms included) + dose/frequency regexes + lab-line pattern.

NEVER invents entities: any span not matched by the dictionaries is ignored —
no-match text yields {"drugs": [], "labs": []}.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(
    os.environ["MEDIKIOSK_DATA_DIR"]
) if (os := __import__("os")) and "MEDIKIOSK_DATA_DIR" in __import__("os").environ else _REPO_ROOT / "data" / "reference"

_DOSE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|ml|g|iu)\b", re.IGNORECASE)
_FREQ_WORDS = {
    "od": "OD",
    "bd": "BD",
    "tds": "TDS",
    "qid": "QID",
    "hs": "HS",
    "sos": "SOS",
    "stat": "STAT",
}
_FREQ_NUM_RE = re.compile(r"\b(\d-\d-\d|\d-\d-\d-\d)\b")
_FREQ_WORD_RE = re.compile(r"\b(od|bd|tds|qid|hs|sos|stat)\b", re.IGNORECASE)
_ROUTE_RE = re.compile(
    r"\b(po|oral|iv|im|sc|sublingual|sl|topical|inhale|inhaler)\b", re.IGNORECASE
)

# Lab value: "<number> <unit>? (<lo>-<hi>)?" — searched after the matched test
# name within the same line.
_LAB_VALUE_RE = re.compile(
    r"\s*[:\-]?\s*(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>[a-zA-Z/%^°µ]+(?:/[a-zA-Z^°µ0-9]+)*)?\s*"
    r"(?:\(\s*(?P<lo>\d+(?:\.\d+)?)\s*[-–]\s*(?P<hi>\d+(?:\.\d+)?)\s*\))?"
)


@lru_cache(maxsize=1)
def _load_drugs() -> list[dict]:
    with open(DATA_DIR / "drugs.json", encoding="utf-8") as f:
        return json.load(f)["drugs"]


@lru_cache(maxsize=1)
def _load_lab_tests() -> list[dict]:
    with open(DATA_DIR / "lab_tests.json", encoding="utf-8") as f:
        return json.load(f)["tests"]


@lru_cache(maxsize=1)
def _build_drug_trie_terms() -> list[tuple[str, str]]:
    """(surface_lower, canonical_name), longest surface first."""
    terms = []
    for d in _load_drugs():
        for syn in d["synonyms"]:
            terms.append((syn.lower(), d["name"]))
    # Longest match wins; equal length → first dictionary entry wins.
    return sorted(set(terms), key=lambda t: -len(t[0]))


@lru_cache(maxsize=1)
def _build_lab_terms() -> list[tuple[str, str]]:
    terms = []
    unit_of = {t["name"]: (t["units"][0] if t["units"] else None) for t in _load_lab_tests()}
    for t in _load_lab_tests():
        for syn in t["synonyms"]:
            terms.append((syn.lower(), t["name"]))
    return sorted(set(terms), key=lambda t: -len(t[0])), unit_of


def _match_dictionary(text: str, terms: list[tuple[str, str]]) -> list[tuple[str, str, int, int]]:
    """Non-overlapping longest-match; returns (canonical, surface, start, end)."""
    hits = []
    taken = [(s, e) for _, _, s, e in hits]
    out: list[tuple[str, str, int, int]] = []
    spans: list[tuple[int, int]] = []
    lower = text.lower()
    for surface, canonical in terms:
        start = 0
        while True:
            i = lower.find(surface, start)
            if i == -1:
                break
            end = i + len(surface)
            start = end
            # Word-boundary guard: ASCII alnum neighbours reject partial words.
            if i > 0 and (lower[i - 1].isalnum() and surface[0].isalnum()):
                continue
            if end < len(lower) and (lower[end].isalnum() and surface[-1].isalnum()):
                continue
            if any(i < e and s < end for s, e in spans):
                continue
            spans.append((i, end))
            out.append((canonical, surface, i, end))
    return out


def _freq_at(text: str, lo: int, hi: int) -> str | None:
    """Frequency appearing near [lo, hi): numeric 1-0-1 style wins over word."""
    window = text[max(0, lo - 20): min(len(text), hi + 20)]
    m_num = _FREQ_NUM_RE.search(window)
    if m_num:
        return m_num.group(1)
    m_word = _FREQ_WORD_RE.search(window)
    if m_word:
        return _FREQ_WORDS[m_word.group(1).lower()]
    return None


def _route_at(text: str, lo: int, hi: int) -> str | None:
    window = text[max(0, lo - 30): min(len(text), hi + 30)]
    m = _ROUTE_RE.search(window)
    return m.group(1).upper() if m else None


def extract_entities(text: str) -> dict:
    """Text → {"drugs": [MedExtract-shaped dicts], "labs": [{test,value,unit,ref_range}]}."""
    drugs_out: list[dict] = []
    labs_out: list[dict] = []

    drug_terms = _build_drug_trie_terms()
    lab_terms, lab_unit = _build_lab_terms()

    lab_matches = _match_dictionary(text, lab_terms)
    drug_matches = _match_dictionary(text, drug_terms)
    lab_spans = [(s, e) for _, _, s, e in lab_matches]

    # Labs: dictionary test name + a number (dose-regex compatible units allowed)
    for canonical, surface, s, e in lab_matches:
        line_end = text.find("\n", e)
        line_end = len(text) if line_end == -1 else line_end
        # Search AFTER the test span — digits inside the name (HbA1c, B12) are
        # not values.
        m = _LAB_VALUE_RE.search(text[e:line_end])
        if not m or m.group("value") is None:
            continue
        value = m.group("value")
        unit = m.group("unit") or lab_unit.get(canonical)
        lo, hi = m.group("lo"), m.group("hi")
        ref = f"{lo}-{hi}" if lo and hi else None
        labs_out.append(
            {"test": canonical, "value": value, "unit": unit, "ref_range": ref}
        )

    # Drugs
    for canonical, surface, s, e in drug_matches:
        dose_m = _DOSE_RE.search(text, e, min(len(text), e + 60))
        dose = None
        if dose_m:
            num, unit = dose_m.group(1), dose_m.group(2).lower()
            dose = f"{num}{unit}"
        freq = _freq_at(text, s, e)
        route = _route_at(text, s, e)
        drugs_out.append(
            {"name": canonical, "dose": dose, "frequency": freq, "route": route}
        )

    return {"drugs": drugs_out, "labs": labs_out}