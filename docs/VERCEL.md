# Vercel deployment

## Live deployment

| | |
|---|---|
| Production URL | **https://ahmedabad-startup-jobs.vercel.app** |
| Vercel project | `dhruvs-projects-76a7424c/ahmedabad-startup-jobs` |
| Project root directory | `frontend/` |
| Backend | this host, behind an ngrok tunnel (`API_PROXY_TARGET`) |
| Database | PostgreSQL 16 in Docker on this host |

The browser talks to the Vercel domain; Next.js proxies `/api/*` to `API_PROXY_TARGET`
(server-side, runtime setting). That keeps the backend location out of the build, so the tunnel
URL can change without a rebuild.

### Environment variables (project)

| Variable | Type | Environments | Purpose |
|---|---|---|---|
| `API_PROXY_TARGET` | Secret | Production, Preview | Where the browser's `/api/*` requests are proxied |
| `NEXT_PUBLIC_SITE_URL` | Config | Production, Preview | Canonical URLs and the sitemap |

### Changing the backend URL

```bash
cd frontend
vercel env rm API_PROXY_TARGET --environment production --yes
vercel env add API_PROXY_TARGET --environment production --value "$NEW_URL" --sensitive --yes
vercel deploy --prod --yes
```

---

## What Vercel can and cannot run here

| Piece | Vercel | Notes |
|---|---|---|
| Next.js frontend | Yes | Native. ISR, edge caching, preview deployments |
| FastAPI REST API | Yes | As a service on Fluid compute — but SSE is less reliable on time-boxed functions |
| **Celery worker + beat** | **Yes — Vercel Daemons** | Public Beta on all plans. Built from a Dockerfile, declared under the `daemons` key in `vercel.json`. Cannot receive inbound traffic; pulls work from a queue. |
| PostgreSQL | Marketplace | Neon via the Marketplace — installed from the dashboard |
| Redis | Marketplace | Upstash via the Marketplace — installed from the dashboard |

**Vercel Daemons change the picture.** They are long-running container processes intended
exactly for Celery workers, so a full Vercel deployment is possible:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "frontend": { "root": "frontend/" },
    "backend": { "root": "backend/", "entrypoint": "main:app" }
  },
  "rewrites": [
    { "source": "/api/v1/(.*)", "destination": { "service": "backend" } },
    { "source": "/(.*)", "destination": { "service": "frontend" } }
  ],
  "daemons": {
    "celery_worker": {
      "root": "backend/",
      "entrypoint": "Dockerfile",
      "command": ["celery", "-A", "app.workers.celery_app.celery_app", "worker", "--loglevel=info"],
      "instances": { "bom1": 1 }
    },
    "celery_beat": {
      "root": "backend/",
      "entrypoint": "Dockerfile",
      "command": ["celery", "-A", "app.workers.celery_app.celery_app", "beat", "--loglevel=info"],
      "instances": { "bom1": 1 }
    }
  }
}
```

Constraints that shape this:

- Daemons run on **production deployments only** during the beta — previews never start them.
- A daemon **cannot receive inbound traffic**; only its own liveness probe reaches it. If you
  configure `livenessProbe`, the worker process must serve that endpoint.
- Instances are capped at **1–2 GiB on Hobby**, and Hobby also meters monthly Active CPU and
  Provisioned Memory.
- **A project whose root directory is a subfolder cannot declare daemons.** The current project
  is rooted at `frontend/`, so a full-Vercel move requires re-rooting the project at the repo
  root and using `services`.
- Vercel sends `SIGTERM` on rollout and waits 30 s by default. Ingestion jobs are already
  idempotent (SAVEPOINT per job, upserts by external id), so a restart mid-run is safe.

## The three deployment shapes

### A — Frontend on Vercel, backend on this host (current)

| Piece | Where |
|---|---|
| Next.js frontend | Vercel |
| FastAPI + Celery worker + Celery beat | this host (Docker Compose) |
| PostgreSQL + Redis | this host (Docker Compose) |

SSE live updates, the 15-minute polling and the daily verification all behave normally. The
trade-off is the tunnel: the ngrok free-tier URL is random, so it changes when the tunnel
restarts and the Vercel env var must be updated and redeployed. A reserved ngrok domain, a
Cloudflare named tunnel or a Tailscale Funnel hostname would fix that; all three need a free
account.

### B — Everything on Vercel

| Piece | Where |
|---|---|
| Next.js frontend | Vercel service |
| FastAPI | Vercel service |
| Celery worker + beat | Vercel daemons |
| PostgreSQL + Redis | Marketplace (Neon, Upstash) |

Requires re-rooting the project at the repo root, installing two Marketplace integrations and
moving the database. The result has no tunnel and no home-hosted dependency, but SSE through a
Vercel service is still less reliable than through the local API, and the whole ingestion
pipeline depends on Hobby-plan daemon quotas.

### C — Separate projects

Frontend and backend as two independent Vercel projects. Useful when they need separate release
cadences; the frontend reaches the backend through `NEXT_PUBLIC_API_URL` (public CORS) or a
service binding (private).

---

## Deploying the frontend

```bash
cd frontend
vercel link --yes --project ahmedabad-startup-jobs
vercel env add API_PROXY_TARGET --environment production --value "$API" --sensitive --yes
vercel env add NEXT_PUBLIC_SITE_URL --environment production --value "$SITE" --yes
vercel deploy --prod --yes
```

`scripts/deploy_vercel.sh` does the GitHub push, the link, the env vars and the deploy in one
step.

## Deploying the API as a Vercel service (Option B)

`backend/api/index.py` is a thin ASGI entry point exporting the FastAPI `app`, and
`backend/vercel.json` declares the `@vercel/python` build. The backend service must set
`DATABASE_URL`, `SYNC_DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `CORS_ORIGINS` and
`ENVIRONMENT`; migrations are applied from a machine with database access:

```bash
alembic upgrade head
```

## Verifying a protected deployment

If a deployment has Vercel Authentication enabled, use the CLI's authenticated client rather
than disabling protection:

```bash
vercel curl https://ahmedabad-startup-jobs.vercel.app/api/v1/stats/dashboard
```

For browser automation, attach the short-lived local token as a request header
(`x-vercel-trusted-oidc-idp-token`) instead of disabling protection.

---

## Keeping this host's stack alive

`scripts/serve.sh` starts and supervises the API and the tunnel on this host:

```bash
scripts/serve.sh start      # start the API and open a tunnel
scripts/serve.sh status     # check both
scripts/serve.sh restart    # restart after a tunnel URL change
scripts/serve.sh stop
```

The current tunnel URL is written to `/tmp/ahsj-tunnel-url`.

---

## Checklist

- [x] `NEXT_PUBLIC_API_URL` unset — the browser uses the same-origin `/api/v1` path
- [x] `API_PROXY_TARGET` set for Production and Preview
- [x] `NEXT_PUBLIC_SITE_URL` set for Production and Preview
- [x] Database migrations applied
- [x] Worker and beat scheduler running on this host
- [x] `scripts/serve.sh status` reports a healthy API and tunnel
- [x] Robots policy audited daily by the `robots-policy` Celery beat task
- [x] `scripts/seed.py` run once to populate the board
- [x] An administrator account created (`admin@ahmedabadstartupjobs.com`)
- [x] The GitHub repository pushed and connected to Vercel for auto-deploy
