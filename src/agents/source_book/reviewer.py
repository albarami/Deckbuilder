"""Source Book Reviewer agent — evaluates Source Book quality.

Red-team critique of the Source Book with per-section scoring,
unsupported claim detection, and fluff identification.
"""

from __future__ import annotations

import json
import logging

from src.config.models import MODEL_MAP
from src.models.source_book import SourceBookReview
from src.models.state import DeckForgeState
from src.services.llm import call_llm

from .prompts import REVIEWER_SYSTEM_PROMPT as SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _build_user_message(state: DeckForgeState) -> str:
    """Build the reviewer user message from Source Book and RFP context."""
    source_book_dump = None
    if state.source_book:
        source_book_dump = state.source_book.model_dump(mode="json")

    rfp_dump = None
    if state.rfp_context:
        rfp_dump = state.rfp_context.model_dump(mode="json")

    # Include reference_index for evidence verification
    ref_index_summary = None
    if state.reference_index:
        ref_index_summary = {
            "total_claims": len(state.reference_index.claims),
            "claim_ids": [c.claim_id for c in state.reference_index.claims[:200]],
        }

    payload = {
        "source_book": source_book_dump,
        "rfp_context": rfp_dump,
        "reference_index_summary": ref_index_summary,
    }

    return json.dumps(payload, ensure_ascii=False, default=str)


async def run(state: DeckForgeState) -> dict:
    """Run the Source Book Reviewer agent.

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

        # Update session accounting
        session = state.session.model_copy(deep=True)
        session.total_llm_calls += 1
        session.total_input_tokens += llm_result.input_tokens
        session.total_output_tokens += llm_result.output_tokens

        return {
            "source_book_review": review,
            "session": session,
        }

    except Exception as e:
        logger.error("Source Book Reviewer failed: %s", e)
        # Return a failing review to prevent silent pass-through
        return {
            "source_book_review": SourceBookReview(
                overall_score=1,
                competitive_viability="not_competitive",
                pass_threshold_met=False,
                rewrite_required=False,  # Don't rewrite if reviewer itself failed
                coherence_issues=[f"Reviewer agent error: {e}"],
            ),
        }
