"""Tests for duplicate detection."""
from app.services.dedup import (
    company_key,
    compare,
    fingerprint,
    jaccard,
    location_key,
    normalize_url,
    title_signature,
    tokenize,
)


def _candidate(**overrides):
    base = {
        "company": "Example Startup",
        "title": "Backend Engineer",
        "location_raw": "Ahmedabad, Gujarat",
        "apply_url": "https://example.com/jobs/1",
        "description": "Build APIs with Python and FastAPI on PostgreSQL.",
    }
    base.update(overrides)
    return base


class TestCompanyKey:
    def test_normalises_suffixes(self):
        assert company_key("Example Startup Pvt Ltd") == company_key("Example Startup")

    def test_case_and_punctuation_insensitive(self):
        assert company_key("example, startup.") == company_key("Example Startup")


class TestNormaliseUrl:
    def test_strips_www_and_trailing_slash(self):
        assert normalize_url("https://www.example.com/jobs/1/") == "example.com/jobs/1"

    def test_drops_tracking_params(self):
        a = normalize_url("https://example.com/jobs/1?utm_source=x")
        b = normalize_url("https://example.com/jobs/1")
        assert a == b


class TestCompare:
    def test_identical_apply_url_is_duplicate(self):
        verdict = compare(
            company="Example Startup",
            title="Backend Engineer",
            location_raw="Ahmedabad",
            apply_url="https://example.com/jobs/1?utm_source=twitter",
            description="Some description",
            candidate=_candidate(),
        )
        assert verdict.is_duplicate is True
        assert verdict.matched_on == "apply_url"

    def test_same_company_title_and_location_is_duplicate(self):
        verdict = compare(
            company="Example Startup",
            title="Backend Engineer",
            location_raw="Ahmedabad, Gujarat",
            apply_url="https://other-board.com/role/9",
            description="Build APIs with Python and FastAPI on PostgreSQL. Ship things daily.",
            candidate=_candidate(),
        )
        assert verdict.is_duplicate is True

    def test_different_company_is_never_duplicate(self):
        verdict = compare(
            company="Another Company",
            title="Backend Engineer",
            location_raw="Ahmedabad, Gujarat",
            apply_url="https://example.com/jobs/1",
            description=_candidate()["description"],
            candidate=_candidate(),
        )
        assert verdict.is_duplicate is False

    def test_same_title_different_location_is_not_duplicate(self):
        verdict = compare(
            company="Example Startup",
            title="Backend Engineer",
            location_raw="Bengaluru, India",
            apply_url="https://example.com/jobs/2",
            description="Build APIs with Python and FastAPI on PostgreSQL.",
            candidate=_candidate(),
        )
        assert verdict.is_duplicate is False

    def test_same_title_alone_is_not_enough(self):
        verdict = compare(
            company="Example Startup",
            title="Backend Engineer",
            location_raw="Ahmedabad, Gujarat",
            apply_url="https://example.com/jobs/999",
            description="Completely different description about marketing and design work.",
            candidate=_candidate(),
        )
        assert verdict.is_duplicate is False

    def test_near_identical_description_is_duplicate(self):
        long_description = (
            "We are looking for a backend engineer to build our APIs with Python and FastAPI "
            "on PostgreSQL, deploy with Docker and work with the founding team in Ahmedabad."
        )
        verdict = compare(
            company="Example Startup",
            title="Senior Platform Engineer",
            location_raw="Ahmedabad",
            apply_url="https://another.com/x",
            description=long_description,
            candidate=_candidate(description=long_description),
        )
        assert verdict.is_duplicate is True


class TestHelpers:
    def test_fingerprint_is_stable(self):
        a = fingerprint("Example Startup", "Backend Engineer", "Ahmedabad")
        b = fingerprint("example startup", "backend engineer", "ahmedabad")
        assert a == b

    def test_title_signature_ignores_fillers(self):
        assert title_signature("Software Engineer, Backend") == title_signature(
            "Backend Software Engineer"
        )

    def test_location_key_normalises_separators(self):
        assert location_key("Ahmedabad, Gujarat") == location_key("Ahmedabad | Gujarat")

    def test_jaccard_bounds(self):
        assert jaccard(set(), {"a"}) == 0.0
        assert jaccard({"a"}, {"a"}) == 1.0

    def test_tokenize_drops_stopwords(self):
        tokens = tokenize("We are a team of engineers")
        assert "engineers" in tokens
        assert "we" not in tokens
