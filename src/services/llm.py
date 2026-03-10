"""Unified LLM wrapper for OpenAI and Anthropic with retries and structured output."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

import anthropic
import openai

from src.config.settings import get_settings
from src.models.common import DeckForgeBaseModel

T = TypeVar("T", bound=DeckForgeBaseModel)

_RETRY_DELAYS = [2, 4, 8]

_RETRYABLE_ERRORS = (
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)

_NON_RETRYABLE_ERRORS = (
    openai.AuthenticationError,
    anthropic.AuthenticationError,
)

_openai_client: openai.AsyncOpenAI | None = None
_anthropic_client: anthropic.AsyncAnthropic | None = None


class LLMError(Exception):
    """Raised when an LLM call fails after all retry attempts."""

    def __init__(self, model: str, attempts: int, last_error: Exception) -> None:
        self.model = model
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"LLM call failed after {attempts} attempts: {last_error}")


@dataclass(frozen=True)
class LLMResponse(Generic[T]):  # noqa: UP046
    """Wrapper holding the parsed model, token counts, and metadata."""

    parsed: T
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: float


def _get_openai_client() -> openai.AsyncOpenAI:
    """Lazy singleton for the OpenAI async client."""
    global _openai_client  # noqa: PLW0603
    if _openai_client is None:
        settings = get_settings()
        _openai_client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
        )
    return _openai_client


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Lazy singleton for the Anthropic async client."""
    global _anthropic_client  # noqa: PLW0603
    if _anthropic_client is None:
        settings = get_settings()
        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
        )
    return _anthropic_client


async def _call_openai(  # noqa: UP047
    model: str,
    system_prompt: str,
    user_message: str,
    response_model: type[T],
    temperature: float,
    max_tokens: int,
) -> tuple[T, int, int]:
    """Call OpenAI chat completions with structured JSON output."""
    client = _get_openai_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "schema": response_model.model_json_schema(),
            },
        },
        temperature=temperature,
        max_completion_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    if content is None:
        raise LLMError(
            model=model, attempts=1,
            last_error=ValueError("OpenAI returned empty content (message.content is None)"),
        )
    if response.usage is None:
        raise LLMError(
            model=model, attempts=1,
            last_error=ValueError("OpenAI returned no usage data"),
        )
    try:
        parsed = response_model.model_validate_json(content)
    except Exception as e:
        raise LLMError(
            model=model, attempts=1,
            last_error=ValueError(f"Structured output validation failed: {e}"),
        ) from e
    return parsed, response.usage.prompt_tokens, response.usage.completion_tokens


async def _call_anthropic(  # noqa: UP047
    model: str,
    system_prompt: str,
    user_message: str,
    response_model: type[T],
    temperature: float,
    max_tokens: int,
) -> tuple[T, int, int]:
    """Call Anthropic messages with tool-use-based structured output."""
    client = _get_anthropic_client()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        tools=[{
            "name": "structured_output",
            "description": f"Return structured data matching {response_model.__name__}",
            "input_schema": response_model.model_json_schema(),
        }],
        tool_choice={"type": "tool", "name": "structured_output"},
        temperature=temperature,
    )
    tool_block = next((block for block in response.content if block.type == "tool_use"), None)
    if tool_block is None:
        raise LLMError(
            model=model, attempts=1,
            last_error=ValueError("Anthropic response contained no tool_use block"),
        )
    try:
        parsed = response_model.model_validate(tool_block.input)
    except Exception as e:
        raise LLMError(
            model=model, attempts=1,
            last_error=ValueError(f"Structured output validation failed: {e}"),
        ) from e
    return parsed, response.usage.input_tokens, response.usage.output_tokens


async def call_llm(  # noqa: UP047
    model: str,
    system_prompt: str,
    user_message: str,
    response_model: type[T],
    temperature: float = 0.0,
    max_tokens: int = 4000,
) -> LLMResponse[T]:
    """Unified LLM call with provider routing, retries, and structured output.

    Args:
        model: Model string from MODEL_MAP (e.g., "gpt-5.4", "claude-opus-4-6").
        system_prompt: System message for the LLM.
        user_message: User message content.
        response_model: Pydantic model class for structured output parsing.
        temperature: Sampling temperature (default 0.0 for deterministic output).
        max_tokens: Maximum tokens in the response.

    Returns:
        LLMResponse[T] with .parsed, .input_tokens, .output_tokens, .model, .latency_ms.

    Raises:
        ValueError: If model string doesn't match any known provider.
        LLMError: If all retry attempts are exhausted or a non-retryable error occurs.
    """
    if model.startswith("gpt"):
        provider_call = _call_openai
    elif model.startswith("claude"):
        provider_call = _call_anthropic
    else:
        raise ValueError(f"Unsupported model: {model}")

    last_error: Exception | None = None
    max_attempts = 1 + len(_RETRY_DELAYS)

    for attempt in range(max_attempts):
        try:
            start = time.perf_counter()
            parsed, in_tokens, out_tokens = await provider_call(
                model=model,
                system_prompt=system_prompt,
                user_message=user_message,
                response_model=response_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            return LLMResponse(
                parsed=parsed,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                model=model,
                latency_ms=elapsed_ms,
            )
        except _NON_RETRYABLE_ERRORS as e:
            raise LLMError(model=model, attempts=attempt + 1, last_error=e) from e
        except _RETRYABLE_ERRORS as e:
            last_error = e
            if attempt < len(_RETRY_DELAYS):
                await asyncio.sleep(_RETRY_DELAYS[attempt])

    raise LLMError(model=model, attempts=max_attempts, last_error=last_error)  # type: ignore[arg-type]
