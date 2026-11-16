"""In-process pub/sub used to push live ingestion events to the browser."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger

log = get_logger(__name__)


def _serialize(payload: dict[str, Any]) -> str:
    payload = dict(payload)
    payload.setdefault("ts", datetime.now(UTC).isoformat())
    return json.dumps(payload, default=str)


class EventBroker:
    """Fan-out broker for Server-Sent Events.

    Each subscriber gets its own bounded queue; slow consumers are dropped
    rather than allowed to block ingestion.
    """

    def __init__(self, max_queue: int = 200) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self.max_queue = max_queue
        self._last_event: dict[str, Any] | None = None

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        message = _serialize({"event": event_type, "data": payload or {}})
        self._last_event = {"event": event_type, "data": payload or {}}
        async with self._lock:
            targets = list(self._subscribers)
        for queue in targets:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                log.warning("sse_queue_full_dropping", event=event_type)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def stream(self, heartbeat: float = 20.0) -> AsyncIterator[str]:
        queue = await self.subscribe()
        try:
            yield ": connected\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=heartbeat)
                    yield f"data: {message}\n\n"
                except TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:  # pragma: no cover - client disconnect
            raise
        finally:
            await self.unsubscribe(queue)


broker = EventBroker()
