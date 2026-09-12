from __future__ import annotations

import json
import os
from typing import Protocol


class LLM(Protocol):
    def extract(self, *, text: str, slot_schema: dict, language: str) -> dict: ...


class OpenAILLM:
    """Real LLM slot-filler (plan AD-3: prompt-hygiene, injectable client)."""

    def __init__(self, client=None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        self.client = client
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def extract(
        self,
        *,
        text: str,
        slot_schema: dict,
        language: str,
        context: dict | None = None,
    ) -> dict:
        # AD-3: PII from `context` is intentionally NOT forwarded to the LLM.
        # Only the utterance text + schema travel over the wire.
        sys = (
            "You extract structured clinical information from patient speech.\n"
            "Return ONLY valid JSON matching the given schema. No prose.\n"
            "Do not infer fields not present in the text."
        )
        try:
            r = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": sys},
                    {"role": "user", "content": json.dumps({"schema": slot_schema, "text": text, "language": language}, ensure_ascii=False)},
                ],
            )
            raw = (r.choices[0].message.content or "{}").strip()
            return json.loads(raw)
        except Exception:
            return {}
