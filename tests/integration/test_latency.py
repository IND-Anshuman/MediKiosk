"""T3.11: latency instrumentation (plan v2).

Every API response carries X-Timing-Api-Ms so the frontend + report script
can measure real turn latency. Budget (docs/ARCHITECTURE.md): p95 turn <= 4s.
"""

from fastapi.testclient import TestClient


def test_healthz_carries_timing_header():
    from medikiosk_api.main import app

    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200
    assert "x-timing-api-ms" in {k.lower() for k in r.headers}
    assert float(r.headers["x-timing-api-ms"]) >= 0.0