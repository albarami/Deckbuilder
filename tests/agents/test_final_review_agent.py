"""Tests for the Final Review Agent (Turn 4) — mock-based, no live API calls."""

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


def _make_final_review() -> DeckReview:
    return DeckReview(
        critiques=[
            SlideCritique(slide_number=1, score=5, issues=[]),
            SlideCritique(slide_number=2, score=4, issues=["Minor formatting"]),
        ],
        overall_score=4,
        coherence_issues=[],
        turn_number=4,
    )


def _make_success_response() -> LLMResponse:
    return LLMResponse(
        parsed=_make_final_review(),
        input_tokens=5000,
        output_tokens=2000,
        model="gpt-5.4",
        latency_ms=18000.0,
    )


def _make_input_state() -> DeckForgeState:
    draft = DeckDraft(
        slides=[
            SlideText(slide_number=1, title="Strong Title", bullets=["Data point"]),
            SlideText(slide_number=2, title="Agenda", bullets=["Topic A"]),
        ],
        turn_number=3,
        mode="strict",
    )
    prev_review = DeckReview(
        critiques=[
            SlideCritique(slide_number=1, score=3, issues=["Weak title"]),
            SlideCritique(slide_number=2, score=2, issues=["Generic"]),
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
        deck_drafts=[
            DeckDraft(slides=[], turn_number=1).model_dump(mode="json"),
            draft.model_dump(mode="json"),
        ],
        deck_reviews=[prev_review.model_dump(mode="json")],
    )


@pytest.mark.asyncio
@patch("src.agents.final_review.agent.call_llm", new_callable=AsyncMock)
async def test_final_review_uses_gpt_model(mock_llm: AsyncMock) -> None:
    """Final Review Agent uses MODEL_MAP['qa_agent'] (GPT-5.4)."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.final_review.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["qa_agent"]


@pytest.mark.asyncio
@patch("src.agents.final_review.agent.call_llm", new_callable=AsyncMock)
async def test_final_review_checks_previous_issues(mock_llm: AsyncMock) -> None:
    """User message includes previous review for comparison."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.final_review.agent import run

    await run(state)

    call_kwargs = mock_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "previous_review" in user_msg
    assert "refined_draft" in user_msg


@pytest.mark.asyncio
@patch("src.agents.final_review.agent.call_llm", new_callable=AsyncMock)
async def test_final_review_handles_llm_error(mock_llm: AsyncMock) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_llm.side_effect = LLMError(
        model="gpt-5.4",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.final_review.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "final_review_agent"
