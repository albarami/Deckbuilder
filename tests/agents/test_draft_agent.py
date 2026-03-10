"""Tests for the Draft Agent (Turn 1) — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
from src.models.iterative import DeckDraft, SlideText
from src.models.rfp import (
    EvaluationCategory,
    EvaluationCriteria,
    EvaluationSubCriterion,
    RFPContext,
)
from src.models.state import DeckForgeState
from src.services.llm import LLMError, LLMResponse

_SAMPLE_REPORT = """\
# Research Report: Renewal of Support for SAP Systems

## 1. Executive Summary

Strategic Gears proposes SAP license renewal [Ref: CLM-0001].

## 3. Relevant Experience

SAP HANA migration for SIDF covering 12 modules [Ref: CLM-0001].
"""


def _make_rfp_context() -> RFPContext:
    return RFPContext(
        rfp_name=BilingualText(en="Renewal of Support for SAP Systems"),
        issuing_entity=BilingualText(en="SIDF"),
        mandate=BilingualText(en="Renew SAP licenses for 24 months."),
        evaluation_criteria=EvaluationCriteria(
            technical=EvaluationCategory(
                weight_pct=80,
                sub_criteria=[
                    EvaluationSubCriterion(name="Previous Experience", weight_pct=60),
                ],
            ),
            financial=EvaluationCategory(weight_pct=20),
        ),
    )


def _make_sample_draft() -> DeckDraft:
    return DeckDraft(
        slides=[
            SlideText(
                slide_number=1,
                title="SAP License Renewal for SIDF",
                bullets=["24-month renewal", "12 modules", "Riyadh-based delivery"],
                speaker_notes="Cover the RFP scope.",
                target_criterion="",
                evidence_level="sourced",
                layout_suggestion="TITLE",
            ),
            SlideText(
                slide_number=2,
                title="Proposal Agenda",
                bullets=["Executive Summary", "Experience", "Approach", "Team"],
                speaker_notes="Walk through agenda.",
                target_criterion="",
                evidence_level="general",
                layout_suggestion="AGENDA",
            ),
        ],
        turn_number=1,
        mode="strict",
    )


def _make_success_response() -> LLMResponse:
    return LLMResponse(
        parsed=_make_sample_draft(),
        input_tokens=5000,
        output_tokens=3000,
        model="claude-opus-4-6",
        latency_ms=30000.0,
    )


def _make_input_state(mode: str = "strict") -> DeckForgeState:
    return DeckForgeState(
        rfp_context=_make_rfp_context(),
        report_markdown=_SAMPLE_REPORT,
        output_language="en",
        evidence_mode=mode,
    )


@pytest.mark.asyncio
@patch("src.agents.draft.agent.call_llm", new_callable=AsyncMock)
async def test_draft_produces_deck_draft(mock_llm: AsyncMock) -> None:
    """Turn 1 produces a DeckDraft stored in state.deck_drafts."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.draft.agent import run

    result = await run(state)

    assert len(result.deck_drafts) == 1
    draft = DeckDraft.model_validate(result.deck_drafts[0])
    assert len(draft.slides) >= 2
    assert draft.turn_number == 1


@pytest.mark.asyncio
@patch("src.agents.draft.agent.call_llm", new_callable=AsyncMock)
async def test_draft_uses_opus_model(mock_llm: AsyncMock) -> None:
    """Draft Agent uses MODEL_MAP['research_agent'] (Claude Opus)."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.draft.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["research_agent"]
    assert "claude" in MODEL_MAP["research_agent"]


@pytest.mark.asyncio
@patch("src.agents.draft.agent.call_llm", new_callable=AsyncMock)
async def test_draft_strict_mode_preserves_refs(mock_llm: AsyncMock) -> None:
    """Strict mode prompt mentions [Ref: CLM-xxxx] preservation."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state(mode="strict")

    from src.agents.draft.agent import run

    await run(state)

    call_kwargs = mock_llm.call_args
    prompt = call_kwargs.kwargs["system_prompt"]
    assert "[Ref:" in prompt or "CLM-" in prompt


@pytest.mark.asyncio
@patch("src.agents.draft.agent.call_llm", new_callable=AsyncMock)
async def test_draft_general_mode_uses_knowledge_graph(mock_llm: AsyncMock) -> None:
    """General mode user_message includes knowledge graph data."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state(mode="general")

    from src.agents.draft.agent import run

    await run(state)

    call_kwargs = mock_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    # General mode should include company context from KG
    assert "company_context" in user_msg or "knowledge_graph" in user_msg


@pytest.mark.asyncio
@patch("src.agents.draft.agent.call_llm", new_callable=AsyncMock)
async def test_draft_handles_llm_error(mock_llm: AsyncMock) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_llm.side_effect = LLMError(
        model="claude-opus-4-6",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.draft.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "draft_agent"
    assert len(result.deck_drafts) == 0
