"""Dashboard statistics and hiring-intelligence analytics.

Everything here is *measured* from the database. AI-derived commentary lives in
a separate module and is clearly labelled as interpretation.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Date, Float, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    IngestionRun,
    JobListing,
    JobSkill,
    JobSource,
    Skill,
    Startup,
)
from app.models.enums import JobStatus, RunStatus, VerificationStatus

ACTIVE_SCOPES = ("ahmedabad", "gujarat", "india_remote", "india", "global")


async def dashboard_stats(db: AsyncSession) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_startups = (
        await db.execute(
            select(func.count(Startup.id)).where(Startup.deleted_at.is_(None))
        )
    ).scalar_one()

    active_jobs = (
        await db.execute(
            select(func.count(JobListing.id))
            .where(JobListing.status == JobStatus.ACTIVE)
            .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
        )
    ).scalar_one()

    async def count_since(moment: datetime) -> int:
        return (
            await db.execute(
                select(func.count(JobListing.id))
                .where(JobListing.status == JobStatus.ACTIVE)
                .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
                .where(func.coalesce(JobListing.discovered_at, JobListing.created_at) >= moment)
            )
        ).scalar_one()

    new_jobs_24h = await count_since(day_ago)
    new_jobs_7d = await count_since(week_ago)
    new_jobs_30d = await count_since(month_ago)

    companies_hiring = (
        await db.execute(
            select(func.count(func.distinct(JobListing.startup_id)))
            .where(JobListing.status == JobStatus.ACTIVE)
            .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
            .where(JobListing.startup_id.isnot(None))
        )
    ).scalar_one()

    internships = (
        await db.execute(
            select(func.count(JobListing.id))
            .where(JobListing.status == JobStatus.ACTIVE)
            .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
            .where(
                or_(
                    JobListing.employment_type == "Internship",
                    func.lower(JobListing.title).like("%intern%"),
                )
            )
        )
    ).scalar_one()

    remote_jobs = (
        await db.execute(
            select(func.count(JobListing.id))
            .where(JobListing.status == JobStatus.ACTIVE)
            .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
            .where(JobListing.is_remote.is_(True))
        )
    ).scalar_one()

    ahmedabad_jobs = (
        await db.execute(
            select(func.count(JobListing.id))
            .where(JobListing.status == JobStatus.ACTIVE)
            .where(JobListing.geo_scope == "ahmedabad")
        )
    ).scalar_one()

    gujarat_jobs = (
        await db.execute(
            select(func.count(JobListing.id))
            .where(JobListing.status == JobStatus.ACTIVE)
            .where(JobListing.geo_scope == "gujarat")
        )
    ).scalar_one()

    total_sources = (await db.execute(select(func.count(JobSource.id)))).scalar_one()
    active_sources = (
        await db.execute(select(func.count(JobSource.id)).where(JobSource.is_active.is_(True)))
    ).scalar_one()

    awaiting_verification = (
        await db.execute(
            select(func.count(JobListing.id)).where(
                JobListing.verification_status.in_(
                    [VerificationStatus.UNVERIFIED, VerificationStatus.STALE]
                )
            )
        )
    ).scalar_one()

    expired_jobs = (
        await db.execute(
            select(func.count(JobListing.id)).where(JobListing.status.in_([JobStatus.EXPIRED, JobStatus.REMOVED]))
        )
    ).scalar_one()

    last_sync = (
        await db.execute(select(func.max(IngestionRun.finished_at)).where(IngestionRun.status == RunStatus.SUCCESS))
    ).scalar_one()
    last_company = (await db.execute(select(func.max(Startup.created_at)))).scalar_one()

    return {
        "total_startups": total_startups,
        "total_active_jobs": active_jobs,
        "new_jobs_24h": new_jobs_24h,
        "new_jobs_7d": new_jobs_7d,
        "new_jobs_30d": new_jobs_30d,
        "companies_hiring": companies_hiring,
        "internship_openings": internships,
        "remote_opportunities": remote_jobs,
        "ahmedabad_jobs": ahmedabad_jobs,
        "gujarat_jobs": gujarat_jobs,
        "total_sources": total_sources,
        "active_sources": active_sources,
        "jobs_awaiting_verification": awaiting_verification,
        "expired_jobs": expired_jobs,
        "last_sync_at": last_sync,
        "last_discovered_company_at": last_company,
        "generated_at": now,
    }


async def _await(db: AsyncSession, stmt: Any) -> Any:
    return (await db.execute(stmt)).scalar_one()


async def daily_postings(db: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(
            cast(func.coalesce(JobListing.posted_at, JobListing.discovered_at), Date).label("day"),
            func.count(JobListing.id),
        )
        .where(func.coalesce(JobListing.posted_at, JobListing.discovered_at) >= since)
        .where(JobListing.status == JobStatus.ACTIVE)
        .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
        .group_by("day")
        .order_by("day")
    )
    rows = (await db.execute(stmt)).all()
    return [{"date": row[0], "count": row[1]} for row in rows]


async def skill_demand(db: AsyncSession, days: int = 60, limit: int = 25) -> list[dict[str, Any]]:
    """Most demanded skills with a measured week-over-week trend."""
    now = datetime.now(timezone.utc)
    recent_cut = now - timedelta(days=days)
    prev_cut = now - timedelta(days=days * 2)

    def count_for(cutoff: datetime, until: datetime) -> Any:
        return (
            select(JobSkill.job_id)
            .join(JobListing, JobListing.id == JobSkill.job_id)
            .where(func.coalesce(JobListing.posted_at, JobListing.discovered_at) >= cutoff)
            .where(func.coalesce(JobListing.posted_at, JobListing.discovered_at) < until)
            .where(JobListing.status == JobStatus.ACTIVE)
            .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
        )

    recent_stmt = (
        select(Skill.name, Skill.category, func.count(JobSkill.job_id))
        .select_from(JobSkill)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(JobSkill.job_id.in_(count_for(recent_cut, now)))
        .group_by(Skill.name, Skill.category)
        .order_by(func.count(JobSkill.job_id).desc())
        .limit(limit)
    )
    prev_stmt = (
        select(Skill.name, func.count(JobSkill.job_id))
        .select_from(JobSkill)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(JobSkill.job_id.in_(count_for(prev_cut, recent_cut)))
        .group_by(Skill.name)
    )
    recent = (await db.execute(recent_stmt)).all()
    previous = {row[0]: row[1] for row in (await db.execute(prev_stmt)).all()}

    out = []
    for name, category, count in recent:
        prev = previous.get(name, 0)
        trend = round(((count - prev) / prev) * 100, 1) if prev else (100.0 if count else 0.0)
        out.append({"skill": name, "category": category, "count": count, "trend": trend})
    return out


async def industry_hiring(db: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
    stmt = (
        select(
            Startup.industry,
            func.count(JobListing.id),
            func.count(func.distinct(Startup.id)),
        )
        .select_from(JobListing)
        .join(Startup, Startup.id == JobListing.startup_id)
        .where(JobListing.status == JobStatus.ACTIVE)
        .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
        .group_by(Startup.industry)
        .order_by(func.count(JobListing.id).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [{"industry": row[0], "count": row[1], "companies": row[2]} for row in rows]


async def top_hiring_companies(db: AsyncSession, limit: int = 12) -> list[dict[str, Any]]:
    stmt = (
        select(
            JobListing.startup_id,
            JobListing.company_name,
            func.count(JobListing.id),
        )
        .where(JobListing.status == JobStatus.ACTIVE)
        .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
        .where(JobListing.startup_id.isnot(None))
        .group_by(JobListing.startup_id, JobListing.company_name)
        .order_by(func.count(JobListing.id).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    ids = [row[0] for row in rows if row[0]]
    startups = {}
    if ids:
        for startup in (await db.execute(select(Startup).where(Startup.id.in_(ids)))).scalars().all():
            startups[startup.id] = startup
    return [
        {
            "startup_id": row[0],
            "name": row[1],
            "openings": row[2],
            "logo_url": startups[row[0]].logo_url if row[0] in startups else None,
            "slug": startups[row[0]].slug if row[0] in startups else None,
            "industry": startups[row[0]].industry if row[0] in startups else None,
        }
        for row in rows
    ]


async def employment_mix(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(JobListing.employment_type, func.count(JobListing.id))
        .where(JobListing.status == JobStatus.ACTIVE)
        .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
        .group_by(JobListing.employment_type)
    )
    rows = (await db.execute(stmt)).all()
    return [{"label": row[0] or "Unspecified", "value": row[1]} for row in rows]


async def experience_mix(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(JobListing.experience_level, func.count(JobListing.id))
        .where(JobListing.status == JobStatus.ACTIVE)
        .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
        .group_by(JobListing.experience_level)
    )
    rows = (await db.execute(stmt)).all()
    order = ["Fresher", "0-1 years", "1-3 years", "3-5 years", "5-8 years", "8+ years"]
    mapping = {row[0] or "Unspecified": row[1] for row in rows}
    return [{"label": label, "value": mapping.get(label, 0)} for label in order]


async def source_breakdown(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(JobListing.source_name, func.count(JobListing.id))
        .where(JobListing.status == JobStatus.ACTIVE)
        .group_by(JobListing.source_name)
        .order_by(func.count(JobListing.id).desc())
        .limit(20)
    )
    rows = (await db.execute(stmt)).all()
    return [{"label": row[0], "value": row[1]} for row in rows]


async def location_breakdown(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(JobListing.geo_scope, func.count(JobListing.id))
        .where(JobListing.status == JobStatus.ACTIVE)
        .group_by(JobListing.geo_scope)
    )
    rows = (await db.execute(stmt)).all()
    from app.services.geo import GEO_SCOPE_LABELS

    return [{"label": GEO_SCOPE_LABELS.get(row[0], row[0]), "value": row[1], "scope": row[0]} for row in rows]
