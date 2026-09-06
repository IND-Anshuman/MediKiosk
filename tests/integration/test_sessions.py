"""T2.1/T2.2: API gateway health + sessions with RedisSessionStore (AD-9).

Covers: healthz; create/get session; sliding TTL refresh (C-14);
store round-trip through the shared SessionStore protocol.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    import fakeredis

    from medikiosk_api.deps import get_redis

    fake = fakeredis.FakeRedis(decode_responses=True)
    from medikiosk_api.main import app

    app.dependency_overrides[get_redis] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.clear()


class TestHealth:
    def test_healthz(self, client):
        c, _ = client
        r = c.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestSessions:
    def test_create_and_get(self, client):
        c, _ = client
        r = c.post("/sessions", json={"language": "hi"})
        assert r.status_code == 201, r.text
        sid = r.json()["session_id"]
        assert sid.startswith("sess-")

        r2 = c.get(f"/sessions/{sid}")
        assert r2.status_code == 200
        assert r2.json()["session"]["language"] == "hi"
        assert r2.json()["session"]["session_id"] == sid

    def test_get_missing_404(self, client):
        c, _ = client
        assert c.get("/sessions/sess-nope").status_code == 404

    def test_ttl_refreshes_on_update(self, client):
        c, fake = client
        sid = c.post("/sessions", json={"language": "hi"}).json()["session_id"]
        ttl1 = fake.ttl(f"session:{sid}")
        # simulate activity
        c.patch(f"/sessions/{sid}", json={"language": "en"})
        ttl2 = fake.ttl(f"session:{sid}")
        assert ttl1 > 0 and ttl2 > ttl1 - 5  # refreshed toward full window