# Data sources

This platform indexes publicly accessible job listings. It never creates a listing, never
invents a salary, and never bypasses an access control.

## Access policy

| Rule | Implementation |
|---|---|
| `robots.txt` is respected | `ingestion/http_client.py` implements a spec-correct evaluator (longest match wins, `Allow` wins ties). Requests to a disallowed path are refused, not retried. |
| Rate limits are honoured | Per-host limiter, default 30 requests/minute; the ATS probe phase uses 90/minute against job-board APIs that are explicitly published for polling. |
| Descriptive user agent | `AhmedabadStartupJobsBot/1.0 (+<site>)` — configurable with `USER_AGENT`. |
| Authentication is never bypassed | No CAPTCHA solving, no paywall circumvention, no logged-in scraping. |
| Paywalls and gated listings are skipped | Sources behind a login are not registered. |

## Registered sources

### Applicant tracking systems

| Platform | Endpoint | `robots.txt` | Notes |
|---|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{board}/jobs` | Allows all except `/embed/` | Public board API; the board token is discovered from the company's own careers page or probed from the domain. |
| Lever | `api.lever.co/v0/postings/{company}` | `Allow: /`, crawl-delay 1 | Public postings API with `mode=json`. |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{company}` | Returns 401 → treated as unrestricted | Public job-board API; unlisted postings are skipped. |
| Workable | `apply.workable.com/api/v1/accounts/{account}/jobs` | No restrictions | Public account API. |
| SmartRecruiters | `api.smartrecruiters.com/v1/companies/{company}/postings` | **Disallows crawling** | The connector exists, but the polite client refuses to fetch it. Enable only if you have an agreement with SmartRecruiters. |

### Remote-job feeds

| Feed | Endpoint | `robots.txt` | Notes |
|---|---|---|---|
| RemoteOK | `remoteok.com/api` | `Allow: /` for generic agents (AI training bots excluded) | Public JSON feed; the legal-notice entry is skipped. |
| Remotive | `remotive.com/api/remote-jobs` | Allows all except a few search/apply paths | Public JSON feed. |
| Arbeitnow | `www.arbeitnow.com/api/job-board-api` | No restrictions | Public JSON feed. |
| Jobicy | `jobicy.com/api/v2/remote-jobs` | Allows all except search-query paths | Public JSON feed. |
| Himalayas | `himalayas.app/jobs/api` | `Allow: /` with pagination paths disallowed | Public JSON feed. |

### Founder-posted openings

| Source | Endpoint | `robots.txt` | Notes |
|---|---|---|---|
| Hacker News "Ask HN: Who is hiring?" | Firebase API (`*.json` explicitly allowed) + Algolia thread mirror | Allows `*.json` only | Each monthly thread contains founders posting their own openings. Comments are parsed in the `Company | Role | Location | Type` format and the employer's own link is preserved as the application URL. |

### Career pages

| Source | What it reads | Notes |
|---|---|---|
| `career_page` connector | `schema.org/JobPosting` JSON-LD on a public careers page | Works with any employer that publishes JobPosting markup. Used for companies without a recognised ATS. |

## Sources we do not read

| Platform | Reason |
|---|---|
| LinkedIn | `robots.txt` and the User Agreement explicitly prohibit automated access. |
| Internshala | `robots.txt` disallows crawling, including its job and internship paths. |
| Naukri, Cutshort, Instahyre | No public API that permits automated access; their terms require a commercial agreement. |
| Google Jobs / Indeed | No public API; scraping would violate their terms. |
| The YC company directory API | `api.ycombinator.com/robots.txt` disallows crawling. The connector exists but is opt-in and off by default — the platform does not bypass the restriction. |

If you hold a licence or partnership with any of these, add the source through the admin API and
the rest of the pipeline — normalisation, de-duplication, verification and publication — works
unchanged.

## Attributing a source

Every listing keeps:

- `original_url` — the page the data was read from.
- `apply_url` — the employer's application link.
- `source_name` and `source_id` — which board it came from.
- `job_source_references` — every additional board the same opening appears on.
- `discovered_at`, `last_verified_at`, `posted_at` — the freshness story.
- `verification_status` — whether we have confirmed it recently.

The public `/sources` page lists every connected source with its contribution, and `/sources/stats`
returns the machine-readable version of the same data.
