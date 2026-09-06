"""RED-first tests for T1.2 clinical ontology loader.

Covers (plan T1.2 v2):
  1. All 5 chief complaints + AYUSH present with correct frameworks
  2. AYUSH = 12 questions (Dashavidha 10 + Agni + Koshtha), all tappable
     (no bare free_text without a skip option)
  3. Red-flag registry covers all 5 complaints
  4. Matcher semantics (C-10): scalar==scalar, list∩list non-empty, list contains scalar
  5. Question model has NO red_flag_if field (C-11 — registry-only)
"""

from pathlib import Path

DATA_DIR = Path("packages/ontology/data")
EXPECTED_COMPLAINTS = {"chest_pain", "fever", "abdominal_pain", "cough", "headache"}
DASHAVIDHA_10 = {
    "prakriti", "vikriti", "sara", "samhanana", "pramana",
    "satmya", "sattva", "ahara_shakti", "vyayama_shakti", "vaya",
}


def _load():
    from medikiosk_ontology.loader import load_ontology

    return load_ontology(DATA_DIR)


class TestComplaints:
    def test_all_five_complaints_present(self):
        onto = _load()
        assert EXPECTED_COMPLAINTS <= set(onto.chief_complaints)

    def test_ayush_has_12_questions_with_agni_koshtha(self):
        onto = _load()
        assert "ayurvedic_assessment" in onto.chief_complaints
        dp = onto.chief_complaints["ayurvedic_assessment"]
        assert dp.framework == "DASHAVIDHA"
        qids = {q.id for q in dp.questions}
        assert DASHAVIDHA_10 <= qids
        assert {"agni", "koshtha"} <= qids
        assert len(dp.questions) == 12

    def test_every_ayush_question_is_tappable(self):
        onto = _load()
        dp = onto.chief_complaints["ayurvedic_assessment"]
        for q in dp.questions:
            assert q.touch_options_en, f"question {q.id} has no touch options"

    def test_each_complaint_has_final_other_problems_question(self):
        onto = _load()
        for name in EXPECTED_COMPLAINTS:
            qids = [q.id for q in onto.chief_complaints[name].questions]
            assert "other_problems" in qids, f"{name} missing other_problems"


class TestRedFlagRegistry:
    def test_registry_covers_all_five_complaints(self):
        onto = _load()
        covered = {rf.chief_complaint for rf in onto.red_flags}
        assert EXPECTED_COMPLAINTS <= covered

    def test_chest_pain_mi_pattern_matches(self):
        onto = _load()
        rf = onto.match_red_flag(
            chief_complaint="chest_pain",
            slots={"radiation": "Left arm", "associated": "Sweating"},
        )
        assert rf is not None and rf.urgency == "immediate"

    def test_matcher_list_intersects_list(self):
        onto = _load()
        # multi-select answer: patient tapped two associated symptoms
        rf = onto.match_red_flag(
            chief_complaint="chest_pain",
            slots={"radiation": ["Left arm", "Back"], "associated": ["Nausea", "Sweating"]},
        )
        assert rf is not None and rf.urgency == "immediate"

    def test_matcher_no_intersection_no_match(self):
        onto = _load()
        rf = onto.match_red_flag(
            chief_complaint="chest_pain",
            slots={"radiation": ["Back"], "associated": ["Nausea"]},
        )
        assert rf is None

    def test_headache_red_flag_immediate(self):
        onto = _load()
        rf = onto.match_red_flag(
            chief_complaint="headache",
            slots={"onset": "Achanak sabse tez (thunderclap)", "associated": ["Dizziness"]},
        )
        assert rf is not None and rf.urgency == "immediate"


class TestModelShape:
    def test_question_has_no_red_flag_if_field(self):
        from medikiosk_ontology.loader import Question

        assert "red_flag_if" not in Question.model_fields
