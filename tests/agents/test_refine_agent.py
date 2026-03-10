"""Tests for the Refine Agent (Turn 3) — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
from src.models.iterative import (
    DeckDraft,
    DeckReview,
    SlideCritique,
    SlideText,
)
from src.models.rfp import (
    EvaluationCategory,
    EvaluationCriteria,
    EvaluationSubCriterion,
    RFPContext,
)
from src.models.state import DeckForgeState
from src.services.llm import LLMError, LLMResponse


def _make_refined_draft() -> DeckDraft:
    return DeckDraft(
        slides=[
            SlideText(
                slide_number=1,
                title="24-Month SAP License Renewal for SIDF",
                bullets=["12 modules renewed", "Riyadh delivery", "SLA commitment"],
                evidence_level="sourced",
            ),
            SlideText(
                slide_number=2,
                title="Structured Agenda Addressing All Criteria",
                bullets=["Experience", "Technical Approach", "Team", "Compliance"],
                evidence_level="general",
            ),
        ],
        turn_number=3,
        mode="strict",
    )


def _make_success_response() -> LLMResponse:
    return LLMResponse(
        parsed=_make_refined_draft(),
        input_tokens=6000,
        output_tokens=4000,
        model="claude-opus-4-6",
        latency_ms=35000.0,
    )


def _make_input_state() -> DeckForgeState:
    draft = DeckDraft(
        slides=[
            SlideText(slide_number=1, title="SAP Renewal", bullets=["Bullet"]),
            SlideText(slide_number=2, title="Agenda", bullets=["Topic"]),
        ],
        turn_number=1,
        mode="strict",
    )
    review = DeckReview(
        critiques=[
            SlideCritique(slide_number=1, score=3, issues=["Weak title"]),
            SlideCritique(slide_number=2, score=2, issues=["Too generic"]),
        ],
        overall_score=2,
        turn_number=2,
    )
    return DeckForgeState(
        rfp_context=RFPContext(
            rfp_name=BilingualText(en="SAP Support Renewal"),
            issuing_entity=BilingualText(en="SIDF"),
            mandate=BilingualText(en="Renew SAP licenses."),
            evaluation_criteria=EvaluationCriteria(
                technical=EvaluationCategory(
                    weight_pct=80,
                    sub_criteria=[
                        EvaluationSubCriterion(name="Experience", weight_pct=60),
                    ],
                ),
                financial=EvaluationCategory(weight_pct=20),
            ),
        ),
        report_markdown="# Report\n\nContent here.",
        evidence_mode="strict",
        deck_drafts=[draft.model_dump(mode="json")],
        deck_reviews=[review.model_dump(mode="json")],
    )


@pytest.mark.asyncio
@patch("src.agents.refine.agent.call_llm", new_callable=AsyncMock)
async def test_refine_receives_draft_and_critique(mock_llm: AsyncMock) -> None:
    """Refine Agent user_message includes both the original draft and the critique."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.refine.agent import run

    await run(state)

    call_kwargs = mock_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "draft" in user_msg
    assert "review" in user_msg


@pytest.mark.asyncio
@patch("src.agents.refine.agent.call_llm", new_callable=AsyncMock)
async def test_refine_uses_opus_model(mock_llm: AsyncMock) -> None:
    """Refine Agent uses MODEL_MAP['research_agent'] (Claude Opus)."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.refine.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["research_agent"]


@pytest.mark.asyncio
@patch("src.agents.refine.agent.call_llm", new_callable=AsyncMock)
async def test_refine_handles_llm_error(mock_llm: AsyncMock) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_llm.side_effect = LLMError(
        model="claude-opus-4-6",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.refine.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "refine_agent"
