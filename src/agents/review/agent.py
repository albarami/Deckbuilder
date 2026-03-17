"""Review Agent — Turn 2: GPT critiques each slide 1-5, flags issues."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.iterative import DeckReview
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, LLMResponse, call_llm

from .prompts import GENERAL_PROMPT, STRICT_PROMPT

REVIEW_INITIAL_MAX_TOKENS = 4000
REVIEW_RETRY_MAX_TOKENS = 12000


def _is_length_limited_error(error: LLMError) -> bool:
    """Return True when the review response hit the token ceiling."""
    message = str(error.last_error).lower()
    return "finish reason: length" in message or "finish_reason: length" in message


def _apply_review_result(
    state: DeckForgeState,
    result: LLMResponse[DeckReview],
) -> DeckForgeState:
    """Persist a successful review result onto the shared pipeline state."""
    state.deck_reviews.append(result.parsed.model_dump(mode="json"))
    state.current_stage = PipelineStage.SLIDE_BUILDING
    state.session.total_input_tokens += result.input_tokens
    state.session.total_output_tokens += result.output_tokens
    state.session.total_llm_calls += 1
    return state


async def run(state: DeckForgeState) -> DeckForgeState:
    """Review Agent — Turn 2 of 5-turn iterative slide builder.

    Reads the latest DeckDraft from state.deck_drafts and produces
    a DeckReview with per-slide critiques.
    """
    is_general = state.evidence_mode == "general"
    system_prompt = GENERAL_PROMPT if is_general else STRICT_PROMPT

    # Get latest draft
    latest_draft = state.deck_drafts[-1] if state.deck_drafts else {}

    user_data = {
        "draft": latest_draft,
        "rfp_context": state.rfp_context.model_dump(mode="json") if state.rfp_context else None,
        "approved_report": state.report_markdown,
        "evidence_mode": state.evidence_mode,
    }

    user_message = json.dumps(user_data, ensure_ascii=False)

    try:
        result = await call_llm(
            model=MODEL_MAP["qa_agent"],
            system_prompt=system_prompt,
            user_message=user_message,
            response_model=DeckReview,
            max_tokens=REVIEW_INITIAL_MAX_TOKENS,
        )
        return _apply_review_result(state, result)
    except LLMError as e:
        if _is_length_limited_error(e):
            try:
                retry_result = await call_llm(
                    model=MODEL_MAP["qa_agent"],
                    system_prompt=system_prompt,
                    user_message=user_message,
                    response_model=DeckReview,
                    max_tokens=REVIEW_RETRY_MAX_TOKENS,
                )
                return _apply_review_result(state, retry_result)
            except LLMError as retry_error:
                e = retry_error

        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="review_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
