"""Seed the database with sources, run discovery and ingest real job data.

Usage:
    python -m scripts.seed                 # full seed + discovery + ingestion
    python -m scripts.seed --no-ingest     # only create sources
    python -m scripts.seed --admin-email admin@example.com --admin-password secret
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import func, select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import get_logger  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ingestion.discovery import (  # noqa: E402
    detect_ats_slugs_from_pages,
    discover_from_yc,
    probe_ats_boards,
    workday_config,
)
from app.ingestion.http_client import PoliteClient  # noqa: E402
from app.models import JobListing, JobSource, Startup, User  # noqa: E402
from app.models.enums import Role, VerificationStatus  # noqa: E402
from app.services.taxonomy import slugify  # noqa: E402

log = get_logger(__name__)

# Public aggregator feeds — each has a documented, unauthenticated JSON endpoint.
AGGREGATOR_SOURCES: list[dict] = [
    {
        "name": "RemoteOK",
        "slug": "remoteok",
        "connector_type": "remoteok",
        "base_url": "https://remoteok.com/api",
        "priority": 60,
        "interval_minutes": 60,
    },
    {
        "name": "Arbeitnow",
        "slug": "arbeitnow",
        "connector_type": "arbeitnow",
        "base_url": "https://www.arbeitnow.com/api/job-board-api",
        "priority": 60,
        "interval_minutes": 120,
    },
    {
        "name": "Himalayas",
        "slug": "himalayas",
        "connector_type": "himalayas",
        "base_url": "https://himalayas.app/jobs/api",
        "priority": 60,
        "interval_minutes": 120,
    },
    {
        "name": "Hacker News — Who is hiring",
        "slug": "hackernews",
        "connector_type": "hackernews",
        "base_url": "https://news.ycombinator.com/item?id=whoishiring",
        "priority": 70,
        "interval_minutes": 360,
    },
]

# Domains of Indian and Gujarat-based startups whose job boards we probe live.
# Every entry is verified at runtime — a domain that no longer resolves simply
# produces no source, and nothing is ever fabricated.
CANDIDATE_DOMAINS: list[str] = [
    # Gujarat / Ahmedabad ecosystem
    "okcredit.com",
    "khatabook.com",
    "perfios.com",
    "zetwerk.com",
    "mobisy.com",
    "chargezone.in",
    "sattrix.in",
    "easiwealth.com",
    "upgrad.com",
    "euphoria.in",
    "onecard.in",
    "pesto.com",
    "morpheus.in",
    "quantiphi.com",
    "virajtech.in",
    "ebizmarts.com",
    "fulfil.io",
    "shippingbox.in",
    "safeshop.in",
    "olxgroup.com",
    "tcs.com",
    "infosys.com",
    "wipro.com",
    "hcltech.com",
    "techmahindra.com",
    "lti.com",
    "ibm.com",
    "sabre.com",
    "adyen.com",
    "visa.co.in",
    "mastercard.co.in",
    "paytm.com",
    "phonepe.com",
    "mobikwik.com",
    "freecharge.com",
    "zerodha.com",
    "upstox.com",
    "indigo.io",
    "cleartrip.com",
    "makemytrip.com",
    "ease-my-trip.com",
    "redbus.in",
    "goibibo.com",
    "oyorooms.com",
    "spinny.com",
    "cardekho.com",
    "stamped.in",
    "grofers.com",
    "bigbasket.com",
    "blinkit.com",
    "swiggy.com",
    "zomato.com",
    "eatsure.com",
    "boat.com",
    "noise.tech",
    "boult.com",
    "ambrane.com",
    "nykaa.com",
    "mamaearth.in",
    "beardo.in",
    "plumgoodness.com",
    "minimalist.com",
    "tata.com",
    "tata1mg.com",
    "jiocloud.com",
    "tatanow.com",
    "mahindra.com",
    "acefinserv.com",
    "hdfcbank.com",
    "icici.com",
    "axisbank.com",
    "kotak.com",
    "nseindia.com",
    "bseindia.com",
    "justdial.com",
    "magicbricks.com",
    "99acres.com",
    "housing.com",
    "nobrokerage.com",
    "healthkart.com",
    "practo.com",
    "netmeds.com",
    "apollohospitals.com",
    "fortishealthcare.com",
    "manipalhospitals.com",
    "docsapp.com",
    "lybrate.com",
    "tatahealth.com",
    "curefit.com",
    "healthifyme.com",
    # India-wide startups and product companies
    "cred.club",
    "razorpay.com",
    "cashfree.com",
    "clear.co.in",
    "groww.in",
    "meesho.com",
    "mindtickle.com",
    "setu.co",
    "zephr.com",
    "chargebee.com",
    "hasura.io",
    "vapi.ai",
    "trychroma.com",
    "epifi.com",
    "slice.com",
    "credible.com",
    "browserstack.com",
    "freshworks.com",
    "sprinklr.com",
    "uniphore.com",
    "gupshup.com",
    "innovaccer.com",
    "observe.ai",
    "madstreetden.com",
    "elasticrun.com",
    "exotel.com",
    "plivo.com",
    "twilio.com",
    "apollo.io",
    "postman.com",
    "sentry.io",
    "airbyte.io",
    "retool.com",
    "render.com",
    "railway.app",
    "convex.dev",
    "clerk.com",
    "posthog.com",
    "cal.com",
    "unkey.com",
    "turso.tech",
    "medusajs.com",
    "plane.so",
    "chatwoot.com",
    "formbricks.com",
    "appwrite.io",
    "supabase.com",
    "dub.co",
    "tldraw.com",
    "excalidraw.com",
    "framer.com",
    "linear.app",
    "descript.com",
    "replicate.com",
    "modal.com",
    "together.ai",
    "groq.com",
    "deepgram.com",
    "assemblyai.com",
    "sarvam.ai",
    "jupiter.money",
    "fi.com",
    "getunicards.com",
    "goibibo.com",
    "learnyuga.com",
    "greatlearning.com",
    "simplilearn.com",
    "geeksforgeeks.org",
    "scalerschool.com",
    "newtonschool.io",
    "codingninjas.com",
    "apna.co",
    "naukri.com",
    "cutshort.io",
    "wellfound.com",
    "internshala.com",
    "foundersmint.com",
    "leadquared.com",
    "zoho.com",
]


async def ensure_aggregator_sources(session, client: PoliteClient | None = None) -> None:
    """Register the public feeds, skipping any whose robots.txt forbids reading them."""
    for spec in AGGREGATOR_SOURCES:
        existing = (
            await session.execute(select(JobSource).where(JobSource.slug == spec["slug"]))
        ).scalar_one_or_none()
        if client is not None:
            allowed = await client._robots_allows(spec["base_url"])
            if not allowed:
                log.warning("source_skipped_robots", slug=spec["slug"], url=spec["base_url"])
                # A previously registered source must not be brought back to
                # life just because the seed script was run again.
                if existing is not None and existing.is_active:
                    existing.is_active = False
                continue
        if existing is not None:
            if not existing.is_active:
                existing.is_active = True
            continue
        config = {"connector_type": spec["connector_type"]}
        session.add(
            JobSource(
                name=spec["name"],
                slug=spec["slug"],
                connector_type=spec["connector_type"],
                base_url=spec["base_url"],
                config=config,
                is_active=True,
                priority=spec["priority"],
                interval_minutes=spec["interval_minutes"],
                notes="Public JSON feed",
            )
        )
        log.info("source_created", slug=spec["slug"])
    await session.commit()


async def ensure_admin(session, email: str, password: str, name: str) -> None:
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        if existing.role != Role.ADMIN:
            existing.role = Role.ADMIN
            await session.commit()
            log.info("admin_promoted", email=email)
        return
    session.add(
        User(
            email=email,
            password_hash=hash_password(password),
            full_name=name,
            role=Role.ADMIN,
            is_active=True,
            is_verified=True,
        )
    )
    await session.commit()
    log.info("admin_created", email=email)


async def discover_and_register(
    session,
    client: PoliteClient,
    probe_client: PoliteClient | None = None,
    limit_domains: int = 120,
) -> dict:
    """Discover companies and register any job boards we can reach."""
    companies = await discover_from_yc(
        client, queries=["india", "gujarat", "ahmedabad", "gandhinagar"], max_pages=3
    )
    log.info("companies_discovered", count=len(companies))

    created_companies = 0
    domains: list[str] = []
    for company in companies:
        slug = slugify(company.name)
        exists = (await session.execute(select(Startup).where(Startup.slug == slug))).scalar_one_or_none()
        if exists is None:
            session.add(
                Startup(
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
                    funding_stage=company.extra.get("funding_stage"),
                )
            )
            created_companies += 1
        if company.website:
            domains.append(company.website)
    await session.commit()

    # Merge curated domains with discovered ones, then probe each for job boards.
    all_domains = list(dict.fromkeys(CANDIDATE_DOMAINS + domains))[:limit_domains]
    log.info("probing_ats_boards", domains=len(all_domains))

    hits_total = 0
    semaphore = asyncio.Semaphore(6)

    async def probe_one(domain: str) -> list[dict]:
        async with semaphore:
            name = domain.split("/")[0].split(".")[0].replace("-", " ").title()
            try:
                page_slugs = await detect_ats_slugs_from_pages(client, f"https://{domain}")
                return await probe_ats_boards(probe_client, name, domain, extra_slugs=page_slugs)
            except Exception as exc:
                log.warning("probe_failed", domain=domain, error=str(exc)[:200])
                return []

    probed = await asyncio.gather(*(probe_one(domain) for domain in all_domains))

    for domain, hits in zip(all_domains, probed, strict=False):
        for hit in hits:
            source_slug = (
                f"workday-{hit['slug'].split('|')[0]}"
                if hit["kind"] == "workday"
                else f"{hit['kind']}-{hit['slug']}"
            )
            exists = (
                await session.execute(select(JobSource).where(JobSource.slug == source_slug))
            ).scalar_one_or_none()
            if exists is not None:
                continue
            startup = (
                await session.execute(
                    select(Startup).where(Startup.website.ilike(f"%{domain}%"))
                )
            ).scalars().first()
            if hit["kind"] == "workday":
                config = workday_config(hit["slug"])
            else:
                config = {"connector_type": hit["kind"]}
                if hit["kind"] == "greenhouse":
                    config["board_token"] = hit["slug"]
                else:
                    config["company"] = hit["slug"]
            session.add(
                JobSource(
                    name=f"{hit['kind'].title()} · {hit['slug']}",
                    slug=source_slug,
                    connector_type=hit["kind"],
                    base_url=hit["probe_url"],
                    company_id=startup.id if startup else None,
                    config=config,
                    is_active=True,
                    priority=80,
                    interval_minutes=60,
                    notes=f"Discovered via ATS probe of {domain}",
                )
            )
            hits_total += 1
            log.info("ats_source_registered", source=source_slug, domain=domain, jobs=hit["job_count"])
    await session.commit()
    return {"companies_created": created_companies, "sources_created": hits_total}


async def discover_from_ingested_jobs(session, client, probe_client=None, limit: int = 80) -> dict:
    """Grow the directory from companies we have already seen hiring.

    Every ingested listing carries the employer's own domain. We use it to
    find their ATS board (and therefore their full, structured job list) and
    to create a company record.
    """
    from urllib.parse import urlparse

    from app.models import JobListing

    probe_client = probe_client or client
    domains: dict[str, str] = {}
    stmt = (
        select(JobListing.company_name, JobListing.apply_url, JobListing.geo_scope)
        .where(JobListing.geo_scope.in_(["ahmedabad", "gujarat", "india_remote", "india"]))
        .limit(4000)
    )
    rows = (await session.execute(stmt)).all()
    for company, apply_url, _scope in rows:
        if not apply_url:
            continue
        host = urlparse(apply_url).netloc.lower()
        if not host or host.startswith("www."):
            host = host[4:]
        if "." not in host or host.endswith("ycombinator.com"):
            continue
        domains.setdefault(host, company)

    probe_client = probe_client or client
    log.info("discovering_from_jobs", domains=len(domains))

    created_sources = 0
    created_companies = 0
    semaphore = asyncio.Semaphore(6)

    async def probe_one(domain: str, company_name: str) -> list[dict]:
        async with semaphore:
            try:
                page_slugs = await detect_ats_slugs_from_pages(client, f"https://{domain}")
                return await probe_ats_boards(probe_client, company_name, domain, extra_slugs=page_slugs)
            except Exception as exc:
                log.warning("probe_failed", domain=domain, error=str(exc)[:200])
                return []

    items = list(domains.items())[:limit]
    probed = await asyncio.gather(*(probe_one(domain, name) for domain, name in items))

    for (domain, company_name), hits in zip(items, probed, strict=False):
        for hit in hits:
            source_slug = f"{hit['kind']}-{hit['slug']}"
            exists = (
                await session.execute(select(JobSource).where(JobSource.slug == source_slug))
            ).scalar_one_or_none()
            if exists is not None:
                continue
            if hit["kind"] == "workday":
                config = workday_config(hit["slug"])
            else:
                config = {"connector_type": hit["kind"]}
                if hit["kind"] == "greenhouse":
                    config["board_token"] = hit["slug"]
                else:
                    config["company"] = hit["slug"]
            session.add(
                JobSource(
                    name=f"{hit['kind'].title()} · {hit['slug']}",
                    slug=source_slug,
                    connector_type=hit["kind"],
                    base_url=hit["probe_url"],
                    config=config,
                    is_active=True,
                    priority=80,
                    interval_minutes=60,
                    notes=f"Discovered from the application link of {company_name}",
                )
            )
            created_sources += 1
            log.info("ats_source_registered", source=source_slug, domain=domain, jobs=hit["job_count"])

        # Make sure a company record exists for the domain.
        slug = slugify(company_name)
        if slug:
            existing = (
                await session.execute(select(Startup).where(Startup.slug == slug))
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    Startup(
                        name=company_name[:200],
                        slug=slug,
                        website=f"https://{domain}",
                        industry="Other technology startups",
                        hq_country="India",
                        discovery_source="ingestion_reconciliation",
                        verification_status="unverified",
                    )
                )
                created_companies += 1
    await session.commit()
    return {"sources_created": created_sources, "companies_created": created_companies}


async def ingest_all(session, client: PoliteClient, limit: int = 60) -> dict:
    from app.ingestion.base import ConnectorContext
    from app.ingestion.pipeline import IngestionStats, JobIngestionPipeline
    from app.ingestion.registry import build_connector

    sources = (
        await session.execute(select(JobSource).where(JobSource.is_active.is_(True)).limit(limit))
    ).scalars().all()

    totals = {"found": 0, "created": 0, "updated": 0, "duplicates": 0, "sources": 0}
    for source in sources:
        config = dict(source.config or {})
        config["client"] = client
        config.setdefault("connector_type", source.connector_type)
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
        except Exception as exc:
            log.warning("ingest_failed", source=source.slug, error=str(exc))
            continue
        stats = IngestionStats()
        stats.found = len(raw_jobs)
        pipeline = JobIngestionPipeline(session, stats)
        await pipeline.ingest_raw_jobs(raw_jobs, source=source, startup_id=source.company_id)
        await session.commit()
        totals["found"] += stats.found
        totals["created"] += stats.created
        totals["updated"] += stats.updated
        totals["duplicates"] += stats.duplicates
        totals["sources"] += 1
        log.info(
            "ingested",
            source=source.slug,
            found=stats.found,
            created=stats.created,
            updated=stats.updated,
            duplicates=stats.duplicates,
        )
    return totals


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-ingest", action="store_true", help="skip ingestion")
    parser.add_argument("--no-discover", action="store_true", help="skip company discovery")
    parser.add_argument("--admin-email", default=os.getenv("ADMIN_EMAIL", "admin@ahmedabadstartupjobs.com"))
    parser.add_argument("--admin-password", default=os.getenv("ADMIN_PASSWORD", "ChangeMe123!"))
    parser.add_argument("--admin-name", default="Platform Admin")
    args = parser.parse_args()

    async with SessionLocal() as session:
        async with PoliteClient(rate_limit_per_host=30) as boot_client:
            await ensure_aggregator_sources(session, boot_client)
        await ensure_admin(session, args.admin_email, args.admin_password, args.admin_name)

        summary: dict = {}
        async with PoliteClient(rate_limit_per_host=30) as client, PoliteClient(
            rate_limit_per_host=90
        ) as probe_client:
            if not args.no_discover:
                summary.update(await discover_and_register(session, client, probe_client))
                summary.update(await discover_from_ingested_jobs(session, client, probe_client))
            if not args.no_ingest:
                summary.update(await ingest_all(session, client))

        total_jobs = (
            await session.execute(select(func.count(JobListing.id)))
        ).scalar_one()
        summary["total_jobs"] = total_jobs
        summary["total_startups"] = (
            await session.execute(select(func.count(Startup.id)))
        ).scalar_one()
        log.info("seed_complete", **summary)
        print(f"Seed complete: {summary}")


if __name__ == "__main__":
    asyncio.run(main())
