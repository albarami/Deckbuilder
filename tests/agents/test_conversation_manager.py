"""Tests for the Conversation Manager — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.actions import (
    ConversationResponse,
    ExportAction,
    RewriteSlideAction,
)
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


def _make_rewrite_response() -> ConversationResponse:
    """ConversationResponse with a RewriteSlideAction."""
    return ConversationResponse(
        response_to_user=(
            "I'll rewrite slide 5 to make it more concise."
        ),
        action=RewriteSlideAction(
            target="S-005",
            scope="slide_only",
            instruction="compress to fewer bullets",
        ),
    )


def _make_export_response() -> ConversationResponse:
    """ConversationResponse with an ExportAction."""
    return ConversationResponse(
        response_to_user="Exporting your deck as PPTX now.",
        action=ExportAction(format="pptx"),
    )


def _make_success_response(
    response: ConversationResponse | None = None,
) -> LLMResponse:
    """LLMResponse wrapping ConversationResponse."""
    return LLMResponse(
        parsed=response or _make_rewrite_response(),
        input_tokens=3000,
        output_tokens=500,
        model="claude-sonnet-4-6",
        latency_ms=8000.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with minimal context for Conversation Manager."""
    return DeckForgeState(
        rfp_context=_make_sample_rfp_context(),
        report_markdown="# Sample Report\n\nContent here.",
        output_language="en",
        current_stage="deck_review",
    )


@pytest.mark.asyncio
@patch("src.agents.conversation.agent.call_llm", new_callable=AsyncMock)
async def test_conversation_happy_path(mock_call_llm: AsyncMock) -> None:
    """User message → state.last_action populated, conversation_history updated."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.conversation.agent import run

    result = await run(state, user_message="Fix slide 5")

    assert result.last_action is not None
    assert isinstance(result.last_action, ConversationResponse)
    assert result.session.total_llm_calls == 1
    # Conversation history should have user turn + assistant turn
    assert len(result.conversation_history) == 2
    assert result.conversation_history[0].role == "user"
    assert result.conversation_history[0].content == "Fix slide 5"
    assert result.conversation_history[1].role == "assistant"


@pytest.mark.asyncio
@patch("src.agents.conversation.agent.call_llm", new_callable=AsyncMock)
async def test_conversation_uses_model_map(
    mock_call_llm: AsyncMock,
) -> None:
    """Agent uses MODEL_MAP['conversation_manager'] — Claude Sonnet, not GPT."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.conversation.agent import run
    from src.config.models import MODEL_MAP

    await run(state, user_message="Fix slide 5")

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["conversation_manager"]
    assert "sonnet" in MODEL_MAP["conversation_manager"]


@pytest.mark.asyncio
@patch("src.agents.conversation.agent.call_llm", new_callable=AsyncMock)
async def test_conversation_uses_system_prompt(
    mock_call_llm: AsyncMock,
) -> None:
    """Agent passes SYSTEM_PROMPT starting with 'You are the Conversation Manager'."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.conversation.agent import run

    await run(state, user_message="Fix slide 5")

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith(
        "You are the Conversation Manager"
    )


@pytest.mark.asyncio
@patch("src.agents.conversation.agent.call_llm", new_callable=AsyncMock)
async def test_conversation_handles_llm_error(
    mock_call_llm: AsyncMock,
) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="claude-sonnet-4-6",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.conversation.agent import run

    result = await run(state, user_message="Fix slide 5")

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "conversation_manager"
    assert result.last_action is None


@pytest.mark.asyncio
@patch("src.agents.conversation.agent.call_llm", new_callable=AsyncMock)
async def test_conversation_updates_token_counts(
    mock_call_llm: AsyncMock,
) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.conversation.agent import run

    result = await run(state, user_message="Fix slide 5")

    assert result.session.total_input_tokens == 3000
    assert result.session.total_output_tokens == 500
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.conversation.agent.call_llm", new_callable=AsyncMock)
async def test_conversation_builds_user_message(
    mock_call_llm: AsyncMock,
) -> None:
    """User message JSON includes all expected fields."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.conversation.agent import run

    await run(state, user_message="Fix slide 5")

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "user_message" in user_msg
    assert "session_state" in user_msg
    assert "user_role" in user_msg
    assert "conversation_history" in user_msg
    assert user_msg["user_message"] == "Fix slide 5"
    assert isinstance(user_msg["session_state"], dict)
    assert user_msg["session_state"]["current_stage"] == "deck_review"


@pytest.mark.asyncio
@patch("src.agents.conversation.agent.call_llm", new_callable=AsyncMock)
async def test_conversation_returns_rewrite_action(
    mock_call_llm: AsyncMock,
) -> None:
    """Mock returns RewriteSlideAction — verify action type in state."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.conversation.agent import run

    result = await run(state, user_message="Fix slide 5")

    assert result.last_action is not None
    assert result.last_action.action.type == "rewrite_slide"
    assert result.last_action.action.target == "S-005"
    assert result.last_action.action.scope == "slide_only"


@pytest.mark.asyncio
@patch("src.agents.conversation.agent.call_llm", new_callable=AsyncMock)
async def test_conversation_returns_export_action(
    mock_call_llm: AsyncMock,
) -> None:
    """Mock returns ExportAction — verify action type in state."""
    mock_call_llm.return_value = _make_success_response(
        response=_make_export_response()
    )
    state = _make_input_state()

    from src.agents.conversation.agent import run

    result = await run(state, user_message="Export as PPTX")

    assert result.last_action is not None
    assert result.last_action.action.type == "export"
    assert result.last_action.action.format == "pptx"


@pytest.mark.asyncio
@patch("src.agents.conversation.agent.call_llm", new_callable=AsyncMock)
async def test_conversation_stage_unchanged(
    mock_call_llm: AsyncMock,
) -> None:
    """Conversation Manager does NOT change state.current_stage."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()
    original_stage = state.current_stage

    from src.agents.conversation.agent import run

    result = await run(state, user_message="Fix slide 5")

    assert result.current_stage == original_stage
