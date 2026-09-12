"""ABDM sandbox adapter (M1: ABHA creation + verification).

Design:
- Creds gated: requires ABDM_CLIENT_ID + ABDM_CLIENT_SECRET.
- Falls back to None when creds are absent (mock mode).
- Verifier accepts 14-digit numbers in 2-4-4-4 or ABHA addresses.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


_ABHA_NUMBER_RE = re.compile(r"^\d{2,4}-\d{4}-\d{4}-\d{4}$")
_ABHA_ADDRESS_RE = re.compile(r"^[\w.\-]+@abdm(\.sbx)?$")


class AbdmSandboxAdapter:
    def __init__(self):
        self.base = os.getenv("ABDM_BASE_URL", "https://sandbox.abdm.gov.in").rstrip("/")
        self.client_id = os.getenv("ABDM_CLIENT_ID", "")
        self.client_secret = os.getenv("ABDM_CLIENT_SECRET", "")
        self._token_cache: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def verify_abha_number(self, abha: str) -> bool:
        if not abha:
            return False
        return bool(_ABHA_NUMBER_RE.match(abha)) or bool(_ABHA_ADDRESS_RE.match(abha))

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "Accept": "application/json"}

    def _get_token(self) -> str | None:
        if self._token_cache:
            return self._token_cache
        url = f"{self.base}/auth/v1/token"
        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "grantType": "client_credentials",
        }
        try:
            with httpx.Client(timeout=5) as c:
                r = c.post(url, json=payload, headers=self._headers())
                r.raise_for_status()
                data = r.json()
                self._token_cache = data.get("accessToken") or data.get("access_token")
                return self._token_cache
        except Exception:
            return None

    def create_abha(
        self,
        mobile: str,
        name: str,
        gender: str,
        year_of_birth: int,
    ) -> dict[str, Any] | None:
        """Return {"abha_number": ...} or None on failure / no creds."""
        if not self.enabled:
            return None
        token = self._get_token()
        if not token:
            return None
        url = f"{self.base}/registration/v1/abha/create"
        payload = {
            "mobile": mobile,
            "name": name,
            "gender": gender.upper(),
            "yearOfBirth": str(year_of_birth),
        }
        headers = {**self._headers(), "Authorization": f"Bearer {token}"}
        try:
            with httpx.Client(timeout=10) as c:
                r = c.post(url, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
        except Exception:
            return None
        abha_number = (
            data.get("abhaNumber")
            or data.get("abha_number")
            or data.get("healthIdNumber")
            or data.get("abha", {}).get("abhaNumber")
        )
        if abha_number:
            return {"abha_number": str(abha_number)}
        return None
