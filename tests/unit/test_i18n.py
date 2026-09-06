"""T1.3: i18n bundle parity tests."""

import json
from pathlib import Path

BASE = Path("packages/i18n/locales")

# Keys required by the plan (v1 list + v2 additions)
REQUIRED = {
    "welcome",
    "consent_intro",
    "consent_his",
    "consent_abha",
    "language_picker_title",
    "record_complete",
    "go_to_room",
    "priority_alert_call_nurse",
    # v2 (confirm echo, consent, multi-complaint)
    "confirm_heard",
    "confirm_yes",
    "confirm_no",
    "revoke_consent",
    "other_problems_intro",
}


def _load(name: str) -> dict:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def test_both_locales_exist():
    hi, en = _load("hi.json"), _load("en.json")
    assert "welcome" in hi and "welcome" in en
    assert hi["welcome"] != en["welcome"]  # genuinely translated


def test_required_keys_present():
    hi, en = _load("hi.json"), _load("en.json")
    assert REQUIRED <= set(hi), f"hi missing: {REQUIRED - set(hi)}"
    assert REQUIRED <= set(en), f"en missing: {REQUIRED - set(en)}"


def test_key_parity():
    hi, en = set(_load("hi.json")), set(_load("en.json"))
    assert not (hi - en), f"missing in en: {hi - en}"
    assert not (en - hi), f"missing in hi: {en - hi}"