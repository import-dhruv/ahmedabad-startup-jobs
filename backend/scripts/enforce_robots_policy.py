"""Enforce the robots policy over registered sources.

Some public feeds publish an API that their `robots.txt` disallows (for
example `Disallow: /api/*`). This script checks every registered source
against its host's robots.txt and, where access is not permitted:

* deactivates the source so the scheduler stops reading it;
* removes the listings that came only from that source (listings that are also
  present on a permitted source keep their reference and their data).

Run it after adding sources and periodically from cron.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import delete, select, update

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import get_logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ingestion.http_client import PoliteClient  # noqa: E402
from app.models import JobListing, JobSource, JobSourceReference  # noqa: E402

log = get_logger(__name__)

# The endpoint each connector actually reads, per connector type.
ENDPOINT_BY_CONNECTOR: dict[str, str] = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/probe/jobs",
    "lever": "https://api.lever.co/v0/postings/probe",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/probe",
    "workable": "https://apply.workable.com/api/v1/accounts/probe/jobs",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/probe/postings",
    "remoteok": "https://remoteok.com/api",
    "remotive": "https://remotive.com/api/remote-jobs",
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
    "jobicy": "https://jobicy.com/api/v2/remote-jobs",
    "himalayas": "https://himalayas.app/jobs/api",
    "hackernews": "https://hacker-news.firebaseio.com/v0/user/whoishiring.json",
    "workday": "https://probe.wd1.myworkdayjobs.com/wday/cxs/probe/probe/jobs",
}


async def audit_robots_policy() -> dict[str, object]:
    """Audit every registered connector source and return what changed."""
    removed_sources: list[str] = []
    removed_jobs = 0

    async with SessionLocal() as session:
        sources = (await session.execute(select(JobSource))).scalars().all()

        async with PoliteClient(rate_limit_per_host=30, max_retries=1) as client:
            for source in sources:
                url = ENDPOINT_BY_CONNECTOR.get(source.connector_type)
                if url is None:
                    # Career pages are evaluated per-URL at fetch time.
                    continue
                allowed = await client._robots_allows(url)
                if allowed:
                    if not source.is_active:
                        source.is_active = True
                        log.info("source_reactivated", source=source.slug)
                    continue

                log.warning("robots_forbids_source", source=source.slug, connector=source.connector_type)
                source.is_active = False
                source.notes = (
                    f"{source.notes or ''} | Inactive: robots.txt disallows reading "
                    f"{url} (audited {datetime.now(UTC).date().isoformat()})"
                ).strip(" |")
                removed_sources.append(source.slug)

                # Remove listings that exist only because of this source.
                job_ids = (
                    await session.execute(
                        select(JobListing.id).where(JobListing.source_id == source.id)
                    )
                ).scalars().all()
                for job_id in job_ids:
                    other_refs = (
                        await session.execute(
                            select(JobSourceReference.id)
                            .where(JobSourceReference.job_id == job_id)
                            .where(JobSourceReference.source_id != source.id)
                            .limit(1)
                        )
                    ).scalar_one_or_none()
                    if other_refs is not None:
                        # The listing is also present on a permitted source.
                        await session.execute(
                            update(JobListing)
                            .where(JobListing.id == job_id)
                            .values(source_id=None, source_name=source.name)
                        )
                        continue
                    await session.execute(delete(JobSourceReference).where(JobSourceReference.job_id == job_id))
                    await session.execute(delete(JobListing).where(JobListing.id == job_id))
                    removed_jobs += 1

        await session.commit()

    return {
        "deactivated_sources": removed_sources,
        "removed_listings": removed_jobs,
    }


async def main() -> None:
    result = await audit_robots_policy()
    sources = result["deactivated_sources"]
    print(
        f"robots audit complete: {len(sources)} source(s) deactivated "
        f"({', '.join(sources) or 'none'}), {result['removed_listings']} listing(s) removed"
    )


if __name__ == "__main__":
    asyncio.run(main())
