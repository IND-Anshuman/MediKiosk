"""PM-JAY / Ayushman Bharat eligibility adapter (plan G5).

Design:
- Credential-gated: requires PMJAY_HOSPITAL_ID + PMJAY_API_KEY.
- Without creds: guide-mode fallback — step-by-step on-screen assist
  (Amrit app / beneficiary portal lookup).
- NEVER fake eligibility. Empty/missing response => "not verified" state.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx


_GUIDE_STEPS = [
    "Open Ayushman Bharat app (Amrit)",
    "Enter your ABHA number",
    "Tap 'Check Eligibility'",
    "Show the green checkmark to the counter staff",
]


class PmjayAdapter:
    def __init__(self):
        self.hospital_id = os.getenv("PMJAY_HOSPITAL_ID", "").strip()
        self.api_key = os.getenv("PMJAY_API_KEY", "").strip()
        self.state_pack = os.getenv("PMJAY_STATE_PACK", "").strip()
        self.base = os.getenv(
            "PMJAY_BASE_URL",
            "https://api.pmjay.gov.in/graphql",  # NHA GraphQL endpoint (empanelled only)
        )

    @property
    def enabled(self) -> bool:
        return bool(self.hospital_id and self.api_key)

    def check_eligibility(
        self,
        abha: str,
        name: str | None = None,
        mobile: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {
                "mode": "guide",
                "guide_steps": _GUIDE_STEPS,
                "eligible": None,
                "note": "Guide mode: ask patient to self-check on Ayushman app.",
            }
        query = """
        query Eligibility($abha: String!, $mobile: String) {
          checkEligibility(abha: $abha, mobile: $mobile) {
            eligible
            scheme
            packageCode
            message
          }
        }
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Hospital-ID": self.hospital_id,
        }
        try:
            with httpx.Client(timeout=10) as c:
                r = c.post(
                    self.base,
                    json={"query": query, "variables": {"abha": abha, "mobile": mobile}},
                    headers=headers,
                )
                r.raise_for_status()
                data = r.json()
            result = (
                data.get("data", {}).get("checkEligibility", {})
            )
            return {
                "mode": "api",
                "eligible": result.get("eligible"),
                "scheme": result.get("scheme", "PM-JAY"),
                "package_code": result.get("packageCode"),
                "message": result.get("message"),
            }
        except Exception as exc:
            return {
                "mode": "api",
                "eligible": None,
                "error": str(exc),
                "note": "PM-JAY check failed; fallback to guide mode.",
                "guide_steps": _GUIDE_STEPS,
            }
