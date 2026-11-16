# Architecture

## 1. System overview

```
                    ┌──────────────────────┐
                    │  Public job boards   │
                    │  ATS APIs, career     │
                    │  pages, feeds, HN     │
                    └──────────┬───────────┘
                               │ HTTP (robots-aware, rate-limited)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Celery worker                                                       │
│  ┌────────────────┐   ┌───────────────┐   ┌──────────────────────┐   │
│  │ Connector      │──►│ Normaliser    │──►│ Dedup + persistence  │   │
│  │ registry       │   │ (geo, skills, │   │ (savepoints, refs)   │   │
│  └────────────────┘   │  exp, salary) │   └──────────┬───────────┘   │
│                        └───────────────┘              │               │
└───────────────────────────────────────────────────────┼───────────────┘
                                                        ▼
                                             ┌─────────────────────┐
                                             │  PostgreSQL         │
                                             │  22 tables + JSONB  │
                                             └──────────┬──────────┘
                                                        │
┌───────────────────────────────────────────────────────┼───────────────┐
│  FastAPI                                              │               │
│  ┌───────────┐ ┌──────────┐ ┌────────┐ ┌───────────┐  │               │
│  │ /jobs     │ │/startups │ │/stats  │ │/me,admin │  │               │
│  └───────────┘ └──────────┘ └────────┘ └───────────┘  │               │
│  ┌──────────────────────────────────────────────┐     │               │
│  │ SSE /events ── live ingestion events ───────┼─────┘               │
│  └──────────────────────────────────────────────┘                     │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │  Next.js frontend   │
                        │  SSR + ISR + client │
                        │  query cache        │
                        └─────────────────────┘
```

## 2. Backend layout

```
backend/app/
├── core/            config, structured logging, password hashing, JWT
├── db/              engine, session factory, declarative base + mixins
├── models/          SQLAlchemy models grouped by domain
│   ├── enums.py         canonical vocabularies (industry, employment, scope…)
│   ├── user.py          users, profiles, saved items, alerts, applications
│   ├── startup.py       startups, founders, funding rounds
│   ├── job.py           job listings, sources, references, skills, categories
│   └── ingestion.py     runs, errors, source health, company verification
├── schemas.py       Pydantic request/response models
├── services/
│   ├── geo.py           city → state → country resolution, geo scopes
│   ├── taxonomy.py      skill catalogue, job categories, industry rules
│   ├── normalizer.py    pure text → canonical job
│   ├── dedup.py         duplicate detection rules
│   ├── matching.py      candidate ↔ job scoring
│   ├── analytics.py     measured dashboard statistics and trends
│   └── ai.py            optional LLM layer + rule-based fallback
├── ingestion/
│   ├── base.py          Connector contract and RawJob DTO
│   ├── http_client.py   robots-aware, rate-limited, retrying HTTP client
│   ├── registry.py      connector_type → implementation
│   ├── discovery.py     company discovery and ATS board probing
│   ├── pipeline.py      normalisation → dedup → persistence
│   └── connectors/      one module per source family
├── workers/         Celery app, tasks, beat schedule, notifications
├── realtime/        in-process pub/sub → Server-Sent Events
└── api/             FastAPI routers and dependencies
```

## 3. Database design

22 tables. Every table has UUID primary keys, `created_at`/`updated_at` timestamps, and foreign
keys with explicit delete behaviour.

### Core entities

| Table | Purpose | Notable constraints |
|---|---|---|
| `users` | Accounts, roles, Google identity | unique email, unique google_id |
| `candidate_profiles` | Skills, experience, preferences, resume | 1:1 with users |
| `startups` | Companies | unique slug, industry/HQ indexes, soft delete |
| `startup_founders` | Public founders | FK cascade |
| `startup_funding` | Funding rounds | unique (startup, round, date) |
| `job_listings` | Every opening | unique slug, `dedup_key` index, status + geo_scope indexes |
| `job_sources` | Registered sources | unique slug, priority, interval, health counters |
| `job_source_references` | A job's presence on each source | unique (job, source, external id) |
| `skills` | Canonical skill catalogue | unique name + slug |
| `job_skills` | Job ↔ skill with confidence | unique (job, skill) |
| `job_categories` | Job ↔ category with confidence | unique (job, category) |
| `saved_jobs` / `saved_startups` | Bookmarks | unique (user, entity) |
| `job_alerts` | User alert definitions | JSONB filters |
| `saved_searches` | Saved filter sets | JSONB filters |
| `job_applications` | Application tracking | unique (user, job) |
| `user_job_views` | Recently viewed | append-only |
| `notifications` | In-app + emailed alerts | read flag |
| `ingestion_runs` | One row per source execution | counters for found/created/updated/duplicates |
| `ingestion_errors` | Failure detail with traceback | FK to run |
| `source_health` | Rolling health per source | success rate, avg duration, last error |
| `company_verification` | Evidence for a company record | JSONB evidence, verifier, timestamp |

### Indexing strategy

- `job_listings(status, posted_at)` — the default listing query.
- `job_listings(geo_scope, status)` — geography filtering.
- `job_listings(dedup_key)` — cheap pre-filter before the similarity comparison.
- `job_listings(source_id)` — per-source reconciliation and expiry.
- `job_skills(skill_id)` + `skills(name)` — facet counts and skill filters.
- `startups(industry)`, `startups(hq_city)`, `startups(hiring_status)` — directory facets.
- `saved_jobs(user_id)`, `job_alerts(user_id)`, `notifications(user_id, is_read)` — candidate views.

### Scale characteristics

The hot paths are (a) the job search query, (b) facet aggregation and (c) ingestion writes.
Pagination is offset-based, which is fine to ~100k rows per filter; beyond that the same
composable filters can be served by keyset pagination on `(posted_at, id)` without changing the
API shape. Bulk ingestion writes one row per job plus skill/category links; indexes are kept
narrow and JSONB payload columns are trimmed before storage.

## 4. Geospatial model

Raw location strings are resolved by `services/geo.py` into:

| Field | Meaning |
|---|---|
| `location_raw` | Exactly what the employer wrote |
| `location_city` / `location_state` / `location_country` | Resolved values |
| `geo_scope` | One of `ahmedabad`, `gujarat`, `india_remote`, `india`, `global`, `other` |

The gazetteer covers Gujarat cities (Ahmedabad, Gandhinagar, GIFT City, Sanand, Dholera,
Surat, Vadodara, Rajkot…) and the major Indian technology hubs, so a bare `"bengaluru"` or
`"S.G. Highway"` still resolves to the right state. `geo_scope` drives the default listing
filter and is exposed as a facet so users can widen it to all of India or to remote-anywhere.

## 5. Ingestion flow

```
discover → register source → fetch → normalise → dedupe → persist → verify → publish
```

1. **Discover** — company websites are read (robots permitting) to find career pages and ATS
   board identifiers. Boards are confirmed by fetching them.
2. **Register** — each confirmed board becomes a row in `job_sources` with its connector type
   and configuration.
3. **Fetch** — the connector returns `RawJob` DTOs using the source's own vocabulary.
4. **Normalise** — `services/normalizer.py` maps everything onto the canonical schema.
5. **Dedupe** — cross-source comparison; duplicates attach a new `job_source_references` row to
   the existing job instead of creating a second record.
6. **Persist** — inside a SAVEPOINT per job, so one malformed listing cannot abort a run.
7. **Verify** — application URLs are re-checked on a daily schedule; unseen listings go stale,
   then expired.

## 6. Real-time updates

`realtime/events.py` is an in-process broker with bounded per-subscriber queues. Ingestion
publishes `jobs.discovered` and `companies.discovered` events; `GET /api/v1/events` streams them
as Server-Sent Events. The frontend's `LiveIndicator` subscribes and shows the activity count.

For a multi-process deployment, swap the broker for Redis pub/sub — the interface is a single
class with `publish`, `subscribe` and `stream`.

## 7. Frontend

- Server components fetch directly from the API with ISR (`revalidate` windows of 2–5 minutes) so
  job and startup pages are crawlable and fast.
- Client components use TanStack Query for interactive search, filters, dashboards.
- Job pages emit `schema.org/JobPosting`; company pages emit `schema.org/Organization`.
- Dark/light themes are CSS-variable based with a `prefers-color-scheme` fallback.

## 8. Security

- Passwords hashed with bcrypt (72-byte truncation, as bcrypt requires).
- JWT access + refresh tokens; the refresh token is stored in an `httpOnly`, `SameSite=Lax`
  cookie scoped to the auth path.
- Google sign-in exchanges an ID token server-side and is disabled unless
  `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` are set.
- Admin routes require the `admin` role; every write route takes the authenticated user as a
  dependency, so ownership checks are explicit.
- CORS is restricted to `CORS_ORIGINS`.

## 9. Observability

- `structlog` for structured, JSON-in-production logging.
- Every ingestion run records counters and duration in `ingestion_runs`; failures land in
  `ingestion_errors` with the traceback.
- `source_health` keeps success rate, consecutive failures, average duration and the last error.
- The admin console surfaces all of it, plus `pg_database_size` for database health.
