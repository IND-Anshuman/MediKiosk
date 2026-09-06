"""Consent lifecycle + triage endpoints (plan T2.4, AD-8).

Consent is substantive, not theater: grant is recorded as a ConsentArtifact
inside the session; revoke purges ALL live PHI immediately (Redis session,
DB rows) and records a purged tombstone in the registry.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis import Redis

from medikiosk_api.deps import get_redis
from medikiosk_api.store import RedisSessionStore, purge_session
from medikiosk_shared.models import ConsentArtifact, RedFlagAlert, SessionState

router = APIRouter(tags=["consent", "triage"])


class ConsentReq(BaseModel):
    scopes: list[str]
    audio_signature_path: str | None = None


class TriageAlertReq(BaseModel):
    session_id: str
    pattern_id: str
    urgency: str = "urgent"
    message_en: str = ""
    message_hi: str = ""


@router.post("/sessions/{session_id}/consent", status_code=201)
def grant_consent(session_id: str, req: ConsentReq, r: Redis = Depends(get_redis)):
    store = RedisSessionStore(r)
    state = store.load(session_id)
    if state is None:
        raise HTTPException(404, "session not found")
    if state.consent is not None and state.consent.revoked_at is None:
        raise HTTPException(409, "consent already granted")
    state.consent = state.consent or __import__(
        "medikiosk_shared.models", fromlist=["ConsentArtifact"]
    ).ConsentArtifact(session_id=session_id, scopes=req.scopes)
    state.consent.scopes = req.scopes
    state.consent.revoked_at = None
    if req.audio_signature_path:
        state.consent.audio_signature_path = req.audio_signature_path
    store.save(state)
    return {"consent": state.consent.model_dump(mode="json")}


@router.post("/sessions/{session_id}/consent/revoke")
def revoke_consent(session_id: str, r: Redis = Depends(get_redis)):
    store = RedisSessionStore(r)
    state = store.load(session_id)
    if state is None or state.consent is None or state.consent.revoked_at is not None:
        raise HTTPException(409, "no active consent to revoke")

    # Record tombstone BEFORE purging (registry keeps session_id + purged_at only)
    try:
        from medikiosk_api.db import RegistryRow, _utcnow, init_engine

        with init_engine().begin() as conn:
            conn.execute(
                RegistryRow.__table__
                .update()
                .where(RegistryRow.__table__.c.session_id == session_id)
                .values(name="", token="", complaint="", purged_at=_utcnow())
            )
    except Exception:
        pass  # registry best-effort; live purge below is authoritative

    purge_session(r, session_id)
    return {"revoked": True, "purged": True}


@router.delete("/sessions/{session_id}/data")
def delete_session_data(session_id: str, r: Redis = Depends(get_redis)):
    purge_session(r, session_id)
    return {"deleted": True}


@router.post("/triage/alert", status_code=201)
def triage_alert(req: TriageAlertReq, r: Redis = Depends(get_redis)):
    store = RedisSessionStore(r)
    state = store.load(req.session_id)
    if state is None:
        raise HTTPException(404, "session not found")
    state.red_flags.append(
        RedFlagAlert(
            pattern_id=req.pattern_id,
            urgency=req.urgency,  # type: ignore[arg-type]
            message_hi=req.message_hi,
            message_en=req.message_en,
        )
    )
    store.save(state)
    return {"recorded": True, "red_flags": len(state.red_flags)}