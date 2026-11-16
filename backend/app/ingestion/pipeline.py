"""Ingestion pipeline: raw source payloads -> normalised, deduplicated rows."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.base import Connector, RawJob
from app.models import (
    IngestionError,
    IngestionRun,
    JobCategory,
    JobListing,
    JobSkill,
    JobSource,
    JobSourceReference,
    Skill,
    Startup,
    VerificationStatus,
)
from app.models.enums import JobStatus, RunStatus
from app.services import dedup as dedup_service
from app.services.normalizer import (
    canonical_employment_type,
    content_hash,
    detect_industry,
    normalize_job_fields,
    taxonomy,
)

log = get_logger(__name__)

# Scopes considered "in platform scope" for the Ahmedabad product.
DEFAULT_SCOPES = {"ahmedabad", "gujarat", "india_remote", "india"}


class IngestionStats:
    def __init__(self) -> None:
        self.found = 0
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.duplicates = 0
        self.errors = 0
        self.out_of_scope = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "jobs_found": self.found,
            "jobs_created": self.created,
            "jobs_updated": self.updated,
            "jobs_skipped": self.skipped,
            "duplicates_found": self.duplicates,
            "errors_count": self.errors,
            "out_of_scope": self.out_of_scope,
        }


class JobIngestionPipeline:
    """Owns persistence semantics for discovered jobs."""

    def __init__(self, session: AsyncSession, stats: IngestionStats | None = None) -> None:
        self.session = session
        self.stats = stats or IngestionStats()

    # -- public API --------------------------------------------------------

    async def ingest_raw_jobs(
        self,
        raw_jobs: Iterable[RawJob],
        *,
        source: JobSource | None = None,
        startup_id: uuid.UUID | None = None,
        persist_out_of_scope: bool = True,
    ) -> IngestionStats:
        for raw in raw_jobs:
            self.stats.found += 1
            try:
                # A SAVEPOINT keeps one malformed row from poisoning the whole run
                # (and from expiring the ORM objects we are still using).
                async with self.session.begin_nested():
                    await self.ingest_one(
                        raw,
                        source=source,
                        startup_id=startup_id,
                        persist_out_of_scope=persist_out_of_scope,
                    )
            except Exception as exc:  # a single bad row must not kill the run
                self.stats.errors += 1
                log.warning(
                    "job_ingest_failed",
                    error=str(exc)[:300],
                    error_type=type(exc).__name__,
                    title=str(raw.title or "")[:120],
                    source=raw.source_key,
                )
        return self.stats

    async def ingest_one(
        self,
        raw: RawJob,
        *,
        source: JobSource | None = None,
        startup_id: uuid.UUID | None = None,
        persist_out_of_scope: bool = True,
    ) -> str:
        job = normalize_job_fields(
            title=raw.title,
            company_name=raw.company_name,
            description=raw.description,
            location_raw=raw.location_raw,
            department=raw.department,
        )

        # Source-provided values win over heuristics where the source is authoritative.
        if raw.employment_type:
            job.employment_type = (
                canonical_employment_type(raw.employment_type) or job.employment_type
            )
        if raw.work_arrangement:
            job.work_arrangement = raw.work_arrangement
        if raw.salary_min is not None:
            job.salary_min = raw.salary_min
        if raw.salary_max is not None:
            job.salary_max = raw.salary_max
        if raw.salary_currency:
            job.salary_currency = raw.salary_currency
        if raw.salary_period:
            job.salary_period = raw.salary_period
        if raw.experience_level and not job.experience_level:
            job.experience_level = raw.experience_level

        location = job.location
        if location and location.scope not in DEFAULT_SCOPES and not persist_out_of_scope:
            self.stats.out_of_scope += 1
            return "out_of_scope"

        resolved_startup_id = startup_id or await self._resolve_startup(raw, source)

        existing = await self._find_by_external(raw)
        if existing is not None:
            await self._update_existing(existing, raw, job)
            self.stats.updated += 1
            return "updated"

        duplicate = await self._find_duplicate(raw, job)
        if duplicate is not None:
            await self._record_reference(duplicate, raw, source)
            duplicate.duplicate_of_id = None
            self.stats.duplicates += 1
            return "duplicate"

        created = await self._create_job(raw, job, source, resolved_startup_id)
        self.stats.created += 1
        return "created"

    # -- internals ---------------------------------------------------------

    async def _resolve_startup(self, raw: RawJob, source: JobSource | None) -> uuid.UUID | None:
        if source is not None and source.company_id is not None:
            return source.company_id
        key = dedup_service.company_key(raw.company_name)
        if not key:
            return None
        stmt = select(Startup).where(Startup.name.ilike(f"%{raw.company_name[:40]}%")).limit(1)
        for startup in (await self.session.execute(stmt)).scalars().all():
            if dedup_service.company_key(startup.name) == key:
                return startup.id
        return None

    async def _find_by_external(self, raw: RawJob) -> JobListing | None:
        stmt = select(JobListing).where(
            JobListing.source_key == raw.source_key,
            JobListing.external_id == raw.external_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _find_duplicate(self, raw: RawJob, job: Any) -> JobListing | None:
        """Look for an existing posting from a *different* source that is the same role."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=120)
        dedup_key = dedup_service.fingerprint(raw.company_name, raw.title, raw.location_raw)

        seen: set[uuid.UUID] = set()
        candidates: list[JobListing] = []

        # Pass 1 — same company + same normalised title (+ location).
        stmt = (
            select(JobListing)
            .where(JobListing.dedup_key == dedup_key)
            .where(JobListing.created_at >= cutoff)
            .limit(50)
        )
        candidates.extend((await self.session.execute(stmt)).scalars().all())

        # Pass 2 — same company, possibly re-titled: compare descriptions.
        if not candidates:
            company_token = dedup_service.company_key(raw.company_name)[:12]
            if len(company_token) >= 4:
                stmt = (
                    select(JobListing)
                    .where(JobListing.company_name.ilike(f"%{company_token[:10]}%"))
                    .where(JobListing.created_at >= cutoff)
                    .where(JobListing.status == JobStatus.ACTIVE)
                    .limit(200)
                )
                candidates.extend((await self.session.execute(stmt)).scalars().all())

        for candidate in candidates:
            if candidate.id in seen:
                continue
            if candidate.source_key == raw.source_key and candidate.external_id == raw.external_id:
                continue
            seen.add(candidate.id)
            verdict = dedup_service.compare(
                company=raw.company_name,
                title=raw.title,
                location_raw=raw.location_raw,
                apply_url=raw.apply_url,
                description=raw.description,
                candidate={
                    "company": candidate.company_name,
                    "title": candidate.title,
                    "location_raw": candidate.location_raw,
                    "apply_url": candidate.apply_url,
                    "description": candidate.description,
                },
            )
            if verdict.is_duplicate:
                log.info(
                    "duplicate_detected",
                    title=raw.title,
                    company=raw.company_name,
                    reason=verdict.reason,
                    confidence=verdict.confidence,
                )
                return candidate
        return None

    async def _create_job(
        self,
        raw: RawJob,
        job: Any,
        source: JobSource | None,
        startup_id: uuid.UUID | None,
    ) -> JobListing:
        now = datetime.now(timezone.utc)
        slug = await self._unique_slug(raw.title, raw.company_name)
        location = job.location
        record = JobListing(
            source_id=source.id if source else None,
            startup_id=startup_id,
            external_id=raw.external_id,
            source_key=raw.source_key,
            title=job.title[:300],
            normalized_title=job.normalized_title[:300],
            slug=slug,
            company_name=job.company_name[:200],
            description=job.description,
            responsibilities=job.responsibilities,
            qualifications=job.qualifications,
            skills_text=(", ".join(name for name, _ in job.skills[:25]) or None),
            category=job.categories[0][0][:80] if job.categories else None,
            department=job.department[:255] if job.department else None,
            experience_level=job.experience_level,
            experience_min_years=job.experience_min_years,
            experience_max_years=job.experience_max_years,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
            salary_period=job.salary_period,
            salary_disclosed=job.salary_min is not None,
            employment_type=job.employment_type,
            work_arrangement=job.work_arrangement,
            is_remote=job.is_remote,
            location_raw=(location.raw if location else raw.location_raw or "")[:300] or None,
            location_city=(location.city if location else None),
            location_state=(location.state if location else None),
            location_country=(location.country if location else None),
            geo_scope=location.scope if location else "other",
            posted_at=raw.posted_at,
            deadline=raw.deadline.date() if raw.deadline else None,
            last_verified_at=now,
            discovered_at=now,
            apply_url=raw.apply_url[:1000],
            original_url=(raw.original_url or raw.apply_url)[:1000],
            source_name=raw.source_name[:160],
            verification_status=VerificationStatus.VERIFIED,
            status=JobStatus.ACTIVE,
            quality_score=job.quality_score,
            content_hash=content_hash(job.description, job.title, raw.apply_url),
            dedup_key=dedup_service.fingerprint(raw.company_name, raw.title, raw.location_raw),
            classification_source="rule",
        )
        self.session.add(record)
        await self.session.flush()
        await self._sync_skills(record, job.skills)
        await self._sync_categories(record, job.categories)
        await self._record_reference(record, raw, source, primary=True)
        return record

    async def _update_existing(self, record: JobListing, raw: RawJob, job: Any) -> None:
        now = datetime.now(timezone.utc)
        new_hash = content_hash(job.description, job.title, raw.apply_url)
        changed = record.content_hash != new_hash
        record.description = job.description or record.description
        record.responsibilities = job.responsibilities or record.responsibilities
        record.qualifications = job.qualifications or record.qualifications
        record.skills_text = ", ".join(name for name, _ in job.skills[:25]) or record.skills_text
        record.category = (job.categories[0][0][:80] if job.categories else None) or record.category
        record.experience_level = job.experience_level or record.experience_level
        record.experience_min_years = job.experience_min_years or record.experience_min_years
        record.experience_max_years = job.experience_max_years or record.experience_max_years
        record.salary_min = job.salary_min if job.salary_min is not None else record.salary_min
        record.salary_max = job.salary_max if job.salary_max is not None else record.salary_max
        record.salary_disclosed = record.salary_min is not None
        record.employment_type = job.employment_type or record.employment_type
        record.work_arrangement = job.work_arrangement or record.work_arrangement
        record.is_remote = job.is_remote
        if job.location:
            record.location_raw = (job.location.raw or record.location_raw or "")[:300] or None
            record.location_city = job.location.city or record.location_city
            record.location_state = job.location.state or record.location_state
            record.location_country = job.location.country or record.location_country
            record.geo_scope = job.location.scope
        record.apply_url = raw.apply_url[:1000]
        record.original_url = (raw.original_url or raw.apply_url)[:1000]
        record.posted_at = raw.posted_at or record.posted_at
        record.deadline = raw.deadline.date() if raw.deadline else record.deadline
        record.last_verified_at = now
        record.status = JobStatus.ACTIVE
        record.verification_status = VerificationStatus.VERIFIED
        record.quality_score = job.quality_score
        if changed:
            record.content_hash = new_hash
            record.updated_at = now
        await self.session.flush()
        await self._sync_skills(record, job.skills)
        await self._sync_categories(record, job.categories)
        await self._record_reference(record, raw, None, primary=True)

    async def _record_reference(
        self,
        record: JobListing,
        raw: RawJob,
        source: JobSource | None,
        primary: bool = False,
    ) -> None:
        source_id = source.id if source else None
        stmt = select(JobSourceReference).where(
            JobSourceReference.job_id == record.id,
            JobSourceReference.external_id == raw.external_id,
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        now = datetime.now(timezone.utc)
        if existing:
            existing.last_seen_at = now
            existing.source_url = raw.original_url or raw.apply_url
            return
        self.session.add(
            JobSourceReference(
                job_id=record.id,
                source_id=source_id,
                external_id=raw.external_id,
                source_url=(raw.original_url or raw.apply_url)[:1000],
                raw_payload=_trim_payload(raw.raw),
                first_seen_at=now,
                last_seen_at=now,
                is_primary=primary,
            )
        )
        await self.session.flush()

    async def _sync_skills(self, record: JobListing, skills: list[tuple[str, float]]) -> None:
        if not skills:
            return
        names = [name for name, _ in skills]
        slugs = [taxonomy.slugify(name) for name in names]
        existing = (
            (
                await self.session.execute(
                    select(Skill).where(or_(Skill.name.in_(names), Skill.slug.in_(slugs)))
                )
            )
            .scalars()
            .all()
        )
        by_name = {s.name: s for s in existing}
        taken_slugs = {s.slug: s.name for s in existing}

        for name, _confidence in skills:
            if name in by_name:
                continue
            category, is_ai = taxonomy.SKILL_CATALOG.get(name, ("Other", False))
            slug = taxonomy.slugify(name)
            if slug in taken_slugs and taken_slugs[slug] != name:
                slug = f"{slug}-{len(taken_slugs)}"
            skill = Skill(
                name=name,
                slug=slug,
                category=category,
                is_ai_skill=is_ai,
                usage_count=0,
            )
            self.session.add(skill)
            await self.session.flush()
            by_name[name] = skill
            taken_slugs[slug] = name

        stmt = select(JobSkill).where(JobSkill.job_id == record.id)
        existing_links = {link.skill_id: link for link in (await self.session.execute(stmt)).scalars().all()}
        for name, confidence in skills:
            skill = by_name[name]
            link = existing_links.get(skill.id)
            if link is None:
                self.session.add(
                    JobSkill(
                        job_id=record.id,
                        skill_id=skill.id,
                        confidence=confidence,
                        source="rule",
                    )
                )
            else:
                link.confidence = max(link.confidence, confidence)
            skill.usage_count += 1
        await self.session.flush()

    async def _sync_categories(self, record: JobListing, categories: list[tuple[str, float]]) -> None:
        if not categories:
            return
        stmt = select(JobCategory).where(JobCategory.job_id == record.id)
        existing = {link.category: link for link in (await self.session.execute(stmt)).scalars().all()}
        for category, confidence in categories:
            link = existing.get(category)
            if link is None:
                self.session.add(
                    JobCategory(
                        job_id=record.id,
                        category=category,
                        confidence=confidence,
                        source="rule",
                    )
                )
        await self.session.flush()

    async def _unique_slug(self, title: str, company: str) -> str:
        base = f"{taxonomy.slugify(title)[:90]}-{taxonomy.slugify(company)[:60]}"
        slug = base
        counter = 2
        while True:
            stmt = select(JobListing.id).where(JobListing.slug == slug)
            if (await self.session.execute(stmt)).scalar_one_or_none() is None:
                return slug
            slug = f"{base}-{counter}"
            counter += 1
            if counter > 50:
                return f"{base}-{uuid.uuid4().hex[:6]}"


def _trim_payload(payload: dict) -> dict:
    """Keep the raw payload small enough for reasonable storage."""
    if not isinstance(payload, dict):
        return {}
    trimmed: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > 20000:
            trimmed[key] = value[:20000]
        elif isinstance(value, (dict, list)):
            trimmed[key] = str(value)[:4000]
        else:
            trimmed[key] = value
    return trimmed


# --- Run bookkeeping --------------------------------------------------------


async def start_run(
    session: AsyncSession, connector: str, source: JobSource | None, trigger: str
) -> IngestionRun:
    run = IngestionRun(
        connector=connector,
        source_id=source.id if source else None,
        status=RunStatus.RUNNING,
        trigger=trigger,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def finish_run(
    session: AsyncSession,
    run: IngestionRun,
    stats: IngestionStats,
    status: str,
    message: str | None = None,
    error: Exception | None = None,
) -> None:
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000) if run.started_at else None
    run.jobs_found = stats.found
    run.jobs_created = stats.created
    run.jobs_updated = stats.updated
    run.jobs_skipped = stats.skipped
    run.duplicates_found = stats.duplicates
    run.errors_count = stats.errors
    run.message = message[:2000] if message else None
    if error is not None:
        session.add(
            IngestionError(
                run_id=run.id,
                source_id=run.source_id,
                level="error",
                error_type=type(error).__name__,
                message=str(error)[:4000],
                url=None,
            )
        )
    await session.commit()


async def mark_missing_jobs_stale(
    session: AsyncSession,
    source: JobSource,
    seen_external_ids: set[str],
    grace_days: int | None = None,
) -> int:
    """Mark jobs from this source that were not seen in the latest run as stale/expired."""
    grace = grace_days if grace_days is not None else settings.job_stale_after_days
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=grace)
    stmt = select(JobListing).where(
        JobListing.source_id == source.id,
        JobListing.last_verified_at < threshold,
    )
    stale_count = 0
    for job in (await session.execute(stmt)).scalars().all():
        if job.external_id in seen_external_ids:
            continue
        job.verification_status = VerificationStatus.STALE
        if job.last_verified_at and (now - job.last_verified_at).days > settings.job_expire_after_days:
            job.status = JobStatus.EXPIRED
        stale_count += 1
    await session.commit()
    return stale_count


async def record_source_health(
    session: AsyncSession,
    source: JobSource,
    *,
    success: bool,
    duration_ms: int = 0,
    error: str | None = None,
    jobs_found: int = 0,
) -> None:
    from app.models import SourceHealth
    from app.models.enums import SourceStatus

    health = (
        await session.execute(select(SourceHealth).where(SourceHealth.source_id == source.id))
    ).scalar_one_or_none()
    if health is None:
        health = SourceHealth(
            source_id=source.id,
            status=SourceStatus.UNKNOWN,
            consecutive_failures=0,
            total_runs=0,
            total_failures=0,
            success_rate=0.0,
            avg_duration_ms=0.0,
            jobs_last_24h=0,
            jobs_last_run=0,
        )
        session.add(health)
        await session.flush()

    health.total_runs += 1
    if success:
        health.consecutive_failures = 0
        health.last_success_at = datetime.now(timezone.utc)
        health.last_error = None
        health.jobs_last_run = jobs_found
        source.last_success_at = health.last_success_at
        source.consecutive_failures = 0
    else:
        health.consecutive_failures += 1
        health.total_failures += 1
        health.last_failure_at = datetime.now(timezone.utc)
        health.last_error = (error or "")[:2000]
        source.consecutive_failures += 1
    health.avg_duration_ms = (health.avg_duration_ms * (health.total_runs - 1) + duration_ms) / max(
        health.total_runs, 1
    )
    health.success_rate = round((health.total_runs - health.total_failures) / max(health.total_runs, 1), 4)
    if health.consecutive_failures >= 5:
        health.status = SourceStatus.UNHEALTHY
    elif health.consecutive_failures > 0:
        health.status = SourceStatus.DEGRADED
    else:
        health.status = SourceStatus.HEALTHY
    source.last_run_at = datetime.now(timezone.utc)
    source.total_jobs_discovered += jobs_found
    await session.commit()
