"""Register or update an ingestion source from the command line.

Example:
    python -m scripts.register_source \
        --name "Workday · Quantiphi" --slug workday-quantiphi \
        --connector-type workday \
        --config '{"tenant": "quantiphi", "region": "wd1", "site": "careers_at_quantiphi"}'
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import get_logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ingestion.registry import CONNECTOR_REGISTRY  # noqa: E402
from app.models import JobSource  # noqa: E402

log = get_logger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--connector-type", required=True, choices=sorted(CONNECTOR_REGISTRY))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--config", default="{}")
    parser.add_argument("--priority", type=int, default=60)
    parser.add_argument("--interval-minutes", type=int, default=60)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--inactive", action="store_true")
    args = parser.parse_args()

    config = json.loads(args.config)
    config.setdefault("connector_type", args.connector_type)

    async with SessionLocal() as session:
        source = (
            await session.execute(select(JobSource).where(JobSource.slug == args.slug))
        ).scalar_one_or_none()
        if source is None:
            source = JobSource(name=args.name, slug=args.slug, connector_type=args.connector_type)
            session.add(source)
        source.name = args.name
        source.connector_type = args.connector_type
        source.base_url = args.base_url
        source.config = config
        source.priority = args.priority
        source.interval_minutes = args.interval_minutes
        source.notes = args.notes
        source.is_active = not args.inactive
        await session.commit()
        print(f"Registered source {source.slug} ({source.connector_type}) — id {source.id}")


if __name__ == "__main__":
    asyncio.run(main())
