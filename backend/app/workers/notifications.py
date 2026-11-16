"""Job-alert matching and email notification delivery."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models import JobAlert, JobListing, Notification, User
from app.models.enums import JobStatus, NotificationType

log = get_logger(__name__)

ACTIVE_SCOPES = ("ahmedabad", "gujarat", "india_remote", "india", "global")


def _matches(alert: JobAlert, job: JobListing) -> bool:
    query = (alert.query or "").strip()
    filters = alert.filters or {}

    if query:
        haystack = f"{job.title} {job.company_name} {job.skills_text or ''}".lower()
        tokens = [t for t in query.lower().split() if len(t) > 1]
        if not any(t in haystack for t in tokens):
            return False

    if filters.get("skills"):
        wanted = {s.strip().lower() for s in filters["skills"] if s.strip()}
        job_skills = {s.strip().lower() for s in (job.skills_text or "").split(",") if s.strip()}
        if not (wanted & job_skills):
            return False

    if filters.get("employment_type") and job.employment_type != filters["employment_type"]:
        return False
    if filters.get("experience_level") and job.experience_level != filters["experience_level"]:
        return False
    if filters.get("work_arrangement") and job.work_arrangement != filters["work_arrangement"]:
        return False
    if filters.get("city") and (job.location_city or "").lower() != filters["city"].lower():
        return False
    if filters.get("company") and filters["company"].lower() not in job.company_name.lower():
        return False
    if filters.get("min_salary") and (job.salary_max or job.salary_min or 0) < filters["min_salary"]:
        return False
    if filters.get("remote") and not job.is_remote:
        return False
    if filters.get("scopes") and job.geo_scope not in filters["scopes"]:
        return False
    return True


async def dispatch_alerts() -> dict[str, Any]:
    """Create notifications for alerts matching recently discovered jobs."""
    now = datetime.now(UTC)
    since = now - timedelta(hours=2)
    created = 0
    emailed = 0

    async with SessionLocal() as session:
        alerts = (
            await session.execute(select(JobAlert).where(JobAlert.is_active.is_(True)))
        ).scalars().all()
        if not alerts:
            return {"alerts": 0, "notifications": 0, "emails": 0}

        recent_jobs = (
            await session.execute(
                select(JobListing)
                .where(JobListing.discovered_at >= since)
                .where(JobListing.status == JobStatus.ACTIVE)
                .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
                .limit(500)
            )
        ).scalars().all()

        for alert in alerts:
            user = await session.get(User, alert.user_id)
            if user is None or not user.is_active:
                continue
            for job in recent_jobs:
                if alert.last_triggered_at and job.discovered_at and job.discovered_at <= alert.last_triggered_at:
                    continue
                if not _matches(alert, job):
                    continue
                session.add(
                    Notification(
                        user_id=user.id,
                        type=NotificationType.ALERT,
                        title=f"New {job.title} at {job.company_name}",
                        body=(
                            f"{job.title} · {job.company_name} · "
                            f"{job.location_city or job.location_raw or 'Remote'}"
                        ),
                        link=f"/jobs/{job.slug}",
                        payload={"job_id": str(job.id), "slug": job.slug},
                    )
                )
                created += 1
                alert.last_triggered_at = job.discovered_at or now
                alert.last_job_id = job.id
                if settings.email_enabled:
                    if await send_email(
                        user.email,
                        f"New job: {job.title} at {job.company_name}",
                        f"{job.title}\n{job.company_name}\n{job.apply_url}\n\n"
                        f"{settings.frontend_base_url}/jobs/{job.slug}",
                    ):
                        emailed += 1
        await session.commit()

    return {"alerts": len(alerts), "notifications": created, "emails": emailed}


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via SMTP when configured; log-only otherwise."""
    if not settings.email_enabled or not settings.smtp_host:
        log.info("email_skipped", to=to, subject=subject)
        return False
    try:
        from email.message import EmailMessage

        import aiosmtplib

        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=settings.smtp_port != 465,
        )
        return True
    except Exception as exc:
        log.warning("email_send_failed", to=to, error=str(exc))
        return False
