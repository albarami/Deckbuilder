"""Tests for src/services/llm.py — unified LLM wrapper. All tests use mocks, no live API calls."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.common import DeckForgeBaseModel


class SampleOutput(DeckForgeBaseModel):
    """Test model for structured output."""
    name: str
    value: int


def _make_openai_response(
    content_json: str, prompt_tokens: int = 100, completion_tokens: int = 50,
) -> MagicMock:
    """Build a mock OpenAI ChatCompletion response."""
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    message = MagicMock()
    message.content = content_json

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_anthropic_response(
    tool_input: dict, input_tokens: int = 100, output_tokens: int = 50,
) -> MagicMock:
    """Build a mock Anthropic Message response with a tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_input

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    response = MagicMock()
    response.content = [tool_block]
    response.usage = usage
    return response


@pytest.fixture(autouse=True)
def _reset_llm_clients():
    """Reset lazy client singletons between tests."""
    import src.services.llm as llm_mod

    llm_mod._openai_client = None
    llm_mod._anthropic_client = None
    yield
    llm_mod._openai_client = None
    llm_mod._anthropic_client = None


@pytest.fixture(autouse=True)
def _set_api_keys():
    """Ensure API keys are set for client initialization."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-key",
        "ANTHROPIC_API_KEY": "test-key",
    }):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


# ── Provider routing tests ──


@pytest.mark.asyncio
async def test_routes_to_openai_for_gpt_model():
    mock_response = _make_openai_response('{"name": "test", "value": 42}')
    with patch(
        "openai.resources.chat.completions.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_create:
        from src.services.llm import call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="You are a test.",
            user_message="Return test data.",
            response_model=SampleOutput,
        )
        mock_create.assert_called_once()
        assert result.parsed.name == "test"
        assert result.parsed.value == 42


@pytest.mark.asyncio
async def test_routes_to_anthropic_for_claude_model():
    mock_response = _make_anthropic_response({"name": "test", "value": 42})
    with patch(
        "anthropic.resources.messages.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_create:
        from src.services.llm import call_llm

        result = await call_llm(
            model="claude-opus-4-6",
            system_prompt="You are a test.",
            user_message="Return test data.",
            response_model=SampleOutput,
        )
        mock_create.assert_called_once()
        assert result.parsed.name == "test"
        assert result.parsed.value == 42


@pytest.mark.asyncio
async def test_unknown_provider_raises_value_error():
    from src.services.llm import call_llm

    with pytest.raises(ValueError, match="Unsupported model"):
        await call_llm(
            model="unknown-model-v1",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )


# ── Response structure tests ──


@pytest.mark.asyncio
async def test_returns_llm_response_with_parsed_model():
    mock_response = _make_openai_response('{"name": "hello", "value": 7}')
    with patch(
        "openai.resources.chat.completions.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from src.services.llm import LLMResponse, call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert isinstance(result, LLMResponse)
        assert isinstance(result.parsed, SampleOutput)
        assert result.parsed.name == "hello"
        assert result.parsed.value == 7


@pytest.mark.asyncio
async def test_response_includes_token_counts_openai():
    mock_response = _make_openai_response(
        '{"name": "t", "value": 1}', prompt_tokens=150, completion_tokens=75,
    )
    with patch(
        "openai.resources.chat.completions.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.input_tokens == 150
        assert result.output_tokens == 75
        assert result.model == "gpt-5.4"
        assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_response_includes_token_counts_anthropic():
    mock_response = _make_anthropic_response(
        {"name": "t", "value": 1}, input_tokens=200, output_tokens=100,
    )
    with patch(
        "anthropic.resources.messages.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="claude-opus-4-6",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.input_tokens == 200
        assert result.output_tokens == 100
        assert result.model == "claude-opus-4-6"


# ── Retry tests ──


@pytest.mark.asyncio
async def test_retries_on_timeout_then_succeeds():
    import openai

    mock_response = _make_openai_response('{"name": "ok", "value": 1}')
    mock_create = AsyncMock(
        side_effect=[
            openai.APITimeoutError(request=MagicMock()),
            openai.APITimeoutError(request=MagicMock()),
            openai.APITimeoutError(request=MagicMock()),
            mock_response,
        ]
    )
    with (
        patch("openai.resources.chat.completions.completions.AsyncCompletions.create", mock_create),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.parsed.name == "ok"
        assert mock_create.call_count == 4
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)
        mock_sleep.assert_any_call(8)


@pytest.mark.asyncio
async def test_raises_llm_error_after_4_failures():
    import openai

    mock_create = AsyncMock(
        side_effect=openai.APITimeoutError(request=MagicMock()),
    )
    with (
        patch("openai.resources.chat.completions.completions.AsyncCompletions.create", mock_create),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        from src.services.llm import LLMError, call_llm

        with pytest.raises(LLMError) as exc_info:
            await call_llm(
                model="gpt-5.4",
                system_prompt="test",
                user_message="test",
                response_model=SampleOutput,
            )
        assert exc_info.value.attempts == 4
        assert exc_info.value.model == "gpt-5.4"
        assert mock_create.call_count == 4


@pytest.mark.asyncio
async def test_retries_on_rate_limit():
    import openai

    mock_response = _make_openai_response('{"name": "ok", "value": 1}')
    mock_create = AsyncMock(
        side_effect=[
            openai.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429),
                body=None,
            ),
            mock_response,
        ]
    )
    with (
        patch("openai.resources.chat.completions.completions.AsyncCompletions.create", mock_create),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.parsed.name == "ok"
        assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_no_retry_on_auth_error():
    import openai

    mock_create = AsyncMock(
        side_effect=openai.AuthenticationError(
            message="bad key",
            response=MagicMock(status_code=401),
            body=None,
        ),
    )
    with patch("openai.resources.chat.completions.completions.AsyncCompletions.create", mock_create):
        from src.services.llm import LLMError, call_llm

        with pytest.raises(LLMError) as exc_info:
            await call_llm(
                model="gpt-5.4",
                system_prompt="test",
                user_message="test",
                response_model=SampleOutput,
            )
        assert exc_info.value.attempts == 1
        assert mock_create.call_count == 1


@pytest.mark.asyncio
async def test_anthropic_retry_on_timeout():
    import anthropic

    mock_response = _make_anthropic_response({"name": "ok", "value": 1})
    mock_create = AsyncMock(
        side_effect=[
            anthropic.APITimeoutError(request=MagicMock()),
            mock_response,
        ]
    )
    with (
        patch("anthropic.resources.messages.messages.AsyncMessages.create", mock_create),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="claude-opus-4-6",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.parsed.name == "ok"
        assert mock_create.call_count == 2


# ── Malformed response tests ──


@pytest.mark.asyncio
async def test_openai_none_content_raises_llm_error():
    """OpenAI returning message.content=None raises LLMError, not AssertionError."""
    mock_response = _make_openai_response('{"name": "x", "value": 1}')
    mock_response.choices[0].message.content = None
    with patch(
        "openai.resources.chat.completions.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from src.services.llm import LLMError, call_llm

        with pytest.raises(LLMError) as exc_info:
            await call_llm(
                model="gpt-5.4",
                system_prompt="test",
                user_message="test",
                response_model=SampleOutput,
            )
        assert exc_info.value.attempts == 1
        assert "empty content" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_anthropic_no_tool_use_block_raises_llm_error():
    """Anthropic returning no tool_use block raises LLMError, not StopIteration."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I cannot do that."

    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50

    mock_response = MagicMock()
    mock_response.content = [text_block]
    mock_response.usage = usage

    with patch(
        "anthropic.resources.messages.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from src.services.llm import LLMError, call_llm

        with pytest.raises(LLMError) as exc_info:
            await call_llm(
                model="claude-opus-4-6",
                system_prompt="test",
                user_message="test",
                response_model=SampleOutput,
            )
        assert exc_info.value.attempts == 1
        assert "tool_use" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_invalid_json_payload_raises_llm_error():
    """Structured output that fails Pydantic validation raises LLMError, not ValidationError."""
    mock_response = _make_openai_response('{"name": "valid", "wrong_field": 42}')
    with patch(
        "openai.resources.chat.completions.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from src.services.llm import LLMError, call_llm

        with pytest.raises(LLMError) as exc_info:
            await call_llm(
                model="gpt-5.4",
                system_prompt="test",
                user_message="test",
                response_model=SampleOutput,
            )
        assert exc_info.value.attempts == 1
