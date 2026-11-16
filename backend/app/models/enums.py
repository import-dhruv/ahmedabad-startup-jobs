"""Canonical enumerations used across the platform."""
from __future__ import annotations

from enum import StrEnum


class Industry(StrEnum):
    ARTIFICIAL_INTELLIGENCE = "Artificial Intelligence"
    MACHINE_LEARNING = "Machine Learning"
    GENERATIVE_AI = "Generative AI"
    SAAS = "SaaS"
    FINTECH = "FinTech"
    HEALTHTECH = "HealthTech"
    EDTECH = "EdTech"
    DEEPTECH = "DeepTech"
    ROBOTICS = "Robotics"
    SEMICONDUCTOR = "Semiconductor"
    ENTERPRISE_SOFTWARE = "Enterprise Software"
    CYBERSECURITY = "Cybersecurity"
    BLOCKCHAIN = "Blockchain"
    ECOMMERCE = "E-commerce"
    CLIMATETECH = "ClimateTech"
    MOBILITY = "Mobility"
    MANUFACTURING_TECH = "Manufacturing Technology"
    DEVELOPER_TOOLS = "Developer Tools"
    GAMING = "Gaming"
    OTHER_TECH = "Other technology startups"


INDUSTRY_SLUGS: dict[str, str] = {
    "Artificial Intelligence": "artificial-intelligence",
    "Machine Learning": "machine-learning",
    "Generative AI": "generative-ai",
    "SaaS": "saas",
    "FinTech": "fintech",
    "HealthTech": "healthtech",
    "EdTech": "edtech",
    "DeepTech": "deeptech",
    "Robotics": "robotics",
    "Semiconductor": "semiconductor",
    "Enterprise Software": "enterprise-software",
    "Cybersecurity": "cybersecurity",
    "Blockchain": "blockchain",
    "E-commerce": "ecommerce",
    "ClimateTech": "climatetech",
    "Mobility": "mobility",
    "Manufacturing Technology": "manufacturing-technology",
    "Developer Tools": "developer-tools",
    "Gaming": "gaming",
    "Other technology startups": "other",
}


class EmploymentType(StrEnum):
    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    INTERNSHIP = "Internship"
    CONTRACT = "Contract"
    FREELANCE = "Freelance"
    APPRENTICESHIP = "Apprenticeship"


class WorkArrangement(StrEnum):
    ONSITE = "On-site"
    HYBRID = "Hybrid"
    REMOTE = "Remote"


class ExperienceLevel(StrEnum):
    FRESHER = "Fresher"
    ENTRY = "0-1 years"
    JUNIOR = "1-3 years"
    MID = "3-5 years"
    SENIOR = "5-8 years"
    LEAD = "8+ years"


EXPERIENCE_ORDER: dict[str, int] = {
    ExperienceLevel.FRESHER: 0,
    ExperienceLevel.ENTRY: 1,
    ExperienceLevel.JUNIOR: 2,
    ExperienceLevel.MID: 3,
    ExperienceLevel.SENIOR: 4,
    ExperienceLevel.LEAD: 5,
}


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    STALE = "stale"
    EXPIRED = "expired"
    REJECTED = "rejected"


class JobStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REMOVED = "removed"
    ON_HOLD = "on_hold"


class HiringStatus(StrEnum):
    HIRING = "hiring"
    NOT_HIRING = "not_hiring"
    UNKNOWN = "unknown"


class FundingStage(StrEnum):
    BOOTSTRAPPED = "Bootstrapped"
    PRE_SEED = "Pre-Seed"
    SEED = "Seed"
    SERIES_A = "Series A"
    SERIES_B = "Series B"
    SERIES_C = "Series C"
    SERIES_D_PLUS = "Series D+"
    UNKNOWN = "Unknown"


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


class ApplicationStatus(StrEnum):
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SourceStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class NotificationType(StrEnum):
    JOB_MATCH = "job_match"
    ALERT = "alert"
    SYSTEM = "system"
