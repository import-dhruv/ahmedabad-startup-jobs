"""Duplicate detection across job sources.

Two postings are considered the same opening only when there is corroborating
evidence: the same application URL, the same external identifier, or the same
company *and* a matching normalised title plus a compatible location *and* a
similar description. Titles alone are never sufficient.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.services.normalizer import normalize_title, strip_html, title_signature

_COMPANY_SUFFIXES = (
    " pvt ltd", " private limited", " llp", " inc", " llc", " ltd", " technologies",
    " technology", " tech", " labs", " systems", " solutions", " software", " services",
    " the",
)

_WORD_RE = re.compile(r"[a-z0-9+#.]+")

STOPWORDS = {
    "a", "an", "and", "the", "of", "for", "to", "in", "with", "on", "at", "we", "our",
    "you", "your", "is", "are", "will", "be", "as", "by", "or", "from", "that", "this",
    "role", "team", "work", "working", "join", "new", "about",
}


def normalize_company(name: str | None) -> str:
    if not name:
        return ""
    value = name.lower().strip()
    value = re.sub(r"\s+", " ", value)
    for suffix in _COMPANY_SUFFIXES:
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value.strip(" -.,&")


def company_key(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_company(name))


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return url.strip().lower()
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = (parsed.path or "").rstrip("/")
    query = parsed.query or ""
    # drop tracking parameters that make the same link look different
    kept = "&".join(
        part for part in query.split("&")
        if part and not part.lower().startswith(("utm_", "gh_src", "ref", "source"))
    )
    return f"{host}{path}" + (f"?{kept}" if kept else "")


def location_key(raw: str | None) -> str:
    if not raw:
        return ""
    value = raw.lower().strip()
    value = re.sub(r"\s*[,/|]\s*", "|", value)
    value = re.sub(r"\s+", " ", value)
    return value


def tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    return {t for t in _WORD_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


@dataclass(slots=True)
class DuplicateVerdict:
    is_duplicate: bool
    confidence: float
    reason: str
    matched_on: str | None = None


def compare(
    *,
    company: str,
    title: str,
    location_raw: str | None,
    apply_url: str | None,
    description: str | None,
    candidate: dict,
) -> DuplicateVerdict:
    """Compare a new posting against an existing record.

    ``candidate`` is a mapping with keys: company, title, location_raw, apply_url,
    description, source_key, external_id.
    """
    new_company = company_key(company)
    old_company = company_key(candidate.get("company"))
    if new_company and old_company and new_company != old_company:
        return DuplicateVerdict(False, 0.0, "different company")

    # 1. Identical application URL is conclusive.
    new_url = normalize_url(apply_url)
    old_url = normalize_url(candidate.get("apply_url"))
    if new_url and old_url and new_url == old_url:
        return DuplicateVerdict(True, 1.0, "identical application URL", "apply_url")

    # 2. Compare title, location and description together. A matching title on
    #    its own is never enough — the description must corroborate it.
    new_sig = title_signature(title)
    old_sig = title_signature(candidate.get("title"))
    title_match = bool(new_sig) and new_sig == old_sig
    if not title_match:
        # titles must also be reasonably similar
        title_match = jaccard(tokenize(title), tokenize(candidate.get("title"))) >= 0.85

    desc_sim = jaccard(tokenize(strip_html(description)), tokenize(candidate.get("description")))

    new_loc = location_key(location_raw)
    old_loc = location_key(candidate.get("location_raw"))
    loc_match = (not new_loc and not old_loc) or new_loc == old_loc
    if not loc_match:
        new_parts = {p for p in new_loc.replace(",", "|").split("|") if p}
        old_parts = {p for p in old_loc.replace(",", "|").split("|") if p}
        # "Ahmedabad" and "Ahmedabad, Gujarat" describe the same place.
        subset = (new_parts and old_parts) and (new_parts <= old_parts or old_parts <= new_parts)
        loc_match = bool(subset) or jaccard(new_parts, old_parts) >= 0.6

    if title_match and loc_match and desc_sim >= 0.35:
        confidence = 0.7 + 0.25 * desc_sim
        return DuplicateVerdict(
            True,
            min(confidence, 0.97),
            "same company, title, location and description",
            "title+location+description",
        )

    # 3. Same company and near-identical description (re-titled posting).
    if desc_sim >= 0.85 and loc_match:
        return DuplicateVerdict(True, 0.75 + 0.2 * desc_sim, "near-identical description", "description")

    return DuplicateVerdict(False, 0.0, "no strong match")


def fingerprint(company: str, title: str, location_raw: str | None) -> str:
    """Stable fingerprint used for cheap pre-filtering in SQL."""
    import hashlib

    raw = f"{company_key(company)}|{normalize_title(title)}|{location_key(location_raw)}"
    return hashlib.sha256(raw.encode()).hexdigest()
