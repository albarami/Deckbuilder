"""Context Agent — parses RFP input into structured RFPContext."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.rfp import RFPContext
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


def _is_schema_drift_error(error: LLMError) -> bool:
    """Return True when the LLM returned near-valid JSON with schema drift."""
    message = str(error.last_error).lower()
    return "structured output validation failed" in message


async def run(state: DeckForgeState) -> DeckForgeState:
    """Context Agent — parse RFP summary into structured RFPContext."""
    user_message = json.dumps({
        "ai_assist_summary": state.ai_assist_summary,
        "uploaded_documents": [
            {"filename": d.filename, "content_text": d.content_text, "language": d.language}
            for d in state.uploaded_documents
        ],
        "user_notes": state.user_notes or None,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["context_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=RFPContext,
        )
        state.rfp_context = result.parsed
        state.current_stage = PipelineStage.CONTEXT_REVIEW
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
        state.session.total_cost_usd += result.cost_usd
    except LLMError as e:
        if _is_schema_drift_error(e):
            try:
                retry_result = await call_llm(
                    model=MODEL_MAP["context_agent"],
                    system_prompt=SYSTEM_PROMPT,
                    user_message=user_message,
                    response_model=RFPContext,
                )
                state.rfp_context = retry_result.parsed
                state.current_stage = PipelineStage.CONTEXT_REVIEW
                state.session.total_input_tokens += retry_result.input_tokens
                state.session.total_output_tokens += retry_result.output_tokens
                state.session.total_llm_calls += 1
                state.session.total_cost_usd += retry_result.cost_usd
                return state
            except LLMError as retry_error:
                e = retry_error

        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="context_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
