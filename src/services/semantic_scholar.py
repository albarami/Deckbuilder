"""Semantic Scholar (S2) Graph API — external academic evidence for retrieval.

Uses ``x-api-key`` authentication (not Bearer). Bulk paper search plus
recommendations for richer recall. There is no anonymous/keyless fallback
after a failed authenticated request.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

S2_BULK_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
S2_RECOMMENDATIONS_URL = "https://api.semanticscholar.org/recommendations/v1/papers"

DEFAULT_TIMEOUT = 60.0
MAX_KEYWORD_PHRASES = 12
MAX_WORDS_PER_QUERY = 5


def normalize_semantic_scholar_api_key(raw: str) -> str:
    """Strip whitespace and accidental ``Bearer `` prefix from env values."""
    key = raw.strip()
    if key.lower().startswith("bearer "):
        return key[7:].strip()
    return key


class SemanticScholarAPIError(RuntimeError):
    """Semantic Scholar HTTP or response error (non-2xx or unexpected payload)."""

    def __init__(self, message: str, *, status_code: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def keyword_phrases_from_queries(queries: list[str], *, max_phrases: int = MAX_KEYWORD_PHRASES) -> list[str]:
    """Derive short keyword phrases (2–5 words) for S2 bulk search.

    Long natural-language strings match poorly; short phrases aligned to titles/abstracts work best.
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in queries:
        text = raw.strip()
        if not text:
            continue
        parts = re.split(r"[\n;]+", text)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            words = part.split()
            if len(words) <= MAX_WORDS_PER_QUERY:
                phrase = part
            else:
                phrase = " ".join(words[:MAX_WORDS_PER_QUERY])
            key = phrase.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(phrase)
            if len(out) >= max_phrases:
                return out
    return out


def _paper_doc_id(paper_id: str) -> str:
    """Stable deckforge id for an S2 paper."""
    return f"S2-{paper_id}"


def _normalize_paper(raw: dict[str, Any]) -> dict[str, Any]:
    """Ensure paperId and common fields exist."""
    pid = raw.get("paperId") or raw.get("paper_id")
    if not pid:
        return {}
    return {
        "paperId": str(pid),
        "title": raw.get("title") or "",
        "year": raw.get("year"),
        "abstract": raw.get("abstract") or "",
        "citationCount": int(raw.get("citationCount") or 0),
        "url": raw.get("url") or "",
    }


class SemanticScholarClient:
    """Async Semantic Scholar API client (authenticated requests only)."""

    def __init__(self, api_key: str, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        key = normalize_semantic_scholar_api_key(api_key)
        if not key:
            msg = "Semantic Scholar API key is required for authenticated requests"
            raise ValueError(msg)
        self._api_key = key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key}

    async def search_papers(
        self,
        query: str,
        *,
        year_from: int = 2020,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search S2 for papers matching a short keyword query (bulk endpoint)."""
        params = {
            "query": query,
            "fields": "title,year,abstract,citationCount,url,paperId",
            "year": f"{year_from}-",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                S2_BULK_SEARCH_URL,
                params=params,
                headers=self._headers(),
            )
        if response.status_code != 200:
            logger.error(
                "Semantic Scholar bulk search failed: status=%s body=%s",
                response.status_code,
                response.text[:2000],
            )
            raise SemanticScholarAPIError(
                f"Semantic Scholar bulk search returned {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )
        payload = response.json()
        papers_raw = payload.get("data") or []
        papers: list[dict[str, Any]] = []
        for item in papers_raw:
            norm = _normalize_paper(item)
            if norm:
                papers.append(norm)
        papers.sort(key=lambda p: p.get("citationCount", 0), reverse=True)
        return papers[:max_results]

    async def get_recommendations(
        self,
        seed_paper_ids: list[str],
        *,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Recommend papers similar to seed papers (positive IDs)."""
        if not seed_paper_ids:
            return []
        params = {
            "fields": "title,url,citationCount,abstract,year,paperId",
            "limit": max_results,
        }
        body = {
            "positivePaperIds": seed_paper_ids,
            "negativePaperIds": [],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                S2_RECOMMENDATIONS_URL,
                params=params,
                json=body,
                headers=self._headers(),
            )
        if response.status_code != 200:
            logger.error(
                "Semantic Scholar recommendations failed: status=%s body=%s",
                response.status_code,
                response.text[:2000],
            )
            raise SemanticScholarAPIError(
                f"Semantic Scholar recommendations returned {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )
        payload = response.json()
        recs_raw = payload.get("recommendedPapers") or []
        papers: list[dict[str, Any]] = []
        for item in recs_raw:
            norm = _normalize_paper(item)
            if norm:
                papers.append(norm)
        return papers


def _citation_score(papers: list[dict[str, Any]]) -> dict[str, float]:
    """Map paperId -> 0..1 score from citation counts within the set."""
    if not papers:
        return {}
    max_c = max((p.get("citationCount") or 0) for p in papers) or 1
    return {p["paperId"]: min(1.0, (p.get("citationCount") or 0) / max_c) for p in papers}


def papers_to_ranker_results(
    papers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build retrieval ranker payloads and doc registry for analysis/load_documents."""
    scores = _citation_score(papers)
    ranker: list[dict[str, Any]] = []
    registry: dict[str, dict[str, Any]] = {}
    for p in papers:
        pid = p["paperId"]
        doc_id = _paper_doc_id(pid)
        abstract = p.get("abstract") or ""
        excerpt = abstract[:500] if abstract else ""
        base = scores.get(pid, 0.5)
        ranker.append({
            "doc_id": doc_id,
            "title": p.get("title") or "Untitled",
            "excerpt": excerpt,
            "metadata": {
                "source": "semantic_scholar",
                "paperId": pid,
                "year": p.get("year"),
                "citationCount": p.get("citationCount", 0),
                "url": p.get("url", ""),
            },
            "search_score": round(0.01 + 0.99 * base, 4),
        })
        registry[doc_id] = p
    return ranker, registry


async def gather_external_evidence(
    planner_queries: list[str],
    *,
    api_key: str,
    year_from: int = 2020,
    max_per_phrase: int = 10,
    seed_count: int = 5,
    max_recommendations: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Run S2 bulk search across keyword phrases, then recommendations from top seeds.

    Returns:
        Tuple of (ranker_result_dicts, doc_id -> paper dict for load_documents).
    """
    phrases = keyword_phrases_from_queries(planner_queries)
    if not phrases:
        return [], {}

    client = SemanticScholarClient(api_key)
    merged: dict[str, dict[str, Any]] = {}

    for phrase in phrases:
        batch = await client.search_papers(phrase, year_from=year_from, max_results=max_per_phrase)
        for p in batch:
            merged[p["paperId"]] = p

    ranked = sorted(merged.values(), key=lambda x: x.get("citationCount", 0), reverse=True)
    seed_ids = [p["paperId"] for p in ranked[:seed_count] if p.get("paperId")]

    if seed_ids:
        recs = await client.get_recommendations(seed_ids, max_results=max_recommendations)
        for p in recs:
            merged[p["paperId"]] = p

    final_list = list(merged.values())
    return papers_to_ranker_results(final_list)
