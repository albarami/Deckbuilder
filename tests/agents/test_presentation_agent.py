"""Tests for the Presentation Agent (Turn 5) — mock-based, no live API calls."""

from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
from src.models.enums import LayoutType
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
from src.models.slides import BodyContent, SlideObject, WrittenSlides
from src.models.state import DeckForgeState
from src.services.llm import LLMError, LLMResponse


def _make_written_slides() -> WrittenSlides:
    return WrittenSlides(
        slides=[
            SlideObject(
                slide_id="S-001",
                title="24-Month SAP License Renewal for SIDF",
                layout_type=LayoutType.TITLE,
                body_content=BodyContent(text_elements=["Presented by Strategic Gears"]),
                speaker_notes="Cover slide. Introduce the proposal.",
            ),
            SlideObject(
                slide_id="S-002",
                title="Proposal Agenda",
                layout_type=LayoutType.AGENDA,
                body_content=BodyContent(
                    text_elements=["Experience", "Approach", "Team", "Compliance"]
                ),
                speaker_notes="Walk through the agenda.",
            ),
        ],
        notes=None,
    )


def _make_success_response() -> LLMResponse:
    return LLMResponse(
        parsed=_make_written_slides(),
        input_tokens=8000,
        output_tokens=6000,
        model="claude-opus-4-6",
        latency_ms=50000.0,
    )


def _make_input_state() -> DeckForgeState:
    draft = DeckDraft(
        slides=[
            SlideText(slide_number=1, title="Strong Title", bullets=["Data"]),
            SlideText(slide_number=2, title="Agenda", bullets=["Topic"]),
        ],
        turn_number=3,
        mode="strict",
    )
    review = DeckReview(
        critiques=[
            SlideCritique(slide_number=1, score=5, issues=[]),
            SlideCritique(slide_number=2, score=4, issues=[]),
        ],
        overall_score=4,
        turn_number=4,
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
@patch("src.agents.presentation.agent.call_llm", new_callable=AsyncMock)
async def test_presentation_produces_written_slides(mock_llm: AsyncMock) -> None:
    """Turn 5 produces WrittenSlides stored in state.written_slides."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.presentation.agent import run

    result = await run(state)

    assert result.written_slides is not None
    assert isinstance(result.written_slides, WrittenSlides)
    assert len(result.written_slides.slides) >= 2
    assert result.written_slides.slides[0].body_content is not None


@pytest.mark.asyncio
@patch("src.agents.presentation.agent.call_llm", new_callable=AsyncMock)
async def test_presentation_uses_opus_model(mock_llm: AsyncMock) -> None:
    """Presentation Agent uses MODEL_MAP['research_agent'] (Claude Opus)."""
    mock_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.presentation.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["research_agent"]


@pytest.mark.asyncio
@patch("src.agents.presentation.agent.call_llm", new_callable=AsyncMock)
async def test_presentation_handles_llm_error(mock_llm: AsyncMock) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_llm.side_effect = LLMError(
        model="claude-opus-4-6",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.presentation.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "presentation_agent"
    assert result.written_slides is None
