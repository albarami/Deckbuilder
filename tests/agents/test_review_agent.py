"""Tests for the Review Agent (Turn 2) — mock-based, no live API calls."""

from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
from src.models.iterative import DeckDraft, DeckReview, SlideCritique, SlideText
from src.models.rfp import (
    EvaluationCategory,
    EvaluationCriteria,
    EvaluationSubCriterion,
    RFPContext,
)
from src.models.state import DeckForgeState
from src.services.llm import LLMError, LLMResponse


def _make_sample_review() -> DeckReview:
    return DeckReview(
        critiques=[
            SlideCritique(
                slide_number=1,
                score=4,
                issues=["Title could be more insight-led"],
                instructions="Rephrase title as a value statement",
            ),
            SlideCritique(
                slide_number=2,
                score=2,
                issues=["Generic bullets", "No numbers"],
                instructions="Rewrite with specific data points",
            ),
        ],
        overall_score=3,
        coherence_issues=["Slides 1-2 narrative gap"],
        turn_number=2,
    )


def _make_success_response() -> LLMResponse:
    return LLMResponse(
        parsed=_make_sample_review(),
        input_tokens=4000,
        output_tokens=2000,
        model="gpt-5.4",
        latency_ms=20000.0,
    )


def _make_input_state() -> DeckForgeState:
    draft = DeckDraft(
        slides=[
            SlideText(slide_number=1, title="SAP Renewal", bullets=["Bullet 1"]),
            SlideText(slide_number=2, title="Agenda", bullets=["Topic A"]),
        ],
        turn_number=1,
        mode="strict",
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
    )


@pytest.mark.asyncio
@patch("src.agents.review.agent.call_llm", new_callable=AsyncMock)
async def test_review_produces_deck_review(mock_llm: AsyncMock) -> None:
    """Turn 2 produces a DeckReview stored in state.deck_reviews."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.review.agent import run

    result = await run(state)

    assert len(result.deck_reviews) == 1
    review = DeckReview.model_validate(result.deck_reviews[0])
    assert len(review.critiques) >= 2
    assert review.turn_number == 2


@pytest.mark.asyncio
@patch("src.agents.review.agent.call_llm", new_callable=AsyncMock)
async def test_review_uses_gpt_model(mock_llm: AsyncMock) -> None:
    """Review Agent uses MODEL_MAP['qa_agent'] (GPT-5.4)."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.review.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["qa_agent"]
    assert "gpt" in MODEL_MAP["qa_agent"]


@pytest.mark.asyncio
@patch("src.agents.review.agent.call_llm", new_callable=AsyncMock)
async def test_review_scores_each_slide(mock_llm: AsyncMock) -> None:
    """Every slide gets a score between 1 and 5."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.review.agent import run

    result = await run(state)

    review = DeckReview.model_validate(result.deck_reviews[0])
    for critique in review.critiques:
        assert 1 <= critique.score <= 5


@pytest.mark.asyncio
@patch("src.agents.review.agent.call_llm", new_callable=AsyncMock)
async def test_review_retries_when_output_hits_length_limit(
    mock_llm: AsyncMock,
) -> None:
    """A length-limited structured output retries with a larger token budget."""
    mock_llm.side_effect = [
        LLMError(
            model="gpt-5.4",
            attempts=1,
            last_error=ValueError(
                "OpenAI returned empty content (message.content=''). Finish reason: length"
            ),
        ),
        _make_success_response(),
    ]
    state = _make_input_state()

    from src.agents.review.agent import run

    result = await run(state)

    assert len(result.deck_reviews) == 1
    assert mock_llm.await_count == 2
    assert mock_llm.await_args_list[0].kwargs["max_tokens"] == 4000
    assert mock_llm.await_args_list[1].kwargs["max_tokens"] > 4000


@pytest.mark.asyncio
@patch("src.agents.review.agent.call_llm", new_callable=AsyncMock)
async def test_review_handles_llm_error(mock_llm: AsyncMock) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_llm.side_effect = LLMError(
        model="gpt-5.4",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.review.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "review_agent"
    assert len(result.deck_reviews) == 0
