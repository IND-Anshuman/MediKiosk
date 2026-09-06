"""SessionStore protocol (plan AD-9): Redis is the SINGLE source of truth
for live-session state. Services (api, dialogue) must read/write sessions
through this protocol — never hold session state in process memory."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import SessionState


@runtime_checkable
class SessionStore(Protocol):
    def save(self, state: SessionState) -> None:
        """Persist the full session state; refreshes the sliding TTL."""
        ...

    def load(self, session_id: str) -> SessionState | None:
        """Load session state by id; None if missing/expired."""
        ...


__all__ = ["SessionStore"]
