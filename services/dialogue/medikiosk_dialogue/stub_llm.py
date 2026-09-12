"""Deterministic rule-based slot-filler (plan: LLM_BACKEND=stub, offline demo).

No external model. For single_choice questions it matches the utterance to
the closest touch option (substring / Devanagari); for free_text it returns
the raw text. This is the production-safe default when no LLM key is set — the
demo never depends on a network call.
"""
from __future__ import annotations

from typing import Any


class StubLLM:
    def extract(self, *, text: str, slot_schema: dict, language: str) -> dict:
        options = slot_schema.get("options") or []
        qtype = slot_schema.get("type", "free_text")
        low = (text or "").strip().lower()
        if qtype == "free_text" or not low:
            return {"choice": text}
        # best substring match to a known option (en or hi)
        best, best_len = None, 0
        for opt in options:
            ol = opt.lower()
            # option inside utterance OR utterance inside option → echo-proof
            if ol in low or low in ol:
                if len(ol) > best_len:
                    best, best_len = opt, len(ol)
        if best is not None:
            return {"choice": best}
        if language == "hi" and low:
            return {"choice": text}
        return {"choice": text}