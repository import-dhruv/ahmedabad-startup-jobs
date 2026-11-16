"""Administration API: sources, ingestion monitoring, verification, companies."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, DbSession
from app.core.logging import get_logger
from app.models import (
    CompanyVerification,
    IngestionError,
    IngestionRun,
    JobListing,
    JobSource,
    Skill,
    Startup,
    StartupFounder,
    StartupFunding,
)
from app.models.enums import JobStatus, RunStatus, VerificationStatus
from app.schemas import (
    AdminOverview,
    ErrorRead,
    HealthRead,
    ImportResult,
    JobAdminUpdate,
    MergeCompaniesRequest,
    RunRead,
    SourceCreate,
    SourceReadAdmin,
    StartupCreate,
    StartupUpdate,
)
from app.services.taxonomy import slugify

log = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[])


@router.get("/overview", response_model=AdminOverview)
async def overview(db: DbSession, _: AdminUser) -> AdminOverview:
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    total_sources = (await db.execute(select(func.count(JobSource.id)))).scalar_one()
    active_sources = (
        await db.execute(select(func.count(JobSource.id)).where(JobSource.is_active.is_(True)))
    ).scalar_one()

    jobs_today = (
        await db.execute(
            select(func.count(JobListing.id)).where(JobListing.discovered_at >= day_ago)
        )
    ).scalar_one()

    successful_runs = (
        await db.execute(
            select(func.count(IngestionRun.id)).where(
                IngestionRun.finished_at >= day_ago, IngestionRun.status == RunStatus.SUCCESS
            )
        )
    ).scalar_one()
    failed_runs = (
        await db.execute(
            select(func.count(IngestionRun.id)).where(
                IngestionRun.finished_at >= day_ago,
                IngestionRun.status.in_([RunStatus.FAILED, RunStatus.PARTIAL]),
            )
        )
    ).scalar_one()
    duplicates = (
        await db.execute(
            select(func.count(IngestionRun.id)).where(
                IngestionRun.finished_at >= day_ago, IngestionRun.duplicates_found > 0
            )
        )
    ).scalar_one()

    awaiting = (
        await db.execute(
            select(func.count(JobListing.id)).where(
                JobListing.verification_status.in_([VerificationStatus.UNVERIFIED, VerificationStatus.STALE])
            )
        )
    ).scalar_one()

    total_startups = (
        await db.execute(select(func.count(Startup.id)).where(Startup.deleted_at.is_(None)))
    ).scalar_one()
    total_jobs = (await db.execute(select(func.count(JobListing.id)))).scalar_one()
    active_jobs = (
        await db.execute(select(func.count(JobListing.id)).where(JobListing.status == JobStatus.ACTIVE))
    ).scalar_one()
    expired_jobs = (
        await db.execute(
            select(func.count(JobListing.id)).where(JobListing.status.in_([JobStatus.EXPIRED, JobStatus.REMOVED]))
        )
    ).scalar_one()
    rejected_jobs = (
        await db.execute(
            select(func.count(JobListing.id)).where(JobListing.verification_status == VerificationStatus.REJECTED)
        )
    ).scalar_one()

    db_size_mb: float | None = None
    try:
        size_bytes = (await db.execute(select(func.pg_database_size(current_database())))).scalar_one()
        db_size_mb = round(size_bytes / (1024 * 1024), 2)
    except Exception:
        db_size_mb = None

    return AdminOverview(
        total_sources=total_sources,
        active_connectors=active_sources,
        jobs_discovered_today=jobs_today,
        successful_runs_24h=successful_runs,
        failed_runs_24h=failed_runs,
        duplicates_detected_24h=duplicates,
        jobs_awaiting_verification=awaiting,
        total_startups=total_startups,
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        expired_jobs=expired_jobs,
        rejected_jobs=rejected_jobs,
        database_size_mb=db_size_mb,
    )


# --- Sources ----------------------------------------------------------------


@router.get("/sources", response_model=list[SourceReadAdmin])
async def list_sources(db: DbSession, _: AdminUser) -> list[SourceReadAdmin]:
    stmt = select(JobSource).order_by(JobSource.priority, JobSource.name)
    return [SourceReadAdmin.model_validate(s) for s in (await db.execute(stmt)).scalars().all()]


@router.post("/sources", response_model=SourceReadAdmin, status_code=status.HTTP_201_CREATED)
async def create_source(payload: SourceCreate, db: DbSession, _: AdminUser) -> SourceReadAdmin:
    from app.ingestion.registry import CONNECTOR_REGISTRY

    if payload.connector_type not in CONNECTOR_REGISTRY:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown connector type. Available: {sorted(CONNECTOR_REGISTRY)}",
        )
    exists = (await db.execute(select(JobSource).where(JobSource.slug == payload.slug))).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A source with this slug already exists")

    config = dict(payload.config)
    config.setdefault("connector_type", payload.connector_type)
    source = JobSource(
        name=payload.name,
        slug=payload.slug,
        connector_type=payload.connector_type,
        base_url=payload.base_url,
        config=config,
        is_active=payload.is_active,
        priority=payload.priority,
        interval_minutes=payload.interval_minutes,
        notes=payload.notes,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return SourceReadAdmin.model_validate(source)


@router.patch("/sources/{source_id}", response_model=SourceReadAdmin)
async def update_source(
    source_id: uuid.UUID, payload: SourceCreate, db: DbSession, _: AdminUser
) -> SourceReadAdmin:
    source = await db.get(JobSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    for field in (
        "name", "base_url", "is_active", "priority", "interval_minutes", "notes",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(source, field, value)
    if payload.config:
        merged = dict(source.config or {})
        merged.update(payload.config)
        source.config = merged
    await db.commit()
    await db.refresh(source)
    return SourceReadAdmin.model_validate(source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: uuid.UUID, db: DbSession, _: AdminUser) -> None:
    source = await db.get(JobSource, source_id)
    if source is not None:
        await db.delete(source)
        await db.commit()


@router.post("/sources/{source_id}/run", response_model=RunRead)
async def run_source_now(source_id: uuid.UUID, db: DbSession, _: AdminUser) -> RunRead:
    """Trigger an immediate ingestion run for a single source."""
    source = await db.get(JobSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")

    from app.workers.tasks import run_single_source

    task = run_single_source.apply_async(args=[str(source.id)], queue="ingestion")
    return RunRead(
        id=uuid.UUID(int=0),
        source_id=source.id,
        connector=source.connector_type,
        status=RunStatus.PENDING,
        trigger="manual",
        jobs_found=0,
        jobs_created=0,
        jobs_updated=0,
        jobs_expired=0,
        jobs_skipped=0,
        duplicates_found=0,
        errors_count=0,
        message=f"Queued as task {task.id}",
    )


# --- Ingestion monitoring ----------------------------------------------------


@router.get("/runs", response_model=list[RunRead])
async def list_runs(
    db: DbSession,
    _: AdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[RunRead]:
    stmt = select(IngestionRun).order_by(IngestionRun.created_at.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(IngestionRun.status == status_filter)
    return [RunRead.model_validate(r) for r in (await db.execute(stmt)).scalars().all()]


@router.get("/errors", response_model=list[ErrorRead])
async def list_errors(
    db: DbSession, _: AdminUser, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[ErrorRead]:
    stmt = select(IngestionError).order_by(IngestionError.created_at.desc()).limit(limit)
    return [ErrorRead.model_validate(e) for e in (await db.execute(stmt)).scalars().all()]


@router.get("/health", response_model=list[HealthRead])
async def source_health(db: DbSession, _: AdminUser) -> list[HealthRead]:
    from app.models import SourceHealth

    stmt = select(SourceHealth).order_by(SourceHealth.success_rate)
    return [HealthRead.model_validate(h) for h in (await db.execute(stmt)).scalars().all()]


@router.get("/connectors")
async def list_connectors(_: AdminUser) -> dict[str, Any]:
    from app.ingestion.registry import CONNECTOR_REGISTRY

    return {
        "connectors": [
            {"type": key, "class": cls.__name__, "doc": (cls.__doc__ or "").strip()}
            for key, cls in CONNECTOR_REGISTRY.items()
        ]
    }


# --- Job review / verification ------------------------------------------------


@router.get("/jobs")
async def admin_jobs(
    db: DbSession,
    _: AdminUser,
    pagination_limit: Annotated[int, Query(alias="limit", ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    verification_status: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    stmt = select(JobListing)
    if verification_status:
        stmt = stmt.where(JobListing.verification_status == verification_status)
    if q:
        stmt = stmt.where(func.lower(JobListing.title).like(f"%{q.lower()}%"))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(JobListing.created_at.desc()).limit(pagination_limit).offset(offset)
    jobs = (await db.execute(stmt)).scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": str(job.id),
                "title": job.title,
                "company": job.company_name,
                "location": job.location_raw,
                "geo_scope": job.geo_scope,
                "employment_type": job.employment_type,
                "status": job.status,
                "verification_status": job.verification_status,
                "quality_score": job.quality_score,
                "apply_url": job.apply_url,
                "source": job.source_name,
                "discovered_at": job.discovered_at,
                "last_verified_at": job.last_verified_at,
            }
            for job in jobs
        ],
    }


@router.patch("/jobs/{job_id}")
async def update_job(
    job_id: uuid.UUID, payload: JobAdminUpdate, db: DbSession, _: AdminUser
) -> dict[str, Any]:
    job = await db.get(JobListing, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is not None:
            setattr(job, field, value)
    if payload.verification_status == VerificationStatus.REJECTED and not job.rejection_reason:
        job.rejection_reason = "Rejected by administrator"
    await db.commit()
    await db.refresh(job)
    return {"id": str(job.id), "status": job.status, "verification_status": job.verification_status}


@router.post("/jobs/{job_id}/verify")
async def verify_job(job_id: uuid.UUID, db: DbSession, _: AdminUser) -> dict[str, Any]:
    """Verify that a job's application URL still resolves."""
    job = await db.get(JobListing, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    from app.ingestion.http_client import PoliteClient

    async with PoliteClient(rate_limit_per_host=10) as client:
        try:
            resp = await client.head(job.apply_url, allow_robots_check=False)
            status_code = resp.status_code
            alive = status_code < 400
        except Exception as exc:
            status_code = None
            alive = False
            log.info("verify_failed", job_id=str(job_id), error=str(exc))

    now = datetime.now(timezone.utc)
    job.last_verified_at = now
    if alive:
        job.verification_status = VerificationStatus.VERIFIED
        job.status = JobStatus.ACTIVE
    else:
        job.verification_status = VerificationStatus.STALE
    await db.commit()
    return {
        "id": str(job.id),
        "alive": alive,
        "http_status": status_code,
        "verification_status": job.verification_status,
        "last_verified_at": now,
    }


# --- Company management -------------------------------------------------------


@router.post("/startups", status_code=status.HTTP_201_CREATED)
async def create_startup(payload: StartupCreate, db: DbSession, _: AdminUser) -> dict[str, Any]:
    slug = slugify(payload.name)
    exists = (await db.execute(select(Startup).where(Startup.slug == slug))).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A startup with this name already exists")
    startup = Startup(**payload.model_dump(), slug=slug, discovery_source=payload.discovery_source or "manual")
    db.add(startup)
    await db.commit()
    await db.refresh(startup)
    return {"id": str(startup.id), "slug": startup.slug, "name": startup.name}


@router.patch("/startups/{startup_id}")
async def update_startup(
    startup_id: uuid.UUID, payload: StartupUpdate, db: DbSession, _: AdminUser
) -> dict[str, Any]:
    startup = await db.get(Startup, startup_id)
    if startup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Startup not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(startup, field, value)
    await db.commit()
    await db.refresh(startup)
    return {"id": str(startup.id), "name": startup.name, "slug": startup.slug}


@router.post("/startups/merge")
async def merge_startups(payload: MergeCompaniesRequest, db: DbSession, _: AdminUser) -> dict[str, Any]:
    """Merge one startup record into another, moving jobs and metadata."""
    target = await db.get(Startup, payload.target_id)
    source = await db.get(Startup, payload.source_id)
    if target is None or source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Startup not found")
    if target.id == source.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot merge a startup into itself")

    moved = await db.execute(
        update(JobListing).where(JobListing.startup_id == source.id).values(startup_id=target.id)
    )
    await db.execute(
        update(StartupFounder).where(StartupFounder.startup_id == source.id).values(startup_id=target.id)
    )
    await db.execute(
        update(StartupFunding).where(StartupFunding.startup_id == source.id).values(startup_id=target.id)
    )
    await db.delete(source)
    await db.commit()
    return {"merged_into": str(target.id), "jobs_moved": moved.rowcount}


@router.post("/startups/import", response_model=ImportResult)
async def import_startups(payload: ImportRequest, db: DbSession, _: AdminUser) -> ImportResult:
    """Bulk import companies from CSV (name, website, industry, city, state, size...)."""
    result = ImportResult(created=0, updated=0, skipped=0, rows_processed=0)
    reader = csv.DictReader(io.StringIO(payload.csv_content))
    for row in reader:
        result.rows_processed += 1
        name = (row.get("name") or "").strip()
        if not name:
            result.skipped += 1
            result.errors.append("Row without a name was skipped")
            continue
        slug = slugify(name)
        existing = (
            await db.execute(select(Startup).where(Startup.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            if not payload.dry_run:
                existing.website = row.get("website") or existing.website
                existing.industry = row.get("industry") or existing.industry
                existing.hq_city = row.get("hq_city") or existing.hq_city
                existing.hq_state = row.get("hq_state") or existing.hq_state
                existing.size_range = row.get("size_range") or existing.size_range
                existing.careers_url = row.get("careers_url") or existing.careers_url
            result.updated += 1
            continue

        if not payload.dry_run:
            startup = Startup(
                name=name,
                slug=slug,
                website=row.get("website") or None,
                logo_url=row.get("logo_url") or None,
                linkedin_url=row.get("linkedin_url") or None,
                description=row.get("description") or None,
                industry=row.get("industry") or "Other technology startups",
                hq_city=row.get("hq_city") or None,
                hq_state=row.get("hq_state") or None,
                hq_country=row.get("hq_country") or "India",
                founded_year=int(row["founded_year"]) if (row.get("founded_year") or "").isdigit() else None,
                size_range=row.get("size_range") or None,
                careers_url=row.get("careers_url") or None,
                discovery_source="csv_import",
            )
            db.add(startup)
        result.created += 1

    if not payload.dry_run:
        await db.commit()
    return result


@router.post("/startups/{startup_id}/verify")
async def verify_startup(startup_id: uuid.UUID, db: DbSession, _: AdminUser) -> dict[str, Any]:
    """Re-check a company's website reachability and refresh its evidence."""
    startup = await db.get(Startup, startup_id)
    if startup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Startup not found")
    if not startup.website:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Startup has no website recorded")

    from app.ingestion.http_client import PoliteClient

    evidence: dict[str, Any] = {}
    alive = False
    async with PoliteClient(rate_limit_per_host=5) as client:
        try:
            resp = await client.head(startup.website, allow_robots_check=False)
            evidence["http_status"] = resp.status_code
            alive = resp.status_code < 400
        except Exception as exc:
            evidence["error"] = str(exc)
    evidence["checked_at"] = datetime.now(timezone.utc).isoformat()

    verification = (
        await db.execute(select(CompanyVerification).where(CompanyVerification.startup_id == startup.id))
    ).scalar_one_or_none()
    if verification is None:
        verification = CompanyVerification(startup_id=startup.id)
        db.add(verification)
    verification.status = VerificationStatus.VERIFIED if alive else VerificationStatus.STALE
    verification.evidence = evidence
    verification.verified_at = datetime.now(timezone.utc)

    startup.verification_status = verification.status
    startup.last_verified_at = verification.verified_at
    await db.commit()
    return {"id": str(startup.id), "alive": alive, "status": verification.status, "evidence": evidence}
