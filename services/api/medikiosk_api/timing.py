"""Latency timing middleware (plan T3.11)."""

from __future__ import annotations

import time

from fastapi import FastAPI, Request


def add_timing_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def timing(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Timing-Api-Ms"] = f"{(time.perf_counter() - t0) * 1000:.1f}"
        return response