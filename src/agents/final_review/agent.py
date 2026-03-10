"""Final Review Agent — Turn 4: GPT second-pass review, coherence check."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.iterative import DeckReview
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


async def run(state: DeckForgeState) -> DeckForgeState:
    """Final Review Agent — Turn 4 of 5-turn iterative slide builder.

    Reads the refined DeckDraft (Turn 3) and previous DeckReview (Turn 2),
    produces a second-pass DeckReview with turn_number=4.
    """
    # Get refined draft (latest = Turn 3)
    refined_draft = state.deck_drafts[-1] if state.deck_drafts else {}
    # Get previous review (Turn 2)
    previous_review = state.deck_reviews[-1] if state.deck_reviews else {}

    user_data = {
        "refined_draft": refined_draft,
        "previous_review": previous_review,
        "rfp_context": state.rfp_context.model_dump(mode="json") if state.rfp_context else None,
        "approved_report": state.report_markdown,
        "evidence_mode": state.evidence_mode,
    }

    user_message = json.dumps(user_data, ensure_ascii=False)

    try:
        result = await call_llm(
            model=MODEL_MAP["qa_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=DeckReview,
            max_tokens=4000,
        )
        state.deck_reviews.append(result.parsed.model_dump(mode="json"))
        state.current_stage = PipelineStage.SLIDE_BUILDING
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="final_review_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
