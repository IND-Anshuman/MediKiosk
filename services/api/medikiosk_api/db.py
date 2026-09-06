"""SQLAlchemy persistence layer (plan T2.3).

Postgres is the doctor-queue store + document registry; Redis stays the
live-session store (AD-9). SQLite is used for tests.

Documents + registry rows are PHI-bearing; `purge_session_data` is the
consent-revoke deletion path (T2.4) and MUST remove every row tied to a
session.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    object_key: Mapped[str] = mapped_column(String(256))
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(32), default="unknown")


class RegistryRow(Base):
    """One row per completed intake — the doctor's queue."""

    __tablename__ = "sessions_registry"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(128))
    complaint: Mapped[str] = mapped_column(String(64))
    red_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="intake")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    summary_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def init_engine(url: str | None = None):
    url = url or os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://medikiosk:medikiosk@localhost:5432/medikiosk"
    )
    # Tests pass sync sqlite URLs; compose uses asyncpg. Normalize to sync
    # drivers for this MVP's registry path (writes happen at submission).
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    return create_engine(url)


def purge_session_data(db: Session, session_id: str) -> None:
    """Consent-revoke deletion (T2.4): remove document rows + zero PHI in registry."""
    db.query(DocumentRow).filter(DocumentRow.session_id == session_id).delete()
    row = db.get(RegistryRow, session_id)
    if row is not None:
        row.name = ""
        row.token = ""
        row.complaint = ""
        row.purged_at = _utcnow()
    db.commit()