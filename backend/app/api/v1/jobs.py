"""Job search, listing and detail endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, OptionalUser, PaginationDep
from app.models import JobListing, JobSkill, JobSource, Skill, Startup, User, UserJobView
from app.models.enums import JobStatus, VerificationStatus
from app.schemas import (
    JobDetail,
    JobListResponse,
    JobSummary,
    LocationRead,
    SalaryRead,
    SourceRead,
)
from app.services.geo import GEO_SCOPE_LABELS

router = APIRouter(prefix="/jobs", tags=["jobs"])

DEFAULT_SCOPES = ["ahmedabad", "gujarat", "india_remote", "india", "global"]
SORT_OPTIONS = ("relevance", "newest", "oldest", "salary_high", "salary_low", "company")


def _job_to_summary(job: JobListing, skills: list[str], categories: list[str]) -> JobSummary:
    startup = job.startup
    company = {
        "id": startup.id if startup else None,
        "name": startup.name if startup else job.company_name,
        "slug": startup.slug if startup else None,
        "logo_url": startup.logo_url if startup else None,
        "industry": startup.industry if startup else None,
        "hq_city": startup.hq_city if startup else None,
    }
    source = None
    if job.source:
        source = SourceRead.model_validate(job.source)
    return JobSummary(
        id=job.id,
        slug=job.slug,
        title=job.title,
        company=company,
        location=LocationRead(
            raw=job.location_raw,
            city=job.location_city,
            state=job.location_state,
            country=job.location_country,
            scope=job.geo_scope,
            is_remote=job.is_remote,
        ),
        employment_type=job.employment_type,
        work_arrangement=job.work_arrangement,
        experience_level=job.experience_level,
        salary=SalaryRead(
            min=job.salary_min,
            max=job.salary_max,
            currency=job.salary_currency,
            period=job.salary_period,
            disclosed=job.salary_disclosed,
        ),
        posted_at=job.posted_at,
        last_verified_at=job.last_verified_at,
        discovered_at=job.discovered_at,
        apply_url=job.apply_url,
        original_url=job.original_url,
        source=source,
        verification_status=job.verification_status,
        status=job.status,
        quality_score=job.quality_score,
        skills=skills,
        categories=categories,
        geo_scope=job.geo_scope,
        is_remote=job.is_remote,
        ai_summary=job.ai_summary,
    )


def _build_filters(
    q: str | None,
    company: str | None,
    skills: list[str] | None,
    experience: list[str] | None,
    employment_type: list[str] | None,
    work_arrangement: list[str] | None,
    city: str | None,
    industry: list[str] | None,
    min_salary: int | None,
    max_salary: int | None,
    remote_only: bool,
    internship_only: bool,
    scopes: list[str],
    source_slug: str | None,
    verified_only: bool,
    posted_within_days: int | None,
    startup_id: uuid.UUID | None,
) -> list[Any]:
    clauses: list[Any] = [
        JobListing.status == JobStatus.ACTIVE,
        JobListing.deleted_at.is_(None),
    ]

    if q:
        terms = [t.strip() for t in q.split() if len(t.strip()) > 1]
        if terms:
            ors = []
            for term in terms[:6]:
                pattern = f"%{term.lower()}%"
                ors.append(
                    or_(
                        func.lower(JobListing.title).like(pattern),
                        func.lower(JobListing.company_name).like(pattern),
                        func.lower(func.coalesce(JobListing.skills_text, "")).like(pattern),
                        func.lower(func.coalesce(JobListing.category, "")).like(pattern),
                        func.lower(func.coalesce(JobListing.description, "")).like(pattern),
                    )
                )
            clauses.append(or_(*ors))

    if company:
        clauses.append(func.lower(JobListing.company_name).like(f"%{company.lower()}%"))

    if skills:
        skill_names = [s.strip() for s in skills if s.strip()]
        if skill_names:
            sub = (
                select(JobSkill.job_id)
                .join(Skill, Skill.id == JobSkill.skill_id)
                .where(Skill.name.in_(skill_names))
            )
            clauses.append(JobListing.id.in_(sub))

    if experience:
        clauses.append(JobListing.experience_level.in_(experience))
    if employment_type:
        clauses.append(JobListing.employment_type.in_(employment_type))
    if work_arrangement:
        clauses.append(JobListing.work_arrangement.in_(work_arrangement))
    if city:
        clauses.append(func.lower(func.coalesce(JobListing.location_city, "")).like(f"%{city.lower()}%"))
    if industry:
        sub = select(Startup.id).where(Startup.industry.in_(industry))
        clauses.append(JobListing.startup_id.in_(sub))
    if min_salary is not None:
        clauses.append(func.coalesce(JobListing.salary_max, JobListing.salary_min) >= min_salary)
    if max_salary is not None:
        clauses.append(func.coalesce(JobListing.salary_min, JobListing.salary_max) <= max_salary)
    if remote_only:
        clauses.append(JobListing.is_remote.is_(True))
    if internship_only:
        clauses.append(
            or_(JobListing.employment_type == "Internship", func.lower(JobListing.title).like("%intern%"))
        )
    if scopes:
        clauses.append(JobListing.geo_scope.in_(scopes))
    if source_slug:
        clauses.append(JobListing.source_key.ilike(f"%{source_slug}%"))
    if verified_only:
        clauses.append(JobListing.verification_status == VerificationStatus.VERIFIED)
    if posted_within_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_within_days)
        clauses.append(func.coalesce(JobListing.posted_at, JobListing.discovered_at) >= cutoff)
    if startup_id:
        clauses.append(JobListing.startup_id == startup_id)
    return clauses


async def _skill_map(db: AsyncSession, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    if not job_ids:
        return {}
    stmt = (
        select(JobSkill.job_id, Skill.name)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(JobSkill.job_id.in_(job_ids))
        .order_by(JobSkill.confidence.desc())
    )
    mapping: dict[uuid.UUID, list[str]] = {}
    for job_id, name in (await db.execute(stmt)).all():
        mapping.setdefault(job_id, []).append(name)
    return mapping


@router.get("", response_model=JobListResponse, summary="Search job openings")
async def search_jobs(
    db: DbSession,
    pagination: PaginationDep,
    q: Annotated[str | None, Query(max_length=200, description="Free-text search")] = None,
    company: Annotated[str | None, Query(max_length=120)] = None,
    skills: Annotated[list[str] | None, Query()] = None,
    experience: Annotated[list[str] | None, Query()] = None,
    employment_type: Annotated[list[str] | None, Query()] = None,
    work_arrangement: Annotated[list[str] | None, Query()] = None,
    city: Annotated[str | None, Query(max_length=120)] = None,
    industry: Annotated[list[str] | None, Query()] = None,
    min_salary: Annotated[int | None, Query(ge=0)] = None,
    max_salary: Annotated[int | None, Query(ge=0)] = None,
    remote: Annotated[bool, Query()] = False,
    internship: Annotated[bool, Query()] = False,
    scope: Annotated[list[str] | None, Query()] = None,
    source: Annotated[str | None, Query(max_length=120)] = None,
    verified_only: Annotated[bool, Query()] = False,
    posted_within_days: Annotated[int | None, Query(ge=1, le=365)] = None,
    startup_id: Annotated[uuid.UUID | None, Query()] = None,
    sort: Annotated[str, Query()] = "relevance",
) -> JobListResponse:
    clauses = _build_filters(
        q=q,
        company=company,
        skills=skills,
        experience=experience,
        employment_type=employment_type,
        work_arrangement=work_arrangement,
        city=city,
        industry=industry,
        min_salary=min_salary,
        max_salary=max_salary,
        remote_only=remote,
        internship_only=internship,
        scopes=scope or DEFAULT_SCOPES,
        source_slug=source,
        verified_only=verified_only,
        posted_within_days=posted_within_days,
        startup_id=startup_id,
    )

    total = (
        await db.execute(select(func.count()).select_from(JobListing).where(and_(*clauses)))
    ).scalar_one()

    stmt = (
        select(JobListing)
        .where(and_(*clauses))
        .options(selectinload(JobListing.startup), selectinload(JobListing.source))
        .order_by(*_order_by(sort, q))
        .limit(pagination.per_page)
        .offset(pagination.offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    skills_map = await _skill_map(db, [row.id for row in rows])

    items = [
        _job_to_summary(row, skills_map.get(row.id, [])[:12], [c for c in [row.category] if c])
        for row in rows
    ]

    facets = await _build_facets(db, and_(*clauses))

    return JobListResponse(
        items=items,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
        pages=max(1, (total + pagination.per_page - 1) // pagination.per_page),
        facets=facets,
    )


def _order_by(sort: str, q: str | None) -> list[Any]:
    posted = func.coalesce(JobListing.posted_at, JobListing.discovered_at)
    if sort == "newest":
        return [posted.desc()]
    if sort == "oldest":
        return [posted.asc()]
    if sort == "salary_high":
        return [func.coalesce(JobListing.salary_max, JobListing.salary_min).desc().nullslast()]
    if sort == "salary_low":
        return [func.coalesce(JobListing.salary_min, JobListing.salary_max).asc().nullslast()]
    if sort == "company":
        return [JobListing.company_name.asc()]
    # relevance: quality + recency, with a light boost for title matches
    if q:
        term = q.strip().split()[0].lower()
        boost = case((func.lower(JobListing.title).like(f"%{term}%"), 1.0), else_=0.0)
        return [(boost + JobListing.quality_score).desc(), posted.desc()]
    return [JobListing.quality_score.desc(), posted.desc()]


async def _build_facets(db: AsyncSession, where_clause: Any) -> dict[str, Any]:
    """Aggregate filter options for the current result set."""
    industry_stmt = (
        select(Startup.industry, func.count(JobListing.id))
        .select_from(JobListing)
        .join(Startup, Startup.id == JobListing.startup_id)
        .where(where_clause)
        .group_by(Startup.industry)
        .limit(25)
    )
    industries = {row[0]: row[1] for row in (await db.execute(industry_stmt)).all()}

    skill_stmt = (
        select(Skill.name, Skill.category, func.count(JobSkill.job_id))
        .select_from(JobSkill)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .join(JobListing, JobListing.id == JobSkill.job_id)
        .where(where_clause)
        .group_by(Skill.name, Skill.category)
        .order_by(func.count(JobSkill.job_id).desc())
        .limit(40)
    )
    skills = [
        {"name": name, "category": category, "count": count}
        for name, category, count in (await db.execute(skill_stmt)).all()
    ]

    city_stmt = (
        select(JobListing.location_city, func.count(JobListing.id))
        .where(where_clause)
        .group_by(JobListing.location_city)
        .order_by(func.count(JobListing.id).desc())
        .limit(25)
    )
    cities = {row[0]: row[1] for row in (await db.execute(city_stmt)).all() if row[0]}

    scope_stmt = (
        select(JobListing.geo_scope, func.count(JobListing.id))
        .where(where_clause)
        .group_by(JobListing.geo_scope)
    )
    scopes = {
        row[0]: row[1] for row in (await db.execute(scope_stmt)).all()
    }

    async def group_counts(column: Any, limit: int = 20) -> dict[str, int]:
        stmt = (
            select(column, func.count(JobListing.id))
            .where(where_clause)
            .group_by(column)
            .order_by(func.count(JobListing.id).desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        return {row[0]: row[1] for row in rows if row[0]}

    return {
        "industries": industries,
        "skills": skills,
        "cities": cities,
        "geo_scopes": {GEO_SCOPE_LABELS.get(k, k): v for k, v in scopes.items()},
        "employment_types": await group_counts(JobListing.employment_type),
        "experience_levels": await group_counts(JobListing.experience_level),
        "work_arrangements": await group_counts(JobListing.work_arrangement),
    }


@router.get("/filters", summary="Available filter options")
async def list_filters(db: DbSession) -> dict[str, Any]:
    from app.models.enums import EmploymentType, ExperienceLevel, WorkArrangement
    from app.services.taxonomy import JOB_CATEGORIES, SKILL_CATALOG

    skill_stmt = (
        select(Skill.name, func.count(JobSkill.job_id))
        .select_from(JobSkill)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .group_by(Skill.name)
        .order_by(func.count(JobSkill.job_id).desc())
        .limit(120)
    )
    top_skills = [{"name": name, "count": count} for name, count in (await db.execute(skill_stmt)).all()]

    city_stmt = (
        select(JobListing.location_city, func.count(JobListing.id))
        .where(JobListing.location_city.isnot(None))
        .group_by(JobListing.location_city)
        .order_by(func.count(JobListing.id).desc())
        .limit(40)
    )
    cities = [{"city": row[0], "count": row[1]} for row in (await db.execute(city_stmt)).all()]

    industry_stmt = (
        select(Startup.industry, func.count(Startup.id)).group_by(Startup.industry)
    )
    industries = {row[0]: row[1] for row in (await db.execute(industry_stmt)).all()}

    return {
        "employment_types": [e.value for e in EmploymentType],
        "experience_levels": [e.value for e in ExperienceLevel],
        "work_arrangements": [w.value for w in WorkArrangement],
        "job_categories": JOB_CATEGORIES,
        "skills": top_skills,
        "all_skills": sorted(SKILL_CATALOG.keys()),
        "cities": cities,
        "industries": industries,
        "geo_scopes": GEO_SCOPE_LABELS,
        "sort_options": list(SORT_OPTIONS),
    }


@router.get("/slug/{slug}", response_model=JobDetail, summary="Job detail by slug")
async def get_job_by_slug(db: DbSession, slug: str) -> JobDetail:
    stmt = select(JobListing.id).where(JobListing.slug == slug)
    job_id = (await db.execute(stmt)).scalar_one_or_none()
    if job_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return await get_job(db, job_id)


@router.get("/{job_id}", response_model=JobDetail, summary="Job detail")
async def get_job(
    db: DbSession,
    job_id: uuid.UUID,
    user: OptionalUser = None,
) -> JobDetail:
    stmt = (
        select(JobListing)
        .where(JobListing.id == job_id)
        .options(
            selectinload(JobListing.startup),
            selectinload(JobListing.source),
            selectinload(JobListing.skill_links),
            selectinload(JobListing.category_links),
            selectinload(JobListing.references),
        )
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    skills = [link.skill.name for link in job.skill_links]
    categories = [link.category for link in job.category_links]

    if user is not None:
        db.add(UserJobView(user_id=user.id, job_id=job.id))
        JobListing.views_count = JobListing.views_count + 1
        await db.commit()

    summary = _job_to_summary(job, skills, categories)
    from app.schemas import JobReferenceRead, StartupRead

    return JobDetail(
        **summary.model_dump(),
        description=job.description,
        responsibilities=job.responsibilities or [],
        qualifications=job.qualifications or [],
        skills_text=job.skills_text,
        department=job.department,
        deadline=job.deadline,
        content_hash=job.content_hash,
        references=[JobReferenceRead.model_validate(ref) for ref in job.references],
        startup=StartupRead.model_validate(job.startup) if job.startup else None,
    )
