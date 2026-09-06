"""Real LLM slot-filler backed by the OpenAI API (plan T3.5).

Protocol: matches the dialogue engine's LLM Protocol —
    extract(*, text, slot_schema, language) -> dict  ('{'choice': ...}' or {})

Plan AD-3 (prompt hygiene): the request payload contains ONLY the patient
utterance and the slot schema. No patient name, ABHA, or session id ever
leaves the kiosk, regardless of what context the caller passes.
Malformed/unavailable LLM output degrades to {} so the engine falls back
to raw-text slots.
"""

from __future__ import annotations

import json
import os
from typing import Any

SYSTEM_PROMPT = (
    "You extract structured clinical information from a patient's speech "
    "for a kiosk intake. Return ONLY valid JSON matching the provided schema. "
    "Never infer fields not present in the utterance. Respond in the "
    "patient's language when the schema allows free text."
)

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAILLM:
    """Slot-filler over the OpenAI chat-completions API.

    `client` is injectable for tests (any object with
    .chat.completions.create(**kwargs) -> obj with .choices[0].message.content).
    """

    def __init__(self, client: Any | None = None, model: str | None = None):
        self._client = client
        self.model = model or os.getenv("LLM_MODEL", _DEFAULT_MODEL)

    @property
    def client(self) -> Any:
        if self._client is None:
            from openai import OpenAI  # imported lazily; only needed live

            self._client = OpenAI()
        return self._client

    def extract(
        self,
        *,
        text: str,
        slot_schema: dict,
        language: str,
        context: dict | None = None,
    ) -> dict:
        """Extract {'choice': ...} from `text` per `slot_schema`.

        `context` (patient record, session id, ...) is accepted for protocol
        compatibility with richer callers but is NEVER placed in the prompt —
        plan AD-3: PII must not reach the remote LLM.
        """
        del context  # explicitly dropped, never serialized into messages
        user_payload = (
            f"language: {language}\n"
            f"slot_schema: {json.dumps(slot_schema, ensure_ascii=False)}\n"
            f"patient utterance: {text}"
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_payload},
                ],
            )
            content = resp.choices[0].message.content or ""
            return json.loads(content)
        except (json.JSONDecodeError, TypeError, ValueError, Exception):
            # any failure (bad JSON, network, client error) -> graceful {}
            return {}