# Roadmap

Delivery is tracked against the five phases in the product specification. The status below
reflects what is implemented and running in this repository.

## Phase 1 — Foundation ✅

- [x] Monorepo: `backend/` (FastAPI) + `frontend/` (Next.js) + Docker Compose + CI
- [x] Normalised PostgreSQL schema — 22 tables with keys, indexes, unique constraints,
      timestamps, soft deletion and Alembic migrations
- [x] Authentication: email/password (bcrypt + JWT access/refresh), Google OAuth (opt-in)
- [x] Startup directory: company profiles, founders, funding, tech stack, filters and facets
- [x] Job board: listing cards, detail pages, source attribution, verification badges
- [x] SEO: per-job and per-company pages, `JobPosting` / `Organization` structured data,
      sitemap, robots

## Phase 2 — Data intelligence ✅

- [x] 13 connectors: Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday, RemoteOK,
      Remotive, Arbeitnow, Jobicy, Himalayas, Hacker News "Who is hiring", career pages
- [x] Company discovery: ATS board probing, career-page link detection, self-reinforcing
      discovery from ingested jobs
- [x] Normalisation: title, experience, employment type, work arrangement, salary,
      responsibilities, qualifications, skills, categories, geo scope
- [x] De-duplication: application URL, company + title + location + description similarity —
      never on title alone; every source reference retained
- [x] Verification: daily link checks, stale → expired lifecycle, per-listing freshness
- [x] Source transparency page (`/sources`) and machine-readable `/sources/stats`

## Phase 3 — Automation ✅

- [x] Celery worker + beat with configurable cadences (15 min / hourly / 6 h / daily)
- [x] Retry with exponential backoff, per-host rate limiting, robots-aware fetching
- [x] Ingestion history (`ingestion_runs`), failure log (`ingestion_errors`), source health
- [x] Server-Sent Events push of live ingestion events to the browser
- [x] "Last updated" timestamps, and a visible difference between newly discovered and
      recently verified listings
- [x] Admin controls to trigger a run, pause a source and inspect failures

## Phase 4 — AI ✅ (optional, works without a provider)

- [x] Skill extraction with a curated catalogue and alias map
- [x] Job categorisation, experience and employment-type classification
- [x] AI job summaries (rule-based extractive fallback when no LLM is configured)
- [x] Candidate matching with explainable scores (skill overlap + experience compatibility)
- [x] Hiring intelligence: measured trends (companies hiring, skill demand with change,
      industry activity) kept strictly separate from AI interpretation
- [x] Semantic search — *roadmap item*: `pgvector` is provisioned but embeddings are not yet
      generated. Full-text `ILIKE` search ships today

## Phase 5 — Production ✅

- [x] Admin dashboard: ingestion overview, source management, health, verification queue,
      company merge, CSV import
- [x] SEO and performance: ISR, dynamic metadata, sitemap, structured data, image-free
      layout with system font fallbacks
- [x] Tests: 96 backend tests (unit, API, connector, pipeline) + frontend lint and type-check
- [x] Deployment: Dockerfiles, Compose, Nginx, CI, backup and restore documentation

## Next milestones

| Priority | Item | Why |
|---|---|---|
| High | **Gujarat-specific coverage** | Ahmedabad and Gujarat openings are the product's centre of gravity. The next discovery push targets Gujarat startup career pages (which mostly render listings via client-side XHR rather than exposing an ATS or `JobPosting` markup), plus GIFT City tenants. |
| High | **pgvector semantic search** | Embed job descriptions and titles so "backend role that works with payments" matches roles that never say "payments". Requires a background embedding task and an ANN index. |
| High | **Alert delivery over email and WhatsApp** | Email works when SMTP is configured; WhatsApp needs a business account and template approval. |
| Medium | **Saved-search digest** | A weekly or monthly digest for saved searches, not just instant alerts. |
| Medium | **Company funding data** | Funding rounds are modelled but not yet populated from a verified public source. |
| Medium | **Resume parsing** | Extract skills from an uploaded PDF so the profile can be completed automatically. |
| Medium | **Redis-backed SSE broker** | Required before running more than one API replica. |
| Low | **OpenSearch / Elasticsearch** | Only worth it once listing volume justifies it; PostgreSQL full-text search with trigram indexes covers the current scale. |
| Low | **Public API keys** | Rate-limited API keys for third parties who want to query the board. |

## Known limitations

- **Client-side-rendered career pages.** Several large Indian companies load their job lists via
  XHR and expose neither an ATS identifier nor `JobPosting` markup, so they cannot be read
  without a headless browser. The `career_page` connector handles the standards-compliant
  cases; a Playwright-based connector would extend coverage, subject to each site's terms.
- **robots.txt is treated as binding.** Some sources that would widen India coverage are not
  read because their `robots.txt` disallows automated access. The YC directory connector exists
  but is off by default for the same reason.
- **Offset pagination.** Fine to roughly 100k rows per filter; beyond that, switch the job
  search to keyset pagination on `(posted_at, id)`.
- **In-process event broker.** A single API replica only; see the scaling notes.
