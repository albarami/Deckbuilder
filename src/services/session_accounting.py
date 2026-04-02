"""Shared session accounting helpers.

Single source of truth for updating SessionMetadata from LLM call results.
Replaces scattered inline session mutation across agent files.
"""

from __future__ import annotations

from src.models.state import SessionMetadata
from src.services.llm import LLMResponse


def update_session_from_llm(
    session: SessionMetadata,
    llm_result: LLMResponse,
) -> SessionMetadata:
    """Increment session accounting from a call_llm() result.

    Returns a new SessionMetadata copy. Does not mutate the input.
    """
    updated = session.model_copy(deep=True)
    updated.total_llm_calls += 1
    updated.total_input_tokens += llm_result.input_tokens
    updated.total_output_tokens += llm_result.output_tokens
    updated.total_cost_usd += llm_result.cost_usd
    return updated


def update_session_from_raw(
    session: SessionMetadata,
    *,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> SessionMetadata:
    """Increment session accounting from raw values.

    For agents that call the Anthropic client directly (not via call_llm).
    Returns a new SessionMetadata copy. Does not mutate the input.
    """
    updated = session.model_copy(deep=True)
    updated.total_llm_calls += 1
    updated.total_input_tokens += input_tokens
    updated.total_output_tokens += output_tokens
    updated.total_cost_usd += cost_usd
    return updated
