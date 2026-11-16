"""Public dashboard statistics and hiring intelligence."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.api.v1.jobs import _job_to_summary
from app.models import JobListing, Startup
from app.models.enums import JobStatus
from app.schemas import DashboardStats, HiringInsight
from app.services import analytics
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/stats", tags=["stats"])

ACTIVE_SCOPES = ("ahmedabad", "gujarat", "india_remote", "india", "global")


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(db: DbSession) -> DashboardStats:
    return DashboardStats(**await analytics.dashboard_stats(db))


@router.get("/trends")
async def trends(db: DbSession, days: Annotated[int, Query(ge=7, le=180)] = 30) -> dict[str, Any]:
    series = await analytics.daily_postings(db, days=days)
    return {"days": days, "series": series}


@router.get("/skills")
async def skills(db: DbSession, limit: Annotated[int, Query(ge=5, le=60)] = 25) -> dict[str, Any]:
    return {"skills": await analytics.skill_demand(db, limit=limit)}


@router.get("/industries")
async def industries(db: DbSession) -> dict[str, Any]:
    return {"industries": await analytics.industry_hiring(db)}


@router.get("/hiring")
async def hiring(db: DbSession) -> dict[str, Any]:
    return {"companies": await analytics.top_hiring_companies(db)}


@router.get("/mix")
async def mix(db: DbSession) -> dict[str, Any]:
    return {
        "employment_types": await analytics.employment_mix(db),
        "experience_levels": await analytics.experience_mix(db),
        "locations": await analytics.location_breakdown(db),
        "sources": await analytics.source_breakdown(db),
    }


@router.get("/insights", response_model=list[HiringInsight])
async def insights(db: DbSession) -> list[HiringInsight]:
    """Hiring intelligence.

    Every insight is *measured* from the database; interpretation is kept
    separate (see `ai_insights`) and explicitly labelled.
    """
    out: list[HiringInsight] = []

    top_companies = await analytics.top_hiring_companies(db, limit=5)
    for company in top_companies:
        out.append(
            HiringInsight(
                key=f"company:{company['startup_id']}",
                label=f"{company['name']} is hiring",
                value=company["openings"],
                detail=f"{company['openings']} active openings"
                + (f" · {company['industry']}" if company.get("industry") else ""),
            )
        )

    skill_rows = await analytics.skill_demand(db, limit=8)
    for row in skill_rows[:5]:
        trend_text = (
            "rising" if row["trend"] > 15 else "falling" if row["trend"] < -15 else "steady"
        )
        out.append(
            HiringInsight(
                key=f"skill:{row['skill']}",
                label=f"{row['skill']} demand is {trend_text}",
                value=row["count"],
                detail=f"{row['count']} openings mention it · {row['trend']:+}% vs previous period",
            )
        )

    industry_rows = await analytics.industry_hiring(db, limit=5)
    for row in industry_rows[:4]:
        out.append(
            HiringInsight(
                key=f"industry:{row['industry']}",
                label=f"{row['industry']} is hiring actively",
                value=row["count"],
                detail=f"{row['count']} openings across {row['companies']} companies",
            )
        )

    internship_count = (
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
    out.append(
        HiringInsight(
            key="internships",
            label="Internship openings are available",
            value=internship_count,
            detail="Freshers and students can apply",
        )
    )
    return out


@router.get("/ai-insights")
async def ai_insights(db: DbSession) -> dict[str, Any]:
    """AI-assisted commentary.

    `interpretations` are generated, not measured — they are clearly separated
    from the measured statistics returned by the other endpoints. When no AI
    provider is configured the section returns an explicit empty state.
    """
    from app.services.ai import get_ai_provider

    provider = get_ai_provider()
    if provider is None:
        return {
            "available": False,
            "reason": "No AI provider configured. Set OPENAI_API_KEY to enable generated commentary.",
            "interpretations": [],
        }

    skill_rows = await analytics.skill_demand(db, limit=10)
    industry_rows = await analytics.industry_hiring(db, limit=6)
    payload = {
        "top_skills": [row["skill"] for row in skill_rows],
        "top_industries": [row["industry"] for row in industry_rows],
        "jobs_posted_30d": sum(row["count"] for row in skill_rows),
    }
    interpretations = await provider.interpret_hiring(payload)
    return {"available": True, "interpretations": interpretations}


@router.get("/recent-jobs")
async def recent_jobs(db: DbSession, limit: Annotated[int, Query(ge=1, le=50)] = 12) -> dict[str, Any]:
    stmt = (
        select(JobListing)
        .where(JobListing.status == JobStatus.ACTIVE)
        .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
        .options(selectinload(JobListing.startup), selectinload(JobListing.source))
        .order_by(func.coalesce(JobListing.discovered_at, JobListing.created_at).desc())
        .limit(limit)
    )
    jobs = (await db.execute(stmt)).scalars().all()
    return {"items": [_job_to_summary(job, [], [job.category] if job.category else []) for job in jobs]}


@router.get("/recent-startups")
async def recent_startups(db: DbSession, limit: Annotated[int, Query(ge=1, le=50)] = 12) -> dict[str, Any]:
    stmt = (
        select(Startup)
        .where(Startup.deleted_at.is_(None))
        .order_by(Startup.created_at.desc())
        .limit(limit)
    )
    startups = (await db.execute(stmt)).scalars().all()
    out = []
    for startup in startups:
        count = (
            await db.execute(
                select(func.count(JobListing.id))
                .where(JobListing.startup_id == startup.id)
                .where(JobListing.status == JobStatus.ACTIVE)
            )
        ).scalar_one()
        out.append(
            {
                "id": str(startup.id),
                "name": startup.name,
                "slug": startup.slug,
                "logo_url": startup.logo_url,
                "website": startup.website,
                "industry": startup.industry,
                "hq_city": startup.hq_city,
                "active_job_count": count,
                "created_at": startup.created_at,
            }
        )
    return {"items": out}
