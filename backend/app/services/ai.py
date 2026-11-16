"""AI intelligence layer.

The platform works fully without an AI provider: rule-based extraction and
extractive summarisation are always available. When ``OPENAI_API_KEY`` is set,
an LLM can refine categorisation, skill extraction and summaries. AI-generated
output is always stored with ``classification_source = 'ai'`` so it can be
distinguished from measured data.
"""
from __future__ import annotations

import json
import re
from typing import Any, Protocol

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

SUMMARY_SENTENCES = 4


class AIProvider(Protocol):
    name: str

    async def summarize_job(self, description: str) -> str | None: ...
    async def classify_job(self, title: str, description: str) -> dict[str, Any] | None: ...
    async def interpret_hiring(self, payload: dict[str, Any]) -> list[str]: ...


# --- Rule based (always available) ------------------------------------------


def extractive_summary(description: str | None, sentences: int = SUMMARY_SENTENCES) -> str | None:
    """Deterministic summary used when no LLM is configured."""
    if not description:
        return None
    from app.services.normalizer import strip_html

    text = strip_html(description)
    if not text:
        return None

    # Prefer the first meaningful paragraph — job posts almost always lead with
    # the company/role overview.
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if len(p.strip()) > 40]
    if not paragraphs:
        return None

    first = paragraphs[0]
    sentences = re.split(r"(?<=[.!?])\s+", first)
    summary = " ".join(s.strip() for s in sentences[:sentences] if s.strip())
    if len(summary) > 600:
        summary = summary[:597].rstrip() + "..."
    return summary or None


class RuleBasedProvider:
    """Fallback provider: deterministic, no network calls."""

    name = "rules"

    async def summarize_job(self, description: str) -> str | None:
        return extractive_summary(description)

    async def classify_job(self, title: str, description: str) -> dict[str, Any] | None:
        return None

    async def interpret_hiring(self, payload: dict[str, Any]) -> list[str]:
        return []


class OpenAIProvider:
    """LLM-backed provider (OpenAI-compatible chat completions API)."""

    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def _chat(self, system: str, user: str, max_tokens: int = 400) -> str | None:
        import httpx

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                resp = await client.post(
                    url, json=payload, headers={"Authorization": f"Bearer {self.api_key}"}
                )
                resp.raise_for_status()
                data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            log.warning("openai_call_failed", error=str(exc))
            return None

    async def summarize_job(self, description: str) -> str | None:
        from app.services.normalizer import strip_html

        text = strip_html(description)[:4000]
        if not text:
            return None
        return await self._chat(
            "You write 2-3 sentence summaries of job postings for a job board. "
            "Be factual, mention the role and the key responsibilities. No marketing language.",
            text,
            max_tokens=180,
        )

    async def classify_job(self, title: str, description: str) -> dict[str, Any] | None:
        from app.services.normalizer import strip_html

        text = strip_html(description)[:5000]
        if not text:
            return None
        raw = await self._chat(
            "You are a job classification engine. Respond ONLY with a JSON object with keys "
            '"category" (string), "skills" (array of strings), "experience_level" (one of: Fresher, '
            '0-1 years, 1-3 years, 3-5 years, 5-8 years, 8+ years), "employment_type" (one of: '
            "Full-time, Part-time, Internship, Contract, Freelance, Apprenticeship), "
            '"seniority" (string). No prose.',
            f"TITLE: {title}\n\nDESCRIPTION:\n{text}",
            max_tokens=400,
        )
        if not raw:
            return None
        try:
            match = re.search(r"\{.*\}", raw, re.S)
            return json.loads(match.group(0)) if match else None
        except json.JSONDecodeError:
            return None

    async def interpret_hiring(self, payload: dict[str, Any]) -> list[str]:
        raw = await self._chat(
            "You are a labour-market analyst. Given aggregate hiring data, return 3 short "
            "bullet-point observations (one per line, no markdown) describing emerging trends. "
            "Only state what the data supports.",
            json.dumps(payload),
            max_tokens=300,
        )
        if not raw:
            return []
        return [line.strip("-• ").strip() for line in raw.splitlines() if line.strip()][:5]


_provider: AIProvider | None = None
_provider_initialised = False


def get_ai_provider() -> AIProvider | None:
    """Return the configured provider, or the rule-based one when AI is disabled."""
    global _provider, _provider_initialised
    if _provider_initialised:
        return _provider
    _provider_initialised = True
    if settings.openai_api_key and settings.ai_enabled:
        _provider = OpenAIProvider(settings.openai_api_key, settings.openai_model)
        log.info("ai_provider_enabled", provider=_provider.name, model=settings.openai_model)
    else:
        _provider = None
    return _provider


def get_effective_provider() -> AIProvider:
    return get_ai_provider() or RuleBasedProvider()
