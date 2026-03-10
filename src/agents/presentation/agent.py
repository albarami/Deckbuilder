"""Presentation Agent — Turn 5: Opus builds final WrittenSlides with layouts."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.slides import WrittenSlides
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


async def run(state: DeckForgeState) -> DeckForgeState:
    """Presentation Agent — Turn 5 of 5-turn iterative slide builder.

    Reads the refined DeckDraft (latest) and final DeckReview,
    produces the final WrittenSlides output with full SlideObject structures.
    """
    # Get refined draft (latest = Turn 3) and final review (Turn 4)
    refined_draft = state.deck_drafts[-1] if state.deck_drafts else {}
    final_review = state.deck_reviews[-1] if state.deck_reviews else {}

    user_data = {
        "refined_draft": refined_draft,
        "final_review": final_review,
        "rfp_context": state.rfp_context.model_dump(mode="json") if state.rfp_context else None,
        "approved_report": state.report_markdown,
        "evidence_mode": state.evidence_mode,
        "output_language": state.output_language,
    }

    user_message = json.dumps(user_data, ensure_ascii=False)

    try:
        result = await call_llm(
            model=MODEL_MAP["research_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=WrittenSlides,
            max_tokens=16000,
        )
        state.written_slides = result.parsed
        state.current_stage = PipelineStage.CONTENT_GENERATION
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="presentation_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
