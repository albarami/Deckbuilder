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


def _generate_search_queries(state: DeckForgeState) -> list[str]:
    """Generate search queries from RFP context and state fields.

    Uses real RFPContext fields: rfp_name, mandate, scope_items, deliverables.
    Uses state-level fields: sector, geography.
    Produces clean, human-readable search strings (no raw object repr).
    """
    queries: list[str] = []

    rfp = state.rfp_context
    sector = state.sector or ""
    geography = state.geography or ""

    # Extract RFP name and mandate (English text only)
    rfp_name = ""
    mandate = ""
    if rfp:
        rfp_name = _extract_bilingual_en(rfp.rfp_name)
        mandate = _extract_bilingual_en(rfp.mandate)

    # Query 1: Sector + RFP name
    if sector and rfp_name:
        queries.append(f"{sector} {rfp_name} best practices")
    elif rfp_name:
        queries.append(f"{rfp_name} consulting methodology")

    # Query 2: Geography + sector
    if geography and sector:
        queries.append(f"{geography} {sector} digital transformation")

    # Query 3: Mandate-based (first 100 chars of mandate text)
    if mandate and len(mandate) > 10:
        mandate_short = mandate[:100].strip()
        queries.append(f"{mandate_short} methodology framework")

    # Query 4: From deliverables (extract .description.en text)
    if rfp and rfp.deliverables:
        del_texts = [
            _extract_bilingual_en(d.description)
            for d in rfp.deliverables[:3]
            if _extract_bilingual_en(d.description)
        ]
        if del_texts:
            keywords = " ".join(del_texts[:2])[:120]
            queries.append(f"{keywords} consulting best practices")

    # Query 5: From scope_items (extract .description.en text)
    if rfp and rfp.scope_items and len(queries) < 5:
        scope_texts = [
            _extract_bilingual_en(s.description)
            for s in rfp.scope_items[:3]
            if _extract_bilingual_en(s.description)
        ]
        if scope_texts:
            keywords = " ".join(scope_texts[:2])[:120]
            queries.append(f"{keywords} framework")

    # Fallback: at least one query
    if not queries:
        if rfp_name:
            queries.append(rfp_name)
        elif mandate:
            queries.append(mandate[:100])
        else:
            queries.append("management consulting methodology best practices")

    return queries[:5]  # Cap at 5 queries


def _gather_raw_evidence(queries: list[str]) -> dict:
    """Run search queries against Semantic Scholar and Perplexity.

    Returns raw results for LLM ranking. Gracefully degrades on failures.
    """
    settings = get_settings()
    scholar_results: list[dict] = []
    perplexity_results: list[dict] = []

    # Semantic Scholar searches (3 queries max)
    try:
        from src.services.semantic_scholar import search_papers

        api_key = settings.semantic_scholar_api_key
        for query in queries[:3]:
            try:
                papers = search_papers(query, api_key=api_key, max_results=3)
                for paper in papers:
                    scholar_results.append({
                        "title": paper.title,
                        "year": paper.year or 0,
                        "abstract": paper.abstract or "",
                        "citation_count": paper.citation_count,
                        "url": paper.url,
                        "source": "semantic_scholar",
                        "query": query,
                    })
            except Exception as e:
                logger.warning("Semantic Scholar query failed: %s — %s", query, e)
    except Exception as e:
        logger.warning("Semantic Scholar service unavailable: %s", e)

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
                        "source": "perplexity",
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

    raw_evidence = _gather_raw_evidence(queries)

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
            max_tokens=4000,
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
                title=sr["title"],
                source_type="academic_paper",
                year=sr.get("year", 0),
                url=sr.get("url", ""),
                abstract=sr.get("abstract", "")[:500],
                relevance_score=0.5,
                relevance_reason="Auto-included (LLM ranking unavailable)",
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
