"""Startup (company) models."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import HiringStatus, VerificationStatus


class Startup(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "startups"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    website: Mapped[str | None] = mapped_column(String(600), nullable=True, index=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str] = mapped_column(String(64), default="Other technology startups", nullable=False, index=True)
    hq_city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    hq_state: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    hq_country: Mapped[str | None] = mapped_column(String(80), default="India", nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_range: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    hiring_status: Mapped[str] = mapped_column(String(16), default=HiringStatus.UNKNOWN, nullable=False, index=True)
    careers_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    tech_stack: Mapped[list[str]] = mapped_column(ARRAY(String(48)), default=list, nullable=False)
    funding_stage: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "job_sources.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_startups_source_id",
        ),
        nullable=True,
    )
    discovery_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(16), default=VerificationStatus.UNVERIFIED, nullable=False, index=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    founders: Mapped[list[StartupFounder]] = relationship(
        back_populates="startup", cascade="all, delete-orphan", lazy="selectin"
    )
    funding_rounds: Mapped[list[StartupFunding]] = relationship(
        back_populates="startup", cascade="all, delete-orphan", lazy="selectin"
    )
    jobs: Mapped[list[JobListing]] = relationship(  # noqa: F821
        back_populates="startup", lazy="noload"
    )

    @property
    def active_job_count(self) -> int:
        return getattr(self, "_active_job_count", 0) or 0


class StartupFounder(UUIDMixin, Base):
    __tablename__ = "startup_founders"

    startup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("startups.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    startup: Mapped[Startup] = relationship(back_populates="founders")


class StartupFunding(UUIDMixin, Base):
    __tablename__ = "startup_funding"

    startup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("startups.id", ondelete="CASCADE"), index=True, nullable=False
    )
    round_type: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_numeric: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    announced_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    investors: Mapped[list[str]] = mapped_column(ARRAY(String(160)), default=list, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default="now()")

    startup: Mapped[Startup] = relationship(back_populates="funding_rounds")

    __table_args__ = (UniqueConstraint("startup_id", "round_type", "announced_date", name="uq_funding_round"),)
