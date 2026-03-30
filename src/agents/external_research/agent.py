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
    """Assign evidence_tier and evidence_class to each source.

    evidence_tier thresholds:
        >= 0.80 → primary
        >= 0.65 → secondary
        <  0.65 → analogical

    evidence_class rules:
        academic papers, industry reports, benchmarks from international
        orgs (McKinsey, BCG, OECD, World Bank, IFC, UNCTAD) → international_benchmark
        Sources from country-specific gov sites, ministry pubs → local_public
        Everything else defaults to international_benchmark
    """
    _LOCAL_INDICATORS = [
        "gov.sa", "gov.qa", "gov.ae", "vision2030", "qnv2030",
        "ministry", "وزارة", "هيئة", "authority",
        "dga.gov", "ndmo.gov", "nca.gov", "zatca.gov",
    ]

    for source in pack.sources:
        # Tier
        if source.relevance_score >= 0.80:
            source.evidence_tier = "primary"
        elif source.relevance_score >= 0.65:
            source.evidence_tier = "secondary"
        else:
            source.evidence_tier = "analogical"

        # Class
        url_lower = (source.url or "").lower()
        title_lower = (source.title or "").lower()
        combined = f"{url_lower} {title_lower}"

        if any(indicator in combined for indicator in _LOCAL_INDICATORS):
            source.evidence_class = "local_public"
        else:
            source.evidence_class = "international_benchmark"


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


def _validate_query(query: str, max_len: int = 120) -> str | None:
    """Validate and clean a search query. Returns None if invalid.

    Ensures queries end at complete word boundaries, removes dangling
    prepositions/conjunctions, and caps length at max_len characters.
    """
    q = query.strip()
    if not q or len(q) < 8:
        return None

    # Step 1: Truncate to max_len at the LAST word boundary
    if len(q) > max_len:
        truncated = q[:max_len]
        # Find last space to avoid cutting mid-word
        last_space = truncated.rfind(" ")
        if last_space > 20:
            q = truncated[:last_space].strip()
        else:
            q = truncated.strip()

    # Step 2: If there's a comma followed by fewer than 3 words, truncate at comma
    if "," in q:
        last_comma = q.rfind(",")
        after_comma = q[last_comma + 1:].strip()
        if after_comma and len(after_comma.split()) < 3:
            q = q[:last_comma].strip()

    # Step 3: Remove trailing clause-starters and prepositions
    # These are words that indicate an incomplete sentence when at the end
    _TRAILING_JUNK = [
        # Clause starters (the sentence continues after these)
        " including", " especially", " particularly", " specifically",
        " such as", " through", " via", " across", " along",
        " regarding", " concerning", " involving",
        # Prepositions and conjunctions
        " with", " without", " and", " or", " for", " in", " of",
        " to", " from", " the", " a", " an", " their", " its",
        " by", " at", " on", " as",
        # Arabic prepositions and conjunctions
        " بما", " مع", " من", " في", " إلى", " على", " عن",
        " و", " أو", " ال", " يشمل",
    ]
    changed = True
    while changed:
        changed = False
        for junk in _TRAILING_JUNK:
            if q.lower().endswith(junk):
                q = q[: -len(junk)].strip()
                changed = True

    # Step 4: If query still ends mid-word (no common ending char),
    # truncate to last complete word
    if q and q[-1].isalpha() and len(q) > 40:
        words = q.split()
        if len(words) > 3:
            # Check if last word looks like a fragment (< 3 chars)
            if len(words[-1]) < 3:
                q = " ".join(words[:-1])

    if not q or len(q) < 8:
        return None
    return q


def _scope_to_research_question(scope_en: str) -> str | None:
    """Convert a scope item's English text into a proper research question.

    Uses keyword detection to identify the domain concept and maps it
    to a human-quality research question. Returns None if no meaningful
    concept is detected.
    """
    text = scope_en.lower()

    # Map domain concepts to research questions
    # Each tuple: (keywords_to_match, research_question)
    _CONCEPT_MAP: list[tuple[list[str], str]] = [
        (["priorit", "needs", "assess", "current"],
         "how do investment promotion agencies assess company needs and prioritize service delivery"),
        (["service", "ecosystem", "portfolio", "design"],
         "how do government agencies design service portfolios for companies expanding internationally"),
        (["institutional framework", "relationship", "managing"],
         "benchmark models for institutional relationship management between investment agencies and national companies"),
        (["strategic support", "activation", "continuous"],
         "operating models for government agencies providing continuous strategic support to national firms"),
        (["export", "expansion", "international"],
         "international benchmarks for government-backed export and international expansion support programs"),
        (["segmentation", "classification", "readiness"],
         "international benchmarks for company segmentation by readiness for cross-border expansion"),
        (["sla", "kpi", "performance", "indicator"],
         "service level agreements and KPI frameworks for investment promotion agencies"),
        (["governance", "oversight", "steering"],
         "governance frameworks for multi-stakeholder consulting engagements in government"),
        (["knowledge transfer", "capacity building"],
         "knowledge transfer methodologies for consulting engagements with government agencies"),
    ]

    for keywords, question in _CONCEPT_MAP:
        if sum(1 for kw in keywords if kw in text) >= 2:
            return question

    # Fallback: extract first meaningful phrase and frame it
    nouns = _extract_domain_nouns(scope_en, max_words=5)
    if nouns and len(nouns.split()) >= 3:
        return f"how do government agencies implement {nouns} programs"
    return None


def _generate_pplx_queries(state: DeckForgeState) -> list[str]:
    """Generate 6-10 Perplexity queries as human-quality research questions.

    Each query contains: actor + action + domain context + output type.
    NO raw RFP text copying. NO noun dumps. NO "best practices for" prefix.
    """
    queries: list[str] = []

    rfp = state.rfp_context
    if not rfp:
        return ["how do consulting firms design service delivery frameworks"]

    # 1. Per scope item — map to curated research questions
    if rfp.scope_items:
        for si in rfp.scope_items[:4]:
            en = _extract_bilingual_en(si.description) or ""
            if en:
                q = _scope_to_research_question(en)
                if q:
                    queries.append(q)

    # 2. Pack-driven seed queries (curated by domain experts)
    pack_ctx = getattr(state, "pack_context", None) or {}
    pack_search = pack_ctx.get("recommended_search_queries", [])
    for pq in pack_search[:5]:
        queries.append(pq)

    # 3. Per deliverable — map to research questions
    if rfp.deliverables:
        for deliv in rfp.deliverables[:2]:
            en = _extract_bilingual_en(deliv.description) or ""
            if en:
                q = _scope_to_research_question(en)
                if q:
                    queries.append(q)

    # 4. Geographic/institutional context
    geography = state.geography or ""
    sector = state.sector or ""
    if geography and sector:
        queries.append(
            f"how does {geography} government evaluate {sector} consulting proposals"
        )

    if not queries:
        queries.append("how do consulting firms design service delivery frameworks")

    # Validate — no truncation, no copy-paste, no noun dumps
    validated = []
    for q in queries:
        clean = _validate_query(q)
        if clean:
            validated.append(clean)

    return _deduplicate(validated)[:10]


def _extract_domain_nouns(text: str, max_words: int = 8) -> str:
    """Extract domain-concept nouns from English text for academic queries.

    Filters out verbs, articles, prepositions, and conjunctions to keep
    only meaningful nouns/adjectives that form academic keyword phrases.
    Returns a phrase of up to *max_words* words.
    """
    # Common non-noun words to strip (verbs, articles, prepositions, etc.)
    _STOP_WORDS = {
        "a", "an", "the", "and", "or", "of", "for", "in", "on", "to",
        "with", "by", "at", "from", "into", "through", "is", "are",
        "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "shall", "should", "would",
        "could", "may", "might", "must", "can", "need", "their",
        "its", "this", "that", "these", "those", "it", "as", "not",
        "all", "each", "every", "both", "such", "than", "also",
        "very", "just", "about", "which", "who", "whom", "what",
        "how", "when", "where", "while", "if", "so", "then",
        # Common RFP verbs
        "analyze", "analyse", "identify", "develop", "design", "assess",
        "evaluate", "review", "prepare", "provide", "support", "ensure",
        "establish", "implement", "define", "determine", "conduct",
        "create", "build", "deliver", "manage", "including", "include",
    }
    words = text.split()
    nouns = [w for w in words if w.lower().strip(",.;:()") not in _STOP_WORDS and len(w) > 2]
    return " ".join(nouns[:max_words])


def _generate_s2_queries(state: DeckForgeState) -> list[str]:
    """Generate 6-10 academic-style S2 queries using 4-bucket approach.

    Bucket A: Core methodology (needs assessment, service design, governance)
    Bucket B: Institutional model (operating models, agency design, frameworks)
    Bucket C: Evaluation/measurement (KPI, maturity, assessment methods)
    Bucket D: Analogical domain (export promotion, investment agencies, trade)

    Each query: 5-8 words, readable English, methodology-focused.
    """
    queries: list[str] = []
    rfp = state.rfp_context
    if not rfp:
        return ["consulting methodology evaluation framework"]

    # Build searchable text from scope items
    scope_text = ""
    if rfp.scope_items:
        for si in rfp.scope_items[:4]:
            en = _extract_bilingual_en(si.description) or ""
            scope_text += " " + en.lower()

    # 1. Pack-driven curated S2 queries (highest priority)
    pack_ctx = getattr(state, "pack_context", None) or {}
    for pq in pack_ctx.get("recommended_s2_queries", [])[:4]:
        clean = _validate_query(pq, max_len=80)
        if clean:
            queries.append(clean)

    # 2. Bucket A — Core methodology queries
    _BUCKET_A = [
        (["needs", "assess", "priorit", "current"],
         "needs assessment methodology for government service agencies"),
        (["service", "portfolio", "design", "catalog"],
         "service portfolio design framework for public agencies"),
        (["governance", "oversight", "steering", "reporting"],
         "project governance framework for consulting engagements"),
        (["roadmap", "phased", "implementation", "timeline"],
         "phased implementation roadmap methodology for government"),
    ]
    for keywords, query in _BUCKET_A:
        if sum(1 for kw in keywords if kw in scope_text) >= 2:
            if query not in queries:
                queries.append(query)

    # 3. Bucket B — Institutional model queries
    _BUCKET_B = [
        (["institutional", "framework", "relationship", "managing"],
         "institutional framework for client relationship management"),
        (["operating", "model", "service delivery"],
         "operating model design for government support agencies"),
        (["stakeholder", "engagement", "communication"],
         "stakeholder engagement framework for public programs"),
    ]
    for keywords, query in _BUCKET_B:
        if sum(1 for kw in keywords if kw in scope_text) >= 2:
            if query not in queries:
                queries.append(query)

    # 4. Bucket C — Evaluation/measurement queries
    _BUCKET_C = [
        (["kpi", "sla", "performance", "indicator"],
         "service level agreement design for public agencies"),
        (["readiness", "maturity", "assessment", "segmentation"],
         "readiness assessment framework for client segmentation"),
        (["monitor", "evaluation", "quality", "measurement"],
         "program evaluation methodology for public services"),
    ]
    for keywords, query in _BUCKET_C:
        if sum(1 for kw in keywords if kw in scope_text) >= 2:
            if query not in queries:
                queries.append(query)

    # 5. Bucket D — Analogical domain queries
    _BUCKET_D = [
        (["export", "expansion", "international", "outbound"],
         "investment promotion agency service delivery framework"),
        (["investment", "promotion", "trade", "enterprise"],
         "export promotion program evaluation methodology"),
        (["support", "national", "companies", "firms"],
         "government agency support programs for firm internationalization"),
    ]
    for keywords, query in _BUCKET_D:
        if sum(1 for kw in keywords if kw in scope_text) >= 2:
            if query not in queries:
                queries.append(query)

    if not queries:
        queries.append("consulting methodology evaluation framework")

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
            max_tokens=16000,
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
