"""Geographic resolution for job locations.

Maps raw location strings from job boards onto city/state/country and a
platform-level *geo scope* so that Ahmedabad-focused queries are precise while
still allowing remote/India-wide roles to surface.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Target geography -------------------------------------------------------

AHMEDABAD_CITIES: dict[str, str] = {
    "ahmedabad": "Gujarat",
    "amd": "Gujarat",
    "sabarmati": "Gujarat",
    "sg highway": "Gujarat",
    "s.g. highway": "Gujarat",
    "bodakdev": "Gujarat",
    "prahlad nagar": "Gujarat",
    "prahladnagar": "Gujarat",
    "sarkhej": "Gujarat",
    "gil city": "Gujarat",
    "gift city": "Gujarat",
    "gandhinagar": "Gujarat",
    "sanand": "Gujarat",
    "dholera": "Gujarat",
    "sanand sarkhej": "Gujarat",
    "kalyan": "Gujarat",
}

GUJARAT_CITIES: dict[str, str] = {
    **AHMEDABAD_CITIES,
    "surat": "Gujarat",
    "vadodara": "Gujarat",
    "rajkot": "Gujarat",
    "bhavnagar": "Gujarat",
    "jamnagar": "Gujarat",
    "anand": "Gujarat",
    "vapi": "Gujarat",
    "valsad": "Gujarat",
    "gandhinagar": "Gujarat",
    "nadiad": "Gujarat",
    "morbi": "Gujarat",
    "bhuj": "Gujarat",
    "mehsana": "Gujarat",
    "bardoli": "Gujarat",
    "dholka": "Gujarat",
    "navsari": "Gujarat",
    "palanpur": "Gujarat",
    "dehgam": "Gujarat",
    "bharna": "Gujarat",
    "karjat": "Gujarat",
    "kheda": "Gujarat",
}

# Major Indian tech hiring hubs — used to resolve bare city names.
INDIAN_CITIES: dict[str, str] = {
    "mumbai": "Maharashtra",
    "bombay": "Maharashtra",
    "pune": "Maharashtra",
    "nagpur": "Maharashtra",
    "nashik": "Maharashtra",
    "bangalore": "Karnataka",
    "bengaluru": "Karnataka",
    "blr": "Karnataka",
    "mysore": "Karnataka",
    "mysuru": "Karnataka",
    "hubballi": "Karnataka",
    "hubli": "Karnataka",
    "mangalore": "Karnataka",
    "hyderabad": "Telangana",
    "telangana": "Telangana",
    "chennai": "Tamil Nadu",
    "madras": "Tamil Nadu",
    "coimbatore": "Tamil Nadu",
    "madurai": "Tamil Nadu",
    "trichy": "Tamil Nadu",
    "tiruchirappalli": "Tamil Nadu",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "noida": "Uttar Pradesh",
    "greater noida": "Uttar Pradesh",
    "gurgaon": "Haryana",
    "gurugram": "Haryana",
    "faridabad": "Haryana",
    "ghaziabad": "Uttar Pradesh",
    "kanpur": "Uttar Pradesh",
    "lucknow": "Uttar Pradesh",
    "jaipur": "Rajasthan",
    "indore": "Madhya Pradesh",
    "bhopal": "Madhya Pradesh",
    "kolkata": "West Bengal",
    "calcutta": "West Bengal",
    "kochi": "Kerala",
    "cochin": "Kerala",
    "trivandrum": "Kerala",
    "thiruvananthapuram": "Kerala",
    "visakhapatnam": "Andhra Pradesh",
    "vizag": "Andhra Pradesh",
    "bhubaneswar": "Odisha",
    "guwahati": "Assam",
    "chandigarh": "Punjab",
    "ludhiana": "Punjab",
    "amritsar": "Punjab",
    "dehradun": "Uttarakhand",
    "jodhpur": "Rajasthan",
    "udaipur": "Rajasthan",
    "agra": "Uttar Pradesh",
    "varanasi": "Uttar Pradesh",
    "bhopal": "Madhya Pradesh",
    "mysore": "Karnataka",
    "ahmedabad": "Gujarat",
    "surat": "Gujarat",
    "vadodara": "Gujarat",
    "rajkot": "Gujarat",
    "gandhinagar": "Gujarat",
}

CITY_TO_STATE: dict[str, str] = {**INDIAN_CITIES, **GUJARAT_CITIES}

COUNTRY_TOKENS: dict[str, str] = {
    "india": "India",
    "bharat": "India",
    "in": "India",
    "united states": "United States",
    "united states of america": "United States",
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "england": "United Kingdom",
    "canada": "Canada",
    "germany": "Germany",
    "netherlands": "Netherlands",
    "singapore": "Singapore",
    "australia": "Australia",
    "ireland": "Ireland",
    "france": "France",
    "spain": "Spain",
    "italy": "Italy",
    "sweden": "Sweden",
    "denmark": "Denmark",
    "poland": "Poland",
    "brazil": "Brazil",
    "mexico": "Mexico",
    "japan": "Japan",
    "china": "China",
    "israel": "Israel",
    "uae": "United Arab Emirates",
    "dubai": "United Arab Emirates",
    "south africa": "South Africa",
    "nigeria": "Nigeria",
    "kenya": "Kenya",
    "new zealand": "New Zealand",
}

# Remote phrasing that does not restrict the hiring country.
REMOTE_PATTERNS = (
    "remote",
    "work from home",
    "wfh",
    "anywhere",
    "distributed",
    "virtual",
    "work remotely",
)

# Remote phrasing that *does* restrict to a country/region.
REMOTE_IN_PATTERNS = (
    "remote - india",
    "remote india",
    "remote, india",
    "india remote",
    "remote (india)",
    "remote - us",
    "remote us",
    "remote - global",
    "remote worldwide",
)

# ---------------------------------------------------------------------------

GEO_SCOPE_AHMEDABAD = "ahmedabad"
GEO_SCOPE_GUJARAT = "gujarat"
GEO_SCOPE_INDIA_REMOTE = "india_remote"
GEO_SCOPE_INDIA = "india"
GEO_SCOPE_GLOBAL = "global"
GEO_SCOPE_OTHER = "other"

GEO_SCOPE_LABELS: dict[str, str] = {
    GEO_SCOPE_AHMEDABAD: "Ahmedabad",
    GEO_SCOPE_GUJARAT: "Gujarat",
    GEO_SCOPE_INDIA_REMOTE: "Remote (India)",
    GEO_SCOPE_INDIA: "India",
    GEO_SCOPE_GLOBAL: "Remote (open to all)",
    GEO_SCOPE_OTHER: "Other locations",
}


@dataclass(slots=True)
class ResolvedLocation:
    raw: str
    city: str | None = None
    state: str | None = None
    country: str | None = None
    is_remote: bool = False
    scope: str = GEO_SCOPE_OTHER
    matched_terms: list[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        parts = [p for p in (self.city, self.state, self.country) if p]
        return ", ".join(parts) if parts else (self.raw or "Not specified")


def _clean(raw: str | None) -> str:
    if not raw:
        return ""
    return re.sub(r"\s+", " ", raw).strip(" -–—|\t\n")


def _title_case(value: str) -> str:
    special = {"and": "and", "of": "of", "the": "the"}
    words = []
    for word in value.split():
        if word in special:
            words.append(word)
            continue
        # Preserve initials such as "S.G." -> "S.G."
        word = re.sub(r"\b([a-z])\.", lambda m: m.group(1).upper() + ".", word)
        words.append(word[:1].upper() + word[1:])
    return " ".join(words)


def detect_country(text: str) -> str | None:
    lowered = text.lower()
    for token, country in COUNTRY_TOKENS.items():
        if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", lowered):
            return country
    return None


def detect_remote(text: str) -> bool:
    lowered = text.lower()
    return any(p in lowered for p in REMOTE_PATTERNS)


def resolve_location(raw: str | None) -> ResolvedLocation:
    """Resolve a raw job location string into structured geo data."""
    text = _clean(raw)
    lowered = text.lower()
    result = ResolvedLocation(raw=text)

    if not text:
        result.scope = GEO_SCOPE_OTHER
        return result

    result.is_remote = detect_remote(text)
    result.country = detect_country(text)

    # city detection: longest match wins to prefer "s.g. highway" over "highway"
    best_city: str | None = None
    best_state: str | None = None
    for city, state in sorted(CITY_TO_STATE.items(), key=lambda kv: -len(kv[0])):
        pattern = rf"(?<![a-z]){re.escape(city)}(?![a-z])"
        if re.search(pattern, lowered):
            best_city, best_state = city, state
            break

    if best_city:
        result.city = _title_case(best_city)
        result.state = best_state
        result.matched_terms.append(best_city)
        if not result.country and best_state:
            result.country = "India"

    # "Bengaluru-VTP, India" style: strip suffix code
    if result.city and result.country == "India":
        result.state = result.state or CITY_TO_STATE.get(result.city.lower())

    is_india = result.country == "India"
    in_ahmedabad = bool(result.city and result.city.lower() in AHMEDABAD_CITIES)
    in_gujarat = bool(result.state == "Gujarat")

    if in_ahmedabad:
        result.scope = GEO_SCOPE_AHMEDABAD
    elif in_gujarat:
        result.scope = GEO_SCOPE_GUJARAT
    elif is_india and result.is_remote:
        result.scope = GEO_SCOPE_INDIA_REMOTE
    elif is_india:
        result.scope = GEO_SCOPE_INDIA
    elif result.is_remote:
        result.scope = GEO_SCOPE_GLOBAL
    elif result.city and result.state and result.country:
        result.scope = GEO_SCOPE_OTHER
    else:
        result.scope = GEO_SCOPE_OTHER

    if result.scope == GEO_SCOPE_INDIA_REMOTE and not result.country:
        result.country = "India"
    if result.scope in {GEO_SCOPE_INDIA_REMOTE, GEO_SCOPE_INDIA} and result.city:
        result.state = result.state or CITY_TO_STATE.get(result.city.lower())
    return result


def normalize_city(value: str | None) -> str | None:
    if not value:
        return None
    v = _clean(value).lower()
    return CITY_TO_STATE.get(v, _title_case(v))


def location_display(city: str | None, state: str | None, country: str | None) -> str:
    parts = [p for p in (city, state, country) if p]
    return ", ".join(parts) if parts else "Not specified"
