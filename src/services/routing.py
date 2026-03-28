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

# Jurisdiction keywords for rule-based classification
_JURISDICTION_KEYWORDS: dict[str, list[str]] = {
    "saudi_arabia": [
        "المملكة العربية السعودية", "السعودية", "الرياض", "جدة", "الدمام",
        "saudi", "riyadh", "jeddah", "ksa",
        "رؤية 2030", "vision 2030",
        "وزارة", "هيئة", "مؤسسة",  # ministry/authority/institution
    ],
    "qatar": [
        "قطر", "الدوحة", "qatar", "doha",
        "qnv 2030", "nds",
    ],
    "uae": [
        "الإمارات", "أبوظبي", "دبي", "uae", "abu dhabi", "dubai",
    ],
}

_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "public_sector": [
        "حكومي", "وزارة", "هيئة", "مؤسسة عامة", "government", "ministry",
        "authority", "public", "كراسة الشروط",
    ],
    "private_sector": [
        "شركة", "مؤسسة خاصة", "company", "private", "corporate",
        "enterprise", "مجموعة",
    ],
}

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "investment_promotion": [
        "استثمار", "توسع خارجي", "تصدير", "شركات وطنية",
        "investment", "export", "internationalization", "outbound",
        "trade promotion", "خدمات داعمة",
    ],
    "digital_transformation": [
        "تحول رقمي", "رقمنة", "digital", "cloud", "ai",
        "تقنية المعلومات", "it",
    ],
    "pmo_operating_model": [
        "مكتب إدارة المشاريع", "pmo", "operating model", "نموذج تشغيلي",
    ],
    "strategy_advisory": [
        "استراتيجي", "strategy", "advisory", "استشار",
    ],
    "service_design": [
        "تصميم خدمات", "service design", "خدمات", "محفظة خدمات",
        "service portfolio",
    ],
}

# Pack file mapping: pack_id → filename
_PACK_FILES: dict[str, str] = {
    "saudi_public_sector": "saudi_public_sector.json",
    "saudi_private_sector": "saudi_private_sector.json",
    "qatar_public_sector": "qatar_public_sector.json",
    "investment_promotion": "investment_promotion.json",
    "generic_mena_public_sector": "generic_mena_public_sector.json",
}

# Jurisdiction → pack_id mapping
_JURISDICTION_PACK_MAP: dict[str, dict[str, str]] = {
    "saudi_arabia": {
        "public_sector": "saudi_public_sector",
        "private_sector": "saudi_private_sector",
        "semi_government": "saudi_public_sector",
        "unknown": "saudi_public_sector",
    },
    "qatar": {
        "public_sector": "qatar_public_sector",
        "private_sector": "qatar_public_sector",  # fallback
        "unknown": "qatar_public_sector",
    },
}

# Generic fallbacks when no jurisdiction pack exists
_FALLBACK_PACK_MAP: dict[str, str] = {
    "public_sector": "generic_mena_public_sector",
    "private_sector": "generic_mena_public_sector",
    "unknown": "generic_mena_public_sector",
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
    for jur, keywords in _JURISDICTION_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in search_text)
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

    # Classify domain
    domain = ""
    domain_score = 0.0
    for dom, keywords in _DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in search_text)
        if hits > domain_score:
            domain = dom
            domain_score = hits

    # Determine client type
    client_type = ""
    if "هيئة" in search_text or "authority" in search_text:
        client_type = "authority"
    elif "وزارة" in search_text or "ministry" in search_text:
        client_type = "ministry"
    elif "شركة" in search_text or "company" in search_text:
        client_type = "private_enterprise"

    # Detect regulatory frame
    regulatory_frame = "none_identified"
    if "رؤية 2030" in search_text or "vision 2030" in search_text:
        regulatory_frame = "vision_2030"
    elif "qnv 2030" in search_text or "nds 2030" in search_text:
        regulatory_frame = "nds_2030"

    # Detect language
    arabic_chars = sum(1 for c in search_text if "\u0600" <= c <= "\u06ff")
    language = "ar" if arabic_chars > len(search_text) * 0.3 else "en"

    # Compute confidence
    confidence = min(
        (jurisdiction_score + sector_score + domain_score) / 10.0,
        1.0,
    )

    classification = RFPClassification(
        jurisdiction=jurisdiction,
        sector=sector,
        client_type=client_type,
        domain=domain,
        regulatory_frame=regulatory_frame,
        language=language,
        confidence=confidence,
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
        fb = _FALLBACK_PACK_MAP.get(classification.sector, "generic_mena_public_sector")
        fallbacks.append(fb)
        logger.warning(
            "No jurisdiction pack for %s/%s — using fallback: %s",
            classification.jurisdiction, classification.sector, fb,
        )

    # 2. Domain pack
    if classification.domain and classification.domain in _PACK_FILES:
        selected.append(classification.domain)

    return selected, fallbacks


def merge_packs(
    selected_ids: list[str],
    fallback_ids: list[str],
) -> dict:
    """Load and merge selected packs into a single context dict.

    Merge precedence: CORE → jurisdiction → client-type → domain → fallback.
    Forbidden assumptions are cumulative (all apply).

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

    # Merge all pack content
    merged = {
        "active_packs": [p.pack_id for p in packs],
        "regulatory_references": [],
        "compliance_patterns": [],
        "evaluator_insights": [],
        "methodology_patterns": [],
        "benchmark_references": [],
        "recommended_search_queries": [],
        "recommended_s2_queries": [],
        "forbidden_assumptions": [],
        "local_terminology": {},
    }

    for pack in packs:
        merged["regulatory_references"].extend(
            [r.model_dump(mode="json") for r in pack.regulatory_references]
        )
        merged["compliance_patterns"].extend(
            [c.model_dump(mode="json") for c in pack.compliance_patterns]
        )
        merged["evaluator_insights"].extend(
            [e.model_dump(mode="json") for e in pack.evaluator_insights]
        )
        merged["methodology_patterns"].extend(
            [m.model_dump(mode="json") for m in pack.methodology_patterns]
        )
        merged["benchmark_references"].extend(
            [b.model_dump(mode="json") for b in pack.benchmark_references]
        )
        merged["recommended_search_queries"].extend(pack.recommended_search_queries)
        merged["recommended_s2_queries"].extend(pack.recommended_s2_queries)
        # Forbidden assumptions are CUMULATIVE
        merged["forbidden_assumptions"].extend(pack.forbidden_assumptions)
        # Terminology: later packs override earlier
        merged["local_terminology"].update(pack.local_terminology)

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
