"""Retrieval Planner — generates search queries from RFP context."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.retrieval import RetrievalQueries
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import PLANNER_SYSTEM_PROMPT


async def run(state: DeckForgeState) -> DeckForgeState:
    """Retrieval Planner — generate search queries for the RFP.

    Reads state.rfp_context and state.output_language, calls the LLM to
    produce RetrievalQueries.  The parsed queries are transient — they are
    not stored in DeckForgeState.  The pipeline orchestrator (LangGraph)
    will consume them when chaining planner → search → ranker.
    """
    user_message = json.dumps({
        "rfp_context": state.rfp_context.model_dump() if state.rfp_context else None,
        "output_language": state.output_language,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["retrieval_planner"],
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_message=user_message,
            response_model=RetrievalQueries,
        )
        # Planner output is transient per design doc — pipeline node
        # chains planner → search → ranker.  Token accounting only.
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="retrieval_planner",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
