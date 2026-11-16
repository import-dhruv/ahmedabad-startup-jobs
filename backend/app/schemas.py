"""Pydantic schemas for the public API."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth -------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=160)


class UserLogin(BaseModel):
    email: str
    password: str


class UserRead(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    avatar_url: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class ProfileRead(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    headline: str | None = None
    bio: str | None = None
    location: str | None = None
    phone: str | None = None
    resume_url: str | None = None
    resume_filename: str | None = None
    experience_years: float | None = None
    skills: list[str] = Field(default_factory=list)
    preferred_job_types: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    preferred_arrangements: list[str] = Field(default_factory=list)
    open_to_remote: bool = True
    expected_salary_min: int | None = None
    expected_salary_max: int | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None


class ProfileUpdate(BaseModel):
    headline: str | None = None
    bio: str | None = None
    location: str | None = None
    phone: str | None = None
    experience_years: float | None = None
    skills: list[str] | None = None
    preferred_job_types: list[str] | None = None
    preferred_locations: list[str] | None = None
    preferred_arrangements: list[str] | None = None
    open_to_remote: bool | None = None
    expected_salary_min: int | None = None
    expected_salary_max: int | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None


# --- Startups ---------------------------------------------------------------


class StartupRead(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    description: str | None = None
    industry: str
    hq_city: str | None = None
    hq_state: str | None = None
    hq_country: str | None = None
    founded_year: int | None = None
    size_range: str | None = None
    hiring_status: str
    careers_url: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    funding_stage: str | None = None
    verification_status: str
    last_verified_at: datetime | None = None
    active_job_count: int = 0
    created_at: datetime


class StartupDetail(StartupRead):
    founders: list[FounderRead] = Field(default_factory=list)
    funding_rounds: list[FundingRead] = Field(default_factory=list)
    recent_jobs: list[JobSummary] = Field(default_factory=list)


class FounderRead(ORMModel):
    id: uuid.UUID
    name: str
    title: str | None = None
    linkedin_url: str | None = None


class FundingRead(ORMModel):
    id: uuid.UUID
    round_type: str
    amount: str | None = None
    currency: str | None = None
    announced_date: date | None = None
    investors: list[str] = Field(default_factory=list)
    source_url: str | None = None
    is_verified: bool = False


# --- Jobs -------------------------------------------------------------------


class SourceRead(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    connector_type: str
    base_url: str | None = None
    is_active: bool
    last_success_at: datetime | None = None


class LocationRead(BaseModel):
    raw: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    scope: str
    is_remote: bool = False


class SalaryRead(BaseModel):
    min: int | None = None
    max: int | None = None
    currency: str | None = None
    period: str | None = None
    disclosed: bool = False


class CompanyRef(BaseModel):
    id: uuid.UUID | None = None
    name: str
    slug: str | None = None
    logo_url: str | None = None
    industry: str | None = None
    hq_city: str | None = None


class JobSummary(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    company: CompanyRef
    location: LocationRead
    employment_type: str | None = None
    work_arrangement: str | None = None
    experience_level: str | None = None
    salary: SalaryRead
    posted_at: datetime | None = None
    last_verified_at: datetime | None = None
    discovered_at: datetime | None = None
    apply_url: str
    original_url: str
    source: SourceRead | None = None
    verification_status: str
    status: str
    quality_score: float = 0.0
    skills: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    geo_scope: str = "other"
    is_remote: bool = False
    ai_summary: str | None = None


class JobDetail(JobSummary):
    description: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    skills_text: str | None = None
    department: str | None = None
    deadline: date | None = None
    content_hash: str | None = None
    references: list[JobReferenceRead] = Field(default_factory=list)
    startup: StartupRead | None = None


class JobReferenceRead(ORMModel):
    id: uuid.UUID
    source_url: str
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    is_primary: bool = False


class JobListResponse(BaseModel):
    items: list[JobSummary]
    total: int
    page: int
    per_page: int
    pages: int
    facets: dict[str, Any] = Field(default_factory=dict)


# --- Stats ------------------------------------------------------------------


class DashboardStats(BaseModel):
    total_startups: int
    total_active_jobs: int
    new_jobs_24h: int
    new_jobs_7d: int
    new_jobs_30d: int
    companies_hiring: int
    internship_openings: int
    remote_opportunities: int
    ahmedabad_jobs: int
    gujarat_jobs: int
    total_sources: int
    active_sources: int
    jobs_awaiting_verification: int
    expired_jobs: int
    last_sync_at: datetime | None = None
    last_discovered_company_at: datetime | None = None
    generated_at: datetime


class TrendPoint(BaseModel):
    date: date
    count: int


class SkillTrend(BaseModel):
    skill: str
    count: int
    category: str | None = None
    trend: float = 0.0


class IndustryTrend(BaseModel):
    industry: str
    count: int
    companies: int


class HiringInsight(BaseModel):
    key: str
    label: str
    value: int
    detail: str | None = None
    measured: bool = True


# --- Alerts / saved ---------------------------------------------------------


class AlertRead(ORMModel):
    id: uuid.UUID
    name: str
    query: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    frequency: str
    is_active: bool
    last_triggered_at: datetime | None = None
    created_at: datetime


class AlertCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    query: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    frequency: str = "instant"
    is_active: bool = True


class SavedSearchRead(ORMModel):
    id: uuid.UUID
    name: str
    query: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    is_default: bool


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    query: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ApplicationRead(ORMModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    notes: str | None = None
    applied_at: datetime | None = None
    created_at: datetime


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    status: str = "applied"
    notes: str | None = None


class NotificationRead(ORMModel):
    id: uuid.UUID
    type: str
    title: str
    body: str | None = None
    link: str | None = None
    is_read: bool
    created_at: datetime


# --- Admin ------------------------------------------------------------------


class SourceReadAdmin(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    connector_type: str
    base_url: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    priority: int
    interval_minutes: int
    total_jobs_discovered: int
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    consecutive_failures: int
    notes: str | None = None


class SourceCreate(BaseModel):
    name: str
    slug: str
    connector_type: str
    base_url: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    priority: int = 50
    interval_minutes: int = 60
    notes: str | None = None


class RunRead(ORMModel):
    id: uuid.UUID
    source_id: uuid.UUID | None = None
    connector: str
    status: str
    trigger: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    jobs_found: int
    jobs_created: int
    jobs_updated: int
    jobs_expired: int
    jobs_skipped: int
    duplicates_found: int
    errors_count: int
    message: str | None = None


class ErrorRead(ORMModel):
    id: uuid.UUID
    run_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    level: str
    error_type: str | None = None
    message: str
    url: str | None = None
    created_at: datetime


class HealthRead(ORMModel):
    id: uuid.UUID
    source_id: uuid.UUID
    status: str
    consecutive_failures: int
    total_runs: int
    total_failures: int
    success_rate: float
    avg_duration_ms: float
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    jobs_last_run: int


class AdminOverview(BaseModel):
    total_sources: int
    active_connectors: int
    jobs_discovered_today: int
    successful_runs_24h: int
    failed_runs_24h: int
    duplicates_detected_24h: int
    jobs_awaiting_verification: int
    total_startups: int
    total_jobs: int
    active_jobs: int
    expired_jobs: int
    rejected_jobs: int
    database_size_mb: float | None = None


class StartupCreate(BaseModel):
    name: str
    website: str | None = None
    logo_url: str | None = None
    linkedin_url: str | None = None
    description: str | None = None
    industry: str = "Other technology startups"
    hq_city: str | None = None
    hq_state: str | None = None
    hq_country: str | None = "India"
    founded_year: int | None = None
    size_range: str | None = None
    hiring_status: str = "unknown"
    careers_url: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    funding_stage: str | None = None
    discovery_source: str | None = "manual"


class StartupUpdate(BaseModel):
    name: str | None = None
    website: str | None = None
    logo_url: str | None = None
    linkedin_url: str | None = None
    description: str | None = None
    industry: str | None = None
    hq_city: str | None = None
    hq_state: str | None = None
    hq_country: str | None = None
    founded_year: int | None = None
    size_range: str | None = None
    hiring_status: str | None = None
    careers_url: str | None = None
    tech_stack: list[str] | None = None
    funding_stage: str | None = None
    verification_status: str | None = None


class JobAdminUpdate(BaseModel):
    verification_status: str | None = None
    status: str | None = None
    rejection_reason: str | None = None
    startup_id: uuid.UUID | None = None
    quality_score: float | None = None


class MergeCompaniesRequest(BaseModel):
    target_id: uuid.UUID
    source_id: uuid.UUID


class ImportRequest(BaseModel):
    csv_content: str
    dry_run: bool = False


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    rows_processed: int


TokenResponse.model_rebuild()
StartupDetail.model_rebuild()
JobDetail.model_rebuild()
