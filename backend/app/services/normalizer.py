"""Normalisation of raw job payloads into a canonical shape.

Pure functions only — no I/O — so they are trivially unit-testable.
"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field

from app.services import taxonomy
from app.services.geo import (
    GEO_SCOPE_AHMEDABAD,
    GEO_SCOPE_GUJARAT,
    GEO_SCOPE_INDIA,
    GEO_SCOPE_INDIA_REMOTE,
    ResolvedLocation,
    resolve_location,
)
from app.services.taxonomy import (
    CATEGORY_RULES,
    INDUSTRY_RULES,
    INTERN_MARKERS,
    SKILL_ALIASES,
    SKILL_CATALOG,
    SKILL_STOPWORDS,
)

# --- HTML / text ------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_BULLET_RE = re.compile(r"^\s*(?:[-*•▪◦‣·]|\d+[.)])\s*", re.M)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _SCRIPT_RE.sub(" ", value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|li|h[1-6]|tr)>", "\n", text, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n", text)
    return text.strip()


def split_bullets(value: str | None) -> list[str]:
    if not value:
        return []
    text = strip_html(value)
    lines = [_BULLET_RE.sub("", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if len(ln) > 2]


RESPONSIBILITY_HEADINGS = (
    "responsibilities", "what you'll do", "what you will do", "your role", "role & responsibilities",
    "about the role", "the role", "job description", "what you will be doing", "day to day",
    "duties", "key responsibilities", "your responsibilities", "role overview", "about the role",
)

QUALIFICATION_HEADINGS = (
    "requirements", "qualifications", "what we're looking for", "what we are looking for",
    "what you need", "skills", "required skills", "must have", "must-have", "minimum qualifications",
    "basic qualifications", "who you are", "we are looking for", "required qualifications",
    "eligibility", "desired", "preferred qualifications", "nice to have", "nice-to-have",
    "good to have", "your profile", "experience",
)

SKILL_HEADINGS = (
    "skills", "required skills", "technical skills", "tech stack", "technologies", "tools",
    "your skills", "core skills", "skills & competencies",
)

SECTION_SPLIT_RE = re.compile(
    r"\n(?=(?:responsibilities|requirements|qualifications|what you'?ll do|what you will do|"
    r"what we'?re looking for|what we are looking for|skills|education|perks & benefits|benefits|"
    r"about the (?:role|company|us)|role|key responsibilities|who you are|duties)\b)",
    re.I,
)


def split_sections(description: str | None) -> dict[str, list[str]]:
    """Split a free-text job description into responsibilities / qualifications / skills."""
    text = strip_html(description)
    if not text:
        return {"responsibilities": [], "qualifications": [], "skills": []}

    sections: dict[str, list[str]] = {}
    chunks = SECTION_SPLIT_RE.split(text)
    for chunk in chunks:
        if not chunk.strip():
            continue
        first_line = chunk.strip().splitlines()[0].lower().strip(" :*-—•")
        body = chunk.split("\n", 1)[1] if "\n" in chunk else ""
        bullets = split_bullets(body) or [ln.strip() for ln in body.splitlines() if ln.strip()]
        if not bullets:
            continue

        if any(h in first_line for h in RESPONSIBILITY_HEADINGS):
            sections.setdefault("responsibilities", []).extend(bullets)
        elif any(h in first_line for h in QUALIFICATION_HEADINGS):
            sections.setdefault("qualifications", []).extend(bullets)
        elif any(h in first_line for h in SKILL_HEADINGS):
            sections.setdefault("skills", []).extend(bullets)

    if "responsibilities" not in sections and "qualifications" not in sections:
        # No recognisable headings — fall back to prose splitting.
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        bullets = split_bullets(text)
        if bullets and len(bullets) >= 3:
            half = len(bullets) // 2
            sections["responsibilities"] = bullets[:half]
            sections["qualifications"] = bullets[half:]
        else:
            sections["responsibilities"] = paragraphs[:6]

    return {
        "responsibilities": sections.get("responsibilities", [])[:25],
        "qualifications": sections.get("qualifications", [])[:25],
        "skills": sections.get("skills", [])[:25],
    }


# --- Titles -----------------------------------------------------------------

TITLE_NOISE_RE = re.compile(
    r"\b(?:m/f/d/f|x|f|m)?\s*(?:fresher|entry[- ]level|junior|senior|sr\.?|staff|principal|lead|"
    r"intern|internship|trainee|apprentice|contract|freelance|part[- ]time|full[- ]time|remote|hybrid|"
    r"onsite|on[- ]site|night shift|day shift|urgent|immediate joiner|openings?|positions?)\b",
    re.I,
)


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    t = strip_html(title).lower().strip()
    t = re.sub(r"\s*[-–—|]\s*.*$", "", t) if len(t) > 90 else t
    t = re.sub(r"\([^)]*\)", " ", t)
    t = TITLE_NOISE_RE.sub(" ", t)
    t = re.sub(r"[^a-z0-9+#./\- ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -")
    t = re.sub(r"\s*([+#])\s*", r"\1", t)
    return t


def title_signature(title: str | None) -> str:
    """Aggressive signature used only to *suggest* duplicates, never to merge blindly."""
    t = normalize_title(title)
    tokens = [tok for tok in t.split() if tok not in {"of", "and", "the", "a", "an", "for", "to"}]
    return " ".join(sorted(set(tokens)))


# --- Experience -------------------------------------------------------------

EXPERIENCE_PATTERNS: list[tuple[str, float, float]] = [
    (r"fresher|graduate|fresh\b|no experience|0\s*years?|entry[- ]level|just graduated|final year", 0, 1),
    (r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\s*(?:\+\s*)?(?:years?|yrs?)", None, None),
    (r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)", None, None),
    (r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*(?:\+\s*)?(?:months?)", None, None),
]


def detect_experience(title: str | None, description: str | None) -> tuple[str | None, float | None, float | None]:
    from app.models.enums import EXPERIENCE_ORDER, ExperienceLevel

    title_l = (title or "").lower()
    body = f"{title or ''}\n{description or ''}".lower()

    for pattern in (r"fresher", r"graduate", r"fresh\b", r"no experience", r"0\s*\+\s*years?"):
        if re.search(pattern, title_l):
            return ExperienceLevel.FRESHER, 0, 1

    level_by_words: list[tuple[str, str]] = [
        (r"\bintern(?:ship)?\b|apprentice|trainee", ExperienceLevel.FRESHER),
        (r"\bentry[- ]level\b", ExperienceLevel.ENTRY),
        (r"\bjunior\b|\bjr\.?\b", ExperienceLevel.JUNIOR),
        (r"\bsenior\b|\bsr\.?\b|\bsnr\b", ExperienceLevel.SENIOR),
        (r"\bstaff\b|\bprincipal\b|\blead\b|\bhead of\b|\bdirector\b|\bmanager\b", ExperienceLevel.LEAD),
        (r"\bmid[- ]level\b|\bintermediate\b", ExperienceLevel.MID),
    ]
    for pattern, level in level_by_words:
        if re.search(pattern, title_l):
            return level, None, None

    # Numeric ranges in the description (prefer explicit "X to Y years").
    rng = re.search(r"(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)", body)
    if rng:
        lo, hi = float(rng.group(1)), float(rng.group(2))
        if hi < 12:
            return _level_for_years(lo), lo, hi

    yrs = re.search(r"(?:minimum|at least|min\.?|of)?\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)", body)
    if yrs:
        lo = float(yrs.group(1))
        if lo < 30:
            return _level_for_years(lo), lo, None

    months = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*months?", body)
    if months:
        lo = float(months.group(1)) / 12
        hi = float(months.group(2)) / 12
        return _level_for_years(lo), lo, hi

    return None, None, None


def _level_for_years(years: float) -> str:
    from app.models.enums import ExperienceLevel

    if years <= 0:
        return ExperienceLevel.FRESHER
    if years < 1:
        return ExperienceLevel.ENTRY
    if years < 3:
        return ExperienceLevel.JUNIOR
    if years < 5:
        return ExperienceLevel.MID
    if years < 8:
        return ExperienceLevel.SENIOR
    return ExperienceLevel.LEAD


# --- Employment type & work arrangement -------------------------------------

EMPLOYMENT_KEYWORDS: list[tuple[str, str]] = [
    ("Internship", (r"\bintern(?:ship)?\b", r"\btrainee\b", r"\bapprentice\b", r"\bco-?op\b")),
    ("Part-time", (r"\bpart[- ]time\b", r"\bpart time\b")),
    ("Freelance", (r"\bfreelance\b", r"\bcontractor\b")),
    ("Contract", (r"\bcontract(?:ual)?\b", r"\bfixed[- ]term\b", r"\bconsultant role\b")),
    ("Apprenticeship", (r"\bapprentice(?:ship)?\b",)),
    ("Full-time", (r"\bfull[- ]time\b", r"\bpermanent\b", r"\bfull time\b")),
]


EMPLOYMENT_TYPE_ALIASES: dict[str, str] = {
    "full_time": "Full-time",
    "full time": "Full-time",
    "fulltime": "Full-time",
    "permanent": "Full-time",
    "part_time": "Part-time",
    "part time": "Part-time",
    "parttime": "Part-time",
    "intern": "Internship",
    "internship": "Internship",
    "trainee": "Internship",
    "apprentice": "Apprenticeship",
    "apprenticeship": "Apprenticeship",
    "contract": "Contract",
    "contractor": "Contract",
    "temporary": "Contract",
    "fixed-term": "Contract",
    "freelance": "Freelance",
    "freelancer": "Freelance",
}


def canonical_employment_type(value: str | None) -> str | None:
    """Map a source-specific employment label onto the platform's canonical set."""
    if not value:
        return None
    cleaned = value.strip().lower().replace("_", " ")
    cleaned = " ".join(cleaned.split())
    if cleaned in EMPLOYMENT_TYPE_ALIASES:
        return EMPLOYMENT_TYPE_ALIASES[cleaned]
    from app.models.enums import EmploymentType

    for option in EmploymentType:
        if option.value.lower() == cleaned:
            return option.value
    return None


def detect_employment_type(title: str | None, description: str | None) -> str | None:
    from app.models.enums import EmploymentType

    title_l = (title or "").lower()
    body = (description or "").lower()

    # The title is the strongest signal; only fall back to the body when the
    # title says nothing about the engagement type.
    for source in (title_l, body):
        if not source:
            continue
        for label, patterns in EMPLOYMENT_KEYWORDS:
            if any(re.search(p, source) for p in patterns):
                return label
    return None


ARRANGEMENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Remote", (r"\bremote\b", r"\bwork from home\b", r"\bwfh\b", r"\banywhere\b", r"\bdistributed\b")),
    ("Hybrid", (r"\bhybrid\b", r"\bpartly remote\b")),
    ("On-site", (r"\bon[- ]?site\b", r"\bin[- ]office\b", r"\bin[- ]person\b", r"\bon office\b")),
]


def detect_work_arrangement(
    title: str | None, description: str | None, location_raw: str | None = None
) -> str | None:
    text = f"{title or ''} {description or ''} {location_raw or ''}".lower()
    for label, patterns in ARRANGEMENT_KEYWORDS:
        if any(re.search(p, text) for p in patterns):
            return label
    return None


# --- Salary -----------------------------------------------------------------

SALARY_PATTERNS = [
    r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:lpa|lakh|lakhs)?\s*(?:a\s*)?(?:per\s*)?(?:annum|year|yr|month|monthly)?",
    r"\$?\s*([\d,]+(?:\.\d+)?)\s*k?\s*(?:per\s*)?(?:annum|year|yr)?",
]


def detect_salary(description: str | None, title: str | None = None) -> tuple[int | None, int | None, str | None, str | None]:
    """Return (min, max, currency, period) only when the text explicitly states a range."""
    if not description:
        return None, None, None, None
    text = strip_html(description)
    currency = None
    if re.search(r"(?:rs\.?|inr|₹)", text, re.I):
        currency = "INR"
    elif re.search(r"\$|usd", text, re.I):
        currency = "USD"

    period = None
    if re.search(r"per\s*month|monthly|/\s*month|p\.m\.", text, re.I):
        period = "month"
    elif re.search(r"per\s*(?:annum|year)|lpa|lakh|\bpa\b|annually|\bctc\b", text, re.I):
        period = "year"

    range_match = re.search(
        r"(?:rs\.?|inr|₹|\$)?\s*([\d,]+(?:\.\d+)?)\s*(?:lpa|lakh| lakhs?)?\s*"
        r"(?:-|–|—|to)\s*"
        r"(?:rs\.?|inr|₹|\$)?\s*([\d,]+(?:\.\d+)?)\s*(?:lpa|lakh| lakhs?|k\b)?",
        text,
        re.I,
    )
    if not range_match:
        # "between ₹15,00,000 and ₹25,00,000 per annum"
        range_match = re.search(
            r"between\s*(?:rs\.?|inr|₹|\$)?\s*([\d,]+(?:\.\d+)?)\s*"
            r"(?:lpa|lakh| lakhs?)?\s*(?:and|to|-|–)\s*"
            r"(?:rs\.?|inr|₹|\$)?\s*([\d,]+(?:\.\d+)?)\s*(?:lpa|lakh| lakhs?|k\b)?",
            text,
            re.I,
        )
    if range_match:
        lo = _parse_amount(range_match.group(1))
        hi = _parse_amount(range_match.group(2))
        if lo is not None and hi is not None and hi >= lo and hi < 100_000_000:
            if period == "year" and currency in (None, "INR") and hi < 1000:
                lo, hi = lo * 100_000, hi * 100_000
            return lo, hi, currency or "INR", period or "year"

    single = re.search(r"(?:rs\.?|inr|₹|\$)\s*([\d,]+(?:\.\d+)?)\s*(lpa|lakh| k\b|k\b)", text, re.I)
    if single:
        val = _parse_amount(single.group(1))
        unit = (single.group(2) or "").lower()
        if val is not None:
            if unit.startswith("lpa") or unit.startswith("lakh"):
                return int(val * 100_000), int(val * 100_000), currency or "INR", "year"
            if unit.startswith("k"):
                return int(val * 1000), int(val * 1000), currency or "INR", "year"
    return None, None, None, None


def _parse_amount(raw: str) -> float | None:
    try:
        return float(raw.replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# --- Skills -----------------------------------------------------------------


def extract_skills(text: str | None, title: str | None = None) -> list[tuple[str, float]]:
    """Extract canonical skills from free text. Returns (skill_name, confidence)."""
    if not text and not title:
        return []
    haystack = f"{title or ''}\n{text or ''}"
    hay = haystack.lower()
    found: dict[str, float] = {}

    for canonical, (category, is_ai) in SKILL_CATALOG.items():
        pattern = rf"(?<![a-z0-9]){re.escape(canonical.lower())}(?![a-z0-9])"
        if re.search(pattern, hay):
            found[canonical] = 1.0 if canonical.lower() in (title or "").lower() else 0.9

    for alias, canonical in SKILL_ALIASES.items():
        if canonical in found:
            continue
        if len(alias) < 2:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9+])"
        if re.search(pattern, hay):
            found[canonical] = 0.75

    # AI-specific skills must be supported by real context, not a single word
    # match buried in a responsibilities list.
    ai_only = {"Agentic AI", "Fine-tuning", "Prompt Engineering", "Vector Search", "MLOps"}
    for skill in list(ai_only):
        if skill not in found:
            continue
        if not re.search(rf"(?<![a-z]){re.escape(skill.lower())}(?![a-z])", hay):
            found.pop(skill, None)
        elif skill in {"Agentic AI", "Fine-tuning", "Prompt Engineering", "MLOps", "Vector Search"}:
            # Require a second supporting signal (framework, model or technique).
            supporting = re.search(
                r"(?<![a-z])(llm|gpt|claude|gemini|llama|rag|retrieval|embedding|vector|"
                r"langchain|langgraph|openai|anthropic|hugging ?face|prompt|agent|tool ?use|"
                r"fine[- ]?tun|pipeline|model|mlops|docker|kubernetes)(?![a-z])",
                hay,
            )
            if not supporting:
                found.pop(skill, None)

    return sorted(found.items(), key=lambda kv: (-kv[1], kv[0]))


def detect_categories(title: str | None, description: str | None) -> list[tuple[str, float]]:
    text = f"{title or ''} {description or ''}".lower()
    results: list[tuple[str, float]] = []
    for category, keywords in CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            results.append((category, 0.85))
    if not results:
        results.append(("Software Engineering", 0.4))
    return results[:4]


def detect_industry(company_text: str | None, job_text: str | None = None) -> str:
    text = f" {company_text or ''} {job_text or ''} ".lower()
    best: tuple[str, int] | None = None
    for industry, keywords in INDUSTRY_RULES:
        hits = sum(1 for kw in keywords if kw in text)
        if hits and (best is None or hits > best[1]):
            best = (industry, hits)
    return best[0] if best else "Other technology startups"


def is_internship(title: str | None, description: str | None, employment_type: str | None) -> bool:
    if employment_type == "Internship":
        return True
    text = f"{title or ''} {description or ''}".lower()
    return any(re.search(rf"(?<![a-z]){re.escape(m)}(?![a-z])", text) for m in INTERN_MARKERS)


# --- Misc -------------------------------------------------------------------


def company_slug(name: str) -> str:
    return taxonomy.slugify(name)


def content_hash(*parts: str | None) -> str:
    joined = "||".join((p or "") for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class NormalizedJob:
    title: str
    normalized_title: str
    company_name: str
    description: str | None
    responsibilities: list[str] = field(default_factory=list)
    qualifications: list[str] = field(default_factory=list)
    skills: list[tuple[str, float]] = field(default_factory=list)
    categories: list[tuple[str, float]] = field(default_factory=list)
    experience_level: str | None = None
    experience_min_years: float | None = None
    experience_max_years: float | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    employment_type: str | None = None
    work_arrangement: str | None = None
    location: ResolvedLocation | None = None
    is_remote: bool = False
    department: str | None = None
    quality_score: float = 0.0


def compute_quality_score(job: NormalizedJob) -> float:
    """Heuristic 0-1 score indicating how complete/usable a listing is."""
    score = 0.0
    if job.description and len(job.description) > 200:
        score += 0.30
    elif job.description and len(job.description) > 60:
        score += 0.15
    if job.experience_level:
        score += 0.12
    if job.employment_type:
        score += 0.10
    if job.location and job.location.scope not in ("other",):
        score += 0.10
    if job.salary_min is not None:
        score += 0.12
    if job.skills:
        score += 0.10
    if job.categories:
        score += 0.06
    if job.work_arrangement:
        score += 0.05
    if job.responsibilities:
        score += 0.05
    return round(min(score, 1.0), 3)


def normalize_job_fields(
    *,
    title: str,
    company_name: str,
    description: str | None,
    location_raw: str | None,
    department: str | None = None,
) -> NormalizedJob:
    clean_desc = strip_html(description)
    sections = split_sections(description)
    level, exp_min, exp_max = detect_experience(title, clean_desc)
    employment = detect_employment_type(title, clean_desc)
    arrangement = detect_work_arrangement(title, clean_desc, location_raw)
    location = resolve_location(location_raw)
    salary_min, salary_max, currency, period = detect_salary(clean_desc, title)

    if arrangement == "Remote":
        location.is_remote = True
    if location.is_remote and location.scope in ("other",):
        location.scope = GEO_SCOPE_INDIA_REMOTE if location.country == "India" else location.scope

    skills = extract_skills(clean_desc, title)
    categories = detect_categories(title, clean_desc)
    if is_internship(title, clean_desc, employment):
        categories = [(c, conf) for c, conf in categories if c not in ("Software Engineering",)]
        categories.insert(0, ("Internship", 0.95))

    job = NormalizedJob(
        title=strip_html(title).strip() or "Untitled role",
        normalized_title=normalize_title(title),
        company_name=strip_html(company_name).strip() or "Unknown company",
        description=clean_desc or None,
        responsibilities=sections["responsibilities"],
        qualifications=sections["qualifications"],
        skills=skills,
        categories=categories,
        experience_level=level,
        experience_min_years=exp_min,
        experience_max_years=exp_max,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        salary_period=period,
        employment_type=employment,
        work_arrangement=arrangement,
        location=location,
        is_remote=location.is_remote,
        department=strip_html(department).strip() if department else None,
    )
    job.quality_score = compute_quality_score(job)
    return job


def geo_in_scope(scope: str, scopes: set[str]) -> bool:
    return scope in scopes


__all__ = [
    "GEO_SCOPE_AHMEDABAD",
    "GEO_SCOPE_GUJARAT",
    "GEO_SCOPE_INDIA",
    "GEO_SCOPE_INDIA_REMOTE",
    "NormalizedJob",
    "compute_quality_score",
    "content_hash",
    "detect_categories",
    "detect_employment_type",
    "detect_experience",
    "detect_industry",
    "detect_salary",
    "detect_work_arrangement",
    "extract_skills",
    "is_internship",
    "normalize_job_fields",
    "normalize_title",
    "split_bullets",
    "split_sections",
    "strip_html",
    "taxonomy",
    "SKILL_STOPWORDS",
]
