"""API integration tests: auth, job search, startups, alerts, admin."""
from __future__ import annotations

import uuid

import pytest

from app.models import JobListing, JobSource, Startup, User
from app.models.enums import JobStatus, Role, VerificationStatus
from app.services.taxonomy import slugify
from tests.conftest import unique_email


def _create_job(
    *,
    title: str = "Backend Engineer",
    company: str = "Ahmedabad Robotics",
    location_city: str = "Ahmedabad",
    location_state: str = "Gujarat",
    geo_scope: str = "ahmedabad",
    employment_type: str | None = "Full-time",
    experience_level: str | None = "1-3 years",
    salary_min: int | None = 1200000,
    salary_max: int | None = 1800000,
    skills: list[str] | None = None,
    status: str = JobStatus.ACTIVE,
    verification_status: str = VerificationStatus.VERIFIED,
    apply_url: str = "https://example.com/jobs/1",
) -> JobListing:
    job = JobListing(
        source_key="test",
        external_id=uuid.uuid4().hex,
        title=title,
        normalized_title=title.lower(),
        slug=f"{slugify(title)}-{slugify(company)}-{uuid.uuid4().hex[:6]}",
        company_name=company,
        description="Build production systems with Python, FastAPI and PostgreSQL.",
        location_city=location_city,
        location_state=location_state,
        location_country="India",
        location_raw=f"{location_city}, {location_state}",
        geo_scope=geo_scope,
        employment_type=employment_type,
        experience_level=experience_level,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="INR" if salary_min else None,
        salary_period="year" if salary_min else None,
        salary_disclosed=salary_min is not None,
        is_remote=geo_scope in {"india_remote", "global"},
        apply_url=apply_url,
        original_url=apply_url,
        source_name="Test source",
        verification_status=verification_status,
        status=status,
        quality_score=0.8,
    )
    job.skills_text = ", ".join(skills or ["Python", "FastAPI", "PostgreSQL"])
    return job


@pytest.mark.asyncio
async def test_register_and_login(client):
    email = unique_email()
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "supersecret1", "full_name": "Test"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == email
    assert body["access_token"]

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"})
    assert login.status_code == 200

    bad = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_registration_is_rejected(client):
    email = unique_email()
    await client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    again = await client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_protected_route_requires_token(client):
    response = await client.get("/api/v1/me/profile")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_profile_update_and_recommendations(client, db):
    email = unique_email()
    register = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "supersecret1"}
    )
    token = register.json()["access_token"]

    update = await client.patch(
        "/api/v1/me/profile",
        json={"skills": ["Python", "FastAPI"], "experience_years": 2, "preferred_locations": ["Ahmedabad"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update.status_code == 200
    assert update.json()["skills"] == ["Python", "FastAPI"]

    profile = await client.get("/api/v1/me/profile", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["experience_years"] == 2


@pytest.mark.asyncio
async def test_job_search_filters_and_facets(client, db):
    db.add(_create_job(title="AI Engineer", skills=["Python", "LLMs"]))
    db.add(_create_job(title="Marketing Lead", geo_scope="global", location_city="Austin",
                             location_state="Texas", skills=["SEO"]))
    await db.commit()

    response = await client.get("/api/v1/jobs", params={"q": "AI Engineer"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any("AI Engineer" == job["title"] for job in body["items"])
    assert "skills" in body["facets"]
    assert "geo_scopes" in body["facets"]

    scoped = await client.get("/api/v1/jobs", params={"scope": "ahmedabad", "q": "AI Engineer"})
    assert scoped.json()["total"] >= 1

    other = await client.get("/api/v1/jobs", params={"scope": "india", "q": "AI Engineer"})
    assert other.json()["total"] == 0


@pytest.mark.asyncio
async def test_job_detail_and_slug_lookup(client, db):
    job = _create_job(title="Research Engineer AI")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    detail = await client.get(f"/api/v1/jobs/{job.id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Research Engineer AI"

    by_slug = await client.get(f"/api/v1/jobs/slug/{job.slug}")
    assert by_slug.status_code == 200
    assert by_slug.json()["id"] == str(job.id)

    missing = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_saved_jobs_lifecycle(client, db):
    email = unique_email()
    register = await client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job = _create_job()
    db.add(job)
    await db.commit()
    await db.refresh(job)

    saved = await client.post(f"/api/v1/me/saved-jobs/{job.id}", headers=headers)
    assert saved.status_code == 201

    listing = await client.get("/api/v1/me/saved-jobs", headers=headers)
    assert listing.json()["total"] == 1

    await client.delete(f"/api/v1/me/saved-jobs/{job.id}", headers=headers)
    listing = await client.get("/api/v1/me/saved-jobs", headers=headers)
    assert listing.json()["total"] == 0


@pytest.mark.asyncio
async def test_alert_crud(client):
    email = unique_email()
    register = await client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/me/alerts",
        json={"name": "AI Engineer roles", "query": "AI Engineer"},
        headers=headers,
    )
    assert created.status_code == 201
    alert_id = created.json()["id"]

    listed = await client.get("/api/v1/me/alerts", headers=headers)
    assert len(listed.json()) == 1

    await client.delete(f"/api/v1/me/alerts/{alert_id}", headers=headers)
    listed = await client.get("/api/v1/me/alerts", headers=headers)
    assert listed.json() == []


@pytest.mark.asyncio
async def test_startup_directory(client, db):
    startup = Startup(
        name="Gujarat Robotics",
        slug=f"gujarat-robotics-{uuid.uuid4().hex[:6]}",
        industry="Robotics",
        hq_city="Ahmedabad",
        hq_state="Gujarat",
        hq_country="India",
        hiring_status="hiring",
        tech_stack=["Python", "ROS"],
    )
    db.add(startup)
    await db.commit()
    await db.refresh(startup)

    listing = await client.get("/api/v1/startups", params={"q": "Gujarat Robotics"})
    assert listing.status_code == 200
    assert any(item["id"] == str(startup.id) for item in listing.json())

    detail = await client.get(f"/api/v1/startups/slug/{startup.slug}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Gujarat Robotics"

    filters = await client.get("/api/v1/startups/filters")
    assert filters.status_code == 200
    assert "Robotics" in filters.json()["industries"]


@pytest.mark.asyncio
async def test_admin_requires_admin_role(client, db):
    email = unique_email()
    register = await client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    token = register.json()["access_token"]

    forbidden = await client.get("/api/v1/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_manage_sources_and_jobs(client, db):
    email = unique_email()
    user = User(email=email, password_hash="x", role=Role.ADMIN, is_active=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    from app.core.security import create_access_token

    token = create_access_token(str(user.id), Role.ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    overview = await client.get("/api/v1/admin/overview", headers=headers)
    assert overview.status_code == 200
    assert "total_sources" in overview.json()

    created = await client.post(
        "/api/v1/admin/sources",
        json={
            "name": "Test Board",
            "slug": f"test-board-{uuid.uuid4().hex[:6]}",
            "connector_type": "greenhouse",
            "config": {"board_token": "example"},
        },
        headers=headers,
    )
    assert created.status_code == 201

    invalid = await client.post(
        "/api/v1/admin/sources",
        json={"name": "Bad", "slug": f"bad-{uuid.uuid4().hex[:6]}", "connector_type": "does-not-exist"},
        headers=headers,
    )
    assert invalid.status_code == 400

    job = _create_job()
    db.add(job)
    await db.commit()
    await db.refresh(job)

    patched = await client.patch(
        f"/api/v1/admin/jobs/{job.id}",
        json={"verification_status": "rejected", "rejection_reason": "Test spam"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["verification_status"] == "rejected"


@pytest.mark.asyncio
async def test_stats_endpoints(client, db):
    db.add(_create_job())
    await db.commit()

    dashboard = await client.get("/api/v1/stats/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["total_active_jobs"] >= 1

    for path in ("/api/v1/stats/trends", "/api/v1/stats/skills", "/api/v1/stats/industries",
                 "/api/v1/stats/hiring", "/api/v1/stats/mix", "/api/v1/stats/insights",
                 "/api/v1/stats/recent-jobs", "/api/v1/stats/recent-startups"):
        response = await client.get(path)
        assert response.status_code == 200, path


@pytest.mark.asyncio
async def test_public_source_listing(client, db):
    source = JobSource(
        name="Public Board",
        slug=f"public-board-{uuid.uuid4().hex[:6]}",
        connector_type="greenhouse",
        config={"board_token": "x"},
        is_active=True,
    )
    db.add(source)
    await db.commit()

    listing = await client.get("/api/v1/sources")
    assert listing.status_code == 200
    assert any(item["name"] == "Public Board" for item in listing.json())


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
