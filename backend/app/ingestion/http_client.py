"""Polite HTTP client: robots.txt awareness, per-host rate limiting, retries."""
from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlsplit

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_USER_AGENT = settings.user_agent


class RobotsPolicy:
    """A minimal, spec-correct robots.txt evaluator.

    ``urllib.robotparser`` returns the *first* matching rule, which incorrectly
    treats ``Disallow: /`` as overriding a later, more specific ``Allow``.
    The de-facto standard (and Google's implementation) is longest-match-wins,
    with ``Allow`` winning ties — that is what this class implements.
    """

    def __init__(self, text: str | None = None) -> None:
        self.rules: list[tuple[re.Pattern[str], bool]] = []
        self.crawl_delay: float | None = None
        self.sitemaps: list[str] = []
        self.allow_all = False
        self.disallow_all = False
        if text is not None:
            self.parse(text)

    def parse(self, text: str) -> None:
        lines = [line.strip() for line in text.splitlines()]
        applies_to_all = False
        # Whether the current group targets our user-agent (or everyone).
        group_is_for_us = False
        seen_specific = False
        expecting_agent = False

        for raw in lines:
            if not raw or raw.startswith("#"):
                continue
            if ":" not in raw:
                continue
            field_name, _, value = raw.partition(":")
            field_name = field_name.strip().lower()
            value = value.strip()

            if field_name == "user-agent":
                if expecting_agent:
                    # New agent follows: finish the previous group.
                    if seen_specific and not group_is_for_us:
                        group_is_for_us = False
                    seen_specific = False
                    group_is_for_us = applies_to_all
                else:
                    group_is_for_us = False
                agent = value.lower()
                if agent == "*":
                    group_is_for_us = True
                    applies_to_all = True
                else:
                    # Our token appears in our descriptive user agent.
                    token = agent.split("/")[0].strip()
                    if token and token in _USER_AGENT.lower():
                        group_is_for_us = True
                        seen_specific = True
                expecting_agent = True
                continue

            expecting_agent = False
            if not group_is_for_us:
                continue

            if field_name in ("allow", "disallow"):
                if field_name == "disallow" and value == "":
                    # "Disallow:" with an empty value means allow everything.
                    continue
                pattern = self._to_regex(value)
                if pattern is None:
                    continue
                self.rules.append((pattern, field_name == "allow"))
            elif field_name == "crawl-delay":
                try:
                    self.crawl_delay = float(value)
                except ValueError:
                    pass
            elif field_name == "sitemap":
                self.sitemaps.append(value)

    @staticmethod
    def _to_regex(pattern: str) -> re.Pattern[str] | None:
        if pattern == "":
            return None
        anchored_start = pattern.startswith("/")
        parts: list[str] = []
        index = 0
        length = len(pattern)
        while index < length:
            char = pattern[index]
            if char == "*":
                parts.append(".*")
            elif char == "$" and index == length - 1:
                parts.append("$")
            else:
                parts.append(re.escape(char))
            index += 1
        body = "".join(parts)
        prefix = "" if anchored_start else ""
        if not body.endswith("$"):
            body += ".*"
        try:
            return re.compile(f"^{prefix}{body}")
        except re.error:
            return None

    def can_fetch(self, url: str) -> bool:
        if self.allow_all:
            return True
        if not self.rules:
            return True
        parsed = urlsplit(url)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        best_length = -1
        best_allow = True
        for pattern, allow in self.rules:
            if pattern.match(path):
                length = len(pattern.pattern)
                if length > best_length or (length == best_length and allow):
                    best_length = length
                    best_allow = allow
        return best_allow


@dataclass
class _HostState:
    last_request: float = 0.0
    request_count: int = 0
    robots: RobotsPolicy | None = None
    robots_fetched: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class PoliteClient:
    """Async HTTP client with host-level politeness and retry/backoff."""

    def __init__(
        self,
        timeout: float | None = None,
        rate_limit_per_host: int = 30,
        max_retries: int = 3,
        respect_robots: bool | None = None,
    ) -> None:
        self.timeout = timeout or settings.http_timeout
        self.rate_limit_per_host = rate_limit_per_host
        self.max_retries = max_retries
        self.respect_robots = settings.respect_robots_txt if respect_robots is None else respect_robots
        self._hosts: dict[str, _HostState] = defaultdict(_HostState)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "PoliteClient":
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=True,
                limits=httpx.Limits(max_connections=settings.http_max_concurrency * 2),
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # -- internals ---------------------------------------------------------

    def _host_state(self, url: str) -> _HostState:
        host = urlparse(url).netloc.lower()
        return self._hosts[host]

    async def _throttle(self, url: str) -> None:
        state = self._host_state(url)
        async with state.lock:
            min_interval = 60.0 / max(self.rate_limit_per_host, 1)
            elapsed = time.monotonic() - state.last_request
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            state.last_request = time.monotonic()
            state.request_count += 1

    async def _robots_allows(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        state = self._host_state(url)
        async with state.lock:
            if not state.robots_fetched:
                robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
                policy = RobotsPolicy()
                try:
                    assert self._client is not None
                    resp = await self._client.get(robots_url, timeout=10)
                    if resp.status_code == 200:
                        policy.parse(resp.text)
                    else:
                        # No usable robots.txt means no restrictions.
                        policy.allow_all = True
                except Exception:
                    policy.allow_all = True
                state.robots = policy
                state.robots_fetched = True
            robots = state.robots
        if robots is None:
            return True
        allowed = robots.can_fetch(url)
        if not allowed:
            log.warning("robots_denied", url=url)
        return allowed

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict | None = None,
        allow_robots_check: bool = True,
        raise_for_status: bool = True,
    ) -> httpx.Response:
        await self.start()
        assert self._client is not None

        if allow_robots_check and self.respect_robots and not await self._robots_allows(url):
            log.warning("robots_denied", url=url)
            raise PermissionError(f"robots.txt disallows fetching {url}")

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            await self._throttle(url)
            try:
                resp = await self._client.request(
                    method, url, headers=headers, params=params, json=json_body
                )
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_error = httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                    backoff = min(2**attempt, 30)
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        backoff = min(int(retry_after), 60)
                    log.warning(
                        "http_retry", url=url, attempt=attempt + 1, status=resp.status_code, backoff=backoff
                    )
                    await asyncio.sleep(backoff)
                    continue
                if raise_for_status:
                    resp.raise_for_status()
                return resp
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                backoff = min(2**attempt, 8)
                log.warning("http_transport_error", url=url, attempt=attempt + 1, error=str(exc))
                await asyncio.sleep(backoff)
        raise last_error or RuntimeError(f"request failed: {url}")

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        resp = await self.request("GET", url, **kwargs)
        return resp.json()

    async def get_text(self, url: str, **kwargs: Any) -> str:
        resp = await self.request("GET", url, **kwargs)
        return resp.text

    async def head(self, url: str, **kwargs: Any) -> httpx.Response:
        resp = await self.request("HEAD", url, raise_for_status=False, **kwargs)
        return resp
