"""Ingestion pipeline tests: discovery, updates, expiry, dedup and verification."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.ingestion.base import RawJob
from app.ingestion.pipeline import (
    IngestionStats,
    JobIngestionPipeline,
    mark_missing_jobs_stale,
    record_source_health,
)
from app.models import JobListing, JobSource, JobSourceReference
from app.models.enums import VerificationStatus


def _raw(
    *,
    title: str = "Backend Engineer",
    company: str = "Example Startup",
    location: str | None = "Ahmedabad, Gujarat",
    apply_url: str = "https://example.com/jobs/1",
    source_key: str = "greenhouse:example",
    external_id: str | None = None,
    description: str = "Build production APIs with Python, FastAPI and PostgreSQL on Docker.",
) -> RawJob:
    return RawJob(
        external_id=external_id or f"{source_key}:{uuid.uuid4().hex[:8]}",
        source_key=source_key,
        source_name="Example Board",
        title=title,
        company_name=company,
        apply_url=apply_url,
        original_url=apply_url,
        description=description,
        location_raw=location,
        posted_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_new_job_is_discovered_and_persisted(db):
    pipeline = JobIngestionPipeline(db, IngestionStats())
    raw = _raw()

    result = await pipeline.ingest_one(raw)
    await db.commit()

    assert result == "created"
    job = (await db.execute(select(JobListing))).scalar_one()
    assert job.title == "Backend Engineer"
    assert job.company_name == "Example Startup"
    assert job.geo_scope == "ahmedabad"
    assert job.verification_status == VerificationStatus.VERIFIED
    assert job.last_verified_at is not None
    assert job.discovered_at is not None
    assert job.apply_url == raw.apply_url

    reference = (await db.execute(select(JobSourceReference))).scalar_one()
    assert reference.external_id == raw.external_id


@pytest.mark.asyncio
async def test_same_source_and_external_id_updates_instead_of_duplicating(db):
    pipeline = JobIngestionPipeline(db, IngestionStats())
    raw = _raw(external_id="greenhouse:example:1")

    await pipeline.ingest_one(raw)
    await db.commit()
    first = (await db.execute(select(JobListing))).scalar_one()

    raw.description = "Updated description with Kubernetes and Docker and PostgreSQL."
    await pipeline.ingest_one(raw)
    await db.commit()

    jobs = (await db.execute(select(JobListing))).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].id == first.id
    assert "Kubernetes" in jobs[0].description


@pytest.mark.asyncio
async def test_same_job_on_two_sources_is_deduplicated(db):
    pipeline = JobIngestionPipeline(db, IngestionStats())
    description = (
        "We are hiring a backend engineer to build APIs with Python and FastAPI on PostgreSQL "
        "and deploy with Docker. You will work closely with the founders in Ahmedabad."
    )
    await pipeline.ingest_one(
        _raw(
            source_key="greenhouse:example",
            external_id="gh-1",
            apply_url="https://boards.greenhouse.io/example/jobs/1",
            description=description,
        )
    )
    await db.commit()

    stats = IngestionStats()
    pipeline = JobIngestionPipeline(db, stats)
    result = await pipeline.ingest_one(
        _raw(
            source_key="lever:example",
            external_id="lv-1",
            apply_url="https://jobs.lever.co/example/1",
            description=description,
        )
    )
    await db.commit()

    assert result == "duplicate"
    jobs = (await db.execute(select(JobListing))).scalars().all()
    assert len(jobs) == 1
    references = (await db.execute(select(JobSourceReference))).scalars().all()
    assert len(references) == 2  # both source references are retained
    assert stats.duplicates == 1


@pytest.mark.asyncio
async def test_different_companies_with_same_title_are_not_merged(db):
    pipeline = JobIngestionPipeline(db, IngestionStats())
    await pipeline.ingest_one(_raw(company="Alpha Startup", apply_url="https://alpha.com/1"))
    await db.commit()

    pipeline = JobIngestionPipeline(db, IngestionStats())
    await pipeline.ingest_one(_raw(company="Beta Startup", apply_url="https://beta.com/1"))
    await db.commit()

    count = (await db.execute(select(func.count(JobListing.id)))).scalar_one()
    assert count == 2


@pytest.mark.asyncio
async def test_missing_jobs_are_marked_stale(db):
    source = JobSource(
        name="Board", slug=f"board-{uuid.uuid4().hex[:6]}", connector_type="greenhouse", config={}
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    pipeline = JobIngestionPipeline(db, IngestionStats())
    raw = _raw()
    await pipeline.ingest_one(raw, source=source)
    await db.commit()

    job = (await db.execute(select(JobListing))).scalar_one()
    job.last_verified_at = datetime.now(UTC) - timedelta(days=30)
    await db.commit()

    stale = await mark_missing_jobs_stale(db, source, set(), grace_days=14)
    await db.commit()

    assert stale == 1
    await db.refresh(job)
    assert job.verification_status == VerificationStatus.STALE


@pytest.mark.asyncio
async def test_jobs_seen_in_the_current_run_are_not_marked_stale(db):
    source = JobSource(
        name="Board", slug=f"board-{uuid.uuid4().hex[:6]}", connector_type="greenhouse", config={}
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    pipeline = JobIngestionPipeline(db, IngestionStats())
    raw = _raw()
    await pipeline.ingest_one(raw, source=source)
    await db.commit()

    job = (await db.execute(select(JobListing))).scalar_one()
    job.last_verified_at = datetime.now(UTC) - timedelta(days=30)
    await db.commit()

    stale = await mark_missing_jobs_stale(db, source, {raw.external_id}, grace_days=14)
    await db.commit()

    assert stale == 0
    await db.refresh(job)
    assert job.verification_status == VerificationStatus.VERIFIED


@pytest.mark.asyncio
async def test_bad_row_does_not_abort_the_run(db):
    pipeline = JobIngestionPipeline(db, IngestionStats())
    good = _raw(apply_url="https://example.com/ok")
    # A title that violates the column length is impossible to create, so we
    # simulate a failure with an object that cannot be persisted.
    broken = _raw(apply_url="https://example.com/broken")
    broken.title = None  # type: ignore[assignment]

    await pipeline.ingest_raw_jobs([broken, good])
    await db.commit()

    jobs = (await db.execute(select(JobListing))).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].apply_url == "https://example.com/ok"


@pytest.mark.asyncio
async def test_source_health_tracking(db):
    source = JobSource(
        name="Board", slug=f"board-{uuid.uuid4().hex[:6]}", connector_type="greenhouse", config={}
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    await record_source_health(db, source, success=True, duration_ms=120, jobs_found=5)
    await record_source_health(db, source, success=False, duration_ms=200, error="boom")
    await db.commit()

    from app.models import SourceHealth

    health = (
        await db.execute(select(SourceHealth).where(SourceHealth.source_id == source.id))
    ).scalar_one()
    assert health.total_runs == 2
    assert health.total_failures == 1
    assert health.consecutive_failures == 1
    assert health.status == "degraded"
    assert health.jobs_last_run == 5


@pytest.mark.asyncio
async def test_out_of_scope_jobs_can_be_skipped(db):
    pipeline = JobIngestionPipeline(db, IngestionStats())
    raw = _raw(location="New York, United States", apply_url="https://example.com/ny")
    result = await pipeline.ingest_one(raw, persist_out_of_scope=False)
    await db.commit()

    assert result == "out_of_scope"
    count = (await db.execute(select(func.count(JobListing.id)))).scalar_one()
    assert count == 0
