"""Analysis Agent — deep extraction from source documents into Reference Index."""

import json
import logging

from src.config.models import MODEL_MAP
from src.models.claims import ReferenceIndex
from src.models.enums import PipelineStage
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _is_request_too_large_error(error: Exception) -> bool:
    """Return True when the provider rejected the request for size."""
    if isinstance(error, LLMError):
        error = error.last_error
    message = str(error).lower()
    return "request_too_large" in message or "request exceeds the maximum size" in message


def _record_analysis_error(
    state: DeckForgeState,
    error: Exception,
    *,
    fallback_attempted: bool = False,
) -> None:
    """Persist analysis-agent failures on state instead of crashing the graph."""
    attempts = error.attempts if isinstance(error, LLMError) else 1
    error_type = type(error.last_error).__name__ if isinstance(error, LLMError) else type(error).__name__

    state.current_stage = PipelineStage.ERROR
    state.errors.append(ErrorInfo(
        agent="analysis_agent",
        error_type=error_type,
        message=str(error),
        retries_attempted=attempts + (1 if fallback_attempted else 0),
    ))
    state.last_error = state.errors[-1]


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

    MAX_CHARS_PER_DOC = 50_000
    MAX_DOCS = 10
    compact_sources = [
        {
            "doc_id": source.get("doc_id"),
            "title": source.get("title"),
            "content_text": str(source.get("content_text", ""))[:MAX_CHARS_PER_DOC],
        }
        for source in approved_sources[:MAX_DOCS]
    ]

    user_message = json.dumps({
        "approved_sources": compact_sources,
        "rfp_context": rfp_dump,
        "evaluation_criteria": evaluation_criteria,
    })
    logger.warning(
        "Analysis payload size: chars=%s docs=%s",
        len(user_message),
        len(approved_sources),
    )

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
    except Exception as error:  # noqa: BLE001
        if _is_request_too_large_error(error):
            logger.warning("Analysis Agent Opus request too large; retrying with GPT-5.4 fallback")
            try:
                fallback_result = await call_llm(
                    model=MODEL_MAP["context_agent"],
                    system_prompt=SYSTEM_PROMPT,
                    user_message=user_message,
                    response_model=ReferenceIndex,
                )
                state.reference_index = fallback_result.parsed
                state.current_stage = PipelineStage.ANALYSIS
                state.session.total_input_tokens += fallback_result.input_tokens
                state.session.total_output_tokens += fallback_result.output_tokens
                state.session.total_llm_calls += 1
                return state
            except Exception as fallback_error:  # noqa: BLE001
                _record_analysis_error(state, fallback_error, fallback_attempted=True)
                return state

        _record_analysis_error(state, error)

    return state
