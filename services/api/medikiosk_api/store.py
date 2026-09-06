"""Redis-backed SessionStore — the single live-state source of truth (AD-9).

Sliding TTL (C-14): every save() refreshes the key's expiry, so a patient
waiting in a long OPD queue never loses a live session to idle expiry.
"""

from __future__ import annotations

import json

import redis as redis_lib

from medikiosk_shared.models import SessionState

SESSION_TTL_SECONDS = 7200  # 2h sliding window


class RedisSessionStore:
    def __init__(self, client: redis_lib.Redis):
        self.client = client

    def save(self, state: SessionState) -> None:
        self.client.set(
            f"session:{state.session_id}",
            state.model_dump_json(),
            ex=SESSION_TTL_SECONDS,
        )

    def load(self, session_id: str) -> SessionState | None:
        raw = self.client.get(f"session:{session_id}")
        if raw is None:
            return None
        return SessionState.model_validate_json(raw)


def purge_session(client: redis_lib.Redis, session_id: str) -> None:
    """Remove all live-session PHI (consent revoke path, T2.4)."""
    client.delete(f"session:{session_id}")


def get_redis() -> redis_lib.Redis:
    import os

    return redis_lib.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )
