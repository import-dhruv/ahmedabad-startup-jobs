"""Candidate-to-job matching.

Transparent, explainable scoring: skill overlap plus experience compatibility
plus location/arrangement preferences. No black box.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import CandidateProfile, JobListing
from app.models.enums import EXPERIENCE_ORDER


@dataclass(slots=True)
class MatchResult:
    job: JobListing
    score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _profile_skill_set(profile: CandidateProfile | None) -> set[str]:
    if profile is None:
        return set()
    return {s.strip().lower() for s in (profile.skills or []) if s.strip()}


def score_job(profile: CandidateProfile | None, job: JobListing, job_skills: list[str]) -> MatchResult:
    reasons: list[str] = []
    score = 0.0

    profile_skills = _profile_skill_set(profile)
    job_skill_set = {s.strip().lower() for s in job_skills if s.strip()}
    matched = sorted(profile_skills & job_skill_set)
    missing = sorted(job_skill_set - profile_skills)

    if job_skill_set:
        overlap_ratio = len(matched) / len(job_skill_set)
        score += overlap_ratio * 55
        if matched:
            reasons.append(f"Matches {len(matched)} of {len(job_skill_set)} required skills")
    elif profile_skills:
        score += 5

    # Experience compatibility
    if profile is not None and profile.experience_years is not None and job.experience_level:
        required = EXPERIENCE_ORDER.get(job.experience_level, 2)
        candidate_years = float(profile.experience_years)
        if candidate_years >= required + 1:
            score += 25
            reasons.append("Experience exceeds the level requested")
        elif candidate_years >= required:
            score += 18
            reasons.append("Experience matches the level requested")
        elif candidate_years >= required - 1:
            score += 8
            reasons.append("Slightly under the preferred experience")
        else:
            score -= 10
            reasons.append("Below the experience level requested")
    elif job.experience_level in ("Fresher", "0-1 years"):
        score += 12
        reasons.append("Open to freshers")

    # Preferred employment types
    if profile is not None and profile.preferred_job_types:
        if job.employment_type and job.employment_type in profile.preferred_job_types:
            score += 8
            reasons.append(f"Matches preferred type: {job.employment_type}")

    # Work arrangement
    if profile is not None and profile.preferred_arrangements:
        if job.work_arrangement and job.work_arrangement in profile.preferred_arrangements:
            score += 7
            reasons.append(f"Matches preferred arrangement: {job.work_arrangement}")
        elif profile.open_to_remote and job.is_remote:
            score += 4

    # Location
    if profile is not None and profile.preferred_locations:
        city = (job.location_city or "").lower()
        state = (job.location_state or "").lower()
        for preferred in profile.preferred_locations:
            p = preferred.strip().lower()
            if p and (p == city or p == state or p in (job.location_raw or "").lower()):
                score += 8
                reasons.append(f"Located in {preferred}")
                break

    # Salary expectations
    if profile is not None and profile.expected_salary_max and job.salary_min:
        if job.salary_min >= profile.expected_salary_max:
            score -= 5
            reasons.append("Salary is below your expectation")

    score = max(0.0, min(100.0, score))
    return MatchResult(
        job=job,
        score=round(score, 1),
        matched_skills=matched,
        missing_skills=missing,
        reasons=reasons,
    )


def score_job_dict(profile: CandidateProfile | None, job: dict[str, Any]) -> dict[str, Any]:
    """Score an already-serialised job payload (used by the API layer)."""
    job_skills = job.get("skills") or []
    profile_skills = _profile_skill_set(profile)
    job_skill_set = {s.strip().lower() for s in job_skills if s.strip()}
    matched = sorted(profile_skills & job_skill_set)
    missing = sorted(job_skill_set - profile_skills)

    score = 0.0
    reasons: list[str] = []
    if job_skill_set:
        score += (len(matched) / len(job_skill_set)) * 55
        if matched:
            reasons.append(f"Matches {len(matched)} of {len(job_skill_set)} required skills")

    experience_years = profile.experience_years if profile else None
    level = job.get("experience_level")
    if experience_years is not None and level:
        required = EXPERIENCE_ORDER.get(level, 2)
        if experience_years >= required + 1:
            score += 25
            reasons.append("Experience exceeds the level requested")
        elif experience_years >= required:
            score += 18
            reasons.append("Experience matches the level requested")
        elif experience_years >= required - 1:
            score += 8
            reasons.append("Slightly under the preferred experience")
        else:
            score -= 10
            reasons.append("Below the experience level requested")
    elif level in ("Fresher", "0-1 years"):
        score += 12
        reasons.append("Open to freshers")

    if profile and profile.preferred_job_types and job.get("employment_type") in profile.preferred_job_types:
        score += 8
        reasons.append(f"Matches preferred type: {job.get('employment_type')}")
    if profile and profile.preferred_arrangements:
        if job.get("work_arrangement") in profile.preferred_arrangements:
            score += 7
            reasons.append(f"Matches preferred arrangement: {job.get('work_arrangement')}")
        elif profile.open_to_remote and job.get("is_remote"):
            score += 4
    if profile and profile.preferred_locations:
        city = (job.get("location_city") or "").lower()
        for preferred in profile.preferred_locations:
            p = preferred.strip().lower()
            if p and (p == city or p in (job.get("location_raw") or "").lower()):
                score += 8
                reasons.append(f"Located in {preferred}")
                break

    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "matched_skills": matched,
        "missing_skills": missing,
        "reasons": reasons,
    }
