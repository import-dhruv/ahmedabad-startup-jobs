"""Job listing, source and skill models."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import JobStatus, VerificationStatus


class JobSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "job_sources"

    name: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    connector_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    base_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("startups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False, index=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    robots_policy: Mapped[str] = mapped_column(String(32), default="respect", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_jobs_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class JobListing(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "job_listings"

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    startup_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("startups.id", ondelete="SET NULL"), nullable=True, index=True
    )

    external_id: Mapped[str | None] = mapped_column(String(160), index=True, nullable=True)
    source_key: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    normalized_title: Mapped[str] = mapped_column(String(300), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    qualifications: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    skills_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)

    experience_level: Mapped[str | None] = mapped_column(String(24), index=True, nullable=True)
    experience_min_years: Mapped[float | None] = mapped_column(nullable=True)
    experience_max_years: Mapped[float | None] = mapped_column(nullable=True)

    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    salary_disclosed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    employment_type: Mapped[str | None] = mapped_column(String(24), index=True, nullable=True)
    work_arrangement: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    location_raw: Mapped[str | None] = mapped_column(String(300), nullable=True)
    location_city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    location_state: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    location_country: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    geo_scope: Mapped[str] = mapped_column(String(24), default="other", nullable=False, index=True)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    apply_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)

    verification_status: Mapped[str] = mapped_column(
        String(16), default=VerificationStatus.UNVERIFIED, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.ACTIVE, nullable=False, index=True)
    quality_score: Mapped[float] = mapped_column(default=0.0, nullable=False, index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    startup: Mapped[Startup | None] = relationship(back_populates="jobs", lazy="joined")  # noqa: F821
    source: Mapped[JobSource | None] = relationship(lazy="joined")
    skill_links: Mapped[list[JobSkill]] = relationship(  # noqa: F821
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )
    category_links: Mapped[list[JobCategory]] = relationship(  # noqa: F821
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )
    references: Mapped[list[JobSourceReference]] = relationship(  # noqa: F821
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_jobs_status_posted", "status", "posted_at"),
        Index("ix_jobs_geo_status", "geo_scope", "status"),
        Index("ix_jobs_search", "title", "company_name"),
    )


class JobSourceReference(UUIDMixin, Base):
    """Tracks a job's presence on every source it was seen on (multi-source dedup)."""

    __tablename__ = "job_source_references"

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_listings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default="now()")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default="now()")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    job: Mapped[JobListing] = relationship(back_populates="references")

    __table_args__ = (
        UniqueConstraint("job_id", "source_id", "external_id", name="uq_job_source_ref"),
    )


class Skill(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(72), unique=True, index=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    is_ai_skill: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)


class JobSkill(UUIDMixin, Base):
    __tablename__ = "job_skills"

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_listings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), index=True, nullable=False
    )
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="rule", nullable=False)

    job: Mapped[JobListing] = relationship(back_populates="skill_links")
    skill: Mapped[Skill] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("job_id", "skill_id", name="uq_job_skill"),)


class JobCategory(UUIDMixin, Base):
    __tablename__ = "job_categories"

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_listings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="rule", nullable=False)

    job: Mapped[JobListing] = relationship(back_populates="category_links")

    __table_args__ = (UniqueConstraint("job_id", "category", name="uq_job_category"),)
