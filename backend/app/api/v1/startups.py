"""Startup directory endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, PaginationDep
from app.models import JobListing, Startup, StartupFounder, StartupFunding
from app.models.enums import JobStatus
from app.schemas import (
    FounderRead,
    FundingRead,
    JobSummary,
    StartupDetail,
    StartupRead,
)
from app.api.v1.jobs import _job_to_summary

router = APIRouter(prefix="/startups", tags=["startups"])


def _with_active_count(startup: Startup, count: int) -> StartupRead:
    data = StartupRead.model_validate(startup)
    data.active_job_count = count
    return data


@router.get("", response_model=list[StartupRead], summary="Search startups")
async def search_startups(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200)] = None,
    industry: Annotated[list[str] | None, Query()] = None,
    hiring_status: Annotated[list[str] | None, Query()] = None,
    funding_stage: Annotated[list[str] | None, Query()] = None,
    size_range: Annotated[list[str] | None, Query()] = None,
    city: Annotated[str | None, Query(max_length=120)] = None,
    state: Annotated[str | None, Query(max_length=120)] = None,
    has_openings: Annotated[bool, Query()] = False,
    sort: Annotated[str, Query()] = "recent",
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[StartupRead]:
    clauses: list[Any] = [Startup.deleted_at.is_(None)]

    if q:
        pattern = f"%{q.lower()}%"
        clauses.append(
            or_(
                func.lower(Startup.name).like(pattern),
                func.lower(func.coalesce(Startup.description, "")).like(pattern),
                func.lower(func.coalesce(Startup.hq_city, "")).like(pattern),
            )
        )
    if industry:
        clauses.append(Startup.industry.in_(industry))
    if hiring_status:
        clauses.append(Startup.hiring_status.in_(hiring_status))
    if funding_stage:
        clauses.append(Startup.funding_stage.in_(funding_stage))
    if size_range:
        clauses.append(Startup.size_range.in_(size_range))
    if city:
        clauses.append(func.lower(func.coalesce(Startup.hq_city, "")).like(f"%{city.lower()}%"))
    if state:
        clauses.append(func.lower(func.coalesce(Startup.hq_state, "")).like(f"%{state.lower()}%"))

    job_count = (
        select(JobListing.startup_id, func.count(JobListing.id))
        .where(JobListing.status == JobStatus.ACTIVE)
        .group_by(JobListing.startup_id)
    ).subquery()

    if has_openings:
        clauses.append(
            Startup.id.in_(select(job_count.c.startup_id).where(job_count.c.count > 0))
        )

    if sort == "name":
        order = Startup.name.asc()
    elif sort == "openings":
        order = func.coalesce(
            select(job_count.c.count).where(job_count.c.startup_id == Startup.id).scalar_subquery(), 0
        ).desc()
    elif sort == "verified":
        order = Startup.verification_status.asc()
    else:
        order = Startup.created_at.desc()

    stmt = (
        select(Startup)
        .where(and_(*clauses))
        .options(selectinload(Startup.founders), selectinload(Startup.funding_rounds))
        .order_by(order)
        .limit(limit)
        .offset(offset)
    )
    startups = (await db.execute(stmt)).scalars().all()

    counts_stmt = (
        select(JobListing.startup_id, func.count(JobListing.id))
        .where(JobListing.startup_id.in_([s.id for s in startups]))
        .where(JobListing.status == JobStatus.ACTIVE)
        .group_by(JobListing.startup_id)
    )
    counts = {row[0]: row[1] for row in (await db.execute(counts_stmt)).all()}

    return [_with_active_count(s, counts.get(s.id, 0)) for s in startups]


@router.get("/filters", summary="Startup filter options")
async def startup_filters(db: DbSession) -> dict[str, Any]:
    industry_rows = (await db.execute(select(Startup.industry, func.count(Startup.id)).group_by(Startup.industry))).all()
    stage_rows = (
        await db.execute(
            select(Startup.funding_stage, func.count(Startup.id))
            .where(Startup.funding_stage.isnot(None))
            .group_by(Startup.funding_stage)
        )
    ).all()
    size_rows = (
        await db.execute(
            select(Startup.size_range, func.count(Startup.id))
            .where(Startup.size_range.isnot(None))
            .group_by(Startup.size_range)
        )
    ).all()
    city_rows = (
        await db.execute(
            select(Startup.hq_city, func.count(Startup.id))
            .where(Startup.hq_city.isnot(None))
            .group_by(Startup.hq_city)
            .order_by(func.count(Startup.id).desc())
            .limit(40)
        )
    ).all()
    return {
        "industries": {row[0]: row[1] for row in industry_rows},
        "funding_stages": {row[0]: row[1] for row in stage_rows},
        "size_ranges": {row[0]: row[1] for row in size_rows},
        "cities": {row[0]: row[1] for row in city_rows},
        "hiring_statuses": ["hiring", "not_hiring", "unknown"],
    }


@router.get("/slug/{slug}", response_model=StartupDetail, summary="Startup detail by slug")
async def startup_by_slug(db: DbSession, slug: str) -> StartupDetail:
    stmt = (
        select(Startup)
        .where(Startup.slug == slug)
        .options(
            selectinload(Startup.founders),
            selectinload(Startup.funding_rounds),
            selectinload(Startup.jobs),
        )
    )
    startup = (await db.execute(stmt)).scalar_one_or_none()
    if startup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Startup not found")

    jobs_stmt = (
        select(JobListing)
        .where(JobListing.startup_id == startup.id)
        .where(JobListing.status == JobStatus.ACTIVE)
        .options(selectinload(JobListing.startup), selectinload(JobListing.source))
        .order_by(func.coalesce(JobListing.posted_at, JobListing.discovered_at).desc())
        .limit(25)
    )
    jobs = (await db.execute(jobs_stmt)).scalars().all()
    job_summaries = [_job_to_summary(job, [], [job.category] if job.category else []) for job in jobs]

    data = StartupRead.model_validate(startup)
    payload = data.model_dump()
    payload["active_job_count"] = len(jobs)
    return StartupDetail(
        **payload,
        founders=[FounderRead.model_validate(f) for f in startup.founders],
        funding_rounds=[FundingRead.model_validate(f) for f in startup.funding_rounds],
        recent_jobs=job_summaries,
    )


@router.get("/{startup_id}", response_model=StartupDetail, summary="Startup detail")
async def get_startup(db: DbSession, startup_id: uuid.UUID) -> StartupDetail:
    stmt = (
        select(Startup)
        .where(Startup.id == startup_id)
        .options(selectinload(Startup.founders), selectinload(Startup.funding_rounds))
    )
    startup = (await db.execute(stmt)).scalar_one_or_none()
    if startup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Startup not found")
    data = StartupRead.model_validate(startup)
    return StartupDetail(**data.model_dump())
