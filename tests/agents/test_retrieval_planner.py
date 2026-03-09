"""Tests for the Retrieval Planner — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
from src.models.retrieval import RetrievalQueries, RetrievalSummary, SearchQuery
from src.models.rfp import RFPContext
from src.models.state import DeckForgeState
from src.services.llm import LLMError, LLMResponse


def _make_sample_rfp_context() -> RFPContext:
    """Minimal valid RFPContext for test fixtures."""
    return RFPContext(
        rfp_name=BilingualText(en="Renewal of Support for SAP Systems"),
        issuing_entity=BilingualText(en="Saudi Industrial Development Fund"),
        mandate=BilingualText(en="Renew and supply SAP licenses for 24 months."),
    )


def _make_sample_retrieval_queries() -> RetrievalQueries:
    """Sample RetrievalQueries result from LLM."""
    return RetrievalQueries(
        search_queries=[
            SearchQuery(
                query="SAP implementation case study",
                strategy="rfp_aligned",
                target_criterion="Technical > Previous Experience",
                language="en",
                priority="high",
            ),
            SearchQuery(
                query="SAP Gold partner certificate",
                strategy="capability_match",
                target_criterion="Compliance > SAP Gold Partnership",
                language="en",
                priority="critical",
            ),
        ],
        retrieval_summary=RetrievalSummary(
            total_queries=2,
            by_strategy={"rfp_aligned": 1, "capability_match": 1},
            highest_priority_criteria=["Previous Experience"],
        ),
    )


def _make_success_response() -> LLMResponse:
    """LLMResponse wrapping valid RetrievalQueries."""
    return LLMResponse(
        parsed=_make_sample_retrieval_queries(),
        input_tokens=200,
        output_tokens=120,
        model="gpt-5.4",
        latency_ms=600.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with rfp_context populated for Retrieval Planner input."""
    return DeckForgeState(
        rfp_context=_make_sample_rfp_context(),
        output_language="en",
    )


@pytest.mark.asyncio
@patch("src.agents.retrieval.planner.call_llm", new_callable=AsyncMock)
async def test_retrieval_planner_happy_path(mock_call_llm: AsyncMock) -> None:
    """Valid RFP context produces updated state with token counts."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.planner import run

    result = await run(state)

    assert result.current_stage != "error"
    assert result.session.total_llm_calls == 1
    mock_call_llm.assert_awaited_once()
    # Verify call_llm was called with RetrievalQueries as response_model
    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["response_model"] is RetrievalQueries


@pytest.mark.asyncio
@patch("src.agents.retrieval.planner.call_llm", new_callable=AsyncMock)
async def test_retrieval_planner_uses_model_map(mock_call_llm: AsyncMock) -> None:
    """Agent calls call_llm with MODEL_MAP['retrieval_planner'], not a hardcoded string."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.planner import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["retrieval_planner"]


@pytest.mark.asyncio
@patch("src.agents.retrieval.planner.call_llm", new_callable=AsyncMock)
async def test_retrieval_planner_uses_system_prompt(mock_call_llm: AsyncMock) -> None:
    """Agent passes PLANNER_SYSTEM_PROMPT from prompts.py to call_llm."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.planner import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith(
        "You are the Retrieval Query Planner"
    )


@pytest.mark.asyncio
@patch("src.agents.retrieval.planner.call_llm", new_callable=AsyncMock)
async def test_retrieval_planner_handles_llm_error(mock_call_llm: AsyncMock) -> None:
    """LLMError is caught, state.errors populated, stage set to ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="gpt-5.4",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.retrieval.planner import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "retrieval_planner"


@pytest.mark.asyncio
@patch("src.agents.retrieval.planner.call_llm", new_callable=AsyncMock)
async def test_retrieval_planner_updates_token_counts(mock_call_llm: AsyncMock) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.planner import run

    result = await run(state)

    assert result.session.total_input_tokens == 200
    assert result.session.total_output_tokens == 120
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.retrieval.planner.call_llm", new_callable=AsyncMock)
async def test_retrieval_planner_builds_user_message(mock_call_llm: AsyncMock) -> None:
    """User message sent to LLM includes rfp_context and output_language."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.planner import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "rfp_context" in user_msg
    assert "output_language" in user_msg
    assert user_msg["output_language"] == "en"
