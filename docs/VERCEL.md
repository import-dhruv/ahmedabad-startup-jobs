# Vercel deployment

Vercel is excellent at the **frontend** and can host the **REST API** as a serverless
function. It cannot run the **ingestion workers** — Celery workers and beat schedulers are
long-lived processes, and Vercel functions are request-scoped and time-boxed.

That matters for this product: without a worker, nothing discovers or refreshes jobs, and the
board slowly goes stale. So there are three viable shapes, in descending order of how much
runs on Vercel.

---

## Option A — Vercel frontend + Vercel API + worker on a long-running host (recommended)

| Piece | Where | Why |
|---|---|---|
| Next.js frontend | Vercel | Native support, ISR, edge caching, preview deploys |
| FastAPI REST API | Vercel (serverless function) | Stateless, scales to zero, fine for search/read |
| Celery worker + beat | Railway / Fly.io / Render / any VPS | Long-running processes |
| PostgreSQL | Neon / Supabase / Railway | Managed, pooled |
| Redis | Upstash / Railway | Managed |

The frontend talks to the API at `NEXT_PUBLIC_API_URL`. The API talks to the same database and
Redis.

**Caveat:** Server-Sent Events are unreliable on Vercel functions (they are bounded by the
function's maximum duration). The live-update indicator will connect and then time out. If that
matters, put the API on the long-running host too — see Option B.

## Option B — Vercel frontend + the whole backend on a long-running host

| Piece | Where |
|---|---|
| Next.js frontend | Vercel |
| FastAPI + Celery worker + Celery beat | Railway / Fly.io / Render / VPS (the existing Docker Compose) |
| PostgreSQL + Redis | Managed or the same host |

Everything in `docker-compose.yml` runs as-is on a Docker-capable host:

```bash
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose up -d api worker beat
```

The frontend on Vercel then points `NEXT_PUBLIC_API_URL` at that host. SSE, the 15-minute
polling and the daily verification all work normally.

**This is the shape the repository is built and documented for.**

## Option C — Everything on Vercel

Only the frontend and the REST API run on Vercel, and the worker runs nowhere. The board keeps
the listings it already has but never updates. Acceptable only as a demo; not acceptable for
the product's promise of "always up to date".

---

## Deploying the frontend

```bash
cd frontend
vercel link                 # or: vercel --prod --yes
vercel env add NEXT_PUBLIC_API_URL production   # https://your-api-host/api/v1
vercel --prod
```

Environment variables:

| Variable | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://api.your-domain.com/api/v1` | Inlined at build time |
| `NEXT_PUBLIC_SITE_URL` | `https://your-frontend-domain.com` | Used for canonical URLs and the sitemap |

## Deploying the API as a Vercel function (Options A and C)

The repository ships `backend/api/index.py`, a thin ASGI entry point:

```bash
cd backend
vercel --prod
```

Environment variables for the API project:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` (Neon/Supabase) |
| `SYNC_DATABASE_URL` | `postgresql+psycopg2://...` (for Alembic) |
| `REDIS_URL` | `redis://...` (Upstash) |
| `SECRET_KEY` | 32 random bytes |
| `CORS_ORIGINS` | your Vercel domain |
| `ENVIRONMENT` | `production` |

Run migrations from a machine with network access to the database:

```bash
alembic upgrade head
```

## Adding the worker to Railway / Fly.io / Render

Point them at the `backend/Dockerfile` and run:

```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=info --concurrency=4
celery -A app.workers.celery_app.celery_app beat --loglevel=info
```

Both need `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.

---

## Checklist

- [ ] `NEXT_PUBLIC_API_URL` set on the Vercel frontend project
- [ ] `NEXT_PUBLIC_SITE_URL` set on the Vercel frontend project
- [ ] CORS on the API allows the Vercel domain
- [ ] Database migrations applied
- [ ] A worker and a beat scheduler are running *somewhere*
- [ ] `scripts/enforce_robots_policy.py` scheduled daily
- [ ] `scripts/seed.py` run once to populate the board
- [ ] An administrator account created
