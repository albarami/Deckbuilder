"""Tests for the Context Agent — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
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


def _make_success_response() -> LLMResponse:
    """LLMResponse wrapping a valid RFPContext."""
    return LLMResponse(
        parsed=_make_sample_rfp_context(),
        input_tokens=150,
        output_tokens=80,
        model="gpt-5.4",
        latency_ms=500.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with ai_assist_summary populated for Context Agent input."""
    return DeckForgeState(
        ai_assist_summary="RFP Name: Renewal of Support for SAP Systems. Entity: SIDF.",
        user_notes="Focus on SAP HANA experience.",
    )


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_happy_path(mock_call_llm: AsyncMock) -> None:
    """Valid AI Assist summary produces an RFPContext in state."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run

    result = await run(state)

    assert result.rfp_context is not None
    assert result.rfp_context.rfp_name.en == "Renewal of Support for SAP Systems"
    assert result.current_stage == "context_review"


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_uses_model_map(mock_call_llm: AsyncMock) -> None:
    """Agent calls call_llm with MODEL_MAP['context_agent'], not a hardcoded string."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["context_agent"]


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_uses_system_prompt(mock_call_llm: AsyncMock) -> None:
    """Agent passes SYSTEM_PROMPT from prompts.py to call_llm."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith("You are the Context Agent")


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_retries_schema_drift_response(
    mock_call_llm: AsyncMock,
) -> None:
    """A structured-output schema drift retries once instead of failing immediately."""
    mock_call_llm.side_effect = [
        LLMError(
            model="gpt-5.4",
            attempts=1,
            last_error=ValueError(
                "Structured output validation failed: 1 validation error for RFPContext\n"
                "evaluation_criteria.financial.sub_items\n"
                "  Extra inputs are not permitted [type=extra_forbidden, input_value=[], input_type=list]"
            ),
        ),
        _make_success_response(),
    ]
    state = _make_input_state()

    from src.agents.context.agent import run

    result = await run(state)

    assert result.rfp_context is not None
    assert result.current_stage == "context_review"
    assert mock_call_llm.await_count == 2


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_handles_llm_error(mock_call_llm: AsyncMock) -> None:
    """LLMError is caught, state.errors populated, stage set to ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="gpt-5.4",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.context.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "context_agent"
    assert result.rfp_context is None


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_updates_token_counts(mock_call_llm: AsyncMock) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run

    result = await run(state)

    assert result.session.total_input_tokens == 150
    assert result.session.total_output_tokens == 80
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_builds_user_message(mock_call_llm: AsyncMock) -> None:
    """User message sent to LLM includes ai_assist_summary, uploaded_documents, and user_notes."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "ai_assist_summary" in user_msg
    assert "uploaded_documents" in user_msg
    assert "user_notes" in user_msg
    assert user_msg["ai_assist_summary"] == state.ai_assist_summary
