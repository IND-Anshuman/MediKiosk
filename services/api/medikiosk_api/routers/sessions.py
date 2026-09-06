"""Session endpoints backed by RedisSessionStore."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis import Redis

from medikiosk_api.deps import get_redis
from medikiosk_api.store import RedisSessionStore
from medikiosk_shared.models import Patient, SessionState

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionReq(BaseModel):
    language: str = "hi"
    name: str | None = None
    token: str | None = None
    abha_id: str | None = None
    phone: str | None = None


class UpdateSessionReq(BaseModel):
    language: str | None = None
    name: str | None = None
    token: str | None = None
    abha_id: str | None = None
    phone: str | None = None


def _store(r: Redis) -> RedisSessionStore:
    return RedisSessionStore(r)


@router.post("", status_code=201)
def create_session(req: CreateSessionReq, r: Redis = Depends(get_redis)):
    state = SessionState(language=req.language)
    idents = []
    if req.token:
        idents.append({"system": "token", "value": req.token})
    if req.abha_id:
        idents.append({"system": "abha", "value": req.abha_id})
    if req.phone:
        idents.append({"system": "phone", "value": req.phone})
    if idents or req.name:
        state.patient = Patient(
            identifiers=idents, name=req.name, language=req.language
        )
    _store(r).save(state)
    return {"session_id": state.session_id, "language": state.language}


@router.get("/{session_id}")
def get_session(session_id: str, r: Redis = Depends(get_redis)):
    state = _store(r).load(session_id)
    if state is None:
        raise HTTPException(404, "session not found")
    return {"session": state.model_dump(mode="json")}


@router.patch("/{session_id}")
def update_session(session_id: str, req: UpdateSessionReq, r: Redis = Depends(get_redis)):
    store = _store(r)
    state = store.load(session_id)
    if state is None:
        raise HTTPException(404, "session not found")
    if req.language:
        state.language = req.language
    if any([req.name, req.token, req.abha_id, req.phone]):
        patient = state.patient or Patient(language=state.language)
        if req.name:
            patient.name = req.name
        if req.token:
            patient.identifiers = [
                i for i in patient.identifiers if i.system != "token"
            ] + [{"system": "token", "value": req.token}]
        if req.abha_id:
            patient.identifiers = [
                i for i in patient.identifiers if i.system != "abha"
            ] + [{"system": "abha", "value": req.abha_id}]
        if req.phone:
            patient.phone = req.phone
        state.patient = patient
    store.save(state)  # sliding TTL refresh happens here
    return {"session": state.model_dump(mode="json")}