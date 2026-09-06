"""ABHA verification adapter protocol (plan T3.9).

The kiosk talks to ABDM through this seam so the sandbox (AbhaMock) and the
real ABDM gateway can be swapped without touching callers. verify(abha)
returns a dict with at least {'valid': bool}; on a real adapter also
name/gender/year_of_birth as returned by the gateway.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AbhaAdapter(Protocol):
    def verify(self, abha: str) -> dict: ...