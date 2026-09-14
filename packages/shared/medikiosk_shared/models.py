"""MediKiosk shared domain models.

Identity model (plan AD-6): ABHA is OPTIONAL. A walk-in patient is identified
by a hospital token (and/or phone). Aadhaar is never collected.

All datetimes are timezone-aware UTC (plan C-07: datetime.utcnow is banned).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    """Timezone-aware UTC now (C-07)."""
    return datetime.now(timezone.utc)


# ABHA number: 14 digits in 2-4-4-4 groups (final digit is a check digit),
# OR an ABHA address: <anything>@abdm (also accept .sbx for sandbox).
_ABHA_NUMBER_RE = re.compile(r"^\d{2,4}-\d{4}-\d{4}-\d{4}$")
_ABHA_ADDRESS_RE = re.compile(r"^[\w.\-]+@abdm(\.sbx)?$")

IdentifierSystem = Literal["abha", "token", "phone"]


class Identifier(BaseModel):
    system: IdentifierSystem
    value: str

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: str, info):
        if info.data.get("system") == "abha":
            if not (_ABHA_NUMBER_RE.match(v) or _ABHA_ADDRESS_RE.match(v)):
                # Reject, never repair (plan AD-6). A malformed ABHA is a
                # data-entry error the caller must fix, not normalize.
                raise ValueError(f"malformed ABHA identifier: {v!r}")
        if not v or not v.strip():
            raise ValueError("identifier value must be non-empty")
        return v.strip()


class Source(str, Enum):
    VOICE = "voice"
    TOUCH = "touch"
    DOCUMENT = "document"
    LLM_PARSED = "llm_parsed"


class Slot(BaseModel):
    key: str
    value: Any
    source: Source
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    confirmed: bool = True
    timestamp: datetime = Field(default_factory=utcnow)


class Answer(BaseModel):
    question_id: str
    raw_text: str
    parsed: dict[str, Any]
    language: str
    timestamp: datetime = Field(default_factory=utcnow)


class ChiefComplaint(BaseModel):
    name: str
    framework: str  # SOCRATES | OPQRST | SAMPLE | DASHAVIDHA
    slots: list[Slot] = []


class Patient(BaseModel):
    """Identity: identifiers[] carries token/phone/abha. No Aadhaar ever."""

    identifiers: list[Identifier] = []
    name: str | None = None
    age: int | None = Field(default=None, ge=0, le=150)
    gender: Literal["male", "female", "other"] | None = None
    language: str = "hi"
    phone: str | None = None
    allergies: list[str] = []
    past_conditions: list[str] = []

    @property
    def abha_id(self) -> str | None:
        for ident in self.identifiers:
            if ident.system == "abha":
                return ident.value
        return None


class RedFlagAlert(BaseModel):
    pattern_id: str
    urgency: Literal["immediate", "urgent", "standard"]
    message_hi: str
    message_en: str


class ClinicalSafetyAlert(BaseModel):
    category: Literal["allergy", "contraindication", "demographic", "interaction"]
    severity: Literal["critical", "major", "moderate", "advisory"]
    title: str
    detail: str
    source_entities: list[str] = []


class ConsentArtifact(BaseModel):
    session_id: str
    scopes: list[str]  # ["his_share", "abha_link", "storage", "analytics_anonymized"]
    audio_signature_path: str | None = None
    signed_at: datetime = Field(default_factory=utcnow)
    revoked_at: datetime | None = None


class MedExtract(BaseModel):
    name: str
    dose: str | None = None
    frequency: str | None = None
    route: str | None = None


class LabExtract(BaseModel):
    test: str
    value: str
    unit: str | None = None
    ref_range: str | None = None
    abnormal: bool = False


class DocumentRecord(BaseModel):
    """One digitized document (plan AD-7 Module B)."""

    doc_id: str = Field(default_factory=lambda: f"doc-{uuid4().hex[:10]}")
    kind: Literal["prescription", "lab", "discharge", "unknown"] = "unknown"
    page_count: int = Field(default=1, ge=1)
    extracted_date: date | None = None
    meds: list[MedExtract] = []
    labs: list[LabExtract] = []
    raw_text_ref: str  # object-store key of raw OCR text


class SessionState(BaseModel):
    session_id: str = Field(default_factory=lambda: f"sess-{uuid4().hex[:12]}")
    identifiers: list[Identifier] = []
    patient: Patient | None = None
    language: str = "hi"
    chief_complaint: ChiefComplaint | None = None
    secondary_complaints: list[str] = []
    answers: list[Answer] = []
    red_flags: list[RedFlagAlert] = []
    safety_alerts: list[ClinicalSafetyAlert] = []
    consent: ConsentArtifact | None = None
    documents: list[DocumentRecord] = []
    summary_md: str | None = None

    @property
    def abha_id(self) -> str | None:
        return self.patient.abha_id if self.patient else None


class FHIRBundle(BaseModel):
    """FHIR R4 Bundle of clinical resources for a session."""

    bundle_id: str = Field(default_factory=lambda: f"bundle-{uuid4().hex[:12]}")
    patient: Patient
    conditions: list[dict[str, Any]] = []
    medication_statements: list[dict[str, Any]] = []
    allergy_intolerances: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    document_references: list[dict[str, Any]] = []
