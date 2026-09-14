"""Tests for regional vernacular idiom mapping and dialogue integration."""

from pathlib import Path
import pytest
from medikiosk_ontology.loader import load_ontology, Question
from medikiosk_dialogue.main import _fuzzy_snap


DATA_DIR = Path("packages/ontology/data")


class TestVernacularIdioms:
    def test_idioms_loaded_into_ontology(self):
        onto = load_ontology(DATA_DIR)
        assert hasattr(onto, "idioms")
        assert "garami badh gayi" in onto.idioms
        assert "pet mein keede" in onto.idioms
        assert "sharir jal raha hai" in onto.idioms

    def test_normalize_idiom_matches(self):
        onto = load_ontology(DATA_DIR)
        res = onto.normalize_idiom("mujhe garami badh gayi hai")
        assert res is not None
        assert res["symptom"] == "fever"
        assert "Fever" in res["canonical"]

    def test_normalize_idiom_abdominal_worms(self):
        onto = load_ontology(DATA_DIR)
        res = onto.normalize_idiom("pet mein keede lagte hain")
        assert res is not None
        assert res["symptom"] == "abdominal_pain"

    def test_fuzzy_snap_with_idiom_matching(self):
        onto = load_ontology(DATA_DIR)
        q = Question(
            id="character",
            type="single_choice",
            voice_hi="Dard kaisa hai?",
            voice_en="How is the pain?",
            touch_options_en=["Burning sensation", "Sharp stabbing", "Dull pressure"],
            touch_options_hi=["Jalta hua", "Chhuru jaisa", "Dheere dard"],
        )
        # Idiom "sharir jal raha hai" -> canonical "Burning sensation" -> matches option
        matched = _fuzzy_snap("sharir jal raha hai", q, onto)
        assert matched in ("Burning sensation", "Jalta hua")
