"""Generic career-page connector.

Reads any public careers page and extracts schema.org/JobPosting markup. This is
the fallback for companies that host their own ATS-less career pages.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.ingestion.base import Connector, ConnectorError, RawJob
from app.ingestion.http_client import PoliteClient
from app.services.normalizer import strip_html

log = get_logger(__name__)

_LD_SCRIPT_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)

ATS_LINK_PATTERNS = (
    ("greenhouse", re.compile(r"boards\.greenhouse\.io/([A-Za-z0-9_\-]+)", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/([A-Za-z0-9_\-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_\-]+)", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/([A-Za-z0-9_\-]+)/", re.I)),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([A-Za-z0-9_\-]+)", re.I)),
    ("recruitee", re.compile(r"([A-Za-z0-9_\-]+)\.recruitee\.com", re.I)),
)

# Workday boards live on <tenant>.wdN.myworkdayjobs.com/<Site_Name>; both the
# tenant and the site path are needed to read the feed.
WORKDAY_LINK_RE = re.compile(
    r"https?://([A-Za-z0-9_\-]+)\.(wd\d+)\.myworkdayjobs\.com/([A-Za-z0-9_\-]+)", re.I
)


def parse_jsonld_blocks(html: str) -> list[dict]:
    blocks: list[dict] = []
    for match in _LD_SCRIPT_RE.finditer(html):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            blocks.extend(b for b in data if isinstance(b, dict))
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks


def collect_job_postings(node: Any, out: list[dict], depth: int = 0) -> None:
    if depth > 10:
        return
    if isinstance(node, dict):
        node_type = node.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if "JobPosting" in types:
            out.append(node)
        for value in node.values():
            collect_job_postings(value, out, depth + 1)
    elif isinstance(node, list):
        for value in node:
            collect_job_postings(value, out, depth + 1)


def detect_ats_links(html: str) -> list[tuple[str, str]]:
    """Detect ATS board references (used by company discovery, not ingestion)."""
    found: list[tuple[str, str]] = []
    for kind, pattern in ATS_LINK_PATTERNS:
        for match in pattern.finditer(html):
            slug = match.group(1)
            if slug and slug.lower() not in {"embed", "jobs", "en", "www"}:
                found.append((kind, slug.lower()))
    for match in WORKDAY_LINK_RE.finditer(html):
        tenant = match.group(1).lower()
        region = match.group(2).lower()
        site = match.group(3)
        found.append(("workday", f"{tenant}|{region}|{site}"))
    # de-duplicate, keep order
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _location_text(posting: dict) -> str | None:
    location = posting.get("jobLocation")
    if isinstance(location, dict):
        location = [location]
    if isinstance(location, list):
        parts: list[str] = []
        for item in location:
            if not isinstance(item, dict):
                continue
            address = item.get("address") or {}
            if isinstance(address, dict):
                bits = [
                    address.get("addressLocality"),
                    address.get("addressRegion"),
                    address.get("addressCountry"),
                ]
                parts.append(", ".join(str(b) for b in bits if b))
            elif item.get("name"):
                parts.append(str(item["name"]))
        if parts:
            return "; ".join(parts)
    if isinstance(posting.get("jobLocation"), str):
        return posting["jobLocation"]
    applicant_location = posting.get("applicantLocationRequirements")
    if isinstance(applicant_location, dict):
        names = applicant_location.get("name")
        if names:
            return ", ".join(names) if isinstance(names, list) else str(names)
    return None


def _employment_type(value: Any) -> str | None:
    if not value:
        return None
    values = value if isinstance(value, list) else [value]
    for item in values:
        v = str(item).lower()
        if "intern" in v:
            return "Internship"
        if "part" in v:
            return "Part-time"
        if "contract" in v:
            return "Contract"
        if "temporary" in v:
            return "Contract"
        if "full" in v:
            return "Full-time"
    return None


class CareerPageConnector(Connector):
    """Extracts schema.org JobPosting entries from a public careers page."""

    type = "career_page"

    async def fetch(self) -> list[RawJob]:
        url = self.ctx.config.get("url")
        if not url:
            raise ConnectorError("career_page source requires config.url")
        client: PoliteClient = self.ctx.config["client"]
        try:
            html = await client.get_text(url)
        except PermissionError as exc:
            raise ConnectorError(f"career page blocked by robots.txt: {url}") from exc
        except Exception as exc:
            raise ConnectorError(f"career page fetch failed {url}: {exc}") from exc

        blocks = parse_jsonld_blocks(html)
        postings: list[dict] = []
        for block in blocks:
            collect_job_postings(block, postings)

        if not postings:
            return []

        company_name = self.ctx.config.get("company_name") or self.ctx.config.get("company") or "Unknown company"
        out: list[RawJob] = []
        for posting in postings:
            title = posting.get("title") or posting.get("name")
            if not title:
                continue
            apply_url = (
                posting.get("url")
                or posting.get("directApply")
                or posting.get("hiringOrganization", {}).get("sameAs")
                or url
            )
            if not isinstance(apply_url, str):
                apply_url = url
            org = posting.get("hiringOrganization") or {}
            org_name = org.get("name") if isinstance(org, dict) else None
            salary = posting.get("baseSalary") or {}
            salary_min = salary_max = None
            currency = None
            if isinstance(salary, dict):
                value = salary.get("value") or {}
                if isinstance(value, dict):
                    currency = value.get("currency")
                    min_value = value.get("minValue")
                    max_value = value.get("maxValue")
                    single = value.get("value")
                    if min_value is not None:
                        salary_min = int(min_value)
                    if max_value is not None:
                        salary_max = int(max_value)
                    if salary_min is None and single is not None:
                        salary_min = salary_max = int(single)

            description_html = posting.get("description") or ""
            description = strip_html(description_html) if isinstance(description_html, str) else ""

            identifier = posting.get("identifier")
            if isinstance(identifier, dict):
                identifier = identifier.get("value")
            job_id = str(identifier or posting.get("url") or title)

            out.append(
                RawJob(
                    external_id=f"career_page:{self.ctx.source_slug}:{abs(hash(job_id))}",
                    source_key=self.ctx.source_slug,
                    source_name=self.ctx.source_name,
                    title=str(title),
                    company_name=str(org_name or company_name),
                    apply_url=apply_url,
                    original_url=str(posting.get("url") or url),
                    description=description_html if isinstance(description_html, str) else description,
                    location_raw=_location_text(posting),
                    department=posting.get("occupationalCategory"),
                    posted_at=_parse_date(posting.get("datePosted")),
                    deadline=_parse_date(posting.get("validThrough")),
                    employment_type=_employment_type(posting.get("employmentType")),
                    work_arrangement=self._work_arrangement(posting.get("jobLocationType")),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=currency,
                    salary_period="year",
                    raw=posting,
                )
            )
        return out

    @staticmethod
    def _work_arrangement(value: Any) -> str | None:
        if not value:
            return None
        values = value if isinstance(value, list) else [value]
        for item in values:
            v = str(item).lower()
            if "remote" in v:
                return "Remote"
            if "hybrid" in v:
                return "Hybrid"
            if "onsite" in v or "on-site" in v:
                return "On-site"
        return None


def extract_page_metadata(html: str) -> dict:
    """Pull company description/logo/social links out of a homepage (discovery)."""
    soup = BeautifulSoup(html, "lxml")
    meta: dict[str, Any] = {}
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        meta["title"] = og["content"].strip()[:200]
    desc = soup.find("meta", attrs={"name": "description"})
    if desc and desc.get("content"):
        meta["description"] = desc["content"].strip()[:1000]
    logo = soup.find("meta", property="og:image")
    if logo and logo.get("content"):
        meta["logo_url"] = logo["content"].strip()[:600]
    for link in soup.find_all("a", href=True):
        href = link["href"]
        low = href.lower()
        if "linkedin.com/company/" in low and "linkedin_url" not in meta:
            meta["linkedin_url"] = href[:600]
        if ("/career" in low or "/jobs" in low or "join" in low) and href.startswith("http"):
            if "careers_url" not in meta:
                meta["careers_url"] = href[:600]
    return meta
