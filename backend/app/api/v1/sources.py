"""Public source registry endpoint (transparency about where data comes from)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.models import JobListing, JobSource
from app.schemas import SourceRead

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceRead], summary="List data sources")
async def list_sources(
    db: DbSession,
    active_only: Annotated[bool, Query()] = True,
) -> list[SourceRead]:
    stmt = select(JobSource).order_by(JobSource.name)
    if active_only:
        stmt = stmt.where(JobSource.is_active.is_(True))
    sources = (await db.execute(stmt)).scalars().all()

    out = []
    for source in sources:
        data = SourceRead.model_validate(source)
        out.append(data)
    return out


@router.get("/stats", summary="Source contribution statistics")
async def source_stats(db: DbSession) -> list[dict[str, Any]]:
    stmt = (
        select(
            JobSource.id,
            JobSource.name,
            JobSource.slug,
            JobSource.connector_type,
            JobSource.last_success_at,
            func.count(JobListing.id),
        )
        .select_from(JobSource)
        .outerjoin(JobListing, JobListing.source_id == JobSource.id)
        .group_by(JobSource.id)
        .order_by(func.count(JobListing.id).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(row[0]),
            "name": row[1],
            "slug": row[2],
            "connector_type": row[3],
            "last_success_at": row[4],
            "active_jobs": row[5],
        }
        for row in rows
    ]
