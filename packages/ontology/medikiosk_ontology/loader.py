"""Clinical ontology loader (plan T1.2 v2).

Key semantics vs v1:
  - Question has NO red_flag_if field (C-11): red flags live only in the
    central registry, which covers all 5 complaints.
  - match_red_flag (C-10) supports multi-select answers:
      * scalar expected vs scalar actual  -> equality
      * list expected vs list actual      -> non-empty intersection
      * list expected vs scalar actual    -> membership
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class Question(BaseModel):
    id: str
    type: Literal["single_choice", "multi_choice", "duration", "free_text", "scale"]
    voice_hi: str
    voice_en: str
    touch_options_hi: list[str] = Field(default_factory=list)
    touch_options_en: list[str] = Field(default_factory=list)
    required: bool = True


class ChiefComplaintDef(BaseModel):
    name: str
    framework: Literal["SOCRATES", "OPQRST", "SAMPLE", "DASHAVIDHA"]
    questions: list[Question]


class RedFlag(BaseModel):
    pattern_id: str
    chief_complaint: str
    match_slots: dict[str, str | list[str]]
    urgency: Literal["immediate", "urgent", "standard"]
    message_hi: str
    message_en: str


def _matches(expected: str | list[str], actual: Any) -> bool:
    """C-10 matcher semantics."""
    actual_list = actual if isinstance(actual, list) else [actual]
    if isinstance(expected, list):
        # non-empty intersection
        return any(a in expected for a in actual_list)
    return expected in actual_list  # scalar expected: membership


class Ontology(BaseModel):
    chief_complaints: dict[str, ChiefComplaintDef] = Field(default_factory=dict)
    red_flags: list[RedFlag] = Field(default_factory=list)
    idioms: dict[str, dict[str, str]] = Field(default_factory=dict)

    def match_red_flag(self, *, chief_complaint: str, slots: dict[str, Any]) -> RedFlag | None:
        for rf in self.red_flags:
            if rf.chief_complaint != chief_complaint:
                continue
            if all(_matches(v, slots.get(k)) for k, v in rf.match_slots.items()):
                return rf
        return None

    def normalize_idiom(self, phrase: str) -> dict[str, str] | None:
        """Map vernacular Indian folk phrase to canonical clinical term."""
        if not phrase or not isinstance(phrase, str):
            return None
        p = phrase.lower().strip()
        for idiom_phrase, info in self.idioms.items():
            if idiom_phrase in p or p in idiom_phrase:
                return info
        return None


def load_ontology(data_dir: Path) -> Ontology:
    raw: dict[str, Any] = {}
    for yaml_file in sorted(data_dir.glob("*.yaml")):
        with open(yaml_file, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
            for key, value in loaded.items():
                if key in raw and isinstance(raw[key], dict) and isinstance(value, dict):
                    raw[key].update(value)
                elif key in raw and isinstance(raw[key], list) and isinstance(value, list):
                    raw[key].extend(value)  # red_flags accumulate across files
                else:
                    raw[key] = value
    return Ontology.model_validate(raw)
