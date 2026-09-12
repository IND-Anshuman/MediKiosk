"""T3.13: PM-JAY eligibility (read-only, credential-gated or guide-mode fallback)."""
from __future__ import annotations

import os
from typing import Any

import pytest


def _adapter():
    from medikiosk_fhir.adapters.pmjay import PmjayAdapter
    return PmjayAdapter()


def test_pmjay_adapter_exists():
    assert hasattr(_adapter(), "check_eligibility")


def test_pmjay_no_creds_returns_guide_mode(monkeypatch):
    monkeypatch.delenv("PMJAY_HOSPITAL_ID", raising=False)
    monkeypatch.delenv("PMJAY_API_KEY", raising=False)
    adapter = _adapter()
    res = adapter.check_eligibility(abha="14-1234-5678-9012")
    assert res["mode"] == "guide"
    assert any("Amrit" in step for step in res.get("guide_steps", []))


def test_pmjay_with_creds_calls_nha(monkeypatch):
    import medikiosk_fhir.adapters.pmjay as mod
    captured = {}

    class FakeResp:
        def raise_for_status(self): return None
        def json(self): return {"data": {"checkEligibility": {"eligible": True, "scheme": "PM-JAY", "packageCode": "ABC123"}}}

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, **kw):
            captured["url"] = url
            return FakeResp()

    monkeypatch.setattr(mod.httpx, "Client", lambda **_: FakeClient())
    monkeypatch.setenv("PMJAY_HOSPITAL_ID", " hosp-1")
    monkeypatch.setenv("PMJAY_API_KEY", "key-1")
    monkeypatch.setenv("PMJAY_STATE_PACK", "tamil_nadu")

    adapter = _adapter()
    res = adapter.check_eligibility(abha="14-1234-5678-9012", name="Ravi")
    assert res["mode"] == "api"
    assert res["eligible"] is True
    assert "graphql" in captured.get("url", "")
