"""Shared pytest fixtures.

Tests run against a dedicated PostgreSQL database (the schema uses JSONB and
ARRAY columns, so SQLite is not an option).
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:change-me@localhost:5433/ahmedabad_jobs_test",
)
os.environ.setdefault(
    "SYNC_DATABASE_URL",
    "postgresql+psycopg2://postgres:change-me@localhost:5433/ahmedabad_jobs_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/15")

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=2, max_overflow=2)
    async with engine.begin() as conn:
        # Recreate a clean schema (handles circular foreign keys cleanly).
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine):
    """A single session shared by the test body and the HTTP client."""
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            # Leave the database clean for the next test.
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "TRUNCATE TABLE "
                        "saved_jobs, saved_startups, job_applications, job_alerts, saved_searches, "
                        "notifications, user_job_views, candidate_profiles, job_source_references, "
                        "job_skills, job_categories, skills, job_listings, startups, job_sources, "
                        "users RESTART IDENTITY CASCADE"
                    )
                )


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"
