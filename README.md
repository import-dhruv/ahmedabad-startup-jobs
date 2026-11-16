# Ahmedabad Startup Jobs

**Every Ahmedabad startup. Every hiring opportunity. One platform. Always up to date.**

A production-grade, real-time startup hiring intelligence platform for Ahmedabad, Gandhinagar,
GIFT City, Sanand and the wider Gujarat startup ecosystem — plus remote roles that Indian
candidates can apply to.

**Live at https://ahmedabad-startup-jobs.vercel.app** — 1,900+ real openings from 24 public job
boards, refreshed every 15 minutes.

**Source: https://github.com/import-dhruv/ahmedabad-startup-jobs**

The platform continuously discovers companies and their job boards, ingests openings from public
APIs and career pages, normalises and de-duplicates them, verifies that application links still
resolve, and publishes the result with full source attribution.

---

## What it does

| Capability | Status |
|---|---|
| Real-time job ingestion from public sources | Greenhouse, Lever, Ashby, Workable, SmartRecruiters, RemoteOK, Remotive, Arbeitnow, Jobicy, Himalayas, Hacker News "Who is hiring", schema.org career pages |
| Company discovery | ATS board probing from live company sites + career-page link detection + self-reinforcing discovery from ingested jobs |
| Normalisation | Title, experience, employment type, work arrangement, salary, skills, responsibilities, qualifications |
| De-duplication | Application URL, company + title + location + description similarity — never on title alone |
| Verification | Daily link checks, stale → expired lifecycle, per-listing source and freshness indicator |
| Search | Free text, skills, experience, employment type, arrangement, city, industry, salary, geo scope, sorting, pagination, facets |
| Candidate features | Profiles, resume upload, saved jobs, saved startups, job alerts, application tracking, recommended jobs with explainable scores |
| Admin | Source management, ingestion monitoring, source health, verification queue, company merge, CSV import |
| AI layer | Skills extraction, job classification, summaries, hiring interpretation — optional, clearly labelled, works without an API key |
| SEO | JobPosting + Organization structured data, per-job and per-company pages, sitemap, robots |
| Deployment | Frontend live on Vercel; API, workers, PostgreSQL and Redis on this host behind a tunnel |

---

## Architecture

```
┌────────────────┐    HTTPS/SSE    ┌────────────────────┐    async SQLAlchemy    ┌──────────────┐
│  Next.js 16    │ ──────────────► │  FastAPI           │ ─────────────────────► │ PostgreSQL 16│
│  App Router    │ ◄────────────── │  REST + SSE        │                        │ + pgvector   │
│  Tailwind v4   │   live events   └────────────────────┘                        └──────────────┘
└────────────────┘                          │                                           ▲
                                            │ Celery (Redis broker)                      │
                                   ┌────────┴─────────┐                                 │
                                   │  Worker + Beat   │ ── ingestion connectors ─────────┘
                                   │  scheduled sync  │
                                   └──────────────────┘
```

- **Frontend** — Next.js (App Router), TypeScript, Tailwind CSS v4, shadcn-style components,
  TanStack Query, Recharts, Framer Motion, Radix UI.
- **Backend** — FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic, Celery, Redis, httpx.
- **Database** — PostgreSQL with 22 normalised tables, JSONB payloads, trigram/FTS-ready indexes.
- **Ingestion** — Modular connectors behind a registry; a new source is one class plus one row.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

---

## Quick start

### 1. Requirements

- Docker 24+ and Docker Compose v2
- (Optional) Python 3.12+ and Node 22+ if you want to run the services outside Docker

### 2. Configure

```bash
cp .env.example .env
# Generate a strong secret
python -c "import secrets; print(secrets.token_hex(32))"   # paste into SECRET_KEY
```

### 3. Start the stack

```bash
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose up -d api worker beat frontend
```

The API is on <http://localhost:8000> (docs at `/docs`), the app on <http://localhost:3000>.

### 4. Seed with real data

```bash
docker compose exec api python -m scripts.seed
```

This registers the public sources, discovers companies, probes their job boards, ingests the
openings and reconciles company records. It is idempotent — re-running it updates rather than
duplicates.

### 5. Create an administrator

```bash
docker compose exec api python -m scripts.seed --no-ingest --no-discover \
  --admin-email you@example.com --admin-password 'YourStrongPassword'
```

The admin console lives at <http://localhost:3000/admin>.

---

## Local development without Docker

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ahmedabad_jobs
alembic upgrade head
uvicorn app.main:app --reload

# Worker + scheduler (separate terminals)
celery -A app.workers.celery_app.celery_app worker --loglevel=info
celery -A app.workers.celery_app.celery_app beat --loglevel=info

# Frontend
cd ../frontend
npm install
npm run dev
```

---

## Scheduled ingestion

| Task | Default cadence | What it does |
|---|---|---|
| `run_due_sources` | every 15 minutes | Polls connected job-board APIs and feeds whose interval has elapsed |
| `refresh_source_health` | hourly | Recomputes per-source success rates and job counts |
| `discover_companies` | every 6 hours | Finds new companies and registers their job boards |
| `verify_job_links` | daily | Re-checks application URLs, marks broken links stale |
| `reconcile_job_status` | daily | Moves unconfirmed listings from stale to expired |
| `enrich_jobs_with_ai` | daily | Generates summaries and refines classification |
| `dispatch_job_alerts` | every 10 minutes | Matches new openings against user alerts |

Cadences live in `backend/app/workers/celery_app.py` and are configurable per source in the
`job_sources` table.

---

## Data-quality guarantees

- Every listing stores the **exact URL** it was read from.
- Every listing records **when it was discovered** and **when it was last verified**.
- A listing is only presented as active when its application link resolved during a recent run.
- **Nothing is fabricated** — no invented companies, roles or salary ranges. A source that cannot
  be read yields nothing.
- `robots.txt` is respected with correct longest-match semantics; sources that disallow
  automated access are skipped.
- Company **headquarters** is stored separately from the **job's location**.
- AI-generated content is labelled as generated and kept separate from measured statistics.

---

## Testing

```bash
cd backend && pytest -q        # unit, API, ingestion and pipeline tests
cd frontend && npm run lint && npx tsc --noEmit
```

The backend suite covers geo resolution, normalisation, salary/experience/skill extraction,
de-duplication rules, every connector's parsing (using recorded public payloads), the ingestion
pipeline lifecycle (discovery, update, expiry, cross-source duplicates, failed rows), the REST
API, authentication and the admin surface.

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design, data flow, schema |
| [`docs/INGESTION.md`](docs/INGESTION.md) | Connectors, discovery, dedup, verification |
| [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md) | Every source, what it is, and its access terms |
| [`docs/API.md`](docs/API.md) | Endpoint reference |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Production deployment, backups, scaling |
| [`docs/VERCEL.md`](docs/VERCEL.md) | The live Vercel deployment, and how to move the whole stack onto Vercel |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phased delivery plan and current status |

---

## Licence

MIT. Job listings belong to the employers who published them — this platform only indexes them
and always links back to the original source.
