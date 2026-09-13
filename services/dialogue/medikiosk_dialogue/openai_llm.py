from __future__ import annotations

import json
import os
from typing import Any, Protocol


class LLM(Protocol):
    def extract(self, *, text: str, slot_schema: dict, language: str) -> dict: ...


class OpenAILLM:
    """Real LLM slot-filler (plan AD-3: prompt-hygiene, injectable client).

    One OpenAI-compatible config for ANY provider:
      OPENAI_API_KEY   — credential (required for live LLM)
      OPENAI_BASE_URL  — endpoint; omit for api.openai.com. Point it at
                         Featherless, Groq, Together, vLLM, Ollama, etc.
      OPENAI_MODEL     — the model id (e.g. gpt-4o-mini, zai-org/glm-5.3-flash)
    If no key is set the client stays None and extract() degrades to {} —
    the service never hard-fails without credentials.
    """

    def __init__(self, client: Any | None = None):
        self._client = client
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._base_url = os.getenv("OPENAI_BASE_URL", "") or None
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def client(self) -> Any | None:
        if self._client is None and self._api_key:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def extract(
        self,
        *,
        text: str,
        slot_schema: dict,
        language: str,
        context: dict | None = None,
    ) -> dict:
        # AD-3: PII from `context` is intentionally NOT forwarded to the LLM.
        client = self.client
        if client is None:
            return {}
        sys = (
            "You extract structured clinical information from patient speech.\n"
            "Return ONLY valid JSON matching the given schema. No prose.\n"
            "Do not infer fields not present in the text."
        )
        try:
            r = client.chat.completions.create(
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