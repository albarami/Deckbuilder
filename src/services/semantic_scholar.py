"""Semantic Scholar API service — academic paper search.

Used by the methodology filler for framework references, maturity model
citations, and benchmark data.  Graceful degradation: returns empty list
on API errors so the pipeline never blocks on external service failures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────

SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"
DEFAULT_TIMEOUT = 10.0  # seconds
DEFAULT_MAX_RESULTS = 5
DEFAULT_FIELDS = "title,year,abstract,citationCount,url"


# ── Models ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScholarAuthor:
    """Author of a Semantic Scholar paper."""

    name: str
    author_id: str = ""


@dataclass(frozen=True)
class ScholarResult:
    """A single paper result from Semantic Scholar."""

    paper_id: str
    title: str
    year: int | None = None
    authors: list[ScholarAuthor] = field(default_factory=list)
    abstract: str | None = None
    citation_count: int = 0
    url: str = ""


# ── Service ───────────────────────────────────────────────────────────


def search_papers(
    query: str,
    *,
    api_key: str = "",
    max_results: int = DEFAULT_MAX_RESULTS,
    year_range: tuple[int, int] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[ScholarResult]:
    """Search Semantic Scholar for academic papers.

    Parameters
    ----------
    query : str
        Search query (e.g., "TOGAF enterprise architecture framework").
    api_key : str
        Semantic Scholar API key (optional, higher rate limits).
    max_results : int
        Maximum number of results to return.
    year_range : tuple[int, int], optional
        Filter by publication year (start, end).
    timeout : float
        Request timeout in seconds.

    Returns
    -------
    list[ScholarResult]
        Matching papers.  Empty list on any error (graceful degradation).
    """
    if not query.strip():
        return []

    params: dict[str, str | int] = {
        "query": query,
        "fields": DEFAULT_FIELDS,
        "year": "2020-",
    }
    if year_range is not None:
        params["year"] = f"{year_range[0]}-{year_range[1]}"

    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                f"{SEMANTIC_SCHOLAR_BASE_URL}/paper/search/bulk",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Semantic Scholar API %d: query=%r, total=%s",
                response.status_code,
                query[:60],
                data.get("total", "?"),
            )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Semantic Scholar API error %d: %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return []
    except (httpx.RequestError, Exception) as exc:
        logger.warning("Semantic Scholar request failed: %s", exc)
        return []

    results: list[ScholarResult] = []
    for paper in data.get("data", [])[:max_results]:
        authors = [
            ScholarAuthor(
                name=a.get("name", ""),
                author_id=str(a.get("authorId", "")),
            )
            for a in (paper.get("authors") or [])
        ]
        results.append(ScholarResult(
            paper_id=paper.get("paperId", ""),
            title=paper.get("title", ""),
            year=paper.get("year"),
            authors=authors,
            abstract=paper.get("abstract"),
            citation_count=paper.get("citationCount", 0),
            url=paper.get("url", ""),
        ))

    logger.info(
        "Semantic Scholar: query='%s' returned %d results",
        query[:60], len(results),
    )
    return results
