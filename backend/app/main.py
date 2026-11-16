"""FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import admin, auth, jobs, sources, startups, stats, user
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal, engine
from app.realtime.events import broker

log = get_logger(__name__)

DESCRIPTION = """
Real-time startup hiring intelligence for Ahmedabad, Gandhinagar, GIFT City and
the wider Gujarat startup ecosystem.

Every listing keeps its original source URL, discovery timestamp and last
verification timestamp. Statistics are computed from stored records only.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api_starting", environment=settings.environment)
    yield
    await engine.dispose()
    log.info("api_stopped")


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(startups.router, prefix=settings.api_prefix)
app.include_router(stats.router, prefix=settings.api_prefix)
app.include_router(user.router, prefix=settings.api_prefix)
app.include_router(sources.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
async def health() -> dict:
    db_ok = True
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        db_ok = False
        log.warning("health_check_db_error", error=str(exc))
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unavailable"}


@app.get("/ready", tags=["system"])
async def ready() -> JSONResponse:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse(status_code=503, content={"ready": False, "error": str(exc)})
    return JSONResponse(status_code=200, content={"ready": True})


@app.get(f"{settings.api_prefix}/events", tags=["system"])
async def events(request: Request):
    """Server-Sent Events stream of live ingestion activity."""
    from fastapi.responses import StreamingResponse

    async def generator():
        async for chunk in broker.stream():
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
