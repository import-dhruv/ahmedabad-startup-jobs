"""Company discovery.

Discovers real companies (and their job boards) from public, documented
endpoints. Every persisted company keeps the evidence URL that produced it.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.core.logging import get_logger
from app.ingestion.http_client import PoliteClient
from app.services.geo import CITY_TO_STATE, detect_country

log = get_logger(__name__)

YC_API = "https://api.ycombinator.com/v0.1/companies"


@dataclass(slots=True)
class DiscoveredCompany:
    name: str
    website: str | None = None
    description: str | None = None
    logo_url: str | None = None
    linkedin_url: str | None = None
    hq_city: str | None = None
    hq_state: str | None = None
    hq_country: str | None = None
    industry: str | None = None
    founded_year: int | None = None
    size_range: str | None = None
    discovery_source: str = "unknown"
    evidence_url: str | None = None
    career_url: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def domain(self) -> str | None:
        if not self.website:
            return None
        host = urlparse(self.website).netloc.lower()
        return host[4:] if host.startswith("www.") else host


def _yc_size(team_size: int | None) -> str | None:
    if not team_size:
        return None
    if team_size <= 10:
        return "1-10"
    if team_size <= 50:
        return "11-50"
    if team_size <= 200:
        return "51-200"
    if team_size <= 500:
        return "201-500"
    return "500+"


def _infer_indry_from_tags(tags: list[str] | None) -> str | None:
    from app.services.normalizer import detect_industry

    if not tags:
        return None
    return detect_industry(" ".join(tags))


async def discover_from_yc(
    client: PoliteClient,
    queries: list[str] | None = None,
    max_pages: int = 4,
    region_filter: str | None = "India",
) -> list[DiscoveredCompany]:
    """Pull companies from the public YC directory API filtered to a region."""
    queries = queries or ["india", "gujarat", "ahmedabad", "gandhinagar"]
    found: dict[str, DiscoveredCompany] = {}

    for query in queries:
        for page in range(1, max_pages + 1):
            url = f"{YC_API}?q={query.replace(' ', '%20')}&per_page=100&page={page}"
            try:
                data = await client.get_json(url)
            except Exception as exc:
                log.warning("yc_fetch_failed", query=query, page=page, error=str(exc))
                break
            companies = data.get("companies") if isinstance(data, dict) else None
            if not isinstance(companies, list) or not companies:
                break

            for company in companies:
                if not isinstance(company, dict):
                    continue
                regions = [str(r) for r in (company.get("regions") or [])]
                locations = [str(loc) for loc in (company.get("locations") or [])]
                if region_filter and region_filter.lower() not in {r.lower() for r in regions}:
                    continue

                name = (company.get("name") or "").strip()
                if not name:
                    continue
                website = company.get("website")
                hq_city = hq_state = hq_country = None
                for loc in locations:
                    lowered = loc.lower()
                    if lowered in CITY_TO_STATE:
                        hq_city = loc.title()
                        hq_state = CITY_TO_STATE[lowered]
                        hq_country = "India"
                        break
                if not hq_country:
                    for region in regions:
                        country = detect_country(region)
                        if country:
                            hq_country = country
                            break

                found[company.get("id") or name] = DiscoveredCompany(
                    name=name,
                    website=website,
                    description=(company.get("oneLiner") or "").strip() or None,
                    logo_url=company.get("smallLogoUrl") or company.get("largeLogoUrl"),
                    hq_city=hq_city,
                    hq_state=hq_state,
                    hq_country=hq_country or "India",
                    industry=_infer_indry_from_tags(company.get("tags") or company.get("industries")),
                    size_range=_yc_size(company.get("teamSize")),
                    discovery_source="yc_directory",
                    evidence_url=company.get("url")
                    or f"https://www.ycombinator.com/companies/{company.get('slug', '')}",
                    extra={
                        "batch": company.get("batch"),
                        "tags": company.get("tags") or [],
                        "yc_slug": company.get("slug"),
                    },
                )
            if page >= int(data.get("totalPages") or 1):
                break

    log.info("yc_discovery_complete", companies=len(found))
    return list(found.values())


# --- ATS detection ----------------------------------------------------------

ATS_PROBE_TEMPLATES: dict[str, str] = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "workable": "https://apply.workable.com/api/v1/accounts/{slug}/jobs",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{slug}/postings",
}

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def candidate_slugs(name: str, domain: str | None) -> list[str]:
    """Derive likely ATS board identifiers from a company name/domain."""
    slugs: list[str] = []

    def add(value: str) -> None:
        slug = _SLUG_STRIP_RE.sub("-", value.lower()).strip("-")
        if slug and slug not in slugs:
            slugs.append(slug)

    if domain:
        base = domain.split("/")[0].lower()
        for prefix in ("www.", "app.", "careers.", "jobs.", "get."):
            if base.startswith(prefix):
                base = base[len(prefix) :]
        add(base)
        if "." in base:
            add(base.split(".")[0])
    add(name)
    add(name.replace(" ", ""))
    add(name.replace(" ", "-"))
    if name.lower().startswith("get "):
        add(name[4:])
    return slugs[:4]



def _count_jobs(payload: object, key: str | None = None) -> int | None:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        if key:
            value = payload.get(key)
            return len(value) if isinstance(value, list) else None
        for candidate in ("jobs", "postings", "results", "content", "data"):
            value = payload.get(candidate)
            if isinstance(value, list):
                return len(value)
        if "error" in payload:
            return None
    return None


CAREER_HREF_RE = re.compile(r"https?://[^\"'<> ]*(?:career|jobs|hiring|join|vacanc|opening)[^\"'<> ]*", re.I)


async def find_career_url(client: PoliteClient, website: str) -> str | None:
    """Find a company's careers page by scanning its homepage links."""
    try:
        html = await client.get_text(website)
    except Exception:
        return None
    host = urlparse(website).netloc.lower().removeprefix("www.")
    candidates: list[str] = []
    for match in CAREER_HREF_RE.finditer(html):
        href = match.group(0).rstrip('"\'<>.,);')
        if host and host not in urlparse(href).netloc.lower():
            continue
        if href not in candidates:
            candidates.append(href)
    if not candidates:
        return None
    candidates.sort(key=len)
    return candidates[0]


async def detect_ats_slugs_from_pages(
    client: PoliteClient, website: str, max_pages: int = 2
) -> list[tuple[str, str]]:
    """Read a company's own pages to find the *exact* ATS board identifiers.

    Career pages commonly link straight to their board (for example
    ``boards.greenhouse.io/razorpaysoftwareprivatelimited``), which is far more
    reliable than guessing slugs from the domain name.
    """
    from app.ingestion.connectors.career_pages import detect_ats_links

    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    async def scan(url: str) -> None:
        try:
            html = await client.get_text(url)
        except Exception:
            return
        for kind, slug in detect_ats_links(html):
            key = (kind, slug)
            if key in seen:
                continue
            seen.add(key)
            found.append(key)

    try:
        home = await client.get_text(website)
    except Exception:
        home = ""

    if home:
        for kind, slug in detect_ats_links(home):
            key = (kind, slug)
            if key not in seen:
                seen.add(key)
                found.append(key)

    pages: list[str] = []
    if home:
        host = urlparse(website).netloc.lower().removeprefix("www.")
        for match in CAREER_HREF_RE.finditer(home):
            href = match.group(0).rstrip('"\'<>.,);')
            if host and host not in urlparse(href).netloc.lower():
                continue
            if href not in pages:
                pages.append(href)
    pages.sort(key=len)

    for page in pages[:max_pages]:
        await scan(page)

    return found


async def probe_ats_boards(
    client: PoliteClient,
    name: str,
    domain: str | None,
    max_probes: int = 8,
    extra_slugs: list[tuple[str, str]] | None = None,
) -> list[dict]:
    """Probe ATS APIs for a company and return the boards that actually exist."""
    hits: list[dict] = []
    attempts = 0
    seen: set[tuple[str, str]] = set()

    # Boards referenced by the company's own pages are tried first.
    for kind, slug in extra_slugs or []:
        if kind == "workday":
            tenant, region, site = slug.split("|")
            url = f"https://{tenant}.{region}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
            try:
                resp = await client.request(
                    "POST",
                    url,
                    json_body={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
                    raise_for_status=False,
                    allow_robots_check=False,
                )
            except Exception:
                continue
            if resp.status_code != 200:
                continue
            try:
                payload = resp.json()
            except Exception:
                continue
            count = _count_jobs(payload, key="jobPostings")
            if not count:
                continue
            hits.append({"kind": "workday", "slug": slug, "job_count": count, "probe_url": url})
            seen.add((kind, slug))
            continue

        template = ATS_PROBE_TEMPLATES.get(kind)
        if not template:
            continue
        url = template.format(slug=slug)
        try:
            resp = await client.request("GET", url, raise_for_status=False, allow_robots_check=False)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        try:
            payload = resp.json()
        except Exception:
            continue
        count = _count_jobs(payload)
        if count is None or count == 0:
            continue
        hits.append({"kind": kind, "slug": slug, "job_count": count, "probe_url": url})
        seen.add((kind, slug))

    for kind, template in ATS_PROBE_TEMPLATES.items():
        for slug in candidate_slugs(name, domain):
            if (kind, slug) in seen:
                continue
            if attempts >= max_probes:
                break
            attempts += 1
            url = template.format(slug=slug)
            try:
                resp = await client.request("GET", url, raise_for_status=False, allow_robots_check=False)
            except Exception:
                continue
            if resp.status_code != 200:
                continue
            try:
                payload = resp.json()
            except Exception:
                continue
            count = _count_jobs(payload)
            if count is None or count == 0:
                continue
            hits.append({"kind": kind, "slug": slug, "job_count": count, "probe_url": url})
            break  # one board per ATS per company
    return hits


def workday_config(slug: str) -> dict[str, str]:
    """Translate a workday slug (tenant|region|site) into connector config."""
    tenant, region, site = slug.split("|")
    return {
        "connector_type": "workday",
        "tenant": tenant,
        "region": region,
        "site": site,
        "company_name": site.replace("_", " ").title(),
    }


async def enrich_company(client: PoliteClient, company: DiscoveredCompany) -> DiscoveredCompany:
    """Fill in company metadata from its own website (public pages only)."""
    if not company.website:
        return company
    from app.ingestion.connectors.career_pages import extract_page_metadata

    try:
        html = await client.get_text(company.website)
    except Exception:
        return company
    meta = extract_page_metadata(html)
    if not company.description and meta.get("description"):
        company.description = meta["description"]
    if not company.logo_url and meta.get("logo_url"):
        company.logo_url = meta["logo_url"]
    if not company.linkedin_url and meta.get("linkedin_url"):
        company.linkedin_url = meta["linkedin_url"]
    if not company.hq_city and meta.get("title"):
        for city in CITY_TO_STATE:
            if city in meta["title"].lower():
                company.hq_city = city.title()
                company.hq_state = CITY_TO_STATE[city]
                company.hq_country = "India"
                break
    if not company.career_url:
        career = await find_career_url(client, company.website)
        if career:
            company.career_url = career
    return company


async def discover_all(
    client: PoliteClient,
    queries: list[str] | None = None,
    domains: list[str] | None = None,
    max_pages: int = 3,
) -> list[DiscoveredCompany]:
    """Full discovery sweep: YC directory + direct domain probing."""
    companies = await discover_from_yc(client, queries=queries, max_pages=max_pages)
    for domain in domains or []:
        name = domain.split("/")[0].split(".")[0].replace("-", " ").title()
        companies.append(
            DiscoveredCompany(
                name=name,
                website=domain if domain.startswith("http") else f"https://{domain}",
                discovery_source="domain_registry",
                evidence_url=domain,
            )
        )
    return companies


async def probe_domains_for_boards(
    client: PoliteClient, domains: list[str], concurrency: int = 6
) -> dict[str, list[dict]]:
    """Probe a list of domains for ATS job boards."""
    semaphore = asyncio.Semaphore(concurrency)

    async def one(domain: str) -> tuple[str, list[dict]]:
        async with semaphore:
            name = domain.split("/")[0].split(".")[0].replace("-", " ").title()
            try:
                hits = await probe_ats_boards(client, name, domain)
            except Exception as exc:
                log.warning("ats_probe_failed", domain=domain, error=str(exc))
                hits = []
            return domain, hits

    results = await asyncio.gather(*(one(d) for d in domains))
    return {domain: hits for domain, hits in results}
