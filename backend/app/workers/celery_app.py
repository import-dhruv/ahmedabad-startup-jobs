"""Celery application and beat schedule."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

celery_app = Celery(
    "ahmedabad_jobs",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=1800,
    task_soft_time_limit=1500,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    # Every 15 minutes: poll connected job-board APIs and feeds.
    "poll-boards": {
        "task": "app.workers.tasks.run_due_sources",
        "schedule": 900.0,
    },
    # Every hour: priority company career pages are covered by run_due_sources
    # via per-source intervals; this task refreshes source health snapshots.
    "hourly-health": {
        "task": "app.workers.tasks.refresh_source_health",
        "schedule": 3600.0,
    },
    # Every 6 hours: discover new companies and career pages.
    "discover-companies": {
        "task": "app.workers.tasks.discover_companies",
        "schedule": crontab(minute=17, hour="*/6"),
    },
    # Daily: verify live application links.
    "verify-jobs": {
        "task": "app.workers.tasks.verify_job_links",
        "schedule": crontab(minute=23, hour=3),
    },
    # Daily: reconcile expired / removed listings.
    "reconcile-jobs": {
        "task": "app.workers.tasks.reconcile_job_status",
        "schedule": crontab(minute=41, hour=4),
    },
    # Daily: AI enrichment (summaries + classification).
    "ai-enrichment": {
        "task": "app.workers.tasks.enrich_jobs_with_ai",
        "schedule": crontab(minute=7, hour=6),
    },
    # Every 10 minutes: dispatch alerts for newly discovered jobs.
    "dispatch-alerts": {
        "task": "app.workers.tasks.dispatch_job_alerts",
        "schedule": 600.0,
    },
}
