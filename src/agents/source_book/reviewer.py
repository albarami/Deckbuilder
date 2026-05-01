"""Source Book Reviewer agent — evaluates Source Book quality.

Red-team critique of the Source Book with per-section scoring,
unsupported claim detection, and fluff identification.

Two review modes:
  - Full review: single LLM call for short Source Books within the
    safe output-token budget.
  - Sectioned review: reviews each section independently, then
    aggregates. Selected DIRECTLY for large Source Books — this is
    the primary path, not a fallback. The writer should never produce
    less content to satisfy the reviewer.

Safety net: if full review unexpectedly fails (finish_reason=length,
empty content, parse error), the system falls back to sectioned review.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from src.config.models import MODEL_MAP
from src.models.source_book import SectionCritique, SourceBookReview
from src.models.state import DeckForgeState
from src.services.llm import call_llm

from .prompts import REVIEWER_SYSTEM_PROMPT as SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Approximate char threshold above which full-review is likely to hit
# GPT-5.5 output limits. When exceeded, go straight to sectioned review.
_SECTIONED_REVIEW_THRESHOLD = 150_000


def _build_user_message(state: DeckForgeState) -> str:
    """Build the reviewer user message from Source Book and RFP context."""
    source_book_dump = None
    if state.source_book:
        source_book_dump = state.source_book.model_dump(mode="json")

    rfp_dump = None
    if state.rfp_context:
        rfp_dump = state.rfp_context.model_dump(mode="json")

    ref_index_summary = None
    if state.reference_index:
        ref_index_summary = {
            "total_claims": len(state.reference_index.claims),
            "claim_ids": [c.claim_id for c in state.reference_index.claims[:200]],
        }

    hard_requirements_summary = None
    if state.rfp_context and state.rfp_context.hard_requirements:
        hard_requirements_summary = [
            {
                "id": hr.requirement_id,
                "obligation": f"{hr.subject} {hr.operator} {hr.value_text} ({hr.unit})",
                "severity": hr.severity,
                "category": hr.category,
            }
            for hr in state.rfp_context.hard_requirements
            if hr.validation_scope == "source_book"
        ]

    conformance_report_summary = None
    if state.conformance_report:
        cr = state.conformance_report
        failures = (
            cr.missing_required_commitments
            + cr.forbidden_claims
            + cr.structural_mismatches
        )
        if failures:
            conformance_report_summary = {
                "status": cr.conformance_status,
                "failures": [
                    {
                        "requirement_id": f.requirement_id,
                        "failure_reason": f.failure_reason[:200],
                        "severity": f.severity,
                        "section": f.source_book_section,
                    }
                    for f in failures[:20]
                ],
                "checked": cr.hard_requirements_checked,
                "passed": cr.hard_requirements_passed,
                "failed": cr.hard_requirements_failed,
            }

    payload = {
        "source_book": source_book_dump,
        "rfp_context": rfp_dump,
        "reference_index_summary": ref_index_summary,
        "hard_requirements_summary": hard_requirements_summary,
        "conformance_report_summary": conformance_report_summary,
    }

    return json.dumps(payload, ensure_ascii=False, default=str)


# ── Section-by-section review ────────────────────────────────────


_SECTION_MAP = [
    ("Section 1 - RFP Interpretation", "rfp_interpretation"),
    ("Section 2 - Client Problem Framing", "client_problem_framing"),
    ("Section 3 - Why Strategic Gears", "why_strategic_gears"),
    ("Section 4 - External Evidence", "external_evidence"),
    ("Section 5 - Proposed Solution", "proposed_solution"),
    ("Section 6 - Slide Blueprint", "slide_blueprints"),
    ("Section 7 - Evidence Ledger", "evidence_ledger"),
]


def _build_section_payload(
    state: DeckForgeState,
    section_name: str,
    section_key: str,
) -> str:
    """Build a reviewer payload for one section only."""
    sb = state.source_book
    if sb is None:
        return "{}"

    section_data = None
    if section_key == "slide_blueprints":
        section_data = [bp.model_dump(mode="json") for bp in sb.slide_blueprints]
    else:
        section_obj = getattr(sb, section_key, None)
        if section_obj is not None:
            section_data = section_obj.model_dump(mode="json")

    # Compact RFP context (just name + scope for section-level review)
    rfp_summary = None
    if state.rfp_context:
        rfp_summary = {
            "rfp_name": state.rfp_context.rfp_name.model_dump(mode="json")
            if state.rfp_context.rfp_name else None,
            "scope_items_count": len(state.rfp_context.scope_items),
        }

    # Conformance failures for this section
    section_failures = []
    if state.conformance_report:
        for f in (
            state.conformance_report.missing_required_commitments
            + state.conformance_report.forbidden_claims
        ):
            if f.source_book_section and section_key in f.source_book_section:
                section_failures.append({
                    "requirement_id": f.requirement_id,
                    "failure_reason": f.failure_reason[:150],
                    "severity": f.severity,
                })

    payload = {
        "review_mode": "sectioned",
        "section_name": section_name,
        "section_data": section_data,
        "rfp_summary": rfp_summary,
        "section_conformance_failures": section_failures[:10],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


_SECTION_REVIEW_PROMPT = """You are reviewing ONE SECTION of a Proposal Source Book.

Review this section for:
1. Depth and accuracy of analysis
2. Evidence quality and citations
3. Compliance with RFP requirements
4. Unsupported claims or fluff
5. Actionable rewrite instructions if score < 4

Score 1-5:
5 = exceptional, proposal-winning depth
4 = solid, minor improvements possible
3 = adequate but needs strengthening
2 = weak, major gaps or unsupported claims
1 = poor, fundamental issues

If conformance failures are reported for this section, reflect them in your score.

Output a JSON SectionCritique with: section_id, score, issues, rewrite_instructions,
unsupported_claims, fluff_detected."""


async def _review_sectioned(state: DeckForgeState, model: str) -> tuple[SourceBookReview, dict | None]:
    """Review the Source Book section-by-section and aggregate.

    Returns (review, session_update) where session_update accumulates
    token/cost accounting from all section-level LLM calls.
    """
    from src.services.session_accounting import update_session_from_llm

    critiques: list[SectionCritique] = []
    coherence_issues: list[str] = []
    session = state.session

    for section_name, section_key in _SECTION_MAP:
        payload = _build_section_payload(state, section_name, section_key)
        if not payload or payload == "{}":
            continue

        try:
            result = await call_llm(
                model=model,
                system_prompt=_SECTION_REVIEW_PROMPT,
                user_message=payload,
                response_model=SectionCritique,
                max_tokens=3000,
            )
            critique = result.parsed
            if not critique.section_id:
                critique.section_id = section_name
            critiques.append(critique)

            # Accumulate session accounting for each section call
            session = update_session_from_llm(session, result)

            logger.info(
                "Sectioned review: %s → score=%d, issues=%d",
                section_name,
                critique.score,
                len(critique.issues),
            )
        except Exception as e:
            logger.warning("Sectioned review failed for %s: %s", section_name, e)
            critiques.append(SectionCritique(
                section_id=section_name,
                score=1,
                issues=[f"Review failed: {e}"],
            ))

    # Aggregate
    if not critiques:
        return (
            SourceBookReview(
                overall_score=1,
                competitive_viability="not_competitive",
                pass_threshold_met=False,
                coherence_issues=["No sections could be reviewed"],
            ),
            session,
        )

    scores = [c.score for c in critiques]
    min_score = min(scores)
    avg_score = sum(scores) / len(scores)

    # Overall score: weighted toward weakest sections (fail-closed)
    # If any section scores 1-2, overall cannot exceed 3
    if min_score <= 2:
        overall = min(3, round(avg_score))
    else:
        overall = round(avg_score)
    overall = max(1, min(5, overall))

    # Threshold: overall >= 4 AND no section < 3
    threshold_met = overall >= 4 and min_score >= 3

    # Viability
    if overall >= 4 and min_score >= 3:
        viability: Literal["strong", "adequate", "weak", "not_competitive"] = "adequate"
    elif overall >= 3:
        viability = "weak"
    else:
        viability = "not_competitive"

    return (
        SourceBookReview(
            section_critiques=critiques,
            overall_score=overall,
            coherence_issues=coherence_issues,
            competitive_viability=viability,
            pass_threshold_met=threshold_met,
            rewrite_required=not threshold_met,
        ),
        session,
    )


# ── Main entry point ─────────────────────────────────────────────


async def run(state: DeckForgeState) -> dict:
    """Run the Source Book Reviewer agent.

    Tries full-review first. If the payload exceeds the threshold or
    the full review fails (finish_reason=length, empty content, JSON
    parse error), automatically falls back to sectioned review.

    Returns a dict with the SourceBookReview and session update.
    """
    user_message = _build_user_message(state)

    logger.info(
        "Source Book Reviewer payload: chars=%d, pass=%d",
        len(user_message),
        state.source_book.pass_number if state.source_book else 0,
    )

    model = MODEL_MAP.get(
        "source_book_reviewer",
        MODEL_MAP.get("conversation_manager"),
    )

    # If payload is too large, skip full review and go straight to sectioned
    if len(user_message) > _SECTIONED_REVIEW_THRESHOLD:
        logger.info(
            "Selected sectioned review due to size (%d chars > %d threshold).",
            len(user_message),
            _SECTIONED_REVIEW_THRESHOLD,
        )
        review, session = await _review_sectioned(state, model)
        logger.info(
            "Sectioned review complete: overall=%d, viability=%s, threshold=%s",
            review.overall_score,
            review.competitive_viability,
            review.pass_threshold_met,
        )
        result = {"source_book_review": review}
        if session is not None:
            result["session"] = session
        return result

    # Try full review
    try:
        llm_result = await call_llm(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=SourceBookReview,
            max_tokens=6000,
        )

        review = llm_result.parsed

        logger.info(
            "Source Book review: overall=%d, viability=%s, "
            "threshold_met=%s, sections_critiqued=%d",
            review.overall_score,
            review.competitive_viability,
            review.pass_threshold_met,
            len(review.section_critiques),
        )

        if review.competitive_viability == "not_competitive":
            logger.warning(
                "CRITICAL: Source Book rated 'not_competitive' — "
                "proposal fundamentals may be weak"
            )

        from src.services.session_accounting import update_session_from_llm
        session = update_session_from_llm(state.session, llm_result)

        return {
            "source_book_review": review,
            "session": session,
        }

    except Exception as e:
        # Full review unexpectedly failed — safety-net fallback to sectioned
        logger.warning(
            "Full review unexpectedly failed (%s). Safety-net: switching to sectioned review.",
            e,
        )
        try:
            review, session = await _review_sectioned(state, model)
            logger.info(
                "Sectioned review (safety-net): overall=%d, viability=%s",
                review.overall_score,
                review.competitive_viability,
            )
            result = {"source_book_review": review}
            if session is not None:
                result["session"] = session
            return result
        except Exception as e2:
            logger.error("Sectioned review also failed: %s", e2)
            return {
                "source_book_review": SourceBookReview(
                    overall_score=1,
                    competitive_viability="not_competitive",
                    pass_threshold_met=False,
                    rewrite_required=False,
                    coherence_issues=[f"Reviewer agent error: {e}; sectioned fallback: {e2}"],
                ),
            }
