"""Connectors for public remote-job aggregator APIs.

These endpoints publish a public JSON feed. We keep the original listing URL for
every record and only trust fields the feed actually provides.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.ingestion.base import Connector, ConnectorError, RawJob
from app.ingestion.http_client import PoliteClient

log = get_logger(__name__)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class RemoteOkConnector(Connector):
    """https://remoteok.com/api — public RSS-equivalent JSON feed."""

    type = "remoteok"
    API = "https://remoteok.com/api"

    async def fetch(self) -> list[RawJob]:
        client: PoliteClient = self.ctx.config["client"]
        try:
            data = await client.get_json(self.API)
        except Exception as exc:
            raise ConnectorError(f"remoteok fetch failed: {exc}") from exc
        if not isinstance(data, list):
            raise ConnectorError("unexpected remoteok payload")

        out: list[RawJob] = []
        for job in data:
            if not isinstance(job, dict):
                continue
            # The first element of the feed is a legal notice, not a job.
            if job.get("legal") or not job.get("position"):
                continue
            job_id = str(job.get("id") or job.get("slug") or "")
            apply_url = job.get("apply_url") or job.get("url") or ""
            if not job_id or not job.get("position") or not apply_url:
                continue
            location = job.get("location") or ""
            out.append(
                RawJob(
                    external_id=f"remoteok:{job_id}",
                    source_key="remoteok",
                    source_name=self.ctx.source_name,
                    title=job.get("position") or "",
                    company_name=job.get("company") or "Unknown company",
                    apply_url=apply_url,
                    original_url=job.get("url") or apply_url,
                    description=job.get("description") or "",
                    location_raw=location,
                    department=", ".join(job.get("tags") or []) or None,
                    posted_at=_parse_ts(job.get("date") or job.get("epoch")),
                    salary_min=job.get("salary_min") or None,
                    salary_max=job.get("salary_max") or None,
                    salary_currency="USD" if job.get("salary_min") else None,
                    salary_period="year" if job.get("salary_min") else None,
                    work_arrangement="Remote",
                    raw=job,
                )
            )
        return out


class RemotiveConnector(Connector):
    """https://remotive.com/api/remote-jobs"""

    type = "remotive"
    API = "https://remotive.com/api/remote-jobs"

    async def fetch(self) -> list[RawJob]:
        client: PoliteClient = self.ctx.config["client"]
        try:
            data = await client.get_json(self.API, params={"limit": 200})
        except Exception as exc:
            raise ConnectorError(f"remotive fetch failed: {exc}") from exc
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            raise ConnectorError("unexpected remotive payload")

        out: list[RawJob] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            url = job.get("url") or ""
            if not job_id or not job.get("title") or not url:
                continue
            location = job.get("candidate_required_location") or job.get("job_location") or ""
            out.append(
                RawJob(
                    external_id=f"remotive:{job_id}",
                    source_key="remotive",
                    source_name=self.ctx.source_name,
                    title=job.get("title") or "",
                    company_name=job.get("company_name") or "Unknown company",
                    apply_url=url,
                    original_url=url,
                    description=job.get("description") or "",
                    location_raw=location,
                    department=job.get("category") or None,
                    posted_at=_parse_ts(job.get("publication_date")),
                    employment_type=job.get("job_type"),
                    work_arrangement="Remote" if job.get("remote", True) else None,
                    raw=job,
                )
            )
        return out


class ArbeitnowConnector(Connector):
    """https://www.arbeitnow.com/api/job-board-api"""

    type = "arbeitnow"
    API = "https://www.arbeitnow.com/api/job-board-api"

    async def fetch(self) -> list[RawJob]:
        client: PoliteClient = self.ctx.config["client"]
        try:
            data = await client.get_json(self.API)
        except Exception as exc:
            raise ConnectorError(f"arbeitnow fetch failed: {exc}") from exc
        jobs = data.get("data") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            raise ConnectorError("unexpected arbeitnow payload")

        out: list[RawJob] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            slug = job.get("slug") or ""
            url = job.get("url") or ""
            if not slug or not job.get("title") or not url:
                continue
            location = job.get("location") or ""
            out.append(
                RawJob(
                    external_id=f"arbeitnow:{slug}",
                    source_key="arbeitnow",
                    source_name=self.ctx.source_name,
                    title=job.get("title") or "",
                    company_name=job.get("company_name") or "Unknown company",
                    apply_url=url,
                    original_url=url,
                    description=job.get("description") or "",
                    location_raw=location,
                    department=", ".join(job.get("tags") or []) or None,
                    posted_at=_parse_ts(job.get("created_at")),
                    work_arrangement="Remote" if job.get("remote") else None,
                    raw=job,
                )
            )
        return out


class JobicyConnector(Connector):
    """https://jobicy.com/api/v2/remote-jobs"""

    type = "jobicy"
    API = "https://jobicy.com/api/v2/remote-jobs"

    async def fetch(self) -> list[RawJob]:
        client: PoliteClient = self.ctx.config["client"]
        try:
            data = await client.get_json(self.API, params={"count": 100})
        except Exception as exc:
            raise ConnectorError(f"jobicy fetch failed: {exc}") from exc
        jobs = data.get("jobList") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            raise ConnectorError("unexpected jobicy payload")

        out: list[RawJob] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or job.get("slug") or "")
            url = job.get("url") or ""
            if not job_id or not job.get("jobTitle") or not url:
                continue
            location = job.get("jobGeo") or job.get("location") or ""
            out.append(
                RawJob(
                    external_id=f"jobicy:{job_id}",
                    source_key="jobicy",
                    source_name=self.ctx.source_name,
                    title=job.get("jobTitle") or "",
                    company_name=job.get("companyName") or "Unknown company",
                    apply_url=url,
                    original_url=url,
                    description=job.get("jobDescription") or job.get("jobDescriptionPlain") or "",
                    location_raw=location,
                    department=job.get("jobIndustry") or None,
                    posted_at=_parse_ts(job.get("pubDate")),
                    employment_type=job.get("jobType"),
                    work_arrangement="Remote",
                    raw=job,
                )
            )
        return out


class HimalayasConnector(Connector):
    """https://himalayas.app/jobs/api"""

    type = "himalayas"
    API = "https://himalayas.app/jobs/api"

    async def fetch(self) -> list[RawJob]:
        client: PoliteClient = self.ctx.config["client"]
        try:
            data = await client.get_json(self.API, params={"limit": 100})
        except Exception as exc:
            raise ConnectorError(f"himalayas fetch failed: {exc}") from exc
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            raise ConnectorError("unexpected himalayas payload")

        out: list[RawJob] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            url = job.get("applicationUrl") or job.get("jobUrl") or ""
            if not job_id or not job.get("title") or not url:
                continue
            out.append(
                RawJob(
                    external_id=f"himalayas:{job_id}",
                    source_key="himalayas",
                    source_name=self.ctx.source_name,
                    title=job.get("title") or "",
                    company_name=job.get("companyName") or "Unknown company",
                    apply_url=url,
                    original_url=job.get("jobUrl") or url,
                    description=job.get("description") or "",
                    location_raw=job.get("location"),
                    posted_at=_parse_ts(job.get("publishedAt")),
                    work_arrangement="Remote",
                    raw=job,
                )
            )
        return out
