"""FastAPI dependencies."""

from __future__ import annotations

from medikiosk_api.store import get_redis  # re-export

__all__ = ["get_redis"]
