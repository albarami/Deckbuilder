"""RFP Routing Service — classify RFP, select packs, merge into context.

Implements the routing architecture:
RFP → Classifier → Pack Selection → Pack Merge → Routing Report
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.models.routing import (
    ContextPack,
    RFPClassification,
    RoutingReport,
)
from src.models.state import DeckForgeState

logger = logging.getLogger(__name__)

# Pack registry directory
_PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"

# ──────────────────────────────────────────────────────────────
# B.8: File-based pack discovery — scan src/packs/*.json at import time
# ──────────────────────────────────────────────────────────────


def _discover_pack_files() -> tuple[
    dict[str, str],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, dict[str, list[str]]],
]:
    """Scan the packs directory for *.json files.

    Returns:
        Tuple of (pack_registry, jurisdiction_kw, sector_kw, domain_kw, domain_tiered_kw).
        - pack_registry: pack_id → filename
        - jurisdiction_kw: jurisdiction_name → keyword list
        - sector_kw: sector_name → keyword list
        - domain_kw: domain_name → flat keyword list (back-compat)
        - domain_tiered_kw: domain_name → {"strong": [...], "medium": [...], "weak": [...]}

    Keywords are extracted from the optional "classification_keywords" field
    in each pack JSON file. Tiered keywords come from the optional
    "tiered_classification_keywords" field used by skeleton domain packs.
    """
    registry: dict[str, str] = {}
    jurisdiction_kw: dict[str, list[str]] = {}
    sector_kw: dict[str, list[str]] = {}
    domain_kw: dict[str, list[str]] = {}
    domain_tiered_kw: dict[str, dict[str, list[str]]] = {}

    if not _PACKS_DIR.is_dir():
        logger.warning("Packs directory not found: %s", _PACKS_DIR)
        return registry, jurisdiction_kw, sector_kw, domain_kw, domain_tiered_kw

    for pack_path in sorted(_PACKS_DIR.glob("*.json")):
        try:
            data = json.loads(pack_path.read_text(encoding="utf-8"))
            pack_id = data.get("pack_id")
            if pack_id:
                registry[pack_id] = pack_path.name
            else:
                logger.warning(
                    "Pack file %s has no pack_id field — skipping", pack_path.name,
                )
                continue

            # Extract classification_keywords if present
            ck = data.get("classification_keywords", {})
            for jur_name, kw_list in ck.get("jurisdiction", {}).items():
                jurisdiction_kw.setdefault(jur_name, []).extend(kw_list)
            for sec_name, kw_list in ck.get("sector", {}).items():
                sector_kw.setdefault(sec_name, []).extend(kw_list)
            for dom_name, kw_list in ck.get("domain", {}).items():
                domain_kw.setdefault(dom_name, []).extend(kw_list)

            # Extract tiered_classification_keywords if present (skeleton packs)
            tk = data.get("tiered_classification_keywords", {})
            for dom_name, tiers in tk.get("domain", {}).items():
                bucket = domain_tiered_kw.setdefault(
                    dom_name, {"strong": [], "medium": [], "weak": []},
                )
                for tier in ("strong", "medium", "weak"):
                    bucket[tier].extend(tiers.get(tier, []))

        except Exception as e:
            logger.error("Failed to read pack file %s: %s", pack_path.name, e)

    # Deduplicate keyword lists while preserving order
    for d in (jurisdiction_kw, sector_kw, domain_kw):
        for key in d:
            d[key] = list(dict.fromkeys(d[key]))
    for dom in domain_tiered_kw:
        for tier in ("strong", "medium", "weak"):
            domain_tiered_kw[dom][tier] = list(
                dict.fromkeys(domain_tiered_kw[dom][tier])
            )

    return registry, jurisdiction_kw, sector_kw, domain_kw, domain_tiered_kw


# Auto-discovered pack registry (built at import time)
(
    _PACK_FILES,
    _PACK_JURISDICTION_KW,
    _PACK_SECTOR_KW,
    _PACK_DOMAIN_KW,
    _PACK_DOMAIN_TIERED_KW,
) = _discover_pack_files()

# ──────────────────────────────────────────────────────────────
# Classification keywords: built ENTIRELY from pack JSON files.
# No hardcoded jurisdiction/sector/domain keywords in this file.
# All keywords come from classification_keywords in pack files.
# ──────────────────────────────────────────────────────────────

# Final keyword dicts: pack-driven ONLY (no hardcoded fallbacks)
_JURISDICTION_KEYWORDS: dict[str, list[str]] = dict(_PACK_JURISDICTION_KW)
_SECTOR_KEYWORDS: dict[str, list[str]] = dict(_PACK_SECTOR_KW)
_DOMAIN_KEYWORDS: dict[str, list[str]] = dict(_PACK_DOMAIN_KW)
_DOMAIN_TIERED_KEYWORDS: dict[str, dict[str, list[str]]] = dict(_PACK_DOMAIN_TIERED_KW)

# Tier weights for weighted domain scoring (Slice 1.2)
_TIER_WEIGHTS: dict[str, int] = {"strong": 5, "medium": 3, "weak": 1}
_DEFAULT_KEYWORD_WEIGHT: int = 3  # weight for untiered keyword hits
_DOMAIN_SCORE_THRESHOLD: float = 3.0  # min weighted score to qualify a domain

# Generic vs specific domains for primary/secondary demotion logic.
# When a specific domain qualifies, generic domains are demoted to secondary.
_GENERIC_DOMAINS: set[str] = {"digital_transformation", "performance_management"}
_SPECIFIC_DOMAINS: set[str] = {
    "ai_governance_ethics",
    "unesco_unesco_ram",
    "international_research_collaboration",
    "government_capacity_building",
    "knowledge_transfer",
    "research_program_evaluation",
}


def _reload_pack_keywords() -> None:
    """Re-scan packs directory and rebuild all keyword dicts.

    Useful for testing: write a temporary pack JSON, call this function,
    and verify the classifier picks up the new keywords.
    """
    global _PACK_FILES, _PACK_JURISDICTION_KW, _PACK_SECTOR_KW, _PACK_DOMAIN_KW
    global _PACK_DOMAIN_TIERED_KW
    global _JURISDICTION_KEYWORDS, _SECTOR_KEYWORDS, _DOMAIN_KEYWORDS
    global _DOMAIN_TIERED_KEYWORDS

    (
        _PACK_FILES,
        _PACK_JURISDICTION_KW,
        _PACK_SECTOR_KW,
        _PACK_DOMAIN_KW,
        _PACK_DOMAIN_TIERED_KW,
    ) = _discover_pack_files()
    _JURISDICTION_KEYWORDS.clear()
    _JURISDICTION_KEYWORDS.update(_PACK_JURISDICTION_KW)
    _SECTOR_KEYWORDS.clear()
    _SECTOR_KEYWORDS.update(_PACK_SECTOR_KW)
    _DOMAIN_KEYWORDS.clear()
    _DOMAIN_KEYWORDS.update(_PACK_DOMAIN_KW)
    _DOMAIN_TIERED_KEYWORDS.clear()
    _DOMAIN_TIERED_KEYWORDS.update(_PACK_DOMAIN_TIERED_KW)


def _score_domain(dom_name: str, search_text: str) -> float:
    """Compute weighted domain score for `search_text`.

    If the domain has tiered keywords (skeleton packs), strong/medium/weak
    matches are scored at 5/3/1. Otherwise each keyword hit scores
    `_DEFAULT_KEYWORD_WEIGHT`.
    """
    if dom_name in _DOMAIN_TIERED_KEYWORDS:
        score = 0.0
        for tier in ("strong", "medium", "weak"):
            weight = _TIER_WEIGHTS[tier]
            for kw in _DOMAIN_TIERED_KEYWORDS[dom_name].get(tier, []):
                if kw.lower() in search_text:
                    score += weight
        return score
    score = 0.0
    for kw in _DOMAIN_KEYWORDS.get(dom_name, []):
        if kw.lower() in search_text:
            score += _DEFAULT_KEYWORD_WEIGHT
    return score


# Subdomain keywords mapped from scope text
_SUBDOMAIN_KEYWORDS: dict[str, list[str]] = {
    "export_support": ["export", "تصدير", "outbound", "trade"],
    "smart_government": ["smart", "ذكي", "e-government", "حكومة إلكترونية"],
    "cloud_migration": ["cloud", "سحاب", "migration", "ترحيل"],
    "erp_implementation": ["erp", "sap", "oracle", "enterprise resource"],
    "organizational_restructuring": ["restructuring", "إعادة هيكلة", "reorganization"],
    "performance_management": ["performance", "أداء", "kpi", "balanced scorecard"],
    "service_portfolio": ["service portfolio", "محفظة خدمات", "service catalog"],
    "investment_attraction": ["fdi", "foreign direct investment", "استثمار أجنبي"],
}

def _build_jurisdiction_pack_map() -> dict[str, dict[str, str]]:
    """Build jurisdiction→sector→pack_id map dynamically from pack files.

    Scans all jurisdiction packs and maps their jurisdiction keywords
    to pack_ids. No hardcoded jurisdiction names.
    """
    jur_map: dict[str, dict[str, str]] = {}
    for pack_path in sorted(_PACKS_DIR.glob("*.json")):
        try:
            data = json.loads(pack_path.read_text(encoding="utf-8"))
            if data.get("pack_type") != "jurisdiction":
                continue
            pack_id = data.get("pack_id", "")
            ck = data.get("classification_keywords", {})
            # Find which jurisdiction(s) this pack serves
            for jur_name in ck.get("jurisdiction", {}):
                if jur_name not in jur_map:
                    jur_map[jur_name] = {}
                # Find which sector(s) this pack serves
                sectors = list(ck.get("sector", {}).keys())
                if sectors:
                    for sec in sectors:
                        jur_map[jur_name][sec] = pack_id
                # Also set as default for unknown sector
                jur_map[jur_name]["unknown"] = pack_id
        except Exception:
            pass
    return jur_map


_JURISDICTION_PACK_MAP: dict[str, dict[str, str]] = _build_jurisdiction_pack_map()


def _build_regulatory_frame_patterns() -> list[tuple[str, str]]:
    """Build regulatory frame detection patterns from pack files.

    Scans all pack files for regulatory_references and builds
    (search_text, frame_name) pairs. No hardcoded jurisdiction-specific
    regulatory keywords.
    """
    patterns: list[tuple[str, str]] = []
    for pack_path in sorted(_PACKS_DIR.glob("*.json")):
        try:
            data = json.loads(pack_path.read_text(encoding="utf-8"))
            for ref in data.get("regulatory_references", []):
                name = ref.get("name", "")
                full_name = ref.get("full_name", "")
                if name and len(name) > 3:
                    frame = name.lower().replace(" ", "_")
                    patterns.append((name.lower(), frame))
                if full_name and len(full_name) > 5:
                    frame = name.lower().replace(" ", "_")
                    patterns.append((full_name.lower(), frame))
        except Exception:
            pass
    return patterns


# B.2: Client-type pack map
_CLIENT_TYPE_PACK_MAP: dict[str, str] = {
    "ministry": "ministry",
    "authority": "authority",
    "private_enterprise": "private_enterprise",
}

# Generic fallbacks when no jurisdiction pack exists
_FALLBACK_PACK_MAP: dict[str, str] = {
    "public_sector": "generic_mena_public_sector",
    "private_sector": "generic_mena_private_sector",
    "semi_government": "generic_mena_public_sector",
    "unknown": "generic_international",
}


def _load_pack(pack_id: str) -> ContextPack | None:
    """Load a context pack from the pack registry directory."""
    filename = _PACK_FILES.get(pack_id)
    if not filename:
        logger.warning("No pack file registered for pack_id: %s", pack_id)
        return None

    pack_path = _PACKS_DIR / filename
    if not pack_path.exists():
        logger.warning("Pack file not found: %s", pack_path)
        return None

    try:
        data = json.loads(pack_path.read_text(encoding="utf-8"))
        return ContextPack.model_validate(data)
    except Exception as e:
        logger.error("Failed to load pack %s: %s", pack_id, e)
        return None


def classify_rfp(state: DeckForgeState) -> RFPClassification:
    """Classify an RFP based on its context to determine pack selection.

    Uses rule-based keyword matching against RFP text. Falls back to
    "unknown" when confidence is low.
    """
    rfp = state.rfp_context
    if not rfp:
        return RFPClassification(confidence=0.0)

    # Build searchable text from RFP fields
    text_parts: list[str] = []
    for field in ["rfp_name", "mandate", "issuing_entity"]:
        val = getattr(rfp, field, None)
        if val:
            if hasattr(val, "en"):
                text_parts.append(getattr(val, "en", "") or "")
            if hasattr(val, "ar"):
                text_parts.append(getattr(val, "ar", "") or "")
            if isinstance(val, str):
                text_parts.append(val)

    for si in rfp.scope_items:
        desc = si.description
        if desc:
            text_parts.append(getattr(desc, "en", "") or "")
            text_parts.append(getattr(desc, "ar", "") or "")

    search_text = " ".join(text_parts).lower()

    # Classify jurisdiction
    jurisdiction = "unknown"
    jurisdiction_score = 0.0
    jurisdiction_scores: dict[str, float] = {}
    for jur, keywords in _JURISDICTION_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in search_text)
        jurisdiction_scores[jur] = hits
        if hits > jurisdiction_score:
            jurisdiction = jur
            jurisdiction_score = hits

    # Classify sector
    sector = "unknown"
    sector_score = 0.0
    for sec, keywords in _SECTOR_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in search_text)
        if hits > sector_score:
            sector = sec
            sector_score = hits

    # Classify domain — weighted multi-label scoring (Slice 1.2)
    # Each domain is scored either via tiered strong/medium/weak weights
    # or, for legacy packs without tiered keywords, via flat default weight.
    domain_scores: dict[str, float] = {}
    for dom in _DOMAIN_KEYWORDS:
        domain_scores[dom] = _score_domain(dom, search_text)

    # Qualifying domains: score above threshold, sorted by score desc.
    qualifying = sorted(
        [(d, s) for d, s in domain_scores.items() if s >= _DOMAIN_SCORE_THRESHOLD],
        key=lambda x: -x[1],
    )
    qualifying_ids = [d for d, _ in qualifying]

    # Demote generic domains to secondary when any specific domain qualifies.
    primary_domains: list[str] = []
    secondary_domains: list[str] = []
    if any(d in _SPECIFIC_DOMAINS for d in qualifying_ids):
        primary_domains = [d for d in qualifying_ids if d not in _GENERIC_DOMAINS]
        secondary_domains = [d for d in qualifying_ids if d in _GENERIC_DOMAINS]
    else:
        primary_domains = list(qualifying_ids)
        secondary_domains = []

    # Back-compat: legacy `domain` field exposes the top primary (or top qualifying).
    if primary_domains:
        domain = primary_domains[0]
    elif qualifying_ids:
        domain = qualifying_ids[0]
    else:
        domain = ""
    domain_score = domain_scores.get(domain, 0.0)

    # B.5: Extract subdomain from scope keywords
    subdomain = ""
    subdomain_score = 0.0
    for sub, keywords in _SUBDOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in search_text)
        if hits > subdomain_score:
            subdomain = sub
            subdomain_score = hits

    # Determine client type
    client_type = ""
    if "هيئة" in search_text or "authority" in search_text:
        client_type = "authority"
    elif "وزارة" in search_text or "ministry" in search_text:
        client_type = "ministry"
    elif "شركة" in search_text or "company" in search_text:
        client_type = "private_enterprise"

    # Detect regulatory frame dynamically from pack regulatory references
    # No hardcoded jurisdiction-specific keywords
    regulatory_frame = "none_identified"
    _reg_frame_patterns = _build_regulatory_frame_patterns()
    for pattern_text, frame_name in _reg_frame_patterns:
        if pattern_text.lower() in search_text:
            regulatory_frame = frame_name
            break

    # B.5: Detect evaluator pattern from evaluation_criteria (single object, not list)
    evaluator_pattern = ""
    ec = getattr(rfp, "evaluation_criteria", None)
    if ec:
        # Use structured award_mechanism if available
        if hasattr(ec, "award_mechanism") and ec.award_mechanism != "unknown":
            evaluator_pattern = ec.award_mechanism
        else:
            # Fallback inference from structure
            has_threshold = bool(
                getattr(ec, "technical_passing_threshold", None)
                or getattr(ec, "passing_score", None)
            )
            has_weights = bool(
                getattr(ec, "technical", None) and getattr(ec, "financial", None)
                and getattr(ec.technical, "weight_pct", None)
                and getattr(ec.financial, "weight_pct", None)
            )
            if has_weights and has_threshold:
                evaluator_pattern = "weighted_technical_financial"
            elif has_weights:
                evaluator_pattern = "weighted_technical_financial"
            elif has_threshold and not has_weights:
                # Threshold without weights — check for financial signal
                has_financial_signal = bool(getattr(ec, "financial", None)) or bool(
                    getattr(ec, "passing_score", None)
                )
                if has_financial_signal:
                    evaluator_pattern = "pass_fail_then_lowest_price"
                else:
                    evaluator_pattern = "technical_only"

    # B.5: Detect proof_types_needed from team_requirements and compliance
    proof_types_needed: list[str] = []
    team_reqs = getattr(rfp, "team_requirements", [])
    if team_reqs:
        proof_types_needed.append("team_cvs")
    compliance_reqs = getattr(rfp, "compliance_requirements", [])
    if compliance_reqs:
        proof_types_needed.append("compliance_certificates")
    if "case" in search_text or "experience" in search_text or "project" in search_text:
        proof_types_needed.append("case_studies")
    if "certification" in search_text or "شهادة" in search_text:
        proof_types_needed.append("certifications")
    if "financial" in search_text or "مالي" in search_text:
        proof_types_needed.append("financial_statements")

    # Detect language
    arabic_chars = sum(1 for c in search_text if "\u0600" <= c <= "\u06ff")
    language = "ar" if arabic_chars > len(search_text) * 0.3 else "en"

    # Compute confidence
    confidence = min(
        (jurisdiction_score + sector_score + domain_score) / 10.0,
        1.0,
    )

    # B.5: Build alternate classifications when confidence < 0.8
    alternate_classifications: list[dict] = []
    if confidence < 0.8:
        # Second-best jurisdiction
        sorted_jurs = sorted(
            jurisdiction_scores.items(), key=lambda x: x[1], reverse=True,
        )
        if len(sorted_jurs) >= 2 and sorted_jurs[1][1] > 0:
            alternate_classifications.append({
                "field": "jurisdiction",
                "value": sorted_jurs[1][0],
                "score": sorted_jurs[1][1],
            })
        # Second-best domain
        sorted_doms = sorted(
            domain_scores.items(), key=lambda x: x[1], reverse=True,
        )
        if len(sorted_doms) >= 2 and sorted_doms[1][1] > 0:
            alternate_classifications.append({
                "field": "domain",
                "value": sorted_doms[1][0],
                "score": sorted_doms[1][1],
            })

    classification = RFPClassification(
        jurisdiction=jurisdiction,
        sector=sector,
        client_type=client_type,
        domain=domain,
        primary_domains=primary_domains,
        secondary_domains=secondary_domains,
        subdomain=subdomain,
        regulatory_frame=regulatory_frame,
        evaluator_pattern=evaluator_pattern,
        proof_types_needed=proof_types_needed,
        language=language,
        confidence=confidence,
        alternate_classifications=alternate_classifications,
    )

    logger.info(
        "RFP classified: jurisdiction=%s, sector=%s, domain=%s, "
        "client_type=%s, confidence=%.2f",
        jurisdiction, sector, domain, client_type, confidence,
    )

    return classification


def select_packs(classification: RFPClassification) -> tuple[list[str], list[str]]:
    """Select context packs based on RFP classification.

    Returns:
        Tuple of (selected_pack_ids, fallback_pack_ids).
    """
    selected: list[str] = []
    fallbacks: list[str] = []

    # 1. Jurisdiction pack
    jur_map = _JURISDICTION_PACK_MAP.get(classification.jurisdiction, {})
    jur_pack = jur_map.get(classification.sector)

    if jur_pack:
        selected.append(jur_pack)
    else:
        # Use generic fallback
        fb = _FALLBACK_PACK_MAP.get(classification.sector, "generic_international")
        fallbacks.append(fb)
        logger.warning(
            "No jurisdiction pack for %s/%s — using fallback: %s",
            classification.jurisdiction, classification.sector, fb,
        )

    # 2. Domain packs — multi-label selection (Slice 1.2).
    # Include every primary and secondary domain pack that exists.
    domain_candidates: list[str] = list(classification.primary_domains) + list(
        classification.secondary_domains
    )
    if not domain_candidates and classification.domain:
        domain_candidates = [classification.domain]
    for dom in domain_candidates:
        if dom in _PACK_FILES and dom not in selected:
            selected.append(dom)

    # 3. Client-type pack (B.2)
    if classification.client_type:
        ct_pack = _CLIENT_TYPE_PACK_MAP.get(classification.client_type)
        if ct_pack and ct_pack in _PACK_FILES:
            selected.append(ct_pack)

    return selected, fallbacks


def merge_packs(
    selected_ids: list[str],
    fallback_ids: list[str],
) -> dict:
    """Load and merge selected packs into a single context dict.

    Merge precedence (B.6):
    - regulatory_references: jurisdiction pack refs override generic ones (by name)
    - methodology_patterns: domain pack patterns take precedence (by framework)
    - forbidden_assumptions: always cumulative (all apply)
    - evaluator_insights, compliance_patterns, benchmark_references: cumulative
    - search queries: cumulative, deduplicated

    Returns a dict with merged pack content for injection into prompts.
    """
    all_ids = selected_ids + fallback_ids
    packs: list[ContextPack] = []
    for pid in all_ids:
        pack = _load_pack(pid)
        if pack:
            packs.append(pack)
        else:
            logger.warning("Could not load pack: %s", pid)

    # Categorize packs by type for precedence logic
    jurisdiction_packs = [p for p in packs if p.pack_type == "jurisdiction"]
    domain_packs = [p for p in packs if p.pack_type == "domain"]
    fallback_packs = [p for p in packs if p.pack_type == "generic_fallback"]
    client_type_packs = [p for p in packs if p.pack_type == "client_type"]

    # B.6: Merge regulatory_references with jurisdiction override
    # Jurisdiction refs override generic/fallback refs with the same name
    reg_refs_by_name: dict[str, dict] = {}
    # First, add fallback refs (lowest precedence)
    for pack in fallback_packs:
        for r in pack.regulatory_references:
            reg_refs_by_name[r.name] = r.model_dump(mode="json")
    # Then client-type refs
    for pack in client_type_packs:
        for r in pack.regulatory_references:
            reg_refs_by_name[r.name] = r.model_dump(mode="json")
    # Then domain refs
    for pack in domain_packs:
        for r in pack.regulatory_references:
            reg_refs_by_name[r.name] = r.model_dump(mode="json")
    # Finally, jurisdiction refs (highest precedence — override by name)
    for pack in jurisdiction_packs:
        for r in pack.regulatory_references:
            reg_refs_by_name[r.name] = r.model_dump(mode="json")

    # B.6: Merge methodology_patterns with domain precedence
    # Domain patterns override generic/fallback patterns with the same framework
    method_by_framework: dict[str, dict] = {}
    # First, fallback patterns (lowest)
    for pack in fallback_packs:
        for m in pack.methodology_patterns:
            method_by_framework[m.framework] = m.model_dump(mode="json")
    # Then client-type
    for pack in client_type_packs:
        for m in pack.methodology_patterns:
            method_by_framework[m.framework] = m.model_dump(mode="json")
    # Then jurisdiction
    for pack in jurisdiction_packs:
        for m in pack.methodology_patterns:
            method_by_framework[m.framework] = m.model_dump(mode="json")
    # Finally, domain patterns (highest precedence — override by framework)
    for pack in domain_packs:
        for m in pack.methodology_patterns:
            method_by_framework[m.framework] = m.model_dump(mode="json")

    # Cumulative fields: compliance_patterns, evaluator_insights,
    # benchmark_references, forbidden_assumptions, search queries
    all_compliance: list[dict] = []
    all_evaluator: list[dict] = []
    all_benchmarks: list[dict] = []
    all_search: list[str] = []
    all_s2: list[str] = []
    all_forbidden: list[str] = []
    all_terminology: dict[str, str] = {}

    for pack in packs:
        all_compliance.extend(
            [c.model_dump(mode="json") for c in pack.compliance_patterns]
        )
        all_evaluator.extend(
            [e.model_dump(mode="json") for e in pack.evaluator_insights]
        )
        all_benchmarks.extend(
            [b.model_dump(mode="json") for b in pack.benchmark_references]
        )
        all_search.extend(pack.recommended_search_queries)
        all_s2.extend(pack.recommended_s2_queries)
        # Forbidden assumptions are CUMULATIVE (B.6)
        all_forbidden.extend(pack.forbidden_assumptions)
        # Terminology: later packs override earlier
        all_terminology.update(pack.local_terminology)

    # Deduplicate search queries while preserving order
    seen_search: set[str] = set()
    deduped_search: list[str] = []
    for q in all_search:
        if q not in seen_search:
            seen_search.add(q)
            deduped_search.append(q)

    seen_s2: set[str] = set()
    deduped_s2: list[str] = []
    for q in all_s2:
        if q not in seen_s2:
            seen_s2.add(q)
            deduped_s2.append(q)

    merged = {
        "active_packs": [p.pack_id for p in packs],
        "regulatory_references": list(reg_refs_by_name.values()),
        "compliance_patterns": all_compliance,
        "evaluator_insights": all_evaluator,
        "methodology_patterns": list(method_by_framework.values()),
        "benchmark_references": all_benchmarks,
        "recommended_search_queries": deduped_search,
        "recommended_s2_queries": deduped_s2,
        "forbidden_assumptions": all_forbidden,
        "local_terminology": all_terminology,
    }

    logger.info(
        "Merged %d packs: %d regulatory refs, %d compliance patterns, "
        "%d evaluator insights, %d methodology patterns, %d benchmarks, "
        "%d search queries, %d forbidden assumptions",
        len(packs),
        len(merged["regulatory_references"]),
        len(merged["compliance_patterns"]),
        len(merged["evaluator_insights"]),
        len(merged["methodology_patterns"]),
        len(merged["benchmark_references"]),
        len(merged["recommended_search_queries"]),
        len(merged["forbidden_assumptions"]),
    )

    return merged


def route_rfp(state: DeckForgeState) -> tuple[RoutingReport, dict]:
    """Full routing pipeline: classify → select → merge → report.

    Returns:
        Tuple of (RoutingReport, merged_pack_context).
    """
    # Classify
    classification = classify_rfp(state)

    # Select packs
    selected, fallbacks = select_packs(classification)

    # Merge
    merged = merge_packs(selected, fallbacks)

    # Build warnings
    warnings: list[str] = []
    if classification.confidence < 0.7:
        warnings.append(
            f"Low routing confidence ({classification.confidence:.2f}). "
            f"Jurisdiction-specific compliance requires manual review."
        )
    if fallbacks:
        warnings.append(
            f"Using fallback packs: {fallbacks}. No dedicated jurisdiction pack available."
        )

    # Build report
    report = RoutingReport(
        classification=classification,
        selected_packs=selected,
        fallback_packs_used=fallbacks,
        merged_regulatory_refs=len(merged["regulatory_references"]),
        merged_compliance_patterns=len(merged["compliance_patterns"]),
        merged_evaluator_insights=len(merged["evaluator_insights"]),
        merged_methodology_patterns=len(merged["methodology_patterns"]),
        merged_benchmark_refs=len(merged["benchmark_references"]),
        merged_search_queries=len(merged["recommended_search_queries"]),
        warnings=warnings,
        routing_confidence=classification.confidence,
    )

    logger.info(
        "Routing complete: packs=%s, fallbacks=%s, confidence=%.2f, warnings=%d",
        selected, fallbacks, classification.confidence, len(warnings),
    )

    return report, merged
