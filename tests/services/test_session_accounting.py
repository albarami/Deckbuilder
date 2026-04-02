"""Tests for session accounting helpers."""

from pytest import approx

from src.models.state import SessionMetadata
from src.services.session_accounting import update_session_from_llm, update_session_from_raw


class _FakeLLMResponse:
    input_tokens = 1000
    output_tokens = 500
    cost_usd = 0.025


def test_update_session_from_llm_basic():
    session = SessionMetadata(session_id="test")
    result = update_session_from_llm(session, _FakeLLMResponse())
    assert result.total_llm_calls == 1
    assert result.total_input_tokens == 1000
    assert result.total_output_tokens == 500
    assert result.total_cost_usd == 0.025
    # Original unchanged
    assert session.total_llm_calls == 0
    assert session.total_cost_usd == 0.0


def test_update_session_from_llm_accumulates():
    session = SessionMetadata(
        session_id="test",
        total_llm_calls=2,
        total_input_tokens=5000,
        total_output_tokens=3000,
        total_cost_usd=0.05,
    )
    result = update_session_from_llm(session, _FakeLLMResponse())
    assert result.total_llm_calls == 3
    assert result.total_input_tokens == 6000
    assert result.total_output_tokens == 3500
    assert result.total_cost_usd == approx(0.075)


def test_update_session_from_raw():
    session = SessionMetadata(session_id="test")
    result = update_session_from_raw(
        session,
        input_tokens=800,
        output_tokens=300,
        cost_usd=0.018,
    )
    assert result.total_llm_calls == 1
    assert result.total_input_tokens == 800
    assert result.total_output_tokens == 300
    assert result.total_cost_usd == 0.018
    # Original unchanged
    assert session.total_llm_calls == 0


def test_update_session_from_raw_accumulates():
    session = SessionMetadata(
        session_id="test",
        total_llm_calls=5,
        total_cost_usd=0.1,
    )
    result = update_session_from_raw(
        session,
        input_tokens=400,
        output_tokens=200,
        cost_usd=0.01,
    )
    assert result.total_llm_calls == 6
    assert result.total_cost_usd == approx(0.11)
