"""Connectors for public applicant-tracking-system job boards.

Each of these platforms exposes a documented, unauthenticated JSON endpoint for
public job boards. We only ever read the public endpoint and always keep the
original posting URL on the record.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.ingestion.base import Connector, ConnectorError, RawJob
from app.ingestion.http_client import PoliteClient
from app.services.normalizer import strip_html

log = get_logger(__name__)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class GreenhouseConnector(Connector):
    """https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"""

    type = "greenhouse"
    API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"

    async def fetch(self) -> list[RawJob]:
        board = self.ctx.config.get("board_token") or self.ctx.config.get("board")
        if not board:
            raise ConnectorError("greenhouse source requires config.board_token")
        client: PoliteClient = self.ctx.config["client"]
        url = self.API.format(board=board)
        try:
            data = await client.get_json(url, params={"content": "true"})
        except Exception as exc:
            raise ConnectorError(f"greenhouse fetch failed for {board}: {exc}") from exc

        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            raise ConnectorError("unexpected greenhouse payload")

        out: list[RawJob] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            title = job.get("title") or ""
            location = job.get("location") or {}
            location_name = location.get("name") if isinstance(location, dict) else str(location)
            apply_url = job.get("absolute_url") or ""
            if not job_id or not title or not apply_url:
                continue
            departments = job.get("departments") or []
            department = departments[0].get("name") if departments and isinstance(departments[0], dict) else None
            offices = job.get("offices") or []
            office = offices[0].get("name") if offices and isinstance(offices[0], dict) else None
            out.append(
                RawJob(
                    external_id=f"greenhouse:{board}:{job_id}",
                    source_key=f"greenhouse:{board}",
                    source_name=self.ctx.source_name,
                    title=title,
                    company_name=job.get("company_name") or self.ctx.config.get("company_name") or board,
                    apply_url=apply_url,
                    original_url=apply_url,
                    description=job.get("content") or "",
                    location_raw=location_name,
                    department=department or office,
                    posted_at=_parse_ts(job.get("updated_at") or job.get("first_published")),
                    updated_at=_parse_ts(job.get("updated_at")),
                    experience_level=None,
                    raw=job,
                )
            )
        return out


class LeverConnector(Connector):
    """https://api.lever.co/v0/postings/{company}?mode=json"""

    type = "lever"
    API = "https://api.lever.co/v0/postings/{company}"

    async def fetch(self) -> list[RawJob]:
        company = self.ctx.config.get("company") or self.ctx.config.get("board_token")
        if not company:
            raise ConnectorError("lever source requires config.company")
        client: PoliteClient = self.ctx.config["client"]
        try:
            data = await client.get_json(self.API.format(company=company), params={"mode": "json"})
        except Exception as exc:
            raise ConnectorError(f"lever fetch failed for {company}: {exc}") from exc

        if not isinstance(data, list):
            raise ConnectorError("unexpected lever payload")

        out: list[RawJob] = []
        for job in data:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            title = job.get("text") or ""
            if not job_id or not title:
                continue
            categories = job.get("categories") or {}
            apply_url = job.get("applyUrl") or job.get("hostedUrl") or ""
            description = job.get("descriptionPlain") or job.get("description") or ""
            lists = job.get("lists") or []
            extra_sections = []
            for section in lists:
                if isinstance(section, dict):
                    extra_sections.append(f"{section.get('text', '')}\n{section.get('content', '')}")
            if extra_sections:
                description = description + "\n\n" + "\n".join(extra_sections)

            salary_min = salary_max = None
            salary_range = job.get("salaryRange") or {}
            if isinstance(salary_range, dict):
                try:
                    salary_min = int(salary_range.get("minValue")) if salary_range.get("minValue") else None
                    salary_max = int(salary_range.get("maxValue")) if salary_range.get("maxValue") else None
                except (TypeError, ValueError):
                    salary_min = salary_max = None

            out.append(
                RawJob(
                    external_id=f"lever:{company}:{job_id}",
                    source_key=f"lever:{company}",
                    source_name=self.ctx.source_name,
                    title=title,
                    company_name=self.ctx.config.get("company_name") or company.replace("-", " ").title(),
                    apply_url=apply_url,
                    original_url=job.get("hostedUrl") or apply_url,
                    description=description,
                    location_raw=categories.get("location"),
                    department=categories.get("department") or categories.get("team"),
                    posted_at=_parse_ts(job.get("createdAt")),
                    updated_at=_parse_ts(job.get("updatedAt")),
                    employment_type=self._map_commitment(categories.get("commitment")),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency="USD" if salary_min else None,
                    salary_period="year" if salary_min else None,
                    raw=job,
                )
            )
        return out

    @staticmethod
    def _map_commitment(commitment: str | None) -> str | None:
        if not commitment:
            return None
        c = commitment.lower()
        if "intern" in c:
            return "Internship"
        if "part-time" in c or "part time" in c:
            return "Part-time"
        if "contract" in c or "freelance" in c:
            return "Contract"
        if "temporary" in c:
            return "Contract"
        if "full-time" in c or "full time" in c:
            return "Full-time"
        return None


class AshbyConnector(Connector):
    """https://api.ashbyhq.com/posting-api/job-board/{company}"""

    type = "ashby"
    API = "https://api.ashbyhq.com/posting-api/job-board/{company}"

    async def fetch(self) -> list[RawJob]:
        company = self.ctx.config.get("company") or self.ctx.config.get("board_token")
        if not company:
            raise ConnectorError("ashby source requires config.company")
        client: PoliteClient = self.ctx.config["client"]
        try:
            data = await client.get_json(self.API.format(company=company))
        except Exception as exc:
            raise ConnectorError(f"ashby fetch failed for {company}: {exc}") from exc

        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            raise ConnectorError("unexpected ashby payload")

        out: list[RawJob] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            if job.get("isListed") is False:
                continue
            job_id = str(job.get("id") or "")
            title = job.get("title") or ""
            apply_url = job.get("applyUrl") or job.get("jobUrl") or ""
            if not job_id or not title:
                continue
            location = job.get("location") or ""
            secondary = job.get("secondaryLocations") or []
            if secondary:
                extra = ", ".join(
                    str(s.get("location")) for s in secondary if isinstance(s, dict) and s.get("location")
                )
                if extra:
                    location = f"{location}, {extra}" if location else extra
            out.append(
                RawJob(
                    external_id=f"ashby:{company}:{job_id}",
                    source_key=f"ashby:{company}",
                    source_name=self.ctx.source_name,
                    title=title,
                    company_name=self.ctx.config.get("company_name") or company.replace("-", " ").title(),
                    apply_url=apply_url,
                    original_url=job.get("jobUrl") or apply_url,
                    description=job.get("descriptionHtml") or job.get("descriptionPlain") or "",
                    location_raw=location,
                    department=job.get("department") or job.get("team"),
                    posted_at=_parse_ts(job.get("publishedAt")),
                    updated_at=_parse_ts(job.get("updatedAt")),
                    employment_type=self._map_type(job.get("employmentType")),
                    work_arrangement="Remote" if job.get("isRemote") else None,
                    raw=job,
                )
            )
        return out

    @staticmethod
    def _map_type(value: str | None) -> str | None:
        if not value:
            return None
        v = value.lower()
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


class WorkableConnector(Connector):
    """https://apply.workable.com/api/v1/accounts/{account}/jobs"""

    type = "workable"
    API = "https://apply.workable.com/api/v1/accounts/{account}/jobs"

    async def fetch(self) -> list[RawJob]:
        account = self.ctx.config.get("account") or self.ctx.config.get("company")
        if not account:
            raise ConnectorError("workable source requires config.account")
        client: PoliteClient = self.ctx.config["client"]
        try:
            data = await client.get_json(self.API.format(account=account))
        except Exception as exc:
            raise ConnectorError(f"workable fetch failed for {account}: {exc}") from exc

        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            raise ConnectorError("unexpected workable payload")

        out: list[RawJob] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            title = job.get("title") or ""
            url = job.get("url") or ""
            if not job_id or not title:
                continue
            description = job.get("description") or ""
            if job.get("requirements"):
                description = f"{description}\n\nRequirements\n{job['requirements']}"
            if job.get("benefits"):
                description = f"{description}\n\nBenefits\n{job['benefits']}"
            out.append(
                RawJob(
                    external_id=f"workable:{account}:{job_id}",
                    source_key=f"workable:{account}",
                    source_name=self.ctx.source_name,
                    title=title,
                    company_name=self.ctx.config.get("company_name") or account.replace("-", " ").title(),
                    apply_url=url,
                    original_url=url,
                    description=description,
                    location_raw=job.get("location") or job.get("city"),
                    department=job.get("department") or job.get("team"),
                    posted_at=_parse_ts(job.get("published_on") or job.get("created_at")),
                    updated_at=_parse_ts(job.get("updated_at")),
                    employment_type=self._map_type(job.get("employment_type")),
                    work_arrangement="Remote" if job.get("remote") else None,
                    raw=job,
                )
            )
        return out

    @staticmethod
    def _map_type(value: str | None) -> str | None:
        if not value:
            return None
        v = value.lower()
        if "intern" in v:
            return "Internship"
        if "part" in v:
            return "Part-time"
        if "freelance" in v:
            return "Freelance"
        if "contract" in v:
            return "Contract"
        if "apprentice" in v:
            return "Apprenticeship"
        if "full" in v:
            return "Full-time"
        return None


class SmartRecruitersConnector(Connector):
    """https://api.smartrecruiters.com/v1/companies/{company}/postings"""

    type = "smartrecruiters"
    API = "https://api.smartrecruiters.com/v1/companies/{company}/postings"

    async def fetch(self) -> list[RawJob]:
        company = self.ctx.config.get("company") or self.ctx.config.get("board_token")
        if not company:
            raise ConnectorError("smartrecruiters source requires config.company")
        client: PoliteClient = self.ctx.config["client"]
        try:
            data = await client.get_json(
                self.API.format(company=company),
                params={"limit": 100, "details": "true"},
            )
        except Exception as exc:
            raise ConnectorError(f"smartrecruiters fetch failed for {company}: {exc}") from exc

        content = data.get("content") if isinstance(data, dict) else data
        if not isinstance(content, list):
            raise ConnectorError("unexpected smartrecruiters payload")

        out: list[RawJob] = []
        for job in content:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            title = job.get("name") or ""
            if not job_id or not title:
                continue
            location = job.get("location") or {}
            location_name = ", ".join(
                str(location.get(k)) for k in ("city", "region", "country") if location.get(k)
            ) or str(job.get("country"))
            department = job.get("department") or {}
            dept_label = department.get("label") if isinstance(department, dict) else None
            out.append(
                RawJob(
                    external_id=f"smartrecruiters:{company}:{job_id}",
                    source_key=f"smartrecruiters:{company}",
                    source_name=self.ctx.source_name,
                    title=title,
                    company_name=self.ctx.config.get("company_name")
                    or (job.get("company") or {}).get("name")
                    or company.replace("-", " ").title(),
                    apply_url=f"https://jobs.smartrecruiters.com/{company}/{job_id}",
                    original_url=f"https://jobs.smartrecruiters.com/{company}/{job_id}",
                    description=strip_html(job.get("description") or job.get("name")),
                    location_raw=location_name,
                    department=dept_label,
                    posted_at=_parse_ts(job.get("releasedDate")),
                    updated_at=_parse_ts(job.get("updatedDate")),
                    employment_type=self._map_type(job.get("typeOfEmployment")),
                    raw=job,
                )
            )
        return out

    @staticmethod
    def _map_type(value: str | None) -> str | None:
        if not value:
            return None
        v = value.lower()
        if "intern" in v:
            return "Internship"
        if "part" in v:
            return "Part-time"
        if "contract" in v:
            return "Contract"
        if "apprentice" in v:
            return "Apprenticeship"
        if "full" in v:
            return "Full-time"
        return None
