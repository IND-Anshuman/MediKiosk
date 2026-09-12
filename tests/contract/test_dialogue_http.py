"""T3.4a: DialogueEngine's HTTP contract (plan v2: /dialogue/start, /dialogue/answer).

The window is served as an independent FastAPI service (compose port 8003).
State flows through a SessionStore (Redis in prod); the LLM is swappable
(stub default, OpenAI when LLM_BACKEND=openai). Existing DialogueEngine
tests run against the class directly; these lock the HTTP wire layer.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class FakeStore:
    """In-memory SessionStore for HTTP tests (no Redis needed)."""

    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    def save(self, state) -> None:
        self.data[state.session_id] = state

    def load(self, session_id: str):
        return self.data.get(session_id)


@pytest.fixture()
def client(monkeypatch):
    import medikiosk_dialogue.main as m

    m._engine = None
    # swap the Redis store for an in-memory one at the HTTP boundary
    monkeypatch.setattr(m, "SessionStoreImpl", FakeStore)
    monkeypatch.setenv("ONTOLOGY_DIR", "packages/ontology/data")
    monkeypatch.setenv("LLM_BACKEND", "stub")
    return TestClient(m.app)


def test_healthz(client):
    assert client.get("/healthz").json()["ok"] is True


def test_start_returns_first_question(client):
    r = client.post("/dialogue/start", json={"chief_complaint": "chest_pain", "language": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"].startswith("sess-")
    assert body["next_question"]["id"] == "onset"


def test_answer_advances_and_returns_next(client):
    sid = client.post("/dialogue/start", json={"chief_complaint": "chest_pain", "language": "en"}).json()["session_id"]
    r = client.post("/dialogue/answer", json={"session_id": sid, "touch_indices": [0]})
    assert r.status_code == 200
    body = r.json()
    assert body["next_question"]["id"] == "location"
    assert body["red_flag"] is None


def test_unknown_session_404(client):
    r = client.post("/dialogue/answer", json={"session_id": "sess-nope", "touch_indices": [0]})
    assert r.status_code == 404