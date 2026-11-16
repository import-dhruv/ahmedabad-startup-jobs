# Ingestion pipeline

## Principles

1. **Never fabricate.** If a source cannot be read, nothing is written. There is no fallback
   that invents a company, a role or a salary.
2. **Respect the source.** `robots.txt` is evaluated with correct longest-match semantics, every
   host is rate-limited, and requests identify themselves with a descriptive user agent.
3. **Keep the evidence.** Every record stores the URL it came from, when it was discovered and
   when it was last verified.
4. **Never merge on title alone.** See [De-duplication](#de-duplication).

## Connector contract

```python
class Connector(abc.ABC):
    type: str

    async def fetch(self) -> list[RawJob]: ...
```

`RawJob` is source-agnostic: an external id, title, company, description, location, dates and the
original URLs. A connector's only job is to translate its source's vocabulary into `RawJob`;
everything else (normalisation, de-duplication, persistence) is shared.

Adding a source therefore means:

1. Write `app/ingestion/connectors/<source>.py` with a `Connector` subclass.
2. Register it in `app/ingestion/registry.py`.
3. Insert a row into `job_sources` with the right `connector_type` and `config`.

No other file changes. The admin API can do step 3 at runtime.

## Sources

| Connector | Endpoint | Access notes |
|---|---|---|
| `greenhouse` | `boards-api.greenhouse.io/v1/boards/{token}/jobs` | Public board API; `robots.txt` allows everything except `/embed/` |
| `lever` | `api.lever.co/v0/postings/{company}` | Public postings API; `robots.txt` allows `/` with a 1s crawl delay |
| `ashby` | `api.ashbyhq.com/posting-api/job-board/{company}` | Public job board API |
| `workable` | `apply.workable.com/api/v1/accounts/{account}/jobs` | Public account API |
| `smartrecruiters` | `api.smartrecruiters.com/v1/companies/{company}/postings` | Public API, but `robots.txt` disallows crawling — the client refuses it unless you deliberately override |
| `remoteok` | `remoteok.com/api` | Public JSON feed; `robots.txt` allows `/` for generic agents |
| `remotive` | `remotive.com/api/remote-jobs` | Public JSON feed |
| `arbeitnow` | `www.arbeitnow.com/api/job-board-api` | Public JSON feed |
| `jobicy` | `jobicy.com/api/v2/remote-jobs` | Public JSON feed |
| `himalayas` | `himalayas.app/jobs/api` | Public JSON feed |
| `hackernews` | Firebase API + Algolia mirror of the monthly "Ask HN: Who is hiring?" thread | The official Firebase API explicitly allows `*.json`; each comment is a founder-posted opening with the employer's own link |
| `career_page` | any public careers page | Reads `schema.org/JobPosting` markup |

Sources we deliberately do **not** read include platforms whose `robots.txt` disallows automated
access (for example Internshala and LinkedIn). They are not bypassed.

## Discovery

### 1. ATS board probing

Given a company domain we derive likely board identifiers (`cred` → `cred`, `cred.club` →
`cred`, `cred-club`) and probe each ATS API. A board is only registered when it returns a
non-empty job list, so a probe either finds a real board or finds nothing.

### 2. Career-page link detection

Company careers pages usually link straight to their board — sometimes with a slug that could
never be guessed (`boards.greenhouse.io/razorpaysoftwareprivatelimited`). We read the homepage
and up to two career pages and extract board identifiers from those links, then probe them
first. This is markedly more accurate than guessing.

### 3. Self-reinforcing discovery

Every ingested listing carries the employer's domain. We take the domains of India-scoped
listings we already hold, look for their boards and careers pages, and register what we find.
Each new board feeds more companies back into the loop.

### 4. Directory connectors

`discover_from_yc` can pull companies from the public YC directory API. That host's
`robots.txt` disallows crawling, so the client refuses it by default and the connector is
opt-in — the platform never bypasses an access restriction to widen its catalogue.

## Normalisation

`services/normalizer.py` is pure and independently testable.

| Field | Rule |
|---|---|
| Title | Strip seniority, location and employment noise (`Senior`, `Remote`, `Full-time`…). Keep technology tokens such as `C++` and `Node.js`. |
| Experience | Title keywords first, then explicit ranges (`3-5 years`), then minimums. Mapped onto `Fresher`, `0-1`, `1-3`, `3-5`, `5-8`, `8+`. |
| Employment type | Title first, then body. Source-supplied labels are canonicalised (`full_time` → `Full-time`). |
| Work arrangement | `Remote` / `Hybrid` / `On-site` from title, body and location. |
| Salary | Only parsed when the employer states a figure or range. `₹15L – ₹25L` → `1500000–2500000 INR/year`. Never inferred, never estimated. |
| Responsibilities / qualifications | The description is split on recognised headings; bullets are extracted. |
| Skills | A curated catalogue with aliases (`k8s` → `Kubernetes`, `agentic` → `Agentic AI`). AI-specific skills require supporting context so that a stray word cannot create a false skill. |
| Categories | Rule-based classification over 28 categories. |
| Location | Resolved to city/state/country plus a `geo_scope`. |

## De-duplication

Two postings are the same opening when there is corroborating evidence:

1. **Identical application URL** (tracking parameters stripped) — conclusive.
2. **Same company + same normalised title + compatible location + a description that overlaps by
   at least 35%** — the description requirement is what stops two different roles at one company
   from being merged.
3. **Same company + near-identical description (≥85%) + compatible location** — a re-posted
   role with a rewritten title.

Compatible location means equal, one being a subset of the other (`Ahmedabad` ⊂
`Ahmedabad, Gujarat`), or a high token overlap.

A matching title on its own is never sufficient. When a duplicate is confirmed, the existing job
keeps its record and a `job_source_references` row is added so every source stays visible.

## Verification and expiry

| Status | Meaning |
|---|---|
| `verified` | The application URL resolved during a recent run and the role was still listed. |
| `unverified` | Newly imported; the first link check has not completed. |
| `stale` | Not confirmed recently (default after 14 days). |
| `expired` | Absent for a prolonged period (default after 45 days) — removed from the public board. |
| `rejected` | Invalid or misleading, marked by an administrator. |

`reconcile_job_status` performs the daily sweep; `verify_job_links` performs the daily link
checks. Listings whose URL breaks are marked stale rather than deleted, so the history remains
auditable.

## Reliability

- Per-host rate limiting (default 30 requests/minute) and exponential backoff with jitter on
  429/5xx and transport errors.
- SAVEPOINT per job, so one malformed listing cannot abort a run.
- Every run writes an `ingestion_runs` row with counters, and failures write
  `ingestion_errors` rows with the traceback.
- `source_health` tracks consecutive failures and flips a source to `degraded`/`unhealthy`,
  which the admin console surfaces.

## Adding your own source

```python
# backend/app/ingestion/connectors/example.py
from app.ingestion.base import Connector, RawJob

class ExampleConnector(Connector):
    type = "example"

    async def fetch(self) -> list[RawJob]:
        client = self.ctx.config["client"]
        data = await client.get_json("https://example.com/api/jobs")
        return [
            RawJob(
                external_id=f"example:{job['id']}",
                source_key="example",
                source_name=self.ctx.source_name,
                title=job["title"],
                company_name=job["company"],
                apply_url=job["url"],
                original_url=job["url"],
                description=job.get("description"),
                location_raw=job.get("location"),
                raw=job,
            )
            for job in data
        ]
```

Register it in `registry.py` and add a `job_sources` row with
`connector_type = "example"` and `config = {}`. The scheduler picks it up on the next cycle.
