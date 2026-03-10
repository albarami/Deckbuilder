"""5-turn iterative slide builder — replaces Structure + Content agents.

Orchestrates:
  Turn 1: Draft Agent    (Opus)  — drafts slide text from approved report
  Turn 2: Review Agent   (GPT)   — critiques each slide 1-5
  Turn 3: Refine Agent   (Opus)  — rewrites weak slides using critique
  Turn 4: Final Review   (GPT)   — second-pass review, coherence check
  Turn 5: Presentation   (Opus)  — builds final WrittenSlides with layouts
"""

import logging

from src.models.enums import PipelineStage
from src.models.iterative import DeckDraft
from src.models.state import DeckForgeState

logger = logging.getLogger(__name__)

# Minimum acceptable slide count from the Draft Agent
MIN_DRAFT_SLIDES = 15


def _detect_evidence_mode(state: DeckForgeState) -> str:
    """Determine evidence mode based on retrieved sources.

    Strict: >= 3 sources AND avg relevance >= 30
    General: otherwise
    """
    sources = state.retrieved_sources
    if not sources:
        return "general"

    included = [s for s in sources if s.recommendation == "include"]
    if len(included) < 3:
        return "general"

    avg_relevance = sum(s.relevance_score for s in included) / len(included)
    if avg_relevance < 30:
        return "general"

    return "strict"


def _get_draft_slide_count(state: DeckForgeState) -> int:
    """Count slides in the latest deck draft."""
    if not state.deck_drafts:
        return 0
    latest = state.deck_drafts[-1]
    draft = DeckDraft(**latest) if isinstance(latest, dict) else latest
    return len(draft.slides)


async def run_iterative_build(state: DeckForgeState) -> DeckForgeState:
    """5-turn iterative slide builder. Replaces Structure + Content agents.

    Each turn reads from and writes to the shared DeckForgeState.
    If any turn hits an LLMError, it sets state.current_stage = ERROR
    and we stop the build immediately (no partial deck).

    Includes a retry guard: if Turn 1 produces fewer than MIN_DRAFT_SLIDES,
    retries once with the same prompt. This handles the edge case where
    the LLM returns an empty or minimal draft (observed in general mode).
    """
    from src.agents.draft.agent import run as draft_run
    from src.agents.final_review.agent import run as final_review_run
    from src.agents.presentation.agent import run as presentation_run
    from src.agents.refine.agent import run as refine_run
    from src.agents.review.agent import run as review_run

    # Detect evidence mode
    state.evidence_mode = _detect_evidence_mode(state)
    logger.info("Evidence mode: %s", state.evidence_mode)

    # Turn 1: Draft (Opus) — with retry guard
    logger.info("Turn 1: Draft Agent (Opus)")
    state = await draft_run(state)
    if state.current_stage == PipelineStage.ERROR:
        return state

    slide_count = _get_draft_slide_count(state)
    if slide_count < MIN_DRAFT_SLIDES:
        logger.warning(
            "Draft produced only %d slides (minimum %d). Retrying...",
            slide_count, MIN_DRAFT_SLIDES,
        )
        # Clear the insufficient draft and retry
        if state.deck_drafts:
            state.deck_drafts.pop()
        state = await draft_run(state)
        if state.current_stage == PipelineStage.ERROR:
            return state

        retry_count = _get_draft_slide_count(state)
        if retry_count < MIN_DRAFT_SLIDES:
            logger.warning(
                "Draft retry produced %d slides (still below %d). Continuing with what we have.",
                retry_count, MIN_DRAFT_SLIDES,
            )

    # Turn 2: Review (GPT)
    logger.info("Turn 2: Review Agent (GPT)")
    state = await review_run(state)
    if state.current_stage == PipelineStage.ERROR:
        return state

    # Turn 3: Refine (Opus)
    logger.info("Turn 3: Refine Agent (Opus)")
    state = await refine_run(state)
    if state.current_stage == PipelineStage.ERROR:
        return state

    # Turn 4: Final Review (GPT)
    logger.info("Turn 4: Final Review Agent (GPT)")
    state = await final_review_run(state)
    if state.current_stage == PipelineStage.ERROR:
        return state

    # Turn 5: Presentation (Opus)
    logger.info("Turn 5: Presentation Agent (Opus)")
    state = await presentation_run(state)

    return state
