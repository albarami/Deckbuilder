"""External Research Agent — gathers external evidence from Semantic Scholar + Perplexity.

Runs search queries against both services, then uses an LLM to rank, filter,
and extract structured evidence into an ExternalEvidencePack.

Designed for graceful degradation: if both services fail, returns an empty
pack with a coverage assessment noting the failure.
"""

from __future__ import annotations

import json
import logging

from src.config.models import MODEL_MAP
from src.config.settings import get_settings
from src.models.external_evidence import ExternalEvidencePack, ExternalSource
from src.models.state import DeckForgeState
from src.services.llm import call_llm

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _extract_bilingual_en(bt) -> str:
    """Extract English text from a BilingualText object safely."""
    if bt is None:
        return ""
    if hasattr(bt, "en") and bt.en:
        return bt.en
    if isinstance(bt, str):
        return bt
    return ""


def _extract_bilingual_any(bt) -> str:
    """Extract text from a BilingualText, preferring English, falling back to Arabic."""
    if bt is None:
        return ""
    if hasattr(bt, "en") and bt.en:
        return bt.en
    if hasattr(bt, "ar") and bt.ar:
        return bt.ar
    if isinstance(bt, str):
        return bt
    return ""


def _generate_search_queries(state: DeckForgeState) -> list[str]:
    """Generate 6-8 search queries from RFP context and state fields.

    Strategy: one query per RFP scope item, one per deliverable cluster,
    plus mandate and RFP-name queries. Each query targets a specific
    RFP scope area, not generic consulting methodology.

    Extracts text in any available language (English preferred, Arabic fallback)
    so queries work for non-English RFPs too.
    """
    queries: list[str] = []

    rfp = state.rfp_context
    if not rfp:
        return ["management consulting methodology best practices"]

    rfp_name = _extract_bilingual_any(rfp.rfp_name)
    mandate = _extract_bilingual_any(rfp.mandate)

    # Query 1: RFP name — broad domain context
    if rfp_name and len(rfp_name) > 5:
        queries.append(f"{rfp_name[:80]} consulting methodology")

    # Query 2: Mandate — the core ask
    if mandate and len(mandate) > 10:
        queries.append(f"{mandate[:100].strip()} best practices")

    # Queries 3-6: One per scope item (most domain-specific)
    if rfp.scope_items:
        for scope_item in rfp.scope_items[:4]:
            text = _extract_bilingual_any(scope_item.description)
            if text and len(text) > 10:
                queries.append(f"{text[:100].strip()} framework methodology")

    # Queries 7-8: From deliverables (each individually)
    if rfp.deliverables:
        for deliv in rfp.deliverables[:2]:
            text = _extract_bilingual_any(deliv.description)
            if text and len(text) > 10:
                queries.append(f"{text[:100].strip()} best practices")

    # Sector/geography if available
    sector = state.sector or ""
    geography = state.geography or ""
    if sector and geography:
        queries.append(f"{geography} {sector} consulting framework")
    elif sector:
        queries.append(f"{sector} consulting best practices")

    # Fallback: at least one query
    if not queries:
        if rfp_name:
            queries.append(rfp_name)
        elif mandate:
            queries.append(mandate[:100])
        else:
            queries.append("management consulting methodology best practices")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique[:8]  # Cap at 8 queries


async def _search_semantic_scholar(queries: list[str], api_key: str) -> list[dict]:
    """Run S2 two-step search + recommendations."""
    from src.services.semantic_scholar import (
        SemanticScholarAPIError,
        SemanticScholarClient,
        shorten_query,
    )

    short_queries: list[str] = []
    for q in queries:
        short_queries.extend(shorten_query(q))
    short_queries = list(dict.fromkeys(short_queries))
    logger.info(
        "S2: %d short queries from %d raw queries",
        len(short_queries),
        len(queries),
    )

    client = SemanticScholarClient(api_key)
    try:
        papers = await client.search_and_recommend(short_queries)
        return papers
    except SemanticScholarAPIError as e:
        logger.error("S2 pipeline failed: %s", e)
        return []


async def _gather_raw_evidence(queries: list[str]) -> dict:
    """Run search queries against Semantic Scholar and Perplexity.

    Returns raw results for LLM ranking. Gracefully degrades on failures.
    """
    settings = get_settings()
    scholar_results: list[dict] = []
    perplexity_results: list[dict] = []

    api_key = settings.semantic_scholar_api_key
    if api_key.strip():
        papers = await _search_semantic_scholar(queries[:3], api_key)
        for paper in papers:
            authors_raw = paper.get("authors", []) or []
            author_names = [
                a.get("name", "") for a in authors_raw if isinstance(a, dict)
            ][:10]
            scholar_results.append({
                "title": paper.get("title", ""),
                "authors": author_names,
                "year": paper.get("year", 0) or 0,
                "abstract": paper.get("abstract", "") or "",
                "citation_count": paper.get("citationCount", 0) or 0,
                "url": paper.get("url", "") or "",
                "provider": "semantic_scholar",
                "selection_method": "search_hit",
                "query": "",
            })
    else:
        logger.warning("Semantic Scholar API key missing — skipping S2 external research")

    # Perplexity searches (2 queries max)
    try:
        from src.services.perplexity import search_web

        api_key = settings.perplexity_api_key.get_secret_value()
        for query in queries[:2]:
            try:
                result = search_web(
                    query,
                    api_key=api_key,
                    system_context=(
                        "You are helping a management consulting firm gather "
                        "evidence for a proposal. Provide specific facts, "
                        "statistics, and benchmark data."
                    ),
                )
                if result:
                    perplexity_results.append({
                        "content": result.content[:2000],
                        "citations": [
                            {"url": c.url, "title": c.title}
                            for c in result.citations
                        ],
                        "provider": "perplexity",
                        "selection_method": "perplexity_synthesis",
                        "query": query,
                    })
            except Exception as e:
                logger.warning("Perplexity query failed: %s — %s", query, e)
    except Exception as e:
        logger.warning("Perplexity service unavailable: %s", e)

    return {
        "scholar_results": scholar_results,
        "perplexity_results": perplexity_results,
    }


async def run(state: DeckForgeState) -> dict:
    """Run the External Research Agent.

    Returns a dict with keys matching DeckForgeState fields to update.
    """
    queries = _generate_search_queries(state)
    if not queries:
        logger.warning("No search queries generated — returning empty evidence pack")
        return {
            "external_evidence_pack": ExternalEvidencePack(
                coverage_assessment="No search queries could be generated from RFP context.",
            ),
        }

    raw_evidence = await _gather_raw_evidence(queries)

    # If both services returned nothing, return empty pack
    total_results = (
        len(raw_evidence["scholar_results"])
        + len(raw_evidence["perplexity_results"])
    )
    if total_results == 0:
        logger.warning("All external searches returned no results — empty evidence pack")
        return {
            "external_evidence_pack": ExternalEvidencePack(
                search_queries_used=queries,
                coverage_assessment=(
                    "Both Semantic Scholar and Perplexity returned no results. "
                    "Proposal will rely on internal evidence only."
                ),
            ),
        }

    # Use LLM to rank, filter, and structure the evidence
    rfp_summary = ""
    if state.rfp_context:
        rfp_name = _extract_bilingual_en(state.rfp_context.rfp_name)
        if rfp_name:
            rfp_summary += f"RFP: {rfp_name}\n"
        mandate = _extract_bilingual_en(state.rfp_context.mandate)
        if mandate:
            rfp_summary += f"Mandate: {mandate[:200]}\n"
        if state.sector:
            rfp_summary += f"Sector: {state.sector}\n"
        if state.rfp_context.scope_items:
            scope_texts = [
                _extract_bilingual_en(s.description)
                for s in state.rfp_context.scope_items[:5]
                if _extract_bilingual_en(s.description)
            ]
            if scope_texts:
                rfp_summary += f"Scope: {', '.join(scope_texts)}\n"

    user_message = json.dumps({
        "rfp_summary": rfp_summary,
        "search_queries": queries,
        "raw_evidence": raw_evidence,
    }, ensure_ascii=False, default=str)

    try:
        model = MODEL_MAP.get(
            "external_research_agent",
            MODEL_MAP.get("conversation_manager", "claude-sonnet-4-20250514"),
        )
        llm_result = await call_llm(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=ExternalEvidencePack,
            max_tokens=8000,
        )
        evidence_pack = llm_result.parsed
        evidence_pack.search_queries_used = queries

        logger.info(
            "External research complete: %d sources from %d queries",
            len(evidence_pack.sources),
            len(queries),
        )

        return {
            "external_evidence_pack": evidence_pack,
            "session": _update_session(state, llm_result),
        }

    except Exception as e:
        logger.error("External research LLM call failed: %s", e)
        # Fallback: build a basic pack from raw results without LLM ranking
        fallback_sources: list[ExternalSource] = []
        for i, sr in enumerate(raw_evidence["scholar_results"][:5]):
            fallback_sources.append(ExternalSource(
                source_id=f"EXT-{i + 1:03d}",
                provider="semantic_scholar",
                title=sr["title"],
                authors=sr.get("authors", []),
                source_type="academic_paper",
                year=sr.get("year", 0),
                url=sr.get("url", ""),
                abstract=sr.get("abstract", "")[:500],
                query_used=sr.get("query", ""),
                relevance_score=0.5,
                relevance_reason="Auto-included (LLM ranking unavailable)",
                citation_count=sr.get("citation_count"),
                selection_method=sr.get("selection_method", "search_hit"),
            ))
        return {
            "external_evidence_pack": ExternalEvidencePack(
                sources=fallback_sources,
                search_queries_used=queries,
                coverage_assessment=(
                    "LLM ranking failed. Sources included without relevance scoring. "
                    f"Error: {e}"
                ),
            ),
        }


def _update_session(state: DeckForgeState, llm_result) -> object:
    """Update session metadata with token usage."""
    session = state.session.model_copy(deep=True)
    session.total_llm_calls += 1
    session.total_input_tokens += llm_result.input_tokens
    session.total_output_tokens += llm_result.output_tokens
    return session
