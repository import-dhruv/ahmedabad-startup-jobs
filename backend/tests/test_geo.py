"""Tests for the geo resolver."""
from app.services.geo import (
    GEO_SCOPE_AHMEDABAD,
    GEO_SCOPE_GLOBAL,
    GEO_SCOPE_GUJARAT,
    GEO_SCOPE_INDIA,
    GEO_SCOPE_INDIA_REMOTE,
    resolve_location,
)


class TestResolveLocation:
    def test_ahmedabad_city(self):
        result = resolve_location("Ahmedabad, Gujarat")
        assert result.city == "Ahmedabad"
        assert result.state == "Gujarat"
        assert result.scope == GEO_SCOPE_AHMEDABAD

    def test_gift_city_is_ahmedabad_scope(self):
        result = resolve_location("GIFT City, Gandhinagar")
        assert result.scope == GEO_SCOPE_AHMEDABAD

    def test_sanand(self):
        result = resolve_location("Sanand, Ahmedabad")
        assert result.scope == GEO_SCOPE_AHMEDABAD

    def test_other_gujarat_city(self):
        result = resolve_location("Surat, Gujarat")
        assert result.state == "Gujarat"
        assert result.scope == GEO_SCOPE_GUJARAT

    def test_india_remote(self):
        result = resolve_location("Remote - India")
        assert result.is_remote is True
        assert result.scope == GEO_SCOPE_INDIA_REMOTE
        assert result.country == "India"

    def test_bare_indian_city_resolves_state(self):
        result = resolve_location("bengaluru")
        assert result.city == "Bengaluru"
        assert result.state == "Karnataka"
        assert result.scope == GEO_SCOPE_INDIA

    def test_greenhouse_style_location(self):
        result = resolve_location("Bengaluru-VTP, India")
        assert result.country == "India"
        assert result.scope == GEO_SCOPE_INDIA

    def test_us_location_is_out_of_scope(self):
        result = resolve_location("New York, New York, United States")
        assert result.country == "United States"
        assert result.scope not in {
            GEO_SCOPE_AHMEDABAD,
            GEO_SCOPE_GUJARAT,
            GEO_SCOPE_INDIA,
            GEO_SCOPE_INDIA_REMOTE,
        }

    def test_generic_remote_is_global(self):
        result = resolve_location("Remote")
        assert result.is_remote is True
        assert result.scope == GEO_SCOPE_GLOBAL

    def test_empty_location(self):
        result = resolve_location(None)
        assert result.scope == "other"
        assert result.display == "Not specified"

    def test_longest_city_match_wins(self):
        # "S.G. Highway" must not be matched as "highway"
        result = resolve_location("S.G. Highway, Ahmedabad")
        assert result.city == "S.G. Highway"
        assert result.scope == GEO_SCOPE_AHMEDABAD
