"""Analysis Agent — deep extraction from source documents into Reference Index."""

import json

from src.config.models import MODEL_MAP
from src.models.claims import ReferenceIndex
from src.models.enums import PipelineStage
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


async def run(state: DeckForgeState, approved_sources: list[dict]) -> DeckForgeState:
    """Analysis Agent — extract structured claims from approved source documents.

    Takes approved_sources as a parameter (not from state) because state only
    stores approved_source_ids.  The pipeline node loads full document content
    from storage using those IDs and passes it here.
    """
    rfp_dump = state.rfp_context.model_dump() if state.rfp_context else None
    evaluation_criteria = None
    if state.rfp_context and state.rfp_context.evaluation_criteria:
        evaluation_criteria = state.rfp_context.evaluation_criteria.model_dump()

    user_message = json.dumps({
        "approved_sources": approved_sources,
        "rfp_context": rfp_dump,
        "evaluation_criteria": evaluation_criteria,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["analysis_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=ReferenceIndex,
        )
        state.reference_index = result.parsed
        state.current_stage = PipelineStage.ANALYSIS
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="analysis_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
