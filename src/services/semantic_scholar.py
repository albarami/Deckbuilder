"""Semantic Scholar — Academic Graph + Recommendations API client.

Follows the official S2 documentation flow:
  1. Bulk search (discovery)
  2. Score & shortlist seed papers
  3. Recommendations expansion from seeds
  4. Hydrate retained papers with full metadata
  5. Classification & export

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

# D2: Module-level call counter for provider usage tracking
_S2_CALL_COUNT: int = 0


def get_s2_usage() -> dict:
    """Return Semantic Scholar API call count for provider usage reporting."""
    return {"calls": _S2_CALL_COUNT}


S2_GRAPH_BASE = "https://api.semanticscholar.org/graph/v1"
S2_RECOMMENDATIONS_BASE = "https://api.semanticscholar.org/recommendations/v1"
S2_BULK_SEARCH_URL = f"{S2_GRAPH_BASE}/paper/search/bulk"
S2_RECOMMENDATIONS_URL = f"{S2_RECOMMENDATIONS_BASE}/papers"

# Field lists per documentation
DISCOVERY_FIELDS = (
    "paperId,title,abstract,year,url,citationCount,"
    "publicationTypes,fieldsOfStudy,openAccessPdf,venue"
)
RECOMMENDATION_FIELDS = "title,url,authors,citationCount,year,abstract"
HYDRATION_FIELDS = (
    "title,abstract,year,url,citationCount,influentialCitationCount,"
    "authors,venue,publicationVenue,openAccessPdf,"
    "fieldsOfStudy,publicationTypes,tldr"
)

# Legacy compat
S2_PAPER_FIELDS = DISCOVERY_FIELDS
MAX_QUERY_WORDS = 8
AUTH_MIN_INTERVAL_SEC = 1.0

# Junk rejection: fields of study that are off-domain for consulting proposals
_REJECT_FIELDS = {
    "medicine", "biology", "chemistry", "physics", "materials science",
    "environmental science", "geology", "astronomy", "mathematics",
    "agricultural and food sciences", "art", "history", "philosophy",
    "geography", "linguistics",
}


class SemanticScholarAPIError(Exception):
    """Raised when S2 returns a non-200 response."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"S2 API {status_code}: {body}")


def shorten_query(raw_query: str) -> list[str]:
    """Split a long planner query into short keyword phrases (<=8 words each)."""
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


def score_paper(paper: dict, query_theme: str = "") -> float:
    """Score a paper for proposal relevance (0.0-1.0).

    Score dimensions:
    - Title relevance keywords
    - Abstract relevance keywords
    - Citation count (log scale)
    - Recency bonus
    - Field-of-study fit
    - Junk penalty
    """
    score = 0.0
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    year = paper.get("year") or 0
    citations = paper.get("citationCount") or 0
    fields = [f.lower() for f in (paper.get("fieldsOfStudy") or [])]

    # Relevance keywords (consulting/institutional/methodology)
    _RELEVANCE_KW = [
        "service", "framework", "portfolio", "governance", "institutional",
        "assessment", "methodology", "evaluation", "benchmark", "model",
        "government", "agency", "public sector", "promotion", "investment",
        "export", "sme", "internationalization", "relationship management",
        "operating model", "service delivery", "kpi", "sla", "readiness",
        "segmentation", "client", "stakeholder", "capacity building",
    ]
    title_hits = sum(1 for kw in _RELEVANCE_KW if kw in title)
    abstract_hits = sum(1 for kw in _RELEVANCE_KW if kw in abstract)
    score += min(title_hits * 0.12, 0.36)
    score += min(abstract_hits * 0.04, 0.24)

    # Citation count (log scale)
    import math
    if citations > 0:
        score += min(math.log10(citations + 1) * 0.05, 0.15)

    # Recency bonus
    if year >= 2022:
        score += 0.10
    elif year >= 2020:
        score += 0.05

    # Field-of-study fit
    good_fields = {"business", "economics", "political science", "sociology",
                   "computer science", "engineering", "education"}
    if fields:
        if any(f in good_fields for f in fields):
            score += 0.10
        if any(f in _REJECT_FIELDS for f in fields):
            score -= 0.30  # Hard penalty for off-domain

    # Junk rejection: medical/clinical/biology
    _JUNK_TITLE_KW = [
        "patient", "clinical", "tumor", "gene", "protein", "cell",
        "therapy", "diagnosis", "treatment", "hospital", "surgery",
        "species", "genome", "neural network", "deep learning",
    ]
    if any(kw in title for kw in _JUNK_TITLE_KW):
        score -= 0.50

    return max(0.0, min(score, 1.0))


@dataclass
class _SearchRunStats:
    """Internal telemetry for search+recommend flow."""

    queries: list[str] = field(default_factory=list)
    seed_ids: list[str] = field(default_factory=list)
    total_discovered: int = 0
    total_after_scoring: int = 0
    total_after_recommendations: int = 0
    junk_rejected: int = 0
    # Per-query bulk search telemetry: query → {total, returned}
    per_query_telemetry: dict = field(default_factory=dict)


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
        """Authenticated GET with retry on 429/500. Raises on persistent failure."""
        global _S2_CALL_COUNT
        for attempt in range(3):
            await self._rate_limit()
            headers = {"x-api-key": self._api_key}
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params, headers=headers)
            _S2_CALL_COUNT += 1
            logger.info("S2 GET %s: %s params=%s", resp.status_code, url, params)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503) and attempt < 2:
                wait = (attempt + 1) * 2  # 2s, 4s backoff
                logger.warning("S2 %d on attempt %d, retrying in %ds", resp.status_code, attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            body = resp.text[:500]
            logger.error("S2 API error %s: %s", resp.status_code, body)
            raise SemanticScholarAPIError(resp.status_code, body)
        raise SemanticScholarAPIError(0, "Max retries exceeded")

    async def _post(self, url: str, params: dict, json_data: dict) -> dict:
        """Authenticated POST with retry on 429/500. Raises on persistent failure."""
        global _S2_CALL_COUNT
        for attempt in range(3):
            await self._rate_limit()
            headers = {"x-api-key": self._api_key}
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, params=params, json=json_data, headers=headers)
            _S2_CALL_COUNT += 1
            logger.info("S2 POST %s: %s", resp.status_code, url)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503) and attempt < 2:
                wait = (attempt + 1) * 2
                logger.warning("S2 %d on attempt %d, retrying in %ds", resp.status_code, attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            body = resp.text[:500]
            logger.error("S2 API error %s: %s", resp.status_code, body)
            raise SemanticScholarAPIError(resp.status_code, body)
        raise SemanticScholarAPIError(0, "Max retries exceeded")

    async def search_papers(
        self,
        query: str,
        year_from: int = 2018,
        max_results: int = 50,
        min_citations: int = 5,
        fields_of_study: list[str] | None = None,
        publication_types: list[str] | None = None,
        sort: str = "citationCount:desc",
    ) -> list[dict]:
        """Step 1: Bulk search with full discovery filters per documentation.

        Uses GET /graph/v1/paper/search/bulk with:
        - year filter (default: 2018-)
        - fieldsOfStudy filter (default: Business,Economics,Political Science,Sociology)
        - publicationTypes filter (default: Review,JournalArticle,Study,BookSection,Book)
        - minCitationCount filter (default: 5 for broad topics)
        - sort by citationCount desc by default
        - DISCOVERY_FIELDS for rich metadata

        Handles token pagination: keeps fetching pages until max_results
        or marginal relevance collapses (empty page / total exhausted).
        """
        params: dict = {
            "query": query,
            "fields": DISCOVERY_FIELDS,
            "year": f"{year_from}-",
        }
        if min_citations > 0:
            params["minCitationCount"] = str(min_citations)
        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)
        if publication_types:
            params["publicationTypes"] = ",".join(publication_types)
        if sort:
            params["sort"] = sort

        all_papers: list[dict] = []
        token: str | None = None
        pages = 0

        while len(all_papers) < max_results and pages < 3:
            if token:
                params["token"] = token

            data = await self._get(S2_BULK_SEARCH_URL, params)
            papers = data.get("data", [])
            next_token = data.get("token")

            if not papers:
                break

            all_papers.extend(papers)
            pages += 1

            if not next_token or next_token == token:
                break
            token = next_token

        total = data.get("total", 0) if data else 0
        logger.info(
            "S2 search: query='%s' total=%s pages=%d returned=%d",
            query, total, pages, len(all_papers),
        )
        all_papers.sort(key=lambda p: p.get("citationCount", 0), reverse=True)
        return all_papers[:max_results], total

    async def get_recommendations(
        self,
        seed_paper_ids: list[str],
        negative_paper_ids: list[str] | None = None,
        max_results: int = 30,
    ) -> list[dict]:
        """Step 3: Get recommended papers with positive AND negative seeds.

        Uses POST /recommendations/v1/papers with:
        - positivePaperIds: best seed papers
        - negativePaperIds: off-domain papers to steer away from
        """
        params = {
            "fields": RECOMMENDATION_FIELDS,
            "limit": min(max_results, 40),
        }
        body = {
            "positivePaperIds": seed_paper_ids,
            "negativePaperIds": negative_paper_ids or [],
        }
        data = await self._post(S2_RECOMMENDATIONS_URL, params, body)
        papers = data.get("recommendedPapers", [])
        logger.info(
            "S2 recommendations: seeds=%s negatives=%s returned=%s",
            len(seed_paper_ids),
            len(negative_paper_ids or []),
            len(papers),
        )
        return papers

    async def hydrate_papers(self, paper_ids: list[str]) -> list[dict]:
        """Step 4: Hydrate shortlisted papers with full metadata.

        Uses POST /graph/v1/paper/batch to enrich papers with:
        title, abstract, year, url, citationCount, influentialCitationCount,
        authors, venue, publicationVenue, openAccessPdf, fieldsOfStudy,
        publicationTypes, tldr
        """
        if not paper_ids:
            return []

        url = f"{S2_GRAPH_BASE}/paper/batch"
        params = {"fields": HYDRATION_FIELDS}
        body = {"ids": paper_ids[:100]}  # API limit: 100 per batch

        try:
            data = await self._post(url, params, body)
            # Response is a list of paper objects (some may be None)
            papers = [p for p in data if p is not None]
            logger.info(
                "S2 hydration: requested=%d returned=%d",
                len(paper_ids), len(papers),
            )
            return papers
        except SemanticScholarAPIError as e:
            logger.warning("S2 hydration failed: %s", e)
            return []

    async def get_author_details(self, author_ids: list[str]) -> list[dict]:
        """Step 4b (optional): Author enrichment for credibility/context.

        Uses POST /graph/v1/author/batch. Only call when author
        credibility matters for proposal evidence strength.
        """
        if not author_ids:
            return []

        url = f"{S2_GRAPH_BASE}/author/batch"
        params = {"fields": "name,affiliations,paperCount,citationCount,hIndex"}
        body = {"ids": author_ids[:100]}

        try:
            data = await self._post(url, params, body)
            authors = [a for a in data if a is not None]
            logger.info(
                "S2 author enrichment: requested=%d returned=%d",
                len(author_ids), len(authors),
            )
            return authors
        except SemanticScholarAPIError as e:
            logger.warning("S2 author enrichment failed (non-blocking): %s", e)
            return []

    async def search_snippets(
        self,
        query: str,
        paper_ids: list[str] | None = None,
        max_results: int = 5,
    ) -> list[dict]:
        """Step 5 (optional): Extract exact supporting excerpts from papers.

        Uses GET /graph/v1/snippet/search for high-value shortlisted papers.
        Only call selectively — not for every paper.
        """
        url = f"{S2_GRAPH_BASE}/snippet/search"
        params: dict = {
            "query": query,
            "limit": max_results,
        }
        if paper_ids:
            params["paper_ids"] = ",".join(paper_ids[:10])

        try:
            data = await self._get(url, params)
            snippets = data.get("data", [])
            logger.info(
                "S2 snippets: query='%s' papers=%s returned=%d",
                query[:40], len(paper_ids or []), len(snippets),
            )
            return snippets
        except SemanticScholarAPIError as e:
            logger.warning("S2 snippet search failed (non-blocking): %s", e)
            return []

    async def search_and_recommend(
        self,
        queries: list[str],
        year_from: int = 2018,
        search_per_query: int = 50,
        recommend_count: int = 30,
    ) -> list[dict]:
        """Full documented flow: search → score → shortlist → recommend → hydrate.

        Step 1: Bulk search per query with filters (fieldsOfStudy, pagination)
        Step 2: Score all discovered papers
        Step 3: Select top 3-5 seeds + identify junk for negative IDs
        Step 4: Recommendations with positive seeds + negative junk papers
        Step 5: Hydrate final shortlist with full metadata
        Step 6: Return merged, scored, deduplicated, hydrated results
        """
        stats = _SearchRunStats(queries=list(queries))
        all_papers: dict[str, dict] = {}

        # Default filters per documentation spec
        _PREFERRED_FIELDS = [
            "Business", "Economics", "Political Science", "Sociology", "Education",
        ]
        _PREFERRED_PUB_TYPES = [
            "Review", "JournalArticle", "Study", "BookSection", "Book",
        ]

        # Step 1: Bulk search with ALL required filters and pagination
        for q in queries:
            try:
                results, bulk_total = await self.search_papers(
                    query=q,
                    year_from=year_from,
                    max_results=search_per_query,
                    min_citations=5,
                    fields_of_study=_PREFERRED_FIELDS,
                    publication_types=_PREFERRED_PUB_TYPES,
                    sort="citationCount:desc",
                )
                # Capture per-query telemetry
                stats.per_query_telemetry[q] = {
                    "bulk_search_total": bulk_total,
                    "bulk_search_returned": len(results),
                }
                for p in results:
                    pid = p.get("paperId", "")
                    if pid and pid not in all_papers:
                        all_papers[pid] = p
            except SemanticScholarAPIError as e:
                logger.warning("S2 search failed for '%s': %s", q, e)
                stats.per_query_telemetry[q] = {
                    "bulk_search_total": 0,
                    "bulk_search_returned": 0,
                    "error": str(e),
                }

        stats.total_discovered = len(all_papers)

        if not all_papers:
            logger.warning("S2: no papers found from search, skipping recommendations")
            return [], stats.per_query_telemetry

        # Step 2: Score all discovered papers
        for pid, paper in all_papers.items():
            paper["_relevance_score"] = score_paper(paper)

        # Identify junk (score < 0.05) — these become negative IDs
        junk_ids = [pid for pid, p in all_papers.items() if p.get("_relevance_score", 0) < 0.05]
        for pid in junk_ids:
            del all_papers[pid]
        stats.junk_rejected = len(junk_ids)
        stats.total_after_scoring = len(all_papers)

        if not all_papers:
            logger.warning("S2: all papers rejected by scoring")
            return [], stats.per_query_telemetry

        # Step 3: Select top 3-5 seeds
        sorted_papers = sorted(
            all_papers.values(),
            key=lambda p: p.get("_relevance_score", 0),
            reverse=True,
        )
        seed_ids = [p["paperId"] for p in sorted_papers[:5]]
        stats.seed_ids = seed_ids
        logger.info(
            "S2: selected %d seed papers (scores: %s)",
            len(seed_ids),
            [f"{p.get('_relevance_score', 0):.2f}" for p in sorted_papers[:5]],
        )

        # Step 4: Recommendations with negative IDs for drift control
        # Use up to 3 junk IDs as negative seeds to steer away from off-domain
        negative_ids = junk_ids[:3] if junk_ids else []
        try:
            recs = await self.get_recommendations(
                seed_ids,
                negative_paper_ids=negative_ids,
                max_results=recommend_count,
            )
            for p in recs:
                pid = p.get("paperId", "")
                if pid and pid not in all_papers:
                    p["_relevance_score"] = score_paper(p)
                    if p["_relevance_score"] >= 0.05:
                        all_papers[pid] = p
        except SemanticScholarAPIError as e:
            logger.warning("S2 recommendations failed: %s", e)

        stats.total_after_recommendations = len(all_papers)

        # Step 5: Hydrate top papers with full metadata
        top_ids = sorted(
            all_papers.keys(),
            key=lambda pid: all_papers[pid].get("_relevance_score", 0),
            reverse=True,
        )[:15]  # Hydrate top 15
        try:
            hydrated = await self.hydrate_papers(top_ids)
            for hp in hydrated:
                pid = hp.get("paperId", "")
                if pid in all_papers:
                    # Merge hydrated fields into existing paper
                    all_papers[pid].update(hp)
                    # Preserve our score
                    if "_relevance_score" not in all_papers[pid]:
                        all_papers[pid]["_relevance_score"] = score_paper(all_papers[pid])
            logger.info("S2 hydration: enriched %d papers", len(hydrated))
        except Exception as e:
            logger.warning("S2 hydration step failed (non-blocking): %s", e)

        # Step 6: Final sort by relevance score
        final = sorted(
            all_papers.values(),
            key=lambda p: p.get("_relevance_score", 0),
            reverse=True,
        )

        logger.info(
            "S2 pipeline: discovered=%d, after_scoring=%d, junk_rejected=%d, "
            "after_recs=%d, seeds=%s",
            stats.total_discovered, stats.total_after_scoring,
            stats.junk_rejected, stats.total_after_recommendations,
            stats.seed_ids[:3],
        )
        return final, stats.per_query_telemetry
