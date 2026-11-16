"""Connector for Workday job boards.

Workday tenants expose a public JSON endpoint under
``/wday/cxs/{tenant}/{site}/jobs``. The listing endpoint is a POST with a small
JSON body; each posting's detail is available at the same path plus the
``externalPath`` returned by the listing.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logging import get_logger
from app.ingestion.base import Connector, ConnectorError, RawJob
from app.ingestion.http_client import PoliteClient

log = get_logger(__name__)

POSTED_AGO_RE = re.compile(r"posted\s+(\d+)\s+(day|hour|minute|week|month)s?", re.I)


def _parse_posted_on(value: str | None) -> datetime | None:
    if not value:
        return None
    match = POSTED_AGO_RE.search(value)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    now = datetime.now(timezone.utc)
    if unit == "hour":
        return now.replace(minute=max(now.minute - amount, 0))
    if unit == "minute":
        return now.replace(second=max(now.second - amount, 0))
    days = amount * (7 if unit == "week" else 30 if unit == "month" else 1)
    return now - timedelta(days=days)


class WorkdayConnector(Connector):
    """Reads a Workday careers site."""

    type = "workday"

    def _base(self) -> str:
        host = self.ctx.config.get("host")
        if host:
            return host.rstrip("/")
        tenant = self.ctx.config.get("tenant")
        region = self.ctx.config.get("region", "wd1")
        if not tenant:
            raise ConnectorError("workday source requires config.tenant")
        return f"https://{tenant}.{region}.myworkdayjobs.com"

    async def fetch(self) -> list[RawJob]:
        client: PoliteClient = self.ctx.config["client"]
        base = self._base()
        site = self.ctx.config.get("site")
        tenant = self.ctx.config.get("tenant") or base.split("//")[1].split(".")[0]
        if not site:
            raise ConnectorError("workday source requires config.site")

        url = f"{base}/wday/cxs/{tenant}/{site}/jobs"
        try:
            response = await client.request(
                "POST",
                url,
                json_body={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""},
            )
            payload = response.json()
        except Exception as exc:
            raise ConnectorError(f"workday fetch failed for {tenant}/{site}: {exc}") from exc

        postings = payload.get("jobPostings") if isinstance(payload, dict) else None
        if not isinstance(postings, list):
            raise ConnectorError("unexpected workday payload")

        total = int(payload.get("total") or len(postings))
        limit = min(int(self.ctx.config.get("page_size", 20)), 50)
        max_pages = min(int(self.ctx.config.get("max_pages", 5)), 25)

        collected: list[dict] = list(postings)
        for page in range(1, max_pages):
            offset = page * limit
            if offset >= total:
                break
            try:
                response = await client.request(
                    "POST",
                    url,
                    json_body={"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""},
                )
                page_payload = response.json()
            except Exception as exc:
                log.warning("workday_page_failed", tenant=tenant, offset=offset, error=str(exc)[:200])
                break
            page_items = page_payload.get("jobPostings") or []
            if not page_items:
                break
            collected.extend(page_items)

        out: list[RawJob] = []
        for posting in collected:
            job = await self._parse_listing(posting, base, tenant, site)
            if job is not None:
                out.append(job)
        log.info("workday_ingested", tenant=tenant, site=site, jobs=len(out))
        return out

    async def _parse_listing(
        self, posting: dict[str, Any], base: str, tenant: str, site: str
    ) -> RawJob | None:
        title = posting.get("title")
        external_path = posting.get("externalPath")
        if not title or not external_path:
            return None

        locations = [posting.get("locationsText") or ""]
        req_id = ""
        for bullet in posting.get("bulletFields") or []:
            if isinstance(bullet, str) and bullet.strip():
                req_id = bullet.strip()
                break

        description = ""
        try:
            detail_url = f"{base}/wday/cxs/{tenant}/{site}{external_path}"
            client: PoliteClient = self.ctx.config["client"]
            response = await client.request("GET", detail_url)
            detail = response.json().get("jobPostingInfo") or {}
            description = detail.get("jobDescription") or ""
            additional = detail.get("additionalLocations") or []
            for extra in additional:
                location = extra.get("location") if isinstance(extra, dict) else None
                if location:
                    locations.append(location)
        except Exception as exc:
            log.warning("workday_detail_failed", tenant=tenant, error=str(exc)[:200])

        location_raw = ", ".join(part for part in locations if part) or None
        job_url = f"{base}{external_path}"
        company = self.ctx.config.get("company_name") or tenant.replace("_", " ").title()

        return RawJob(
            external_id=f"workday:{tenant}:{req_id or external_path}",
            source_key=f"workday-{tenant}",
            source_name=self.ctx.source_name,
            title=title,
            company_name=company,
            apply_url=job_url,
            original_url=job_url,
            description=description,
            location_raw=location_raw,
            posted_at=_parse_posted_on(posting.get("postedOn")),
            raw=posting,
        )
