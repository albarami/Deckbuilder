"""Refine Agent — Turn 3: Opus rewrites weak slides using critique."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.iterative import DeckDraft
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


async def run(state: DeckForgeState) -> DeckForgeState:
    """Refine Agent — Turn 3 of 5-turn iterative slide builder.

    Reads the original DeckDraft and DeckReview critique, produces
    an improved DeckDraft with turn_number=3.
    """
    latest_draft = state.deck_drafts[-1] if state.deck_drafts else {}
    latest_review = state.deck_reviews[-1] if state.deck_reviews else {}

    user_data = {
        "draft": latest_draft,
        "review": latest_review,
        "rfp_context": state.rfp_context.model_dump(mode="json") if state.rfp_context else None,
        "approved_report": state.report_markdown,
        "evidence_mode": state.evidence_mode,
    }

    user_message = json.dumps(user_data, ensure_ascii=False)

    try:
        result = await call_llm(
            model=MODEL_MAP["research_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=DeckDraft,
            max_tokens=16000,
        )
        state.deck_drafts.append(result.parsed.model_dump(mode="json"))
        state.current_stage = PipelineStage.SLIDE_BUILDING
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="refine_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
