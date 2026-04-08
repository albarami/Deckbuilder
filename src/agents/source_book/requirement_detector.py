"""Requirement-density detection for dynamic Section 1 structure.

Analyzes RFP context to classify requirement density as high/medium/low.
High-density RFPs (many prescriptive requirements, explicit deliverables,
detailed evaluation criteria) trigger:
- Compliance matrix generation (Section 1)
- Delivery-control matrix generation (Section 1)
- Ambiguity table generation (Section 1)

This is a pre-generation pass: density score is injected into the shared
context so prompts can adapt their output structure dynamically.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from src.models.state import DeckForgeState

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Density signal patterns
# ──────────────────────────────────────────────────────────────

_PRESCRIPTIVE_MARKERS_EN = [
    r"\bmust\b", r"\bshall\b", r"\brequired\s+to\b", r"\bmandatory\b",
    r"\bobligation\b", r"\bconform\s+to\b", r"\bcomply\s+with\b",
    r"\bminimum\s+\d+", r"\bat\s+least\s+\d+", r"\bno\s+fewer\s+than\b",
    r"\bsubmit\s+within\b", r"\bdeadline\b", r"\bpenalty\b",
    r"\bliquidated\s+damages\b", r"\bservice\s+level\b", r"\bSLA\b",
    r"\bKPI\b", r"\bperformance\s+metric\b",
]

_PRESCRIPTIVE_MARKERS_AR = [
    r"يجب", r"يلزم", r"إلزامي", r"الحد\s+الأدنى", r"لا\s+يقل\s+عن",
    r"موعد\s+نهائي", r"غرامة", r"مستوى\s+خدمة", r"مؤشر\s+أداء",
    r"شرط\s+أساسي", r"متطلب\s+إلزامي", r"وفقاً\s+لـ",
    r"الالتزام\s+بـ", r"ضمان\s+مالي",
]

_DELIVERABLE_MARKERS = [
    r"\bdeliverable\b", r"\bmilestone\b", r"\bphase\s+\d+\b",
    r"\btask\s+\d+\b", r"\bwork\s*package\b", r"\bSOW\b",
    r"تسليم", r"مرحلة\s+\d+", r"مهمة\s+\d+", r"حزمة\s+عمل",
]

_EVALUATION_MARKERS = [
    r"\bscoring\b", r"\bweight\b", r"\b\d+\s*%\s*(technical|financial)\b",
    r"\bevaluation\s+criteria?\b", r"\bselection\s+criteria?\b",
    r"معيار\s+تقييم", r"معايير\s+الاختيار", r"وزن\s+\d+",
    r"درجة\s+فنية", r"درجة\s+مالية",
]

_COMPILED_PRESCRIPTIVE = [
    re.compile(p, re.IGNORECASE)
    for p in _PRESCRIPTIVE_MARKERS_EN + _PRESCRIPTIVE_MARKERS_AR
]
_COMPILED_DELIVERABLES = [re.compile(p, re.IGNORECASE) for p in _DELIVERABLE_MARKERS]
_COMPILED_EVALUATION = [re.compile(p, re.IGNORECASE) for p in _EVALUATION_MARKERS]


@dataclass
class DensityAnalysis:
    """Result of requirement-density analysis."""

    density: Literal["high", "medium", "low"]
    prescriptive_count: int
    deliverable_count: int
    evaluation_count: int
    compliance_items_found: int
    should_generate_compliance_matrix: bool
    should_generate_delivery_matrix: bool
    should_generate_ambiguity_table: bool
    signals: list[str]


def _count_matches(text: str, patterns: list[re.Pattern[str]]) -> int:
    """Count total matches across all patterns in text."""
    return sum(len(p.findall(text)) for p in patterns)


def _extract_rfp_text(state: DeckForgeState) -> str:
    """Extract all available RFP text for density analysis."""
    parts: list[str] = []

    if state.rfp_context:
        rfp = state.rfp_context
        if rfp.project_title:
            title = rfp.project_title
            parts.append(title.en if hasattr(title, "en") and title.en else str(title))
        if rfp.scope_items:
            for item in rfp.scope_items:
                parts.append(getattr(item, "description", str(item)))
        if rfp.compliance_requirements:
            for cr in rfp.compliance_requirements:
                parts.append(getattr(cr, "requirement_text", str(cr)))
        if rfp.evaluation_criteria:
            for ec in rfp.evaluation_criteria:
                desc = getattr(ec, "description", "")
                parts.append(f"{desc} weight={getattr(ec, 'weight', '')}")
        if rfp.deliverables:
            for d in rfp.deliverables:
                parts.append(getattr(d, "description", str(d)))

    return "\n".join(parts)


def detect_requirement_density(state: DeckForgeState) -> DensityAnalysis:
    """Analyze RFP context and classify requirement density.

    Args:
        state: Current pipeline state with rfp_context populated.

    Returns:
        DensityAnalysis with density level and generation recommendations.
    """
    rfp_text = _extract_rfp_text(state)
    if not rfp_text:
        return DensityAnalysis(
            density="low",
            prescriptive_count=0,
            deliverable_count=0,
            evaluation_count=0,
            compliance_items_found=0,
            should_generate_compliance_matrix=False,
            should_generate_delivery_matrix=False,
            should_generate_ambiguity_table=False,
            signals=["No RFP text available for density analysis"],
        )

    prescriptive = _count_matches(rfp_text, _COMPILED_PRESCRIPTIVE)
    deliverables = _count_matches(rfp_text, _COMPILED_DELIVERABLES)
    evaluation = _count_matches(rfp_text, _COMPILED_EVALUATION)

    compliance_count = 0
    if state.rfp_context and state.rfp_context.compliance_requirements:
        compliance_count = len(state.rfp_context.compliance_requirements)

    signals: list[str] = []
    score = 0

    if prescriptive >= 15:
        score += 3
        signals.append(f"High prescriptive language: {prescriptive} markers")
    elif prescriptive >= 8:
        score += 2
        signals.append(f"Moderate prescriptive language: {prescriptive} markers")
    elif prescriptive >= 3:
        score += 1
        signals.append(f"Low prescriptive language: {prescriptive} markers")

    if deliverables >= 8:
        score += 2
        signals.append(f"Rich deliverable structure: {deliverables} markers")
    elif deliverables >= 4:
        score += 1
        signals.append(f"Moderate deliverable structure: {deliverables} markers")

    if evaluation >= 5:
        score += 2
        signals.append(f"Detailed evaluation criteria: {evaluation} markers")
    elif evaluation >= 2:
        score += 1
        signals.append(f"Some evaluation criteria: {evaluation} markers")

    if compliance_count >= 5:
        score += 2
        signals.append(f"Explicit compliance requirements: {compliance_count}")
    elif compliance_count >= 2:
        score += 1
        signals.append(f"Some compliance requirements: {compliance_count}")

    # Classify density
    if score >= 6:
        density: Literal["high", "medium", "low"] = "high"
    elif score >= 3:
        density = "medium"
    else:
        density = "low"

    analysis = DensityAnalysis(
        density=density,
        prescriptive_count=prescriptive,
        deliverable_count=deliverables,
        evaluation_count=evaluation,
        compliance_items_found=compliance_count,
        should_generate_compliance_matrix=density in ("high", "medium") and compliance_count >= 2,
        should_generate_delivery_matrix=density == "high" and deliverables >= 6,
        should_generate_ambiguity_table=density in ("high", "medium"),
        signals=signals,
    )

    logger.info(
        "Requirement density: %s (score=%d, prescriptive=%d, "
        "deliverables=%d, evaluation=%d, compliance=%d)",
        density, score, prescriptive, deliverables, evaluation, compliance_count,
    )

    return analysis
