"""Tests for LLM wrapper temperature parameter compatibility.

GPT-5 series and Claude Opus 4.7+ do not support the temperature
parameter. The wrapper must omit it for those models while preserving
it for models that still support it.

Tests in two tiers:
  1. Helper tests: _supports_temperature() returns correct bool per model.
  2. Wrapper behavior tests: mock provider clients and assert actual API
     kwargs include/omit temperature as expected.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import DeckForgeBaseModel
from src.services.llm import _call_anthropic, _call_openai, _supports_temperature


# ── _supports_temperature helper ─────────────────────────────────


def test_gpt55_does_not_support_temperature():
    assert _supports_temperature("gpt-5.5") is False


def test_gpt54_does_not_support_temperature():
    assert _supports_temperature("gpt-5.4") is False


def test_gpt5_does_not_support_temperature():
    assert _supports_temperature("gpt-5") is False


def test_gpt55_pro_does_not_support_temperature():
    assert _supports_temperature("gpt-5.5-pro") is False


def test_opus47_does_not_support_temperature():
    assert _supports_temperature("claude-opus-4-7") is False


def test_gpt41_supports_temperature():
    assert _supports_temperature("gpt-4.1") is True


def test_gpt4o_supports_temperature():
    assert _supports_temperature("gpt-4o") is True


def test_sonnet46_supports_temperature():
    assert _supports_temperature("claude-sonnet-4-6") is True


def test_opus46_supports_temperature():
    """Legacy Opus 4.6 still supports temperature."""
    assert _supports_temperature("claude-opus-4-6") is True


def test_sonnet_20250514_supports_temperature():
    assert _supports_temperature("claude-sonnet-4-20250514") is True


# ── Wrapper behavior tests (mock provider clients) ───────────────
# These prove the actual kwargs sent to the API include/omit temperature.


class _DummyResponse(DeckForgeBaseModel):
    """Minimal Pydantic model for structured output in tests."""

    answer: str = "test"


def _make_openai_response():
    """Build a fake OpenAI chat completion response."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"answer": "test"}',
                ),
                finish_reason="stop",
            ),
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def _make_anthropic_response():
    """Build a fake Anthropic messages response."""
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                name="structured_output",
                input={"answer": "test"},
            ),
        ],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


@pytest.mark.asyncio
async def test_openai_gpt55_omits_temperature_from_api_call():
    """GPT-5.5 call must NOT include 'temperature' in kwargs."""
    mock_create = AsyncMock(return_value=_make_openai_response())
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=mock_create),
        ),
    )
    with patch("src.services.llm._get_openai_client", return_value=mock_client):
        await _call_openai(
            model="gpt-5.5",
            system_prompt="test",
            user_message="test",
            response_model=_DummyResponse,
            temperature=0.0,
            max_tokens=100,
        )
    call_kwargs = mock_create.call_args.kwargs
    assert "temperature" not in call_kwargs, (
        f"temperature should be omitted for gpt-5.5, got kwargs: {list(call_kwargs.keys())}"
    )


@pytest.mark.asyncio
async def test_openai_gpt41_keeps_temperature_in_api_call():
    """GPT-4.1 call must include 'temperature' in kwargs."""
    mock_create = AsyncMock(return_value=_make_openai_response())
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=mock_create),
        ),
    )
    with patch("src.services.llm._get_openai_client", return_value=mock_client):
        await _call_openai(
            model="gpt-4.1",
            system_prompt="test",
            user_message="test",
            response_model=_DummyResponse,
            temperature=0.5,
            max_tokens=100,
        )
    call_kwargs = mock_create.call_args.kwargs
    assert "temperature" in call_kwargs, "temperature should be kept for gpt-4.1"
    assert call_kwargs["temperature"] == 0.5


@pytest.mark.asyncio
async def test_anthropic_opus47_omits_temperature_from_api_call():
    """Claude Opus 4.7 call must NOT include 'temperature' in kwargs."""
    mock_create = AsyncMock(return_value=_make_anthropic_response())
    mock_client = SimpleNamespace(
        messages=SimpleNamespace(create=mock_create),
    )
    with patch("src.services.llm._get_anthropic_client", return_value=mock_client):
        await _call_anthropic(
            model="claude-opus-4-7",
            system_prompt="test",
            user_message="test",
            response_model=_DummyResponse,
            temperature=0.1,
            max_tokens=100,
        )
    call_kwargs = mock_create.call_args.kwargs
    assert "temperature" not in call_kwargs, (
        f"temperature should be omitted for claude-opus-4-7, got kwargs: {list(call_kwargs.keys())}"
    )


@pytest.mark.asyncio
async def test_anthropic_sonnet46_keeps_temperature_in_api_call():
    """Claude Sonnet 4.6 call must include 'temperature' in kwargs."""
    mock_create = AsyncMock(return_value=_make_anthropic_response())
    mock_client = SimpleNamespace(
        messages=SimpleNamespace(create=mock_create),
    )
    with patch("src.services.llm._get_anthropic_client", return_value=mock_client):
        await _call_anthropic(
            model="claude-sonnet-4-6",
            system_prompt="test",
            user_message="test",
            response_model=_DummyResponse,
            temperature=0.1,
            max_tokens=100,
        )
    call_kwargs = mock_create.call_args.kwargs
    assert "temperature" in call_kwargs, "temperature should be kept for claude-sonnet-4-6"
    assert call_kwargs["temperature"] == 0.1
