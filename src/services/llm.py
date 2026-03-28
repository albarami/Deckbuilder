"""Unified LLM wrapper for OpenAI and Anthropic with retries and structured output."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

import anthropic
import openai

from src.config.settings import get_settings
from src.models.common import DeckForgeBaseModel

logger = logging.getLogger(__name__)

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

# ── Global cost tracker ──────────────────────────────────────
# Per-million-token pricing (USD). Update when models change.
_MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-5.4":          {"input": 2.50, "output": 10.00},
    "gpt-4.1":          {"input": 2.00, "output": 8.00},
    "gpt-4o":           {"input": 2.50, "output": 10.00},
    # Anthropic
    "claude-opus-4-6":  {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6":{"input": 3.00, "output": 15.00},
}


@dataclass
class LLMCallRecord:
    """One recorded LLM call for cost tracking."""

    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    caller: str  # response_model name (e.g. 'SourceBook')


_call_log: list[LLMCallRecord] = []


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost for a single LLM call."""
    pricing = _MODEL_PRICING.get(model)
    if not pricing:
        # Fallback: match prefix
        for key, val in _MODEL_PRICING.items():
            if model.startswith(key.split("-")[0]):
                pricing = val
                break
    if not pricing:
        return 0.0
    return (
        input_tokens * pricing["input"] / 1_000_000
        + output_tokens * pricing["output"] / 1_000_000
    )


def reset_cost_tracker() -> None:
    """Clear the global call log. Call before a pipeline run."""
    _call_log.clear()


def get_cost_summary() -> dict:
    """Return aggregated cost summary from the global call log."""
    total_input = sum(r.input_tokens for r in _call_log)
    total_output = sum(r.output_tokens for r in _call_log)
    total_cost = sum(r.cost_usd for r in _call_log)
    total_latency = sum(r.latency_ms for r in _call_log)

    by_model: dict[str, dict] = {}
    for r in _call_log:
        if r.model not in by_model:
            by_model[r.model] = {
                "calls": 0, "input_tokens": 0,
                "output_tokens": 0, "cost_usd": 0.0,
            }
        by_model[r.model]["calls"] += 1
        by_model[r.model]["input_tokens"] += r.input_tokens
        by_model[r.model]["output_tokens"] += r.output_tokens
        by_model[r.model]["cost_usd"] += r.cost_usd

    return {
        "total_calls": len(_call_log),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "total_cost_usd": round(total_cost, 4),
        "total_latency_s": round(total_latency / 1000, 1),
        "by_model": {
            m: {**v, "cost_usd": round(v["cost_usd"], 4)}
            for m, v in by_model.items()
        },
        "calls": [
            {
                "model": r.model, "caller": r.caller,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": round(r.cost_usd, 4),
                "latency_s": round(r.latency_ms / 1000, 1),
            }
            for r in _call_log
        ],
    }


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
    if not content:
        raise LLMError(
            model=model, attempts=1,
            last_error=ValueError(
                f"OpenAI returned empty content (message.content={content!r}). "
                f"Finish reason: {response.choices[0].finish_reason}"
            ),
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

    # Diagnostic logging for empty tool responses
    if not tool_block.input or tool_block.input == {}:
        logger.warning(
            "Anthropic returned EMPTY tool input for %s. "
            "stop_reason=%s, input_tokens=%d, output_tokens=%d, max_tokens=%d",
            response_model.__name__,
            response.stop_reason,
            response.usage.input_tokens,
            response.usage.output_tokens,
            max_tokens,
        )

    try:
        parsed = response_model.model_validate(tool_block.input)
    except Exception as first_err:
        # Retry: if any field value is a JSON string instead of a dict/list,
        # recursively parse it. This handles Anthropic returning e.g.
        # external_evidence: '{"entries": [...]}' instead of a dict.
        import json as _json

        def _fix_string_json(obj: object) -> tuple[object, bool]:
            """Recursively parse JSON strings in dicts/lists."""
            changed = False
            if isinstance(obj, dict):
                fixed = {}
                for k, v in obj.items():
                    if isinstance(v, str) and v.strip()[:1] in ("{", "["):
                        try:
                            fixed[k] = _json.loads(v)
                            changed = True
                            logger.info(
                                "LLM string-to-dict fix: parsed field '%s'", k,
                            )
                        except _json.JSONDecodeError:
                            fixed[k] = v
                    else:
                        inner, inner_changed = _fix_string_json(v)
                        fixed[k] = inner
                        changed = changed or inner_changed
                return fixed, changed
            if isinstance(obj, list):
                fixed_list = []
                for item in obj:
                    inner, inner_changed = _fix_string_json(item)
                    fixed_list.append(inner)
                    changed = changed or inner_changed
                return fixed_list, changed
            return obj, False

        raw_input = tool_block.input if tool_block.input else {}
        fixed_input, did_fix = _fix_string_json(raw_input)

        if did_fix:
            try:
                parsed = response_model.model_validate(fixed_input)
                logger.info(
                    "LLM string-to-dict fix: validation succeeded for %s",
                    response_model.__name__,
                )
            except Exception as retry_err:
                raise LLMError(
                    model=model, attempts=1,
                    last_error=ValueError(
                        f"Structured output validation failed after "
                        f"string-to-dict fix: {retry_err}"
                    ),
                ) from retry_err
        else:
            raise LLMError(
                model=model, attempts=1,
                last_error=ValueError(
                    f"Structured output validation failed: {first_err}"
                ),
            ) from first_err
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
            # Record in global cost tracker
            cost = _compute_cost(model, in_tokens, out_tokens)
            _call_log.append(LLMCallRecord(
                model=model,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                latency_ms=elapsed_ms,
                cost_usd=cost,
                caller=response_model.__name__,
            ))
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
        except Exception as e:  # noqa: BLE001
            raise LLMError(model=model, attempts=attempt + 1, last_error=e) from e

    raise LLMError(model=model, attempts=max_attempts, last_error=last_error)  # type: ignore[arg-type]
