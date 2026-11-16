# API reference

Base URL: `http://localhost:8000/api/v1` (configurable via `API_PREFIX`).
Interactive docs: `/docs` (Swagger) and `/redoc`.

All responses are JSON. Errors use FastAPI's `{"detail": "..."}` shape.

---

## Jobs

### `GET /jobs`

Search job openings. Every filter is optional and they combine with AND.

| Parameter | Type | Notes |
|---|---|---|
| `q` | string | Free-text across title, company, skills, category and description |
| `company` | string | Company name contains |
| `skills` | string (repeatable) | Matches any of the listed canonical skills |
| `experience` | string (repeatable) | `Fresher`, `0-1 years`, `1-3 years`, `3-5 years`, `5-8 years`, `8+ years` |
| `employment_type` | string (repeatable) | `Full-time`, `Part-time`, `Internship`, `Contract`, `Freelance`, `Apprenticeship` |
| `work_arrangement` | string (repeatable) | `On-site`, `Hybrid`, `Remote` |
| `city` | string | Location city contains |
| `industry` | string (repeatable) | Matches the linked company's industry |
| `min_salary` / `max_salary` | int | Annual amount in the listing's currency |
| `remote` | bool | Remote roles only |
| `internship` | bool | Internships only |
| `scope` | string (repeatable) | `ahmedabad`, `gujarat`, `india_remote`, `india`, `global` (default: all five) |
| `source` | string | Source slug contains |
| `verified_only` | bool | Only listings confirmed recently |
| `posted_within_days` | int | 1–365 |
| `startup_id` | uuid | Restrict to one company |
| `sort` | string | `relevance` (default), `newest`, `oldest`, `salary_high`, `salary_low`, `company` |
| `page` / `per_page` | int | `per_page` max 100 |

**Response**

```json
{
  "items": [ { "id": "…", "slug": "…", "title": "…", "company": { … }, "location": { … },
               "salary": { … }, "skills": ["Python"], "categories": ["Backend Engineering"],
               "verification_status": "verified", "apply_url": "https://…" } ],
  "total": 128,
  "page": 1,
  "per_page": 25,
  "pages": 6,
  "facets": {
    "industries": { "SaaS": 12 },
    "skills": [ { "name": "Python", "category": "Programming", "count": 31 } ],
    "cities": { "Ahmedabad": 14 },
    "geo_scopes": { "Ahmedabad": 14, "Remote (India)": 22 },
    "employment_types": { "Full-time": 90 },
    "experience_levels": { "1-3 years": 40 },
    "work_arrangements": { "Remote": 38 }
  }
}
```

### `GET /jobs/filters`

All filter vocabularies and the current facet values — employment types, experience levels, work
arrangements, job categories, top skills, cities, industries, geo scopes and sort options.

### `GET /jobs/{id}`

Full listing: description, responsibilities, qualifications, skills, salary, deadline, source
references and the linked startup. Requires nothing; when an `Authorization` header is present
the view is recorded.

### `GET /jobs/slug/{slug}`

The same listing addressed by its SEO slug.

---

## Startups

| Endpoint | Notes |
|---|---|
| `GET /startups` | Filters: `q`, `industry`, `hiring_status`, `funding_stage`, `size_range`, `city`, `state`, `has_openings`, `sort` (`recent`, `name`, `openings`, `verified`), `limit`, `offset` |
| `GET /startups/filters` | Industry, funding stage, size range and city counts |
| `GET /startups/{id}` | Company detail |
| `GET /startups/slug/{slug}` | Company detail with founders, funding rounds and current openings |

Company headquarters (`hq_city`, `hq_state`, `hq_country`) is stored separately from the
location of each job.

---

## Statistics

| Endpoint | Returns |
|---|---|
| `GET /stats/dashboard` | Totals: startups, active jobs, new in 24h/7d/30d, companies hiring, internships, remote roles, Ahmedabad and Gujarat counts, source counts, jobs awaiting verification, last sync time |
| `GET /stats/trends?days=30` | Openings published per day |
| `GET /stats/skills` | Skills ranked by openings in the last 60 days with change vs. the previous period |
| `GET /stats/industries` | Openings and company counts per industry |
| `GET /stats/hiring` | Companies ranked by number of open roles |
| `GET /stats/mix` | Employment-type, experience, location and source breakdowns |
| `GET /stats/insights` | Measured hiring insights (company, skill and industry signals) |
| `GET /stats/ai-insights` | AI interpretation, clearly separated from measured data; returns an explicit empty state when no provider is configured |
| `GET /stats/recent-jobs?limit=12` | Most recently discovered openings |
| `GET /stats/recent-startups?limit=12` | Most recently discovered companies |

---

## Authentication

| Endpoint | Purpose |
|---|---|
| `POST /auth/register` | Email + password → tokens and user |
| `POST /auth/login` | Email + password → tokens and user |
| `POST /auth/refresh` | Refresh cookie → new tokens |
| `POST /auth/logout` | Clears the refresh cookie |
| `GET /auth/me` | Current user |
| `GET /auth/google/config` | Whether Google sign-in is configured |
| `GET /auth/google/url` | Google OAuth redirect URL |
| `POST /auth/google` | Exchange a Google ID token for a session |

Authenticated calls use `Authorization: Bearer <access_token>`. The refresh token is also set as
an `httpOnly` cookie scoped to `/api/v1/auth`.

---

## Candidate (`/me`)

| Endpoint | Purpose |
|---|---|
| `GET /me/profile` · `PATCH /me/profile` | Read and update the candidate profile |
| `POST /me/profile/resume` | Upload a resume (multipart, ≤5 MB, pdf/doc/docx/txt/rtf) |
| `GET/POST/DELETE /me/saved-jobs/{id}` | Saved jobs |
| `GET/POST/DELETE /me/saved-startups/{id}` | Saved companies |
| `GET/POST/PATCH/DELETE /me/alerts[/{id}]` | Job alerts |
| `GET/POST/DELETE /me/saved-searches[/{id}]` | Saved filter sets |
| `GET/POST/PATCH /me/applications[/{id}]` | Application tracking |
| `GET /me/recently-viewed` | Recently viewed listings |
| `GET /me/recommendations` | Scored matches with `matched_skills`, `missing_skills` and human-readable reasons |
| `GET /me/notifications` · `POST /me/notifications/{id}/read` | Notifications |

---

## Admin (`/admin`, requires the `admin` role)

| Endpoint | Purpose |
|---|---|
| `GET /admin/overview` | Sources, jobs discovered today, successful/failed runs, duplicates, awaiting verification, database size |
| `GET /admin/sources` · `POST` · `PATCH /{id}` · `DELETE /{id}` | Manage ingestion sources |
| `POST /admin/sources/{id}/run` | Queue an immediate ingestion run |
| `GET /admin/runs` | Recent runs with counters and duration |
| `GET /admin/errors` | Recent failures with tracebacks |
| `GET /admin/health` | Per-source health: success rate, average duration, consecutive failures, last error |
| `GET /admin/connectors` | Available connector types |
| `GET /admin/jobs` | Review listings (filter by verification status or title) |
| `PATCH /admin/jobs/{id}` | Set verification status, status, rejection reason, company or quality score |
| `POST /admin/jobs/{id}/verify` | Re-check the application URL now |
| `POST /admin/startups` · `PATCH /admin/startups/{id}` | Company records |
| `POST /admin/startups/merge` | Merge one company into another, moving jobs, founders and funding |
| `POST /admin/startups/import` | Bulk import companies from CSV |
| `POST /admin/startups/{id}/verify` | Re-check a company website and record evidence |

---

## Sources and events

| Endpoint | Purpose |
|---|---|
| `GET /sources` | Registered sources (transparency page) |
| `GET /sources/stats` | Per-source contribution counts |
| `GET /api/v1/events` | Server-Sent Events stream: `jobs.discovered`, `companies.discovered` |

---

## System

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness plus database reachability |
| `GET /ready` | Readiness probe (503 when the database is unreachable) |
| `GET /docs`, `/redoc`, `/openapi.json` | API documentation |
