"""Ingestion telemetry models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import RunStatus, SourceStatus


class IngestionRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_runs"

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    connector: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default=RunStatus.PENDING, nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(24), default="schedule", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jobs_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_expired: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class IngestionError(UUIDMixin, Base):
    __tablename__ = "ingestion_errors"

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    level: Mapped[str] = mapped_column(String(16), default="error", nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default="now()")


class SourceHealth(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "source_health"

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_sources.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default=SourceStatus.UNKNOWN, nullable=False, index=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    jobs_last_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_last_run: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CompanyVerification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "company_verification"

    startup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("startups.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="unverified", nullable=False, index=True)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
