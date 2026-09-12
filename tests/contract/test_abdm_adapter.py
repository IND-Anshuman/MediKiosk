"""T3.9 addendum: ABDM sandbox adapter (M1: ABHA creation/verification)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from medikiosk_fhir.adapters.abdm_sandbox import AbdmSandboxAdapter


def test_adba_adapter_exists():
    assert hasattr(AbdmSandboxAdapter, "create_abha")
    assert hasattr(AbdmSandboxAdapter, "verify_abha_number")


def test_verify_abha_number_valid():
    adapter = AbdmSandboxAdapter()
    assert adapter.verify_abha_number("14-3344-5566-7788") is True
    assert adapter.verify_abha_number("12-3456-7890-1234") is True


def test_verify_abha_number_invalid():
    adapter = AbdmSandboxAdapter()
    assert adapter.verify_abha_number("1-2345-6789-0123") is False  # too short first group
    assert adapter.verify_abha_number("not-a-number") is False
    assert adapter.verify_abha_number("") is False


def test_create_abha_without_creds_returns_none(monkeypatch):
    monkeypatch.delenv("ABDM_CLIENT_ID", raising=False)
    monkeypatch.delenv("ABDM_CLIENT_SECRET", raising=False)
    adapter = AbdmSandboxAdapter()
    assert adapter.enabled is False
    res = adapter.create_abha(mobile="9999999999", name="Ravi", gender="M", year_of_birth=1985)
    assert res is None


def test_create_abha_with_creds_calls_sandbox(monkeypatch):
    import medikiosk_fhir.adapters.abdm_sandbox as mod

    captured: dict[str, object] = {}

    class FakeResp:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kw):
            captured["url"] = url
            captured["kw"] = kw
            if "/auth/v1" in url:
                return FakeResp({"accessToken": "tok"})
            if "/registration/v1/abha/create" in url:
                return FakeResp({"abhaNumber": "14-1234-5678-9012"})
            return FakeResp({})

    monkeypatch.setattr(mod.httpx, "Client", lambda **_: FakeClient())
    monkeypatch.setenv("ABDM_BASE_URL", "https://sandbox.abdm.gov.in")
    monkeypatch.setenv("ABDM_CLIENT_ID", "test-client")
    monkeypatch.setenv("ABDM_CLIENT_SECRET", "test-secret")

    adapter = AbdmSandboxAdapter()
    res = adapter.create_abha(mobile="9999999999", name="Ravi", gender="M", year_of_birth=1985)
    assert res == {"abha_number": "14-1234-5678-9012"}
    assert "/registration/v1/abha/create" in str(captured.get("url", ""))
