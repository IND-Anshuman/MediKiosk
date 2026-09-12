"""Summarizer HTTP surface (plan T3.8).

POST /summarize     {session: SessionState-dict} -> {summary_md}
POST /summarize.pdf {session: SessionState-dict} -> application/pdf bytes

LLM client is injectable for tests (x-inject-client: explode -> failing stub,
phrasify degrades to raw text). No PII is required for the render itself.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import Response
from medikiosk_shared.models import SessionState
from pydantic import BaseModel

from .summarizer import Summarizer, _OpenAIPhrasifier


class SummarizeRequest(BaseModel):
    session: dict[str, Any]


def _default_summarizer() -> Summarizer:
    # Live client only constructed when credentials exist; phrasify degrades
    # to raw text otherwise, so the endpoint never hard-fails. Prefers
    # Featherless (OpenAI-compatible) when FEATHERLESS_API_KEY is set.
    api_key = os.getenv("FEATHERLESS_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return Summarizer(client=None)
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=os.getenv("FEATHERLESS_BASE_URL", "") or None)
        return Summarizer(client=client)
    except Exception:
        return Summarizer(client=None)


app = FastAPI(title="medikiosk-summarizer")
_state: dict[str, Any] = {"summarizer": None}


def get_phrasifier():
    """Test/observability hook: current summarizer instance (never None)."""
    if _state["summarizer"] is None:
        _state["summarizer"] = _default_summarizer()
    return _state["summarizer"]


def _summarizer_for(request: Request) -> Summarizer:
    if request.headers.get("x-inject-client") == "explode":

        class Exploding:
            def phrasify(self, text: str, language: str) -> str:
                raise RuntimeError("injected LLM failure")

        return Summarizer(client=Exploding())
    return get_phrasifier()


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/summarize")
def summarize(req: SummarizeRequest, request: Request):
    session = SessionState.model_validate(req.session)
    summ = _summarizer_for(request)
    return {"summary_md": summ.render(session)}


@app.post("/summarize.pdf")
def summarize_pdf(req: SummarizeRequest, request: Request):
    session = SessionState.model_validate(req.session)
    summ = _summarizer_for(request)
    pdf_bytes = summ.pdf(session)
    return Response(content=pdf_bytes, media_type="application/pdf")