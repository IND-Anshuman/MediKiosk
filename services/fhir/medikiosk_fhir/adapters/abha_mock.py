"""Demo ABHA adapter (ABDM sandbox stand-in, plan T3.9).

Accepts any syntactically well-formed ABHA and returns a fixed demo
identity. Never used for real verification — swap for the ABDM gateway
client when credentials land (plan 0.5, application pending).
"""

from __future__ import annotations

import re

_ABHA_LIKE = r"^([\w.\-]+@abdm(\.sbx)?|\d{2,4}-\d{4}-\d{4}-\d{4})$"


class AbhaMock:
    def verify(self, abha: str) -> dict:
        valid = bool(re.match(_ABHA_LIKE, abha or ""))
        return {"valid": valid, "name": "Demo User"} if valid else {"valid": False}