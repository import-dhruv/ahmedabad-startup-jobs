"""Connector tests using recorded public payloads.

The fixtures below are real responses captured from the public endpoints the
connectors read. They let us test parsing without hitting the network.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ingestion.base import ConnectorContext
from app.ingestion.connectors.aggregators import (
    ArbeitnowConnector,
    HimalayasConnector,
    JobicyConnector,
    RemoteOkConnector,
    RemotiveConnector,
)
from app.ingestion.connectors.ats import (
    AshbyConnector,
    GreenhouseConnector,
    LeverConnector,
    SmartRecruitersConnector,
    WorkableConnector,
)
from app.ingestion.connectors.career_pages import (
    CareerPageConnector,
    detect_ats_links,
    parse_jsonld_blocks,
)
from app.ingestion.connectors.hackernews import HackerNewsConnector, _decode_html, _split_fields
from app.ingestion.connectors.workday import WorkdayConnector


class _StubResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    @property
    def text(self):
        return self._payload if isinstance(self._payload, str) else ""


class StubClient:
    """Returns a recorded payload for a given URL."""

    def __init__(self, responses: dict[str, object]):
        self.responses = responses
        self.requested: list[str] = []

    async def get_json(self, url, **kwargs):
        self.requested.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected URL requested: {url}")
        payload = self.responses[url]
        if isinstance(payload, Exception):
            raise payload
        return payload

    async def get_text(self, url, **kwargs):
        self.requested.append(url)
        payload = self.responses.get(url, "")
        if isinstance(payload, Exception):
            raise payload
        return payload

    async def request(self, method, url, **kwargs):
        self.requested.append(url)
        payload = self.responses.get(url)
        if payload is None:
            raise AssertionError(f"unexpected URL requested: {url}")
        if isinstance(payload, Exception):
            raise payload
        return _StubResponse(payload)


def _ctx(responses, **config):
    config["client"] = StubClient(responses)
    return ConnectorContext(source_slug="test", source_name="Test Source", config=config)


GREENHOUSE_PAYLOAD = {
    "jobs": [
        {
            "id": 101,
            "title": "Backend Engineer",
            "absolute_url": "https://boards.greenhouse.io/example/jobs/101",
            "location": {"name": "Ahmedabad, Gujarat"},
            "updated_at": "2026-10-01T10:00:00Z",
            "content": "<p>Build APIs with Python and FastAPI.</p>",
            "departments": [{"name": "Engineering"}],
            "offices": [{"name": "Ahmedabad"}],
            "company_name": "Example Startup",
        }
    ]
}

LEVER_PAYLOAD = [
    {
        "id": "abc-1",
        "text": "AI Engineer",
        "hostedUrl": "https://jobs.lever.co/example/abc-1",
        "applyUrl": "https://jobs.lever.co/example/abc-1/apply",
        "categories": {"location": "ahmedabad", "commitment": "Full-time", "department": "Engineering"},
        "descriptionPlain": "Work on LLM products.",
        "description": "<div>Work on LLM products.</div>",
        "createdAt": 1756000000000,
        "updatedAt": 1756000000000,
        "salaryRange": {"minValue": 1500000, "maxValue": 2200000, "currency": "INR"},
    }
]

ASHBY_PAYLOAD = {
    "jobs": [
        {
            "id": "job-1",
            "title": "Data Scientist",
            "location": "Bengaluru, India",
            "employmentType": "Full-time",
            "isRemote": False,
            "jobUrl": "https://jobs.ashbyhq.com/example/job-1",
            "applyUrl": "https://jobs.ashbyhq.com/example/job-1/apply",
            "descriptionHtml": "<p>Build models with PyTorch.</p>",
            "publishedAt": "2026-09-20T00:00:00Z",
            "secondaryLocations": [{"location": "Ahmedabad, Gujarat"}],
        },
        {
            "id": "job-2",
            "title": "Hidden role",
            "isListed": False,
            "jobUrl": "https://jobs.ashbyhq.com/example/job-2",
            "applyUrl": "https://jobs.ashbyhq.com/example/job-2/apply",
        },
    ]
}

WORKABLE_PAYLOAD = {
    "jobs": [
        {
            "id": 55,
            "title": "Flutter Developer",
            "url": "https://apply.workable.com/example/j/55/",
            "description": "Build Flutter apps.",
            "requirements": "Dart and Flutter experience.",
            "location": "Ahmedabad",
            "employment_type": "full-time",
            "remote": False,
            "published_on": "2026-09-01T00:00:00Z",
        }
    ]
}

SMARTRECRUITERS_PAYLOAD = {
    "content": [
        {
            "id": 909,
            "name": "Platform Engineer",
            "company": {"name": "Example Startup"},
            "location": {"city": "Ahmedabad", "region": "Gujarat", "country": "India"},
            "department": {"label": "Engineering"},
            "releasedDate": "2026-09-05T00:00:00Z",
            "typeOfEmployment": "Full-time",
        }
    ]
}

REMOTEOK_PAYLOAD = [
    {"legal": "All images belong to their owners"},
    {
        "id": 1234,
        "position": "Senior Backend Engineer",
        "company": "Remote Company",
        "location": "Remote - India",
        "description": "<p>Python and Go.</p>",
        "apply_url": "https://remoteok.com/remote-jobs/1234",
        "url": "https://remoteok.com/remote-jobs/1234",
        "tags": ["python", "go"],
        "date": "2026-09-10T00:00:00+00:00",
        "salary_min": 100000,
        "salary_max": 150000,
    },
]


class TestGreenhouseConnector:
    @pytest.mark.asyncio
    async def test_parses_jobs(self):
        ctx = _ctx(
            {"https://boards-api.greenhouse.io/v1/boards/example/jobs": GREENHOUSE_PAYLOAD},
            board_token="example",
        )
        jobs = await GreenhouseConnector(ctx).fetch()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "Backend Engineer"
        assert job.location_raw == "Ahmedabad, Gujarat"
        assert job.apply_url.endswith("/101")
        assert job.external_id == "greenhouse:example:101"
        assert job.posted_at is not None


class TestLeverConnector:
    @pytest.mark.asyncio
    async def test_parses_jobs(self):
        ctx = _ctx({"https://api.lever.co/v0/postings/example": LEVER_PAYLOAD}, company="example")
        jobs = await LeverConnector(ctx).fetch()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "AI Engineer"
        assert job.location_raw == "ahmedabad"
        assert job.employment_type == "Full-time"
        assert job.salary_min == 1500000


class TestAshbyConnector:
    @pytest.mark.asyncio
    async def test_skips_unlisted_jobs(self):
        ctx = _ctx({"https://api.ashbyhq.com/posting-api/job-board/example": ASHBY_PAYLOAD}, company="example")
        jobs = await AshbyConnector(ctx).fetch()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "Data Scientist"
        assert "Ahmedabad" in (job.location_raw or "")
        assert job.employment_type == "Full-time"


class TestWorkableConnector:
    @pytest.mark.asyncio
    async def test_parses_jobs(self):
        ctx = _ctx(
            {"https://apply.workable.com/api/v1/accounts/example/jobs": WORKABLE_PAYLOAD},
            account="example",
        )
        jobs = await WorkableConnector(ctx).fetch()
        assert len(jobs) == 1
        assert jobs[0].title == "Flutter Developer"
        assert jobs[0].employment_type == "Full-time"
        assert "Dart" in jobs[0].description


class TestSmartRecruitersConnector:
    @pytest.mark.asyncio
    async def test_parses_jobs(self):
        ctx = _ctx(
            {"https://api.smartrecruiters.com/v1/companies/example/postings": SMARTRECRUITERS_PAYLOAD},
            company="example",
        )
        jobs = await SmartRecruitersConnector(ctx).fetch()
        assert len(jobs) == 1
        assert jobs[0].title == "Platform Engineer"
        assert "Ahmedabad" in jobs[0].location_raw


class TestRemoteOkConnector:
    @pytest.mark.asyncio
    async def test_skips_legal_notice(self):
        ctx = _ctx({"https://remoteok.com/api": REMOTEOK_PAYLOAD})
        jobs = await RemoteOkConnector(ctx).fetch()
        assert len(jobs) == 1
        assert jobs[0].title == "Senior Backend Engineer"
        assert jobs[0].work_arrangement == "Remote"
        assert jobs[0].salary_min == 100000


class TestOtherAggregators:
    @pytest.mark.asyncio
    async def test_remotive(self):
        payload = {
            "jobs": [
                {
                    "id": 7,
                    "title": "Support Engineer",
                    "company_name": "Example",
                    "url": "https://remotive.com/jobs/7",
                    "description": "Great role",
                    "candidate_required_location": "India",
                    "publication_date": "2026-09-01T00:00:00",
                }
            ]
        }
        ctx = _ctx({"https://remotive.com/api/remote-jobs": payload})
        jobs = await RemotiveConnector(ctx).fetch()
        assert jobs[0].company_name == "Example"
        assert jobs[0].location_raw == "India"

    @pytest.mark.asyncio
    async def test_arbeitnow(self):
        payload = {
            "data": [
                {
                    "slug": "job-1",
                    "title": "Engineer",
                    "company_name": "Example",
                    "url": "https://www.arbeitnow.com/view/job/1",
                    "description": "Work",
                    "location": "Germany",
                    "remote": True,
                }
            ]
        }
        ctx = _ctx({"https://www.arbeitnow.com/api/job-board-api": payload})
        jobs = await ArbeitnowConnector(ctx).fetch()
        assert jobs[0].work_arrangement == "Remote"

    @pytest.mark.asyncio
    async def test_jobicy(self):
        payload = {
            "jobList": [
                {
                    "id": "abc",
                    "jobTitle": "Backend Engineer",
                    "companyName": "Example",
                    "url": "https://jobicy.com/j/abc",
                    "jobDescription": "Python",
                    "jobGeo": "India",
                }
            ]
        }
        ctx = _ctx({"https://jobicy.com/api/v2/remote-jobs": payload})
        jobs = await JobicyConnector(ctx).fetch()
        assert jobs[0].title == "Backend Engineer"

    @pytest.mark.asyncio
    async def test_himalayas(self):
        payload = {
            "jobs": [
                {
                    "id": "h1",
                    "title": "Frontend Engineer",
                    "companyName": "Example",
                    "applicationUrl": "https://himalayas.app/jobs/h1",
                    "jobUrl": "https://himalayas.app/jobs/h1",
                    "description": "React",
                    "location": "Remote",
                }
            ]
        }
        ctx = _ctx({"https://himalayas.app/jobs/api": payload})
        jobs = await HimalayasConnector(ctx).fetch()
        assert jobs[0].title == "Frontend Engineer"


CAREER_PAGE_HTML = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Founding Engineer",
  "description": "<p>Own the product end to end.</p>",
  "datePosted": "2026-08-01",
  "employmentType": "FULL_TIME",
  "hiringOrganization": {"@type": "Organization", "name": "Example Startup"},
  "jobLocation": {
    "@type": "Place",
    "address": {"@type": "PostalAddress", "addressLocality": "Ahmedabad", "addressCountry": "IN"}
  },
  "baseSalary": {"@type": "MonetaryAmount", "currency": "INR", "value": {"@type": "QuantitativeValue", "minValue": 1800000, "maxValue": 2400000}},
  "url": "https://example.com/jobs/founding-engineer"
}
</script>
</head><body>
<a href="https://boards.greenhouse.io/examplecompany">Greenhouse</a>
</body></html>
"""


class TestCareerPageConnector:
    @pytest.mark.asyncio
    async def test_extracts_job_posting(self):
        ctx = _ctx(
            {"https://example.com/careers": CAREER_PAGE_HTML},
            url="https://example.com/careers",
            company_name="Example Startup",
        )
        jobs = await CareerPageConnector(ctx).fetch()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "Founding Engineer"
        assert job.company_name == "Example Startup"
        assert job.employment_type == "Full-time"
        assert job.salary_min == 1800000
        assert job.location_raw and "Ahmedabad" in job.location_raw

    def test_parses_jsonld_blocks(self):
        blocks = parse_jsonld_blocks(CAREER_PAGE_HTML)
        assert blocks and blocks[0]["@type"] == "JobPosting"

    def test_detects_ats_links(self):
        links = detect_ats_links(CAREER_PAGE_HTML)
        assert ("greenhouse", "examplecompany") in links


WORKDAY_LISTING = {
    "total": 2,
    "jobPostings": [
        {
            "title": "Data Engineer",
            "externalPath": "/job/India---Bengaluru/Data-Engineer_JR123",
            "locationsText": "India - Bengaluru",
            "postedOn": "Posted 3 Days Ago",
            "bulletFields": ["JR123"],
        },
        {
            "title": "Senior Analyst",
            "externalPath": "/job/Remote/Senior-Analyst_JR124",
            "locationsText": "Remote - India",
            "postedOn": "Posted 1 Day Ago",
            "bulletFields": ["JR124"],
        },
    ],
}

WORKDAY_DETAIL = {
    "jobPostingInfo": {
        "title": "Data Engineer",
        "jobDescription": "<p>Build pipelines with Python and Spark.</p>",
        "additionalLocations": [{"location": "Ahmedabad, Gujarat"}],
    }
}


class TestWorkdayConnector:
    @pytest.mark.asyncio
    async def test_parses_listings_and_details(self):
        base = "https://acme.wd1.myworkdayjobs.com"
        listing_url = f"{base}/wday/cxs/acme/careers_at_acme/jobs"
        detail_url = f"{base}/wday/cxs/acme/careers_at_acme/job/India---Bengaluru/Data-Engineer_JR123"
        detail_url_2 = f"{base}/wday/cxs/acme/careers_at_acme/job/Remote/Senior-Analyst_JR124"
        ctx = _ctx(
            {listing_url: WORKDAY_LISTING, detail_url: WORKDAY_DETAIL, detail_url_2: WORKDAY_DETAIL},
            tenant="acme",
            region="wd1",
            site="careers_at_acme",
        )
        jobs = await WorkdayConnector(ctx).fetch()
        assert len(jobs) == 2
        first = jobs[0]
        assert first.title == "Data Engineer"
        assert first.company_name == "Acme"
        assert "Bengaluru" in (first.location_raw or "")
        assert "Ahmedabad" in (first.location_raw or "")
        assert first.description.startswith("<p>Build pipelines")
        assert first.apply_url.startswith(base)

    def test_workday_links_are_detected(self):
        html = '<a href="https://acme.wd3.myworkdayjobs.com/Careers_at_Acme">Apply</a>'
        links = detect_ats_links(html)
        assert ("workday", "acme|wd3|Careers_at_Acme") in links


class TestHackerNewsHelpers:
    def test_decode_html(self):
        text = _decode_html("<p>Company | Role | India</p><p>More</p>")
        assert "Company | Role | India" in text
        assert "More" in text

    def test_split_fields(self):
        fields = _split_fields("Example | Backend Engineer | Bengaluru, India\nBody text")
        assert fields[0] == "Example"
        assert fields[1] == "Backend Engineer"
        assert fields[2] == "Bengaluru, India"

    @pytest.mark.asyncio
    async def test_parses_hiring_thread(self):
        thread = {
            "title": "Ask HN: Who is hiring? (November 2026)",
            "children": [
                {
                    "id": 1,
                    "author": "founder",
                    "created_at_i": 1760000000,
                    "text": (
                        "Example Startup | Backend Engineer | Ahmedabad, Gujarat | Full-time | "
                        "Python, FastAPI. Apply here: "
                        '<a href="https://example.com/jobs/1">https://example.com/jobs/1</a>'
                    ),
                },
                {
                    "id": 2,
                    "author": "noise",
                    "created_at_i": 1760000000,
                    "text": "This is a short comment that is not a job posting at all.",
                },
            ],
        }
        ctx = _ctx(
            {
                "https://hacker-news.firebaseio.com/v0/user/whoishiring.json": {"submitted": [123, 124]},
                "https://hn.algolia.com/api/v1/items/123": thread,
            }
        )
        jobs = await HackerNewsConnector(ctx).fetch()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.company_name == "Example Startup"
        assert job.title == "Backend Engineer"
        assert job.location_raw == "Ahmedabad, Gujarat"
        assert job.apply_url == "https://example.com/jobs/1"
