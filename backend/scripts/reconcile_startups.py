"""Reconcile company records with the jobs we have ingested.

Creates a startup record for every company that appears in ingested jobs, links
the jobs to it, and attaches a website when the employer's domain can be
derived from the listing URLs. Everything is derived from real source data.
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from urllib.parse import urlparse

from sqlalchemy import func, select, update

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import get_logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import JobListing, JobSource, Startup  # noqa: E402
from app.services.dedup import company_key  # noqa: E402
from app.services.normalizer import detect_industry  # noqa: E402
from app.services.taxonomy import slugify  # noqa: E402

log = get_logger(__name__)


def _domain_for(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if not host or host.startswith("www."):
        host = host[4:] if host.startswith("www.") else host
    if not host or "." not in host:
        return None
    if host.endswith("ycombinator.com") or host.endswith("remoteok.com"):
        return None
    return host


async def main() -> None:
    async with SessionLocal() as session:
        jobs = (await session.execute(select(JobListing))).scalars().all()
        log.info("jobs_loaded", count=len(jobs))

        # company key -> (display name, most common domain, job ids, skills text)
        buckets: dict[str, dict] = {}
        for job in jobs:
            key = company_key(job.company_name) or slugify(job.company_name)
            if not key:
                continue
            bucket = buckets.setdefault(
                key,
                {"name": job.company_name, "domains": Counter(), "jobs": [], "scopes": Counter(), "text": []},
            )
            domain = _domain_for(job.apply_url) or _domain_for(job.original_url)
            if domain:
                bucket["domains"][domain] += 1
            bucket["jobs"].append(job.id)
            bucket["scopes"][job.geo_scope] += 1
            if job.title:
                bucket["text"].append(job.title)
            if job.skills_text:
                bucket["text"].append(job.skills_text)

        created = 0
        linked = 0
        for bucket in buckets.values():
            slug = slugify(bucket["name"])
            if not slug:
                continue
            startup = (
                await session.execute(select(Startup).where(Startup.slug == slug))
            ).scalar_one_or_none()
            domain = bucket["domains"].most_common(1)[0][0] if bucket["domains"] else None
            website = f"https://{domain}" if domain else None

            # Infer the industry from the roles we have actually seen for them.
            inferred = detect_industry(" ".join(bucket["text"][:40])) if bucket["text"] else None

            if startup is None:
                startup = Startup(
                    name=bucket["name"][:200],
                    slug=slug,
                    website=website,
                    industry=inferred or "Other technology startups",
                    hq_country="India",
                    discovery_source="ingestion_reconciliation",
                    verification_status="unverified",
                )
                session.add(startup)
                await session.flush()
                created += 1
            else:
                if website and not startup.website:
                    startup.website = website
                if inferred and startup.industry == "Other technology startups":
                    startup.industry = inferred
                if startup.hiring_status == "unknown" and bucket["jobs"]:
                    startup.hiring_status = "hiring"

            await session.execute(
                update(JobListing)
                .where(JobListing.id.in_(bucket["jobs"]))
                .values(startup_id=startup.id)
            )
            linked += len(bucket["jobs"])

        await session.commit()

        # Link sources to the company they belong to.
        sources = (await session.execute(select(JobSource))).scalars().all()
        for source in sources:
            if source.company_id is not None:
                continue
            count = (
                await session.execute(
                    select(func.count(JobListing.id)).where(JobListing.source_id == source.id)
                )
            ).scalar_one()
            if not count:
                continue
            row = (
                await session.execute(
                    select(JobListing.startup_id, func.count(JobListing.id))
                    .where(JobListing.source_id == source.id, JobListing.startup_id.isnot(None))
                    .group_by(JobListing.startup_id)
                    .order_by(func.count(JobListing.id).desc())
                    .limit(1)
                )
            ).first()
            if row:
                source.company_id = row[0]
        await session.commit()

        total_startups = (await session.execute(select(func.count(Startup.id)))).scalar_one()
        log.info(
            "reconciliation_complete",
            companies_created=created,
            jobs_linked=linked,
            total_startups=total_startups,
        )
        print(
            f"Reconciled: {created} companies created, {linked} jobs linked, "
            f"{total_startups} startups total"
        )


if __name__ == "__main__":
    asyncio.run(main())
