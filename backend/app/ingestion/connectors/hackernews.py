"""Connector for Hacker News "Ask HN: Who is hiring?" threads.

The official Hacker News Firebase API explicitly allows access to ``*.json``
endpoints, and the Algolia mirror returns a whole thread in a single request.
Founders post their own openings here, so each comment is a genuine job post
with the employer's own link.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.ingestion.base import Connector, ConnectorError, RawJob
from app.ingestion.http_client import PoliteClient

log = get_logger(__name__)

HN_USER_API = "https://hacker-news.firebaseio.com/v0/user/whoishiring.json"
HN_ITEM_API = "https://hn.algolia.com/api/v1/items/{item_id}"

_ANCHOR_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
_PARAGRAPH_RE = re.compile(r"<\s*p\s*/?\s*>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")

# "Company | Role | Location | Type | Extra" is the canonical comment format.
_PIPE_SPLIT_RE = re.compile(r"\s*\|\s*")

# Job boards that are aggregators rather than the employer themselves.
_AGGREGATOR_HOSTS = {
    "news.ycombinator.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "www.linkedin.com",
    "github.com",
    "t.me",
    "reddit.com",
    "youtu.be",
    "bit.ly",
    "tinyurl.com",
}


def _decode_html(value: str) -> str:
    text = value.replace("<p>", "\n").replace("</p>", "\n").replace("<br>", "\n").replace("<br/>", "\n")
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("&#x2F;", "/").replace("&#47;", "/").replace("&#x3D;", "=")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _extract_links(text: str) -> list[str]:
    links: list[str] = []
    for href, _label in _ANCHOR_RE.findall(text):
        href = html.unescape(href).replace("&#x2F;", "/").replace("&#47;", "/")
        if not href.startswith("http"):
            continue
        host = href.split("/")[2].lower()
        if host in _AGGREGATOR_HOSTS:
            continue
        if href not in links:
            links.append(href)
    return links


def _split_fields(text: str) -> list[str]:
    first_line = text.split("\n", 1)[0].strip()
    if "|" not in first_line:
        return []
    return [part.strip() for part in _PIPE_SPLIT_RE.split(first_line)]


def _guess_experience(text: str) -> str | None:
    lowered = text.lower()
    years = re.search(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)", lowered)
    if years:
        value = int(years.group(1))
        if value >= 8:
            return "8+ years"
        if value >= 5:
            return "5-8 years"
        if value >= 3:
            return "3-5 years"
        if value >= 1:
            return "1-3 years"
    if re.search(r"\b(fresher|graduate|new grad|0\s*years)\b", lowered):
        return "Fresher"
    if re.search(r"\bsenior\b|\bsr\.?\b|\bstaff\b|\bprincipal\b", lowered):
        return "5-8 years"
    if re.search(r"\bjunior\b|\bjr\.?\b", lowered):
        return "1-3 years"
    if re.search(r"\bintern(?:ship)?\b", lowered):
        return "Fresher"
    return None


def _guess_employment(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"\bintern(?:ship)?\b", lowered):
        return "Internship"
    if re.search(r"\bpart[- ]time\b", lowered):
        return "Part-time"
    if re.search(r"\bcontract(?:or)?\b", lowered):
        return "Contract"
    if re.search(r"\bfreelance\b", lowered):
        return "Freelance"
    if re.search(r"\bfull[- ]time\b", lowered):
        return "Full-time"
    return None


class HackerNewsConnector(Connector):
    """Reads the monthly 'Who is hiring?' threads."""

    type = "hackernews"
    respects_robots = True

    async def fetch(self) -> list[RawJob]:
        client: PoliteClient = self.ctx.config["client"]
        limit = int(self.ctx.config.get("thread_limit", 2))
        max_comments = int(self.ctx.config.get("max_comments", 400))

        try:
            payload = await client.get_json(HN_USER_API)
        except Exception as exc:
            raise ConnectorError(f"hackernews user api failed: {exc}") from exc

        thread_ids = payload.get("submitted") or []
        if not isinstance(thread_ids, list) or not thread_ids:
            raise ConnectorError("no 'who is hiring' threads available")

        # Only the two most recent threads: each thread id pair is
        # ("who is hiring", "who wants to be hired"); we want the former.
        hiring_ids = [tid for tid in thread_ids[: limit * 6] if isinstance(tid, int)][: limit * 3]

        out: list[RawJob] = []
        seen_comments: set[int] = set()

        for thread_id in hiring_ids:
            try:
                thread = await client.get_json(HN_ITEM_API.format(item_id=thread_id))
            except Exception as exc:
                log.warning("hn_thread_failed", thread_id=thread_id, error=str(exc))
                continue

            title = (thread.get("title") or "").lower()
            if "who is hiring" not in title:
                continue

            children = thread.get("children") or []
            for comment in children[:max_comments]:
                job = self._parse_comment(comment, thread_id)
                if job is None:
                    continue
                if job.external_id in seen_comments:
                    continue
                seen_comments.add(job.external_id)
                out.append(job)
            if out:
                break

        log.info("hn_threads_parsed", jobs=len(out))
        return out

    def _parse_comment(self, comment: dict[str, Any], thread_id: int) -> RawJob | None:
        raw_text = comment.get("text") or ""
        if not raw_text:
            return None
        text = _decode_html(raw_text)
        if len(text) < 40:
            return None

        fields = _split_fields(text)
        if len(fields) < 2:
            return None

        company = fields[0][:200]
        if len(company) > 120 or "\n" in company:
            return None
        # Skip comments that are not job posts (e.g. recruiting advice).
        if re.search(r"(?i)^(i|we|note|question|advice|hiring manager|tl;dr)\b", company):
            return None

        role = fields[1][:300]
        location = fields[2][:300] if len(fields) > 2 else None

        links = _extract_links(raw_text)
        apply_url = comment.get("url") or (links[0] if links else None)
        if not apply_url:
            return None
        host = apply_url.split("/")[2].lower()
        if host in _AGGREGATOR_HOSTS:
            apply_url = links[1] if len(links) > 1 else None
            if not apply_url:
                return None

        body = text.split("\n", 1)[1] if "\n" in text else text
        description = f"{company} is hiring: {role}" + (f" — {location}" if location else "")
        if body.strip():
            description += "\n\n" + body.strip()[:6000]

        return RawJob(
            external_id=f"hackernews:{comment.get('id')}",
            source_key="hackernews",
            source_name=self.ctx.source_name,
            title=role,
            company_name=company,
            apply_url=apply_url[:1000],
            original_url=apply_url[:1000],
            description=description,
            location_raw=location,
            experience_level=_guess_experience(text),
            employment_type=_guess_employment(text),
            posted_at=datetime.fromtimestamp(comment.get("created_at_i", 0), tz=timezone.utc)
            if comment.get("created_at_i")
            else None,
            raw={
                "author": comment.get("author"),
                "thread_id": thread_id,
                "points": comment.get("points"),
                "hn_id": comment.get("id"),
            },
        )
