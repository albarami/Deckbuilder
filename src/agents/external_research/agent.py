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


def _classify_evidence_tiers(pack: ExternalEvidencePack) -> None:
    """Assign evidence_tier to each source based on relevance_score.

    Thresholds:
        >= 0.80 → primary (directly about the RFP domain)
        >= 0.65 → secondary (transferable methodology from adjacent domain)
        <  0.65 → analogical (cross-domain analogy, limited direct applicability)
    """
    for source in pack.sources:
        if source.relevance_score >= 0.80:
            source.evidence_tier = "primary"
        elif source.relevance_score >= 0.65:
            source.evidence_tier = "secondary"
        else:
            source.evidence_tier = "analogical"


def _append_tier_counts(pack: ExternalEvidencePack) -> None:
    """Append primary/secondary/analogical counts to coverage_assessment."""
    counts = {"primary": 0, "secondary": 0, "analogical": 0}
    for source in pack.sources:
        counts[source.evidence_tier] += 1
    tier_line = (
        f"\n\nEvidence Tier Breakdown: "
        f"primary_source_count: {counts['primary']}, "
        f"secondary_source_count: {counts['secondary']}, "
        f"analogical_source_count: {counts['analogical']}"
    )
    pack.coverage_assessment = (pack.coverage_assessment or "") + tier_line


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


def _generate_pplx_queries(state: DeckForgeState) -> list[str]:
    """Generate 6-8 Perplexity queries from RFP context.

    Strategy: one query per RFP scope item, one per deliverable cluster,
    plus mandate and RFP-name queries. Each query targets a specific
    RFP scope area for web synthesis evidence.
    """
    queries: list[str] = []

    rfp = state.rfp_context
    if not rfp:
        return ["management consulting methodology best practices"]

    rfp_name = _extract_bilingual_any(rfp.rfp_name)
    mandate = _extract_bilingual_any(rfp.mandate)

    if rfp_name and len(rfp_name) > 5:
        queries.append(f"{rfp_name[:80]} consulting methodology")

    if mandate and len(mandate) > 10:
        queries.append(f"{mandate[:100].strip()} best practices")

    if rfp.scope_items:
        for scope_item in rfp.scope_items[:4]:
            text = _extract_bilingual_any(scope_item.description)
            if text and len(text) > 10:
                queries.append(f"{text[:100].strip()} framework methodology")

    if rfp.deliverables:
        for deliv in rfp.deliverables[:2]:
            text = _extract_bilingual_any(deliv.description)
            if text and len(text) > 10:
                queries.append(f"{text[:100].strip()} best practices")

    sector = state.sector or ""
    geography = state.geography or ""
    if sector and geography:
        queries.append(f"{geography} {sector} consulting framework")
    elif sector:
        queries.append(f"{sector} consulting best practices")

    if not queries:
        if rfp_name:
            queries.append(rfp_name)
        elif mandate:
            queries.append(mandate[:100])
        else:
            queries.append("management consulting methodology best practices")

    return _deduplicate(queries)[:8]


def _generate_s2_queries(state: DeckForgeState) -> list[str]:
    """Generate short academic-style queries for Semantic Scholar.

    S2 works best with 3-5 word keyword phrases. Long natural
    language sentences return irrelevant medical/science papers.
    """
    queries: list[str] = []
    rfp = state.rfp_context
    if not rfp:
        return ["consulting methodology evaluation"]

    sector = state.sector or ""

    if rfp.scope_items:
        for scope_item in rfp.scope_items[:4]:
            text = _extract_bilingual_any(scope_item.description)
            if text:
                words = text.split()[:4]
                phrase = " ".join(words)
                if sector:
                    queries.append(f"{phrase} {sector}")
                else:
                    queries.append(f"{phrase} framework")

    if rfp.deliverables:
        for deliv in rfp.deliverables[:2]:
            text = _extract_bilingual_any(deliv.description)
            if text:
                words = text.split()[:3]
                queries.append(" ".join(words) + " assessment")

    mandate = _extract_bilingual_any(rfp.mandate)
    if mandate:
        words = mandate.split()[:4]
        queries.append(" ".join(words) + " evaluation")

    if not queries:
        queries.append("consulting methodology evaluation")

    return _deduplicate(queries)[:5]


def _generate_supplementary_queries(
    state: DeckForgeState,
    existing_sources: list[dict],
) -> list[str]:
    """Generate supplementary queries for scope areas not yet covered.

    Compares RFP scope items against mapped themes in existing sources.
    Produces targeted queries for uncovered areas.
    """
    rfp = state.rfp_context
    if not rfp or not rfp.scope_items:
        return []

    covered_themes: set[str] = set()
    for src in existing_sources:
        content = src.get("content", "") + src.get("abstract", "")
        content_lower = content.lower()
        for scope_item in rfp.scope_items:
            text = _extract_bilingual_any(scope_item.description)
            if text:
                key_words = [w.lower() for w in text.split()[:3] if len(w) > 3]
                if any(kw in content_lower for kw in key_words):
                    covered_themes.add(text[:50])

    supplementary: list[str] = []
    sector = state.sector or ""
    geography = state.geography or ""
    geo_prefix = f"{geography} " if geography else ""

    for scope_item in rfp.scope_items:
        text = _extract_bilingual_any(scope_item.description)
        if text and text[:50] not in covered_themes:
            words = text.split()[:6]
            phrase = " ".join(words)
            supplementary.append(
                f"{geo_prefix}{phrase} {sector} best practices".strip()
            )

    if rfp.deliverables:
        for deliv in rfp.deliverables:
            text = _extract_bilingual_any(deliv.description)
            if text and text[:50] not in covered_themes:
                words = text.split()[:5]
                supplementary.append(
                    " ".join(words) + " benchmarking"
                )

    return _deduplicate(supplementary)[:4]


def _deduplicate(items: list[str]) -> list[str]:
    """Deduplicate while preserving order."""
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


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


async def _gather_raw_evidence(
    pplx_queries: list[str],
    s2_queries: list[str],
) -> dict:
    """Run search queries against Semantic Scholar and Perplexity.

    Uses separate query lists: short academic phrases for S2,
    longer natural-language queries for Perplexity.
    Returns raw results for LLM ranking. Gracefully degrades on failures.
    """
    settings = get_settings()
    scholar_results: list[dict] = []
    perplexity_results: list[dict] = []

    api_key = settings.semantic_scholar_api_key
    if api_key.strip() and s2_queries:
        papers = await _search_semantic_scholar(s2_queries[:5], api_key)
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

    # Perplexity searches (up to 4 queries for broader coverage)
    try:
        from src.services.perplexity import search_web

        api_key = settings.perplexity_api_key.get_secret_value()
        for query in pplx_queries[:4]:
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
    """Run the External Research Agent with two-pass coverage strategy.

    Pass 1: Run initial queries against S2 and Perplexity.
    Pass 2: Evaluate coverage. If fewer than 4 usable sources or
            major scope gaps, generate supplementary Perplexity queries.

    Returns a dict with keys matching DeckForgeState fields to update.
    """
    pplx_queries = _generate_pplx_queries(state)
    s2_queries = _generate_s2_queries(state)
    all_queries = _deduplicate(pplx_queries + s2_queries)

    if not all_queries:
        logger.warning("No search queries generated — returning empty evidence pack")
        return {
            "external_evidence_pack": ExternalEvidencePack(
                coverage_assessment="No search queries could be generated from RFP context.",
            ),
        }

    # Pass 1: initial queries
    raw_evidence = await _gather_raw_evidence(pplx_queries, s2_queries)

    # Pass 2: evaluate coverage and run supplementary queries if needed
    total_pass1 = (
        len(raw_evidence["scholar_results"])
        + len(raw_evidence["perplexity_results"])
    )
    if total_pass1 < 4:
        supp_queries = _generate_supplementary_queries(
            state, raw_evidence["perplexity_results"],
        )
        if supp_queries:
            logger.info(
                "Coverage gap: %d sources from pass 1, running %d "
                "supplementary Perplexity queries",
                total_pass1, len(supp_queries),
            )
            supp_evidence = await _gather_raw_evidence(
                pplx_queries=supp_queries, s2_queries=[],
            )
            raw_evidence["perplexity_results"].extend(
                supp_evidence["perplexity_results"]
            )
            all_queries = _deduplicate(all_queries + supp_queries)
            logger.info(
                "After pass 2: %d total sources",
                len(raw_evidence["scholar_results"])
                + len(raw_evidence["perplexity_results"]),
            )

    queries = all_queries

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
        _classify_evidence_tiers(evidence_pack)
        _append_tier_counts(evidence_pack)

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
        fallback_pack = ExternalEvidencePack(
            sources=fallback_sources,
            search_queries_used=queries,
            coverage_assessment=(
                "LLM ranking failed. Sources included without relevance scoring. "
                f"Error: {e}"
            ),
        )
        _classify_evidence_tiers(fallback_pack)
        _append_tier_counts(fallback_pack)
        return {"external_evidence_pack": fallback_pack}


def _update_session(state: DeckForgeState, llm_result) -> object:
    """Update session metadata with token usage."""
    session = state.session.model_copy(deep=True)
    session.total_llm_calls += 1
    session.total_input_tokens += llm_result.input_tokens
    session.total_output_tokens += llm_result.output_tokens
    return session
