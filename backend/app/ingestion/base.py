"""Connector contracts shared by every ingestion source."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.enums import WorkArrangement


@dataclass(slots=True)
class RawJob:
    """A job as returned by a source, before normalisation."""

    external_id: str
    source_key: str
    source_name: str
    title: str
    company_name: str
    apply_url: str
    original_url: str
    description: str | None = None
    location_raw: str | None = None
    department: str | None = None
    posted_at: datetime | None = None
    updated_at: datetime | None = None
    deadline: datetime | None = None
    employment_type: str | None = None
    work_arrangement: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    experience_level: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConnectorContext:
    """Everything a connector needs that is not the job payload itself."""

    source_slug: str
    source_name: str
    config: dict[str, Any]
    startup_id: str | None = None


class ConnectorError(Exception):
    """Raised when a source cannot be fetched or parsed."""


class Connector(abc.ABC):
    """Base class for all ingestion connectors."""

    type: str = "base"
    #: Whether the connector respects robots.txt / requires care with crawl rate.
    respects_robots: bool = True

    def __init__(self, ctx: ConnectorContext) -> None:
        self.ctx = ctx

    @abc.abstractmethod
    async def fetch(self) -> list[RawJob]:
        """Fetch and return jobs from the source. Raise ConnectorError on failure."""

    def supports(self, config: dict[str, Any]) -> bool:
        """Return True when the connector can handle this source configuration."""
        return True

    @staticmethod
    def _work_arrangement(value: str | None) -> str | None:
        if not value:
            return None
        v = value.lower()
        if "remote" in v:
            return WorkArrangement.REMOTE
        if "hybrid" in v:
            return WorkArrangement.HYBRID
        if "on-site" in v or "onsite" in v:
            return WorkArrangement.ONSITE
        return None
