"""Connector registry — maps a source's connector_type to an implementation."""
from __future__ import annotations

from app.ingestion.base import Connector, ConnectorContext
from app.ingestion.connectors.aggregators import (
    ArbeitnowConnector,
    HimalayasConnector,
    JobicyConnector,
    RemoteOkConnector,
    RemotiveConnector,
)
from app.ingestion.connectors.ats import (
    AshbyConnector,
    GreenhouseConnector,
    LeverConnector,
    SmartRecruitersConnector,
    WorkableConnector,
)
from app.ingestion.connectors.career_pages import CareerPageConnector
from app.ingestion.connectors.hackernews import HackerNewsConnector
from app.ingestion.connectors.workday import WorkdayConnector

CONNECTOR_REGISTRY: dict[str, type[Connector]] = {
    GreenhouseConnector.type: GreenhouseConnector,
    LeverConnector.type: LeverConnector,
    AshbyConnector.type: AshbyConnector,
    WorkableConnector.type: WorkableConnector,
    SmartRecruitersConnector.type: SmartRecruitersConnector,
    RemoteOkConnector.type: RemoteOkConnector,
    RemotiveConnector.type: RemotiveConnector,
    ArbeitnowConnector.type: ArbeitnowConnector,
    JobicyConnector.type: JobicyConnector,
    HimalayasConnector.type: HimalayasConnector,
    CareerPageConnector.type: CareerPageConnector,
    HackerNewsConnector.type: HackerNewsConnector,
    WorkdayConnector.type: WorkdayConnector,
}


def build_connector(ctx: ConnectorContext) -> Connector:
    connector_cls = CONNECTOR_REGISTRY.get(ctx.config.get("connector_type") or "")
    if connector_cls is None:
        raise KeyError(f"unknown connector type: {ctx.config.get('connector_type')}")
    return connector_cls(ctx)


def available_connectors() -> list[str]:
    return sorted(CONNECTOR_REGISTRY)
