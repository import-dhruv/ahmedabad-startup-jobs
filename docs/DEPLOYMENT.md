# Deployment

## 1. Overview

| Service | Image | Role | Port |
|---|---|---|---|
| `postgres` | postgres:16-alpine | Primary database | 5432 |
| `redis` | redis:7-alpine | Celery broker + result backend | 6379 |
| `api` | built from `backend/Dockerfile` | FastAPI (REST + SSE) | 8000 |
| `worker` | same image | Celery worker | — |
| `beat` | same image | Celery beat scheduler | — |
| `frontend` | built from `frontend/Dockerfile` | Next.js | 3000 |
| `nginx` | nginx:1.27-alpine | Reverse proxy (optional, `production` profile) | 80 |

## 2. Environment variables

Copy `.env.example` to `.env` and set at minimum:

```bash
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=<strong password>
POSTGRES_USER=postgres
POSTGRES_DB=ahmedabad_jobs
DATABASE_URL=postgresql+asyncpg://postgres:<password>@postgres:5432/ahmedabad_jobs
CORS_ORIGINS=https://your-domain.com
NEXT_PUBLIC_API_URL=https://your-domain.com/api/v1
```

Optional integrations (the platform is fully functional without them):

| Variable | Effect when unset |
|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google sign-in is disabled; `/auth/google/config` reports `enabled: false` |
| `OPENAI_API_KEY` + `AI_ENABLED=true` | AI summaries and interpretation are disabled; the rule-based extractor still runs and `/stats/ai-insights` returns an explicit empty state |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` + `EMAIL_ENABLED=true` | Alerts are stored in-app only; no email is sent |

Never commit `.env`. It is in `.gitignore`.

## 3. First deployment

```bash
git clone <your-repo> && cd ahmedabad-startup-jobs
cp .env.example .env
$EDITOR .env

docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose up -d api worker beat frontend
docker compose exec api python -m scripts.seed
```

Check the deployment:

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/api/v1/stats/dashboard
```

## 4. Migrations

```bash
# Apply
docker compose exec api alembic upgrade head

# Create a new migration after changing the models
docker compose exec api alembic revision --autogenerate -m "describe the change"

# Roll back one revision
docker compose exec api alembic downgrade -1
```

The CI workflow applies every migration, rolls it back and re-applies it, so a migration that
cannot round-trip fails the build.

## 5. Seed and operations

```bash
# Full refresh: sources + discovery + ingestion
docker compose exec api python -m scripts.seed

# Sources only
docker compose exec api python -m scripts.seed --no-ingest --no-discover

# Discovery only
docker compose exec api python -m scripts.seed --no-ingest

# Register an additional source
docker compose exec api python -m scripts.register_source \
  --name "Workday · Acme" --slug workday-acme --connector-type workday \
  --config '{"tenant": "acme", "region": "wd1", "site": "careers_at_acme"}'

# Reconcile company records with ingested jobs
docker compose exec api python -m scripts.reconcile_startups

# Create or promote an administrator
docker compose exec api python -m scripts.seed --no-ingest --no-discover \
  --admin-email admin@example.com --admin-password 'StrongPassword123!'
```

## 6. Scaling

**API** — stateless. Scale with `--scale api=4`. Behind a load balancer, enable the sticky
session flag only if you replace the in-process SSE broker with Redis pub/sub.

**Workers** — `--scale worker=4`. The worker is I/O bound, so it scales almost linearly. Give
Celery its own queue (`-Q ingestion`) if ingestion latency matters more than throughput.

**Beat** — run exactly one instance. It only enqueues tasks.

**Database** — the read path is index-backed; add a read replica when the dashboard and job
search are under load. Keep `pg_stat_statements` enabled to find the queries that need
indexing.

**SSE** — the current broker is in-process. With multiple API replicas, replace
`app/realtime/events.py` with a Redis pub/sub implementation (the interface is three methods).

## 7. Backups

```bash
# Nightly logical backup
docker compose exec -T postgres pg_dump -U postgres -Fc ahmedabad_jobs > "backup-$(date +%F).dump"

# Restore
cat backup-2026-01-01.dump | docker compose exec -T postgres pg_restore -U postgres -d ahmedabad_jobs --clean --if-exists
```

For continuous protection, use WAL-G or pgBackRest against a managed PostgreSQL service, and
snapshot the Redis volume only if you rely on Celery result state (the platform does not — task
results are transient).

The database is the only stateful component that matters. Resumes live on the API container's
filesystem under `RESUME_STORAGE_PATH`; move that to an S3-compatible bucket for a multi-node
deployment.

## 8. Monitoring

Health endpoints:

- `GET /health` — liveness plus database reachability.
- `GET /ready` — readiness; returns 503 when the database is unreachable.

The admin console at `/admin` surfaces everything operationally important:

- ingestion runs per source with counters and duration;
- source health (success rate, consecutive failures, average duration, last error);
- jobs discovered today, duplicates caught, listings awaiting verification;
- database size.

Structured logs are emitted on stdout (`structlog`; JSON in production). Ship them with your
log aggregator and alert on `source_health.status = 'unhealthy'` and on sustained
`ingestion_runs.status = 'failed'`.

## 9. Security checklist

- [ ] `SECRET_KEY` is a fresh 32-byte random value.
- [ ] `POSTGRES_PASSWORD` is strong and not the default.
- [ ] `CORS_ORIGINS` lists only your real domains.
- [ ] `DEBUG=false` and `ENVIRONMENT=production`.
- [ ] TLS terminated at the load balancer or nginx.
- [ ] The database is not exposed publicly (only the API is).
- [ ] Backups are scheduled and a restore has been tested.
- [ ] `/admin` is reachable only to accounts with the `admin` role.

## 10. Production checklist

- [ ] `docker compose --profile production up -d` (adds nginx).
- [ ] Celery beat is running exactly once.
- [ ] The seed has been run so the board is populated.
- [ ] `robots.txt` and the sitemap are served correctly.
- [ ] Google Search Console has the sitemap submitted.
- [ ] An administrator account exists with a strong password.
