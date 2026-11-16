"""Background tasks: ingestion, discovery, verification, enrichment, alerts."""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task
from sqlalchemy import func, select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.ingestion.base import ConnectorContext
from app.ingestion.http_client import PoliteClient
from app.ingestion.pipeline import (
    IngestionStats,
    JobIngestionPipeline,
    finish_run,
    mark_missing_jobs_stale,
    record_source_health,
    start_run,
)
from app.ingestion.registry import build_connector
from app.models import (
    JobListing,
    JobSource,
    Startup,
)
from app.models.enums import JobStatus, RunStatus, VerificationStatus
from app.realtime.events import broker

log = get_logger(__name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a synchronous Celery task."""
    return asyncio.run(coro)


async def _ingest_source(source_id: str, trigger: str = "schedule") -> dict[str, Any]:
    async with SessionLocal() as session:
        source = await session.get(JobSource, uuid.UUID(source_id))
        if source is None or not source.is_active:
            log.info("source_skipped", source_id=source_id, reason="missing or inactive")
            return {"skipped": True}

        run = await start_run(session, source.connector_type, source, trigger)
        stats = IngestionStats()
        async with PoliteClient(rate_limit_per_host=source.rate_limit_per_minute) as client:
            config = dict(source.config or {})
            config["client"] = client
            config.setdefault("connector_type", source.connector_type)
            if source.connector_type == "workday" and "company_name" not in config:
                config["company_name"] = source.name
            if source.connector_type == "career_page" and source.base_url:
                config.setdefault("url", source.base_url)
            ctx = ConnectorContext(
                source_slug=source.slug,
                source_name=source.name,
                config=config,
                startup_id=str(source.company_id) if source.company_id else None,
            )
            try:
                connector = build_connector(ctx)
                raw_jobs = await connector.fetch()
                stats.found = len(raw_jobs)
                pipeline = JobIngestionPipeline(session, stats)
                await pipeline.ingest_raw_jobs(
                    raw_jobs,
                    source=source,
                    startup_id=source.company_id,
                )
                seen = {job.external_id for job in raw_jobs}
                await mark_missing_jobs_stale(session, source, seen)
                await finish_run(session, run, stats, RunStatus.SUCCESS, message=f"{stats.found} jobs fetched")
                await record_source_health(
                    session, source, success=True, duration_ms=run.duration_ms or 0, jobs_found=stats.found
                )
            except Exception as exc:
                log.warning("source_run_failed", source=source.slug, error=str(exc))
                await finish_run(session, run, stats, RunStatus.FAILED, message=str(exc), error=exc)
                await record_source_health(
                    session, source, success=False, duration_ms=run.duration_ms or 0, error=str(exc)
                )
                await session.rollback()

    if stats.created:
        await broker.publish(
            "jobs.discovered",
            {
                "source": source.name,
                "created": stats.created,
                "updated": stats.updated,
                "found": stats.found,
            },
        )
    return stats.as_dict()


@shared_task(name="app.workers.tasks.run_single_source")
def run_single_source(source_id: str) -> dict[str, Any]:
    return _run_async(_ingest_source(source_id, trigger="manual"))


@shared_task(name="app.workers.tasks.run_due_sources")
def run_due_sources() -> dict[str, Any]:
    """Run every active source whose interval has elapsed."""

    async def _run() -> dict[str, Any]:
        async with SessionLocal() as session:
            now = datetime.now(UTC)
            sources = (await session.execute(select(JobSource).where(JobSource.is_active.is_(True)))).scalars().all()
            due = [
                s
                for s in sources
                if s.last_run_at is None
                or (now - s.last_run_at) >= timedelta(minutes=s.interval_minutes)
            ]
        results = []
        for source in due:
            try:
                results.append(await _ingest_source(str(source.id)))
            except Exception as exc:
                log.warning("source_run_error", source=source.slug, error=str(exc))
        return {"ran": len(results), "results": results}

    return _run_async(_run())


@shared_task(name="app.workers.tasks.discover_companies")
def discover_companies() -> dict[str, Any]:
    """Discover new companies and register their job boards as sources."""

    async def _run() -> dict[str, Any]:
        from app.ingestion.discovery import (
            discover_from_yc,
            probe_domains_for_boards,
            workday_config,
        )

        async with SessionLocal() as session:
            async with PoliteClient(rate_limit_per_host=20) as client:
                companies = await discover_from_yc(
                    client, queries=["india", "gujarat", "ahmedabad", "gandhinagar"], max_pages=3
                )
                known_slugs = {
                    row[0] for row in (await session.execute(select(Startup.slug))).all()
                }
                created = 0
                probed_domains: list[str] = []
                for company in companies:
                    if not company.website:
                        continue
                    from app.services.taxonomy import slugify

                    slug = slugify(company.name)
                    if slug in known_slugs:
                        continue
                    domain = company.domain
                    if not domain:
                        continue
                    probed_domains.append(domain)
                    exists = (
                        await session.execute(select(Startup).where(Startup.name == company.name))
                    ).scalar_one_or_none()
                    if exists is None:
                        startup = Startup(
                            name=company.name,
                            slug=slug,
                            website=company.website,
                            logo_url=company.logo_url,
                            description=company.description,
                            industry=company.industry or "Other technology startups",
                            hq_city=company.hq_city,
                            hq_state=company.hq_state,
                            hq_country=company.hq_country or "India",
                            size_range=company.size_range,
                            discovery_source=company.discovery_source,
                            verification_status=VerificationStatus.UNVERIFIED,
                        )
                        session.add(startup)
                        await session.flush()
                        created += 1
                await session.commit()

                boards = await probe_domains_for_boards(client, probed_domains[:120])
                sources_created = 0
                for domain, hits in boards.items():
                    for hit in hits:
                        if hit["kind"] == "workday":
                            config = workday_config(hit["slug"])
                            source_slug = f"workday-{hit['slug'].split('|')[0]}"
                        else:
                            config = {"connector_type": hit["kind"]}
                            if hit["kind"] == "greenhouse":
                                config["board_token"] = hit["slug"]
                            else:
                                config["company"] = hit["slug"]
                        exists = (
                            await session.execute(select(JobSource).where(JobSource.slug == source_slug))
                        ).scalar_one_or_none()
                        if exists is not None:
                            continue
                        startup = (
                            await session.execute(
                                select(Startup).where(Startup.website.like(f"%{domain}%"))
                            )
                        ).scalars().first()
                        source = JobSource(
                            name=f"{hit['kind'].title()} · {hit['slug'].split('|')[0]}",
                            slug=source_slug,
                            connector_type=hit["kind"],
                            base_url=hit["probe_url"],
                            company_id=startup.id if startup else None,
                            config=config,
                            is_active=True,
                            priority=70,
                            interval_minutes=60,
                            notes=f"Auto-discovered from {domain}",
                        )
                        session.add(source)
                        sources_created += 1
                await session.commit()
            await broker.publish(
                "companies.discovered",
                {"companies": created, "sources": sources_created},
            )
            return {"companies_created": created, "sources_created": sources_created}

    return _run_async(_run())


@shared_task(name="app.workers.tasks.verify_job_links")
def verify_job_links() -> dict[str, Any]:
    """Re-check application URLs for jobs that have not been verified recently."""

    async def _run() -> dict[str, Any]:
        from app.ingestion.http_client import PoliteClient

        cutoff = datetime.now(UTC) - timedelta(days=2)
        async with SessionLocal() as session:
            stmt = (
                select(JobListing)
                .where(JobListing.status == JobStatus.ACTIVE)
                .where(
                    (JobListing.last_verified_at.is_(None)) | (JobListing.last_verified_at < cutoff)
                )
                .order_by(JobListing.last_verified_at.asc().nullsfirst())
                .limit(400)
            )
            jobs = (await session.execute(stmt)).scalars().all()
            broken = 0
            checked = 0
            async with PoliteClient(rate_limit_per_host=6) as client:
                for job in jobs:
                    try:
                        resp = await client.head(job.apply_url, allow_robots_check=False)
                        alive = resp.status_code < 400
                    except Exception:
                        alive = False
                    checked += 1
                    job.last_verified_at = datetime.now(UTC)
                    if alive:
                        job.verification_status = VerificationStatus.VERIFIED
                    else:
                        job.verification_status = VerificationStatus.STALE
                        broken += 1
                await session.commit()
            return {"checked": checked, "broken": broken}

    return _run_async(_run())


@shared_task(name="app.workers.tasks.reconcile_job_status")
def reconcile_job_status() -> dict[str, Any]:
    """Mark listings that have not been seen recently as stale or expired."""

    async def _run() -> dict[str, Any]:
        now = datetime.now(UTC)
        stale_cut = now - timedelta(days=settings.job_stale_after_days)
        expire_cut = now - timedelta(days=settings.job_expire_after_days)
        async with SessionLocal() as session:
            stale = (
                await session.execute(
                    select(func.count(JobListing.id)).where(
                        JobListing.status == JobStatus.ACTIVE,
                        JobListing.last_verified_at < stale_cut,
                    )
                )
            ).scalar_one()
            expired = 0
            for job in (
                await session.execute(
                    select(JobListing).where(
                        JobListing.status == JobStatus.ACTIVE,
                        JobListing.last_verified_at < expire_cut,
                    )
                )
            ).scalars().all():
                job.status = JobStatus.EXPIRED
                job.verification_status = VerificationStatus.EXPIRED
                expired += 1
            await session.commit()
            return {"marked_stale": stale, "expired": expired}

    return _run_async(_run())


@shared_task(name="app.workers.tasks.enrich_jobs_with_ai")
def enrich_jobs_with_ai() -> dict[str, Any]:
    """Generate summaries and refine classification for recently added jobs."""

    async def _run() -> dict[str, Any]:
        from app.services.ai import get_effective_provider

        provider = get_effective_provider()
        cutoff = datetime.now(UTC) - timedelta(days=3)
        async with SessionLocal() as session:
            stmt = (
                select(JobListing)
                .where(JobListing.ai_summary.is_(None))
                .where(JobListing.created_at >= cutoff)
                .limit(150)
            )
            jobs = (await session.execute(stmt)).scalars().all()
            processed = 0
            for job in jobs:
                summary = await provider.summarize_job(job.description or "")
                if summary:
                    job.ai_summary = summary
                    job.classification_source = provider.name
                    processed += 1
            await session.commit()
            return {"processed": processed, "provider": provider.name}

    return _run_async(_run())


@shared_task(name="app.workers.tasks.dispatch_job_alerts")
def dispatch_job_alerts() -> dict[str, Any]:
    """Match newly discovered jobs against user alerts and create notifications."""
    from app.workers.notifications import dispatch_alerts

    return _run_async(dispatch_alerts())


@shared_task(name="app.workers.tasks.refresh_source_health")
def refresh_source_health() -> dict[str, Any]:
    """Recompute per-source health snapshots."""

    async def _run() -> dict[str, Any]:
        from app.models import SourceHealth

        async with SessionLocal() as session:
            sources = (await session.execute(select(JobSource))).scalars().all()
            for source in sources:
                health = (
                    await session.execute(select(SourceHealth).where(SourceHealth.source_id == source.id))
                ).scalar_one_or_none()
                if health is None:
                    continue
                recent_cut = datetime.now(UTC) - timedelta(hours=24)
                count = (
                    await session.execute(
                        select(func.count(JobListing.id)).where(
                            JobListing.source_id == source.id,
                            JobListing.discovered_at >= recent_cut,
                        )
                    )
                ).scalar_one()
                health.jobs_last_24h = count
            await session.commit()
            return {"sources": len(sources)}

    return _run_async(_run())
