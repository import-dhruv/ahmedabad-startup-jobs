"""Candidate-facing endpoints: profile, saved items, alerts, applications."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, PaginationDep
from app.core.config import settings
from app.core.logging import get_logger
from app.models import (
    CandidateProfile,
    JobAlert,
    JobApplication,
    JobListing,
    JobSkill,
    Notification,
    SavedJob,
    SavedSearch,
    SavedStartup,
    Skill,
    Startup,
    UserJobView,
)
from app.models.enums import JobStatus
from app.schemas import (
    AlertCreate,
    AlertRead,
    ApplicationCreate,
    ApplicationRead,
    NotificationRead,
    ProfileRead,
    ProfileUpdate,
    SavedSearchCreate,
    SavedSearchRead,
)
from app.services.matching import score_job_dict

log = get_logger(__name__)

router = APIRouter(prefix="/me", tags=["candidate"])

ACTIVE_SCOPES = ("ahmedabad", "gujarat", "india_remote", "india", "global")


async def _get_or_create_profile(db: Any, user_id: uuid.UUID) -> CandidateProfile:
    stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if profile is None:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("/profile", response_model=ProfileRead)
async def get_profile(user: CurrentUser, db: DbSession) -> ProfileRead:
    profile = await _get_or_create_profile(db, user.id)
    return ProfileRead.model_validate(profile)


@router.patch("/profile", response_model=ProfileRead)
async def update_profile(payload: ProfileUpdate, user: CurrentUser, db: DbSession) -> ProfileRead:
    profile = await _get_or_create_profile(db, user.id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return ProfileRead.model_validate(profile)


@router.post("/profile/resume", response_model=ProfileRead)
async def upload_resume(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File(description="Resume file (pdf, doc, docx, txt) up to 5MB")],
) -> ProfileRead:
    allowed = {".pdf", ".doc", ".docx", ".txt", ".rtf"}
    filename = file.filename or "resume"
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported resume type: {suffix}")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Resume must be under 5MB")

    profile = await _get_or_create_profile(db, user.id)
    storage = settings.resume_storage_path
    try:
        import pathlib

        path = pathlib.Path(storage)
        path.mkdir(parents=True, exist_ok=True)
        target = path / f"{user.id}{suffix}"
        target.write_bytes(content)
        profile.resume_url = "/api/v1/me/profile/resume/file"
        profile.resume_filename = filename
        profile.resume_uploaded_at = datetime.now(UTC)
    except OSError as exc:
        log.warning("resume_save_failed", error=str(exc))
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not store the resume") from exc

    await db.commit()
    await db.refresh(profile)
    return ProfileRead.model_validate(profile)


# --- Saved jobs / startups --------------------------------------------------


@router.post("/saved-jobs/{job_id}", status_code=status.HTTP_201_CREATED)
async def save_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession) -> dict[str, bool]:
    exists = (
        await db.execute(select(SavedJob).where(SavedJob.user_id == user.id, SavedJob.job_id == job_id))
    ).scalar_one_or_none()
    if exists is None:
        job = await db.get(JobListing, job_id)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        db.add(SavedJob(user_id=user.id, job_id=job_id))
        await db.commit()
    return {"saved": True}


@router.delete("/saved-jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    saved = (
        await db.execute(select(SavedJob).where(SavedJob.user_id == user.id, SavedJob.job_id == job_id))
    ).scalar_one_or_none()
    if saved is not None:
        await db.delete(saved)
        await db.commit()


@router.get("/saved-jobs")
async def list_saved_jobs(user: CurrentUser, db: DbSession, pagination: PaginationDep) -> dict[str, Any]:
    total = (
        await db.execute(select(func.count(SavedJob.id)).where(SavedJob.user_id == user.id))
    ).scalar_one()
    stmt = (
        select(JobListing)
        .join(SavedJob, SavedJob.job_id == JobListing.id)
        .where(SavedJob.user_id == user.id)
        .options(selectinload(JobListing.startup), selectinload(JobListing.source))
        .order_by(SavedJob.created_at.desc())
        .limit(pagination.per_page)
        .offset(pagination.offset)
    )
    jobs = (await db.execute(stmt)).scalars().all()
    from app.api.v1.jobs import _job_to_summary

    skill_stmt = select(JobSkill.job_id, Skill.name).join(Skill, Skill.id == JobSkill.skill_id).where(
        JobSkill.job_id.in_([j.id for j in jobs] or [uuid.UUID(int=0)])
    )
    skill_map: dict[uuid.UUID, list[str]] = {}
    for job_id, name in (await db.execute(skill_stmt)).all():
        skill_map.setdefault(job_id, []).append(name)

    return {
        "items": [
            _job_to_summary(job, skill_map.get(job.id, []), [job.category] if job.category else [])
            for job in jobs
        ],
        "total": total,
        "page": pagination.page,
        "per_page": pagination.per_page,
    }


@router.post("/saved-startups/{startup_id}", status_code=status.HTTP_201_CREATED)
async def save_startup(startup_id: uuid.UUID, user: CurrentUser, db: DbSession) -> dict[str, bool]:
    exists = (
        await db.execute(
            select(SavedStartup).where(
                SavedStartup.user_id == user.id, SavedStartup.startup_id == startup_id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        startup = await db.get(Startup, startup_id)
        if startup is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Startup not found")
        db.add(SavedStartup(user_id=user.id, startup_id=startup_id))
        await db.commit()
    return {"saved": True}


@router.delete("/saved-startups/{startup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_startup(startup_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    saved = (
        await db.execute(
            select(SavedStartup).where(
                SavedStartup.user_id == user.id, SavedStartup.startup_id == startup_id
            )
        )
    ).scalar_one_or_none()
    if saved is not None:
        await db.delete(saved)
        await db.commit()


@router.get("/saved-startups")
async def list_saved_startups(user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    stmt = (
        select(Startup)
        .join(SavedStartup, SavedStartup.startup_id == Startup.id)
        .where(SavedStartup.user_id == user.id)
        .order_by(SavedStartup.created_at.desc())
    )
    startups = (await db.execute(stmt)).scalars().all()
    out = []
    for startup in startups:
        count = (
            await db.execute(
                select(func.count(JobListing.id))
                .where(JobListing.startup_id == startup.id)
                .where(JobListing.status == JobStatus.ACTIVE)
            )
        ).scalar_one()
        out.append(
            {
                "id": str(startup.id),
                "name": startup.name,
                "slug": startup.slug,
                "logo_url": startup.logo_url,
                "website": startup.website,
                "industry": startup.industry,
                "hq_city": startup.hq_city,
                "active_job_count": count,
            }
        )
    return out


# --- Alerts ------------------------------------------------------------------


@router.get("/alerts", response_model=list[AlertRead])
async def list_alerts(user: CurrentUser, db: DbSession) -> list[AlertRead]:
    stmt = select(JobAlert).where(JobAlert.user_id == user.id).order_by(JobAlert.created_at.desc())
    alerts = (await db.execute(stmt)).scalars().all()
    return [AlertRead.model_validate(a) for a in alerts]


@router.post("/alerts", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
async def create_alert(payload: AlertCreate, user: CurrentUser, db: DbSession) -> AlertRead:
    alert = JobAlert(user_id=user.id, **payload.model_dump())
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return AlertRead.model_validate(alert)


@router.patch("/alerts/{alert_id}", response_model=AlertRead)
async def update_alert(alert_id: uuid.UUID, payload: AlertCreate, user: CurrentUser, db: DbSession) -> AlertRead:
    alert = (
        await db.execute(select(JobAlert).where(JobAlert.id == alert_id, JobAlert.user_id == user.id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    await db.commit()
    await db.refresh(alert)
    return AlertRead.model_validate(alert)


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    alert = (
        await db.execute(select(JobAlert).where(JobAlert.id == alert_id, JobAlert.user_id == user.id))
    ).scalar_one_or_none()
    if alert is not None:
        await db.delete(alert)
        await db.commit()


# --- Saved searches ----------------------------------------------------------


@router.get("/saved-searches", response_model=list[SavedSearchRead])
async def list_saved_searches(user: CurrentUser, db: DbSession) -> list[SavedSearchRead]:
    stmt = (
        select(SavedSearch)
        .where(SavedSearch.user_id == user.id)
        .order_by(SavedSearch.created_at.desc())
    )
    return [SavedSearchRead.model_validate(s) for s in (await db.execute(stmt)).scalars().all()]


@router.post("/saved-searches", response_model=SavedSearchRead, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    payload: SavedSearchCreate, user: CurrentUser, db: DbSession
) -> SavedSearchRead:
    search = SavedSearch(user_id=user.id, **payload.model_dump())
    db.add(search)
    await db.commit()
    await db.refresh(search)
    return SavedSearchRead.model_validate(search)


@router.delete("/saved-searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(search_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    search = (
        await db.execute(
            select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id)
        )
    ).scalar_one_or_none()
    if search is not None:
        await db.delete(search)
        await db.commit()


# --- Applications ------------------------------------------------------------


@router.get("/applications", response_model=list[ApplicationRead])
async def list_applications(user: CurrentUser, db: DbSession) -> list[ApplicationRead]:
    stmt = (
        select(JobApplication)
        .where(JobApplication.user_id == user.id)
        .order_by(JobApplication.created_at.desc())
    )
    return [ApplicationRead.model_validate(a) for a in (await db.execute(stmt)).scalars().all()]


@router.post("/applications", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate, user: CurrentUser, db: DbSession
) -> ApplicationRead:
    exists = (
        await db.execute(
            select(JobApplication).where(
                JobApplication.user_id == user.id, JobApplication.job_id == payload.job_id
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        return ApplicationRead.model_validate(exists)
    job = await db.get(JobListing, payload.job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    application = JobApplication(
        user_id=user.id,
        job_id=payload.job_id,
        status=payload.status,
        notes=payload.notes,
        applied_at=datetime.now(UTC),
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return ApplicationRead.model_validate(application)


@router.patch("/applications/{application_id}", response_model=ApplicationRead)
async def update_application(
    application_id: uuid.UUID, payload: ApplicationCreate, user: CurrentUser, db: DbSession
) -> ApplicationRead:
    application = (
        await db.execute(
            select(JobApplication).where(
                JobApplication.id == application_id, JobApplication.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    application.status = payload.status
    if payload.notes is not None:
        application.notes = payload.notes
    await db.commit()
    await db.refresh(application)
    return ApplicationRead.model_validate(application)


# --- Recently viewed ---------------------------------------------------------


@router.get("/recently-viewed")
async def recently_viewed(user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    stmt = (
        select(JobListing, UserJobView.viewed_at)
        .join(UserJobView, UserJobView.job_id == JobListing.id)
        .where(UserJobView.user_id == user.id)
        .options(selectinload(JobListing.startup), selectinload(JobListing.source))
        .order_by(UserJobView.viewed_at.desc())
        .limit(20)
    )
    from app.api.v1.jobs import _job_to_summary

    rows = (await db.execute(stmt)).all()
    return [
        {**_job_to_summary(job, [], [job.category] if job.category else []).model_dump(),
         "viewed_at": viewed_at.isoformat()}
        for job, viewed_at in rows
    ]


# --- Recommendations ---------------------------------------------------------


@router.get("/recommendations")
async def recommendations(user: CurrentUser, db: DbSession, limit: int = Query(12, ge=1, le=50)) -> dict[str, Any]:
    """Jobs scored against the candidate profile (transparent skill/experience match)."""
    profile = await _get_or_create_profile(db, user.id)

    stmt = (
        select(JobListing)
        .where(JobListing.status == JobStatus.ACTIVE)
        .where(JobListing.geo_scope.in_(ACTIVE_SCOPES))
        .options(selectinload(JobListing.startup), selectinload(JobListing.source))
        .order_by(func.coalesce(JobListing.posted_at, JobListing.discovered_at).desc())
        .limit(400)
    )
    jobs = (await db.execute(stmt)).scalars().all()

    skill_stmt = select(JobSkill.job_id, Skill.name).join(Skill, Skill.id == JobSkill.skill_id).where(
        JobSkill.job_id.in_([j.id for j in jobs] or [uuid.UUID(int=0)])
    )
    skill_map: dict[uuid.UUID, list[str]] = {}
    for job_id, name in (await db.execute(skill_stmt)).all():
        skill_map.setdefault(job_id, []).append(name)

    from app.api.v1.jobs import _job_to_summary

    scored = []
    for job in jobs:
        payload = _job_to_summary(job, skill_map.get(job.id, []), [job.category] if job.category else [])
        match = score_job_dict(profile, payload.model_dump())
        # Only surface roles that share something meaningful with the profile.
        if not match["matched_skills"] and match["score"] < 30:
            continue
        scored.append((match, payload))

    scored.sort(key=lambda item: item[0]["score"], reverse=True)
    top = scored[:limit]
    return {
        "items": [
            {
                "job": payload.model_dump(),
                "match": match,
            }
            for match, payload in top
        ],
        "profile_complete": bool(profile.skills or profile.experience_years is not None),
        "note": "Scores are computed from your profile's skills and experience against each listing.",
    }


# --- Notifications -----------------------------------------------------------


@router.get("/notifications", response_model=list[NotificationRead])
async def list_notifications(
    user: CurrentUser, db: DbSession, unread_only: bool = False
) -> list[NotificationRead]:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(50)
    return [NotificationRead.model_validate(n) for n in (await db.execute(stmt)).scalars().all()]


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
async def mark_read(notification_id: uuid.UUID, user: CurrentUser, db: DbSession) -> NotificationRead:
    notification = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return NotificationRead.model_validate(notification)
