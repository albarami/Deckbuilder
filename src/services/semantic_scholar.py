"""Semantic Scholar — Academic Graph + Recommendations API client.

Uses x-api-key authentication. Rate limit: 1 req/s across all endpoints.
If the key returns 403, log the error and raise. NO anonymous fallback.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

S2_GRAPH_BASE = "https://api.semanticscholar.org/graph/v1"
S2_RECOMMENDATIONS_BASE = "https://api.semanticscholar.org/recommendations/v1"
S2_BULK_SEARCH_URL = f"{S2_GRAPH_BASE}/paper/search/bulk"
S2_RECOMMENDATIONS_URL = f"{S2_RECOMMENDATIONS_BASE}/papers"
S2_PAPER_FIELDS = "paperId,title,year,abstract,citationCount,url"
MAX_QUERY_WORDS = 5
AUTH_MIN_INTERVAL_SEC = 1.0


class SemanticScholarAPIError(Exception):
    """Raised when S2 returns a non-200 response."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"S2 API {status_code}: {body}")


def shorten_query(raw_query: str) -> list[str]:
    """Split a long planner query into short keyword phrases (<=5 words each).

    Long natural language queries return 0 results from S2.
    Short 2-5 word keyword phrases work well.
    """
    fragments = re.split(r"[;\n,]", raw_query)
    short_phrases: list[str] = []
    for frag in fragments:
        words = frag.strip().split()
        if not words:
            continue
        if len(words) <= MAX_QUERY_WORDS:
            short_phrases.append(" ".join(words))
        else:
            short_phrases.append(" ".join(words[:MAX_QUERY_WORDS]))
    return [p for p in short_phrases if len(p) > 3]


@dataclass
class _SearchRunStats:
    """Internal telemetry for search+recommend flow."""

    queries: list[str] = field(default_factory=list)
    seed_ids: list[str] = field(default_factory=list)


class SemanticScholarClient:
    """Async client for S2 Academic Graph + Recommendations APIs."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        self._api_key = api_key.strip()
        self._timeout = timeout
        self._next_request_at = 0.0
        self._lock = asyncio.Lock()

    async def _rate_limit(self) -> None:
        """Enforce 1 req/s across all authenticated calls."""
        async with self._lock:
            now = time.monotonic()
            wait = self._next_request_at - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_request_at = time.monotonic() + AUTH_MIN_INTERVAL_SEC

    async def _get(self, url: str, params: dict) -> dict:
        """Authenticated GET. Raises on non-200. NO fallback."""
        await self._rate_limit()
        headers = {"x-api-key": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params=params, headers=headers)
        logger.info("S2 GET %s: %s params=%s", resp.status_code, url, params)
        if resp.status_code != 200:
            body = resp.text[:500]
            logger.error("S2 API error %s: %s", resp.status_code, body)
            raise SemanticScholarAPIError(resp.status_code, body)
        return resp.json()

    async def _post(self, url: str, params: dict, json_data: dict) -> dict:
        """Authenticated POST. Raises on non-200. NO fallback."""
        await self._rate_limit()
        headers = {"x-api-key": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, params=params, json=json_data, headers=headers)
        logger.info("S2 POST %s: %s", resp.status_code, url)
        if resp.status_code != 200:
            body = resp.text[:500]
            logger.error("S2 API error %s: %s", resp.status_code, body)
            raise SemanticScholarAPIError(resp.status_code, body)
        return resp.json()

    async def search_papers(
        self, query: str, year_from: int = 2020, max_results: int = 10
    ) -> list[dict]:
        """Bulk search for papers matching a SHORT keyword query."""
        params = {
            "query": query,
            "fields": S2_PAPER_FIELDS,
            "year": f"{year_from}-",
        }
        data = await self._get(S2_BULK_SEARCH_URL, params)
        papers = data.get("data", [])
        logger.info(
            "S2 search: query='%s' total=%s returned=%s",
            query,
            data.get("total", 0),
            len(papers),
        )
        papers.sort(key=lambda p: p.get("citationCount", 0), reverse=True)
        return papers[:max_results]

    async def get_recommendations(
        self, seed_paper_ids: list[str], max_results: int = 20
    ) -> list[dict]:
        """Get recommended papers based on seed papers."""
        params = {
            "fields": S2_PAPER_FIELDS,
            "limit": min(max_results, 500),
        }
        body = {
            "positivePaperIds": seed_paper_ids,
            "negativePaperIds": [],
        }
        data = await self._post(S2_RECOMMENDATIONS_URL, params, body)
        papers = data.get("recommendedPapers", [])
        logger.info(
            "S2 recommendations: seeds=%s returned=%s",
            len(seed_paper_ids),
            len(papers),
        )
        return papers

    async def search_and_recommend(
        self,
        queries: list[str],
        year_from: int = 2020,
        search_per_query: int = 5,
        recommend_count: int = 20,
    ) -> list[dict]:
        """Two-step flow: search → seed → recommend → merge."""
        all_papers: dict[str, dict] = {}
        stats = _SearchRunStats(queries=list(queries))

        for q in queries:
            try:
                results = await self.search_papers(q, year_from, search_per_query)
                for p in results:
                    pid = p.get("paperId", "")
                    if pid and pid not in all_papers:
                        all_papers[pid] = p
            except SemanticScholarAPIError as e:
                logger.warning("S2 search failed for '%s': %s", q, e)

        if not all_papers:
            logger.warning("S2: no papers found from search, skipping recommendations")
            return []

        sorted_papers = sorted(
            all_papers.values(),
            key=lambda p: p.get("citationCount", 0),
            reverse=True,
        )
        seed_ids = [p["paperId"] for p in sorted_papers[:5]]
        stats.seed_ids = seed_ids
        logger.info("S2: using %s seed papers for recommendations", len(seed_ids))

        try:
            recs = await self.get_recommendations(seed_ids, recommend_count)
            for p in recs:
                pid = p.get("paperId", "")
                if pid and pid not in all_papers:
                    all_papers[pid] = p
        except SemanticScholarAPIError as e:
            logger.warning("S2 recommendations failed: %s", e)

        final = sorted(
            all_papers.values(),
            key=lambda p: p.get("citationCount", 0),
            reverse=True,
        )
        logger.info("S2 total: %s unique papers (search + recommendations)", len(final))
        return final
