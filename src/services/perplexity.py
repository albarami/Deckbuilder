"""Perplexity API service — web search for industry context.

Used by the understanding filler for industry context and the methodology
filler for recent best practices.  Graceful degradation: returns None
on API errors so the pipeline never blocks on external service failures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────

PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
DEFAULT_TIMEOUT = 15.0  # seconds
DEFAULT_MODEL = "sonar"


# ── Models ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PerplexityCitation:
    """A citation from a Perplexity search result."""

    url: str
    title: str = ""


@dataclass(frozen=True)
class PerplexityResult:
    """Result from a Perplexity web search query."""

    content: str
    citations: list[PerplexityCitation] = field(default_factory=list)
    model: str = ""


# ── Service ───────────────────────────────────────────────────────────


def search_web(
    query: str,
    *,
    api_key: str = "",
    system_context: str = "",
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT,
) -> PerplexityResult | None:
    """Search the web via Perplexity for industry context.

    Parameters
    ----------
    query : str
        Search query (e.g., "Saudi Arabia digital transformation trends 2025").
    api_key : str
        Perplexity API key.  Required for actual API calls.
    system_context : str
        System prompt context to guide the search result format.
    model : str
        Perplexity model to use.
    timeout : float
        Request timeout in seconds.

    Returns
    -------
    PerplexityResult or None
        Search result with citations, or None on any error (graceful degradation).
    """
    if not query.strip():
        return None

    if not api_key:
        logger.warning("Perplexity API key not configured — skipping web search")
        return None

    messages = []
    if system_context:
        messages.append({"role": "system", "content": system_context})
    messages.append({"role": "user", "content": query})

    payload = {
        "model": model,
        "messages": messages,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{PERPLEXITY_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Perplexity API %d: model=%s, query=%r",
                response.status_code,
                model,
                query[:60],
            )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Perplexity API error %d: %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return None
    except (httpx.RequestError, Exception) as exc:
        logger.warning("Perplexity request failed: %s", exc)
        return None

    # Extract content from chat completion response
    choices = data.get("choices", [])
    if not choices:
        logger.warning("Perplexity returned no choices")
        return None

    content = choices[0].get("message", {}).get("content", "")

    # Extract citations if available
    citations: list[PerplexityCitation] = []
    for cite in data.get("citations", []):
        if isinstance(cite, str):
            citations.append(PerplexityCitation(url=cite))
        elif isinstance(cite, dict):
            citations.append(PerplexityCitation(
                url=cite.get("url", ""),
                title=cite.get("title", ""),
            ))

    logger.info(
        "Perplexity: query='%s' returned %d chars, %d citations",
        query[:60], len(content), len(citations),
    )
    return PerplexityResult(
        content=content,
        citations=citations,
        model=data.get("model", model),
    )
