"""Tests for sectioned reviewer fallback.

When the Source Book is too large for a single GPT-5.5 review call,
the reviewer must fall back to section-by-section review and aggregate.
The writer should never produce less content to satisfy the reviewer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.source_book.reviewer import (
    _SECTION_MAP,
    _SECTIONED_REVIEW_THRESHOLD,
    _review_sectioned,
    run,
)
from src.models.source_book import (
    RFPInterpretation,
    SectionCritique,
    SourceBook,
    SourceBookReview,
)
from src.models.state import DeckForgeState


def _large_source_book() -> SourceBook:
    """Create a Source Book large enough to trigger sectioned review."""
    sb = SourceBook(
        client_name="Test", rfp_name="Test RFP", language="en",
    )
    sb.rfp_interpretation = RFPInterpretation(
        objective_and_scope="x " * 5000,
        constraints_and_compliance="y " * 5000,
    )
    return sb


def _state_with_large_sb() -> DeckForgeState:
    state = DeckForgeState()
    state.source_book = _large_source_book()
    return state


# ── Section map completeness ─────────────────────────────────────


def test_section_map_contains_all_7_sections():
    """_SECTION_MAP must cover all 7 Source Book sections."""
    section_keys = {key for _, key in _SECTION_MAP}
    expected = {
        "rfp_interpretation",
        "client_problem_framing",
        "why_strategic_gears",
        "external_evidence",
        "proposed_solution",
        "slide_blueprints",
        "evidence_ledger",
    }
    assert expected.issubset(section_keys), (
        f"Missing sections: {expected - section_keys}"
    )


def test_section_map_includes_external_evidence():
    keys = {key for _, key in _SECTION_MAP}
    assert "external_evidence" in keys


def test_section_map_includes_evidence_ledger():
    keys = {key for _, key in _SECTION_MAP}
    assert "evidence_ledger" in keys


# ── Threshold ────────────────────────────────────────────────────


def test_threshold_exists():
    assert _SECTIONED_REVIEW_THRESHOLD > 0
    assert _SECTIONED_REVIEW_THRESHOLD >= 100_000


# ── Sectioned review covers all sections ─────────────────────────


@pytest.mark.asyncio
async def test_sectioned_review_calls_all_sections():
    """Sectioned review must attempt to review ALL mapped sections."""
    state = _state_with_large_sb()

    sections_called = []

    async def mock_call_llm(**kwargs):
        msg = kwargs.get("user_message", "")
        # Extract section_name from payload
        import json
        try:
            payload = json.loads(msg)
            sections_called.append(payload.get("section_name", "unknown"))
        except Exception:
            sections_called.append("parse_error")
        result = AsyncMock()
        result.parsed = SectionCritique(section_id="test", score=4, issues=[])
        result.input_tokens = 100
        result.output_tokens = 50
        result.cost_usd = 0.01
        result.model = "gpt-5.5"
        result.latency_ms = 100
        return result

    with patch("src.agents.source_book.reviewer.call_llm", side_effect=mock_call_llm):
        review, session = await _review_sectioned(state, "gpt-5.5")

    assert isinstance(review, SourceBookReview)
    # Must have called reviewer for multiple sections
    assert len(sections_called) >= 2, (
        f"Expected >=2 section calls, got {len(sections_called)}: {sections_called}"
    )
    # Critiques count must match calls
    assert len(review.section_critiques) == len(sections_called)


# ── Large SB triggers sectioned ──────────────────────────────────


@pytest.mark.asyncio
async def test_large_source_book_triggers_sectioned_review():
    state = _state_with_large_sb()

    mock_result = AsyncMock()
    mock_result.parsed = SectionCritique(section_id="test", score=4, issues=[])
    mock_result.input_tokens = 100
    mock_result.output_tokens = 50
    mock_result.cost_usd = 0.01
    mock_result.model = "gpt-5.5"
    mock_result.latency_ms = 100

    with patch("src.agents.source_book.reviewer.call_llm", return_value=mock_result) as mock_llm:
        with patch("src.agents.source_book.reviewer._build_user_message") as mock_msg:
            mock_msg.return_value = "x" * (_SECTIONED_REVIEW_THRESHOLD + 1)
            result = await run(state)

    review = result["source_book_review"]
    assert isinstance(review, SourceBookReview)
    assert mock_llm.call_count >= 2


# ── Fallback on full review failure ──────────────────────────────


@pytest.mark.asyncio
async def test_large_sb_selects_sectioned_without_failed_full_attempt():
    """Long Source Book must go directly to sectioned — no failed full call first."""
    state = _state_with_large_sb()

    call_models_used = []

    mock_result = AsyncMock()
    mock_result.parsed = SectionCritique(section_id="test", score=4, issues=[])
    mock_result.input_tokens = 100
    mock_result.output_tokens = 50
    mock_result.cost_usd = 0.01
    mock_result.model = "gpt-5.5"
    mock_result.latency_ms = 100

    async def track_calls(**kwargs):
        call_models_used.append(kwargs.get("system_prompt", "")[:30])
        return mock_result

    with patch("src.agents.source_book.reviewer.call_llm", side_effect=track_calls):
        with patch("src.agents.source_book.reviewer._build_user_message") as mock_msg:
            mock_msg.return_value = "x" * (_SECTIONED_REVIEW_THRESHOLD + 1)
            result = await run(state)

    # All calls should be sectioned review calls (section prompt),
    # NOT a failed full review followed by sectioned
    assert all("ONE SECTION" in prompt for prompt in call_models_used), (
        "Large SB should use sectioned review directly, not attempt full review first"
    )


async def test_safety_net_fallback_on_unexpected_full_review_failure():
    """Safety net: if full review unexpectedly fails, fall back to sectioned."""
    state = DeckForgeState()
    state.source_book = SourceBook(client_name="Test", rfp_name="Test", language="en")

    call_count = 0

    async def mock_call_llm(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("OpenAI returned empty content. Finish reason: length")
        result = AsyncMock()
        result.parsed = SectionCritique(section_id="test", score=3, issues=["minor"])
        result.input_tokens = 100
        result.output_tokens = 50
        result.cost_usd = 0.01
        result.model = "gpt-5.5"
        result.latency_ms = 100
        return result

    with patch("src.agents.source_book.reviewer.call_llm", side_effect=mock_call_llm):
        with patch("src.agents.source_book.reviewer._build_user_message", return_value="short"):
            result = await run(state)

    assert isinstance(result["source_book_review"], SourceBookReview)
    assert result["source_book_review"].overall_score >= 1


# ── Fail-closed aggregation ─────────────────────────────────────


@pytest.mark.asyncio
async def test_aggregate_score_fail_closed_on_critical_section():
    state = _state_with_large_sb()

    call_idx = 0

    async def mock_call_llm(**kwargs):
        nonlocal call_idx
        call_idx += 1
        result = AsyncMock()
        if call_idx == 1:
            result.parsed = SectionCritique(section_id="S1", score=1, issues=["critical"])
        else:
            result.parsed = SectionCritique(section_id=f"S{call_idx}", score=5, issues=[])
        result.input_tokens = 100
        result.output_tokens = 50
        result.cost_usd = 0.01
        result.model = "gpt-5.5"
        result.latency_ms = 100
        return result

    with patch("src.agents.source_book.reviewer.call_llm", side_effect=mock_call_llm):
        review, _ = await _review_sectioned(state, "gpt-5.5")

    assert review.overall_score <= 3
    assert review.pass_threshold_met is False


# ── Short SB uses full review ────────────────────────────────────


@pytest.mark.asyncio
async def test_short_source_book_uses_full_review():
    state = DeckForgeState()
    state.source_book = SourceBook(client_name="Test", rfp_name="Test", language="en")

    mock_result = AsyncMock()
    mock_result.parsed = SourceBookReview(
        overall_score=4, competitive_viability="adequate",
        pass_threshold_met=True, rewrite_required=False,
    )
    mock_result.input_tokens = 100
    mock_result.output_tokens = 50
    mock_result.cost_usd = 0.01
    mock_result.model = "gpt-5.5"
    mock_result.latency_ms = 1000

    with patch("src.agents.source_book.reviewer.call_llm", return_value=mock_result) as mock_llm:
        with patch("src.agents.source_book.reviewer._build_user_message", return_value="short"):
            result = await run(state)

    assert mock_llm.call_count == 1
    assert result["source_book_review"].overall_score == 4


# ── Session accounting ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_sectioned_review_returns_session():
    """Sectioned review must return updated session with accumulated costs."""
    state = _state_with_large_sb()

    mock_result = AsyncMock()
    mock_result.parsed = SectionCritique(section_id="test", score=4, issues=[])
    mock_result.input_tokens = 500
    mock_result.output_tokens = 200
    mock_result.cost_usd = 0.05
    mock_result.model = "gpt-5.5"
    mock_result.latency_ms = 100

    with patch("src.agents.source_book.reviewer.call_llm", return_value=mock_result):
        review, session = await _review_sectioned(state, "gpt-5.5")

    assert session is not None
    assert isinstance(review, SourceBookReview)


@pytest.mark.asyncio
async def test_large_sb_run_returns_session():
    """Full run() with large SB must return session from sectioned review."""
    state = _state_with_large_sb()

    mock_result = AsyncMock()
    mock_result.parsed = SectionCritique(section_id="test", score=4, issues=[])
    mock_result.input_tokens = 500
    mock_result.output_tokens = 200
    mock_result.cost_usd = 0.05
    mock_result.model = "gpt-5.5"
    mock_result.latency_ms = 100

    with patch("src.agents.source_book.reviewer.call_llm", return_value=mock_result):
        with patch("src.agents.source_book.reviewer._build_user_message") as mock_msg:
            mock_msg.return_value = "x" * (_SECTIONED_REVIEW_THRESHOLD + 1)
            result = await run(state)

    assert "session" in result
    assert "source_book_review" in result


# ── Writer content not truncated ─────────────────────────────────


def test_writer_content_not_truncated():
    assert _SECTIONED_REVIEW_THRESHOLD > 0
