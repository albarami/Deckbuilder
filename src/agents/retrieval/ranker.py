"""Retrieval Ranker — ranks search results by relevance to the RFP."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.retrieval import RankedSourcesOutput
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import RANKER_SYSTEM_PROMPT


async def run(state: DeckForgeState, search_results: list[dict]) -> DeckForgeState:
    """Retrieval Ranker — rank search results against RFP criteria.

    Takes search_results as a parameter (not from state) because the search
    service provides them in-memory during the planner → search → ranker chain.
    Writes ranked sources to state.retrieved_sources for Gate 2 review.
    """
    user_message = json.dumps({
        "rfp_context": state.rfp_context.model_dump() if state.rfp_context else None,
        "search_results": search_results,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["retrieval_ranker"],
            system_prompt=RANKER_SYSTEM_PROMPT,
            user_message=user_message,
            response_model=RankedSourcesOutput,
        )
        state.retrieved_sources = list(result.parsed.ranked_sources)
        state.current_stage = PipelineStage.SOURCE_REVIEW
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
        state.session.total_cost_usd += result.cost_usd
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="retrieval_ranker",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
