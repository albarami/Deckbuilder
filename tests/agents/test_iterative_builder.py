"""Tests for the 5-turn iterative slide builder orchestrator."""

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


def _make_rfp() -> RFPContext:
    return RFPContext(
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
    )


def _make_input_state() -> DeckForgeState:
    return DeckForgeState(
        rfp_context=_make_rfp(),
        report_markdown="# Report\n\nContent here.",
        evidence_mode="strict",
    )


def _draft_response() -> LLMResponse:
    # Must produce >= MIN_DRAFT_SLIDES (15) to avoid retry guard
    slides = [
        SlideText(slide_number=i, title=f"Slide {i}", bullets=[f"B{i}"])
        for i in range(1, 17)
    ]
    return LLMResponse(
        parsed=DeckDraft(
            slides=slides,
            turn_number=1,
        ),
        input_tokens=5000,
        output_tokens=3000,
        model="claude-opus-4-6",
        latency_ms=30000.0,
    )


def _review_response() -> LLMResponse:
    return LLMResponse(
        parsed=DeckReview(
            critiques=[SlideCritique(slide_number=1, score=3, issues=["Weak"])],
            overall_score=3,
            turn_number=2,
        ),
        input_tokens=4000,
        output_tokens=2000,
        model="gpt-5.4",
        latency_ms=20000.0,
    )


def _refine_response() -> LLMResponse:
    return LLMResponse(
        parsed=DeckDraft(
            slides=[SlideText(slide_number=1, title="Better Title", bullets=["B1+"])],
            turn_number=3,
        ),
        input_tokens=6000,
        output_tokens=4000,
        model="claude-opus-4-6",
        latency_ms=35000.0,
    )


def _final_review_response() -> LLMResponse:
    return LLMResponse(
        parsed=DeckReview(
            critiques=[SlideCritique(slide_number=1, score=5, issues=[])],
            overall_score=5,
            turn_number=4,
        ),
        input_tokens=5000,
        output_tokens=2000,
        model="gpt-5.4",
        latency_ms=18000.0,
    )


def _presentation_response() -> LLMResponse:
    return LLMResponse(
        parsed=WrittenSlides(
            slides=[
                SlideObject(
                    slide_id="S-001",
                    title="Final Title",
                    layout_type=LayoutType.TITLE,
                    body_content=BodyContent(text_elements=["Final content"]),
                    speaker_notes="Final notes",
                ),
            ],
        ),
        input_tokens=8000,
        output_tokens=6000,
        model="claude-opus-4-6",
        latency_ms=50000.0,
    )


@pytest.mark.asyncio
@patch("src.agents.presentation.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.final_review.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.refine.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.review.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.draft.agent.call_llm", new_callable=AsyncMock)
async def test_5_turns_execute_in_sequence(
    mock_draft: AsyncMock,
    mock_review: AsyncMock,
    mock_refine: AsyncMock,
    mock_final_review: AsyncMock,
    mock_presentation: AsyncMock,
) -> None:
    """All 5 agents are called in sequence."""
    mock_draft.return_value = _draft_response()
    mock_review.return_value = _review_response()
    mock_refine.return_value = _refine_response()
    mock_final_review.return_value = _final_review_response()
    mock_presentation.return_value = _presentation_response()

    state = _make_input_state()

    from src.agents.iterative.builder import run_iterative_build

    result = await run_iterative_build(state)

    assert mock_draft.call_count == 1
    assert mock_review.call_count == 1
    assert mock_refine.call_count == 1
    assert mock_final_review.call_count == 1
    assert mock_presentation.call_count == 1
    assert result.written_slides is not None
    assert len(result.deck_drafts) == 2  # Turn 1 + Turn 3
    assert len(result.deck_reviews) == 2  # Turn 2 + Turn 4


@pytest.mark.asyncio
@patch("src.agents.presentation.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.final_review.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.refine.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.review.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.draft.agent.call_llm", new_callable=AsyncMock)
async def test_correct_models_per_turn(
    mock_draft: AsyncMock,
    mock_review: AsyncMock,
    mock_refine: AsyncMock,
    mock_final_review: AsyncMock,
    mock_presentation: AsyncMock,
) -> None:
    """Turns 1,3,5 use Opus; turns 2,4 use GPT."""
    mock_draft.return_value = _draft_response()
    mock_review.return_value = _review_response()
    mock_refine.return_value = _refine_response()
    mock_final_review.return_value = _final_review_response()
    mock_presentation.return_value = _presentation_response()

    from src.agents.iterative.builder import run_iterative_build
    from src.config.models import MODEL_MAP

    state = _make_input_state()
    await run_iterative_build(state)

    # Opus turns (1, 3, 5)
    assert mock_draft.call_args.kwargs["model"] == MODEL_MAP["research_agent"]
    assert mock_refine.call_args.kwargs["model"] == MODEL_MAP["research_agent"]
    assert mock_presentation.call_args.kwargs["model"] == MODEL_MAP["research_agent"]

    # GPT turns (2, 4)
    assert mock_review.call_args.kwargs["model"] == MODEL_MAP["qa_agent"]
    assert mock_final_review.call_args.kwargs["model"] == MODEL_MAP["qa_agent"]


@pytest.mark.asyncio
@patch("src.agents.presentation.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.final_review.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.refine.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.review.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.draft.agent.call_llm", new_callable=AsyncMock)
async def test_token_counts_accumulated(
    mock_draft: AsyncMock,
    mock_review: AsyncMock,
    mock_refine: AsyncMock,
    mock_final_review: AsyncMock,
    mock_presentation: AsyncMock,
) -> None:
    """Session token totals accumulate across all 5 turns."""
    mock_draft.return_value = _draft_response()
    mock_review.return_value = _review_response()
    mock_refine.return_value = _refine_response()
    mock_final_review.return_value = _final_review_response()
    mock_presentation.return_value = _presentation_response()

    from src.agents.iterative.builder import run_iterative_build

    state = _make_input_state()
    result = await run_iterative_build(state)

    # Sum of all 5 agents' input tokens: 5000+4000+6000+5000+8000 = 28000
    assert result.session.total_input_tokens == 28000
    # Sum of all 5 agents' output tokens: 3000+2000+4000+2000+6000 = 17000
    assert result.session.total_output_tokens == 17000
    assert result.session.total_llm_calls == 5


@pytest.mark.asyncio
async def test_pipeline_wiring_has_build_slides_node() -> None:
    """The compiled graph contains a 'build_slides' node."""
    from src.pipeline.graph import build_graph

    graph = build_graph()
    # LangGraph compiled graphs expose nodes via .nodes attribute
    node_names = set(graph.nodes.keys())
    assert "build_slides" in node_names
    # Old nodes should be gone
    assert "structure" not in node_names
    assert "content" not in node_names


@pytest.mark.asyncio
@patch("src.agents.review.agent.call_llm", new_callable=AsyncMock)
@patch("src.agents.draft.agent.call_llm", new_callable=AsyncMock)
async def test_llm_error_on_any_turn_sets_error_stage(
    mock_draft: AsyncMock,
    mock_review: AsyncMock,
) -> None:
    """LLMError on Turn 2 stops the build and sets error stage."""
    mock_draft.return_value = _draft_response()
    mock_review.side_effect = LLMError(
        model="gpt-5.4",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )

    from src.agents.iterative.builder import run_iterative_build

    state = _make_input_state()
    result = await run_iterative_build(state)

    assert result.current_stage == "error"
    assert len(result.errors) >= 1
    # Build should have stopped — no written_slides
    assert result.written_slides is None
