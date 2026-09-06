"""T2.4: consent lifecycle (AD-8) + triage alert endpoint.

DPDP substance: grant -> revoke -> purge must leave NO retrievable PHI.
Purge without prior consent grant -> 409. Duplicate grant -> 409.
"""

import fakeredis
import pytest
from fastapi.testclient import TestClient

from medikiosk_api.deps import get_redis


@pytest.fixture()
def client():
    fake = fakeredis.FakeRedis(decode_responses=True)
    from medikiosk_api.main import app

    app.dependency_overrides[get_redis] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.clear()


def _make_session(c):
    return c.post("/sessions", json={"language": "hi"}).json()["session_id"]


def test_grant_consent_records_scopes(client):
    c, _ = client
    sid = _make_session(c)
    r = c.post(
        f"/sessions/{sid}/consent",
        json={"scopes": ["his_share", "storage"]},
    )
    assert r.status_code == 201
    body = c.get(f"/sessions/{sid}").json()["session"]
    assert body["consent"]["scopes"] == ["his_share", "storage"]
    assert body["consent"]["revoked_at"] is None


def test_duplicate_grant_conflict(client):
    c, _ = client
    sid = _make_session(c)
    body = {"scopes": ["his_share"]}
    assert c.post(f"/sessions/{sid}/consent", json=body).status_code == 201
    assert c.post(f"/sessions/{sid}/consent", json=body).status_code == 409


def test_revoke_then_purge_leaves_no_phi(client):
    c, fake = client
    sid = _make_session(c)
    c.post(f"/sessions/{sid}/consent", json={"scopes": ["his_share", "storage"]})

    r = c.post(f"/sessions/{sid}/consent/revoke")
    assert r.status_code == 200

    # After revoke+purge: live session is gone (404) — no PHI retrievable.
    assert c.get(f"/sessions/{sid}").status_code == 404
    assert fake.get(f"session:{sid}") is None


def test_revoke_without_grant_conflict(client):
    c, _ = client
    sid = _make_session(c)
    assert c.post(f"/sessions/{sid}/consent/revoke").status_code == 409


def test_triage_alert_records_flag(client):
    c, _ = client
    sid = _make_session(c)
    r = c.post(
        f"/triage/alert",
        json={
            "session_id": sid,
            "pattern_id": "mi_suspect",
            "urgency": "immediate",
            "message_en": "Possible cardiac emergency",
        },
    )
    assert r.status_code == 201
    body = c.get(f"/sessions/{sid}").json()["session"]
    assert body["red_flags"], "red flag not persisted to session"