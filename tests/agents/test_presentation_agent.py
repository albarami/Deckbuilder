"""Tests for the Presentation Agent (Turn 5) — mock-based, no live API calls."""

import json
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


def _make_strict_input_state_with_refs() -> DeckForgeState:
    draft = DeckDraft(
        slides=[
            SlideText(
                slide_number=1,
                title="Strong Title",
                bullets=["12 modules delivered [Ref: CLM-0001]"],
                speaker_notes="Explain the 12-module scope [Ref: CLM-0002].",
            ),
        ],
        turn_number=3,
        mode="strict",
    )
    review = DeckReview(
        critiques=[
            SlideCritique(slide_number=1, score=5, issues=[]),
        ],
        overall_score=5,
        turn_number=4,
    )
    return DeckForgeState(
        rfp_context=RFPContext(
            rfp_name=BilingualText(en="SAP Support Renewal"),
            issuing_entity=BilingualText(en="SIDF"),
            mandate=BilingualText(en="Renew SAP licenses."),
        ),
        report_markdown="# Report\n\n12 modules delivered [Ref: CLM-0001].",
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


def test_presentation_main_payload_matches_turn_five_contract() -> None:
    """Main payload should send slide-ready inputs, not the full approved report."""
    from src.agents.presentation.agent import _build_user_message

    state = _make_input_state()
    payload = json.loads(_build_user_message(state))

    assert "refined_draft" in payload
    assert "final_review" in payload
    assert "approved_report" not in payload
    assert payload["rfp_context"] == {
        "rfp_name": {"en": "SAP Support Renewal", "ar": None},
        "issuing_entity": {"en": "SIDF", "ar": None},
    }


@pytest.mark.asyncio
@patch("src.agents.presentation.agent.call_llm", new_callable=AsyncMock)
async def test_presentation_restores_source_refs_from_refined_draft(
    mock_llm: AsyncMock,
) -> None:
    """Presentation output should preserve structural source refs and strip inline tags."""
    mock_llm.return_value = LLMResponse(
        parsed=WrittenSlides(
            slides=[
                SlideObject(
                    slide_id="S-001",
                    title="Strong Title",
                    layout_type=LayoutType.CONTENT_1COL,
                    body_content=BodyContent(
                        text_elements=["12 modules delivered [Ref: CLM-0001]"],
                    ),
                    speaker_notes="Explain the 12-module scope [Ref: CLM-0002].",
                    source_refs=[],
                ),
            ],
            notes=None,
        ),
        input_tokens=1000,
        output_tokens=1000,
        model="claude-opus-4-6",
        latency_ms=1000.0,
    )
    state = _make_strict_input_state_with_refs()

    from src.agents.presentation.agent import run

    result = await run(state)

    slide = result.written_slides.slides[0]
    assert slide.source_refs == ["CLM-0001", "CLM-0002"]
    assert "[Ref:" not in slide.body_content.text_elements[0]
    assert "[Ref:" not in slide.speaker_notes


@pytest.mark.asyncio
@patch("src.agents.presentation.agent.call_llm", new_callable=AsyncMock)
async def test_presentation_retries_empty_structured_output(
    mock_llm: AsyncMock,
) -> None:
    """An empty structured response retries with a larger token budget."""
    mock_llm.side_effect = [
        LLMError(
            model="claude-opus-4-6",
            attempts=1,
            last_error=ValueError(
                "Structured output validation failed: 1 validation error for WrittenSlides\nslides\n  Field required [type=missing, input_value={}, input_type=dict]"
            ),
        ),
        _make_success_response(),
    ]
    state = _make_input_state()

    from src.agents.presentation.agent import run

    result = await run(state)

    assert result.written_slides is not None
    assert mock_llm.await_count == 2
    assert mock_llm.await_args_list[0].kwargs["max_tokens"] == 16000
    assert mock_llm.await_args_list[1].kwargs["max_tokens"] > 16000


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
