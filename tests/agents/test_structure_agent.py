"""Tests for the Structure Agent — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
from src.models.enums import LayoutType
from src.models.rfp import (
    EvaluationCategory,
    EvaluationCriteria,
    EvaluationSubCriterion,
    RFPContext,
)
from src.models.slide_blueprint import SlideBlueprint, SlideBlueprintEntry
from src.models.state import DeckForgeState
from src.services.llm import LLMError, LLMResponse


def _make_sample_rfp_context() -> RFPContext:
    """Minimal valid RFPContext for test fixtures."""
    return RFPContext(
        rfp_name=BilingualText(en="Renewal of Support for SAP Systems"),
        issuing_entity=BilingualText(en="Saudi Industrial Development Fund"),
        mandate=BilingualText(en="Renew and supply SAP licenses for 24 months."),
        evaluation_criteria=EvaluationCriteria(
            technical=EvaluationCategory(
                weight_pct=70,
                sub_criteria=[
                    EvaluationSubCriterion(name="Previous Experience", weight_pct=40),
                    EvaluationSubCriterion(name="Technical Approach", weight_pct=30),
                ],
            ),
            financial=EvaluationCategory(weight_pct=30),
        ),
    )


_SAMPLE_REPORT_MARKDOWN = """\
# Research Report: Renewal of Support for SAP Systems

## 1. Executive Summary

Strategic Gears has delivered SAP projects for government entities [Ref: CLM-0001].

## 3. Relevant Experience

SAP HANA migration for SIDF [Ref: CLM-0001].

## 7. Identified Gaps

GAP: No NCA cybersecurity compliance evidence [GAP-001].
"""


def _make_sample_slide_blueprint() -> SlideBlueprint:
    """Sample template-locked blueprint response."""
    return SlideBlueprint(
        entries=[
            SlideBlueprintEntry(
                section_id="S01",
                section_name="Proposal Shell",
                ownership="hybrid",
                slide_title="Renewal of Support for SAP Systems",
                key_message="Proposal structure for SAP renewal",
                house_action="include_as_is",
            ),
            SlideBlueprintEntry(
                section_id="S02",
                section_name="Introduction Message",
                ownership="dynamic",
                slide_title="Strategic Gears SAP Expertise",
                key_message="Proven SAP delivery for public-sector entities",
                bullet_points=["8 consultants", "12 modules", "9-month delivery"],
                evidence_ids=["CLM-0001"],
                visual_guidance="Executive message layout",
            ),
            SlideBlueprintEntry(
                section_id="S03",
                section_name="Table of Contents",
                ownership="hybrid",
                slide_title="Table of Contents",
                key_message="Template-native section sequence",
                house_action="include_as_is",
            ),
        ]
    )


def _make_success_response() -> LLMResponse:
    """LLMResponse wrapping valid SlideBlueprint."""
    return LLMResponse(
        parsed=_make_sample_slide_blueprint(),
        input_tokens=6000,
        output_tokens=3000,
        model="gpt-5.4",
        latency_ms=45000.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with report_markdown and rfp_context for Structure Agent."""
    return DeckForgeState(
        rfp_context=_make_sample_rfp_context(),
        report_markdown=_SAMPLE_REPORT_MARKDOWN,
        output_language="en",
    )


@pytest.mark.asyncio
@patch("src.agents.slide_architect.structure.agent.call_llm", new_callable=AsyncMock)
async def test_structure_happy_path(mock_call_llm: AsyncMock) -> None:
    """Approved report + rfp_context → state.slide_blueprint populated."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.structure.agent import run

    result = await run(state)

    assert result.slide_blueprint is not None
    assert isinstance(result.slide_blueprint, SlideBlueprint)
    assert result.slide_outline is not None  # compatibility object for downstream consumers
    assert result.current_stage == "outline_review"
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.slide_architect.structure.agent.call_llm", new_callable=AsyncMock)
async def test_structure_uses_model_map(mock_call_llm: AsyncMock) -> None:
    """Agent uses MODEL_MAP['structure_agent'], resolves to GPT-5.4, not Claude."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.structure.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["structure_agent"]
    assert "gpt" in MODEL_MAP["structure_agent"]
    assert call_kwargs.kwargs["response_model"] is SlideBlueprint


@pytest.mark.asyncio
@patch("src.agents.slide_architect.structure.agent.call_llm", new_callable=AsyncMock)
async def test_structure_uses_system_prompt(mock_call_llm: AsyncMock) -> None:
    """Agent passes SYSTEM_PROMPT starting with 'You are the Structure Agent'."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.structure.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith(
        "You are the Structure Agent"
    )


@pytest.mark.asyncio
@patch("src.agents.slide_architect.structure.agent.call_llm", new_callable=AsyncMock)
async def test_structure_handles_llm_error(mock_call_llm: AsyncMock) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="gpt-5.4",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.structure.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "structure_agent"
    assert result.slide_outline is None
    assert result.slide_blueprint is None


@pytest.mark.asyncio
@patch("src.agents.slide_architect.structure.agent.call_llm", new_callable=AsyncMock)
async def test_structure_updates_token_counts(mock_call_llm: AsyncMock) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.structure.agent import run

    result = await run(state)

    assert result.session.total_input_tokens == 6000
    assert result.session.total_output_tokens == 3000
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.slide_architect.structure.agent.call_llm", new_callable=AsyncMock)
async def test_structure_builds_user_message(mock_call_llm: AsyncMock) -> None:
    """User message includes approved_report, rfp_context, presentation_type, evaluation_criteria, output_language."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.structure.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "approved_report" in user_msg
    assert "rfp_context" in user_msg
    assert "presentation_type" in user_msg
    assert "evaluation_criteria" in user_msg
    assert "output_language" in user_msg
    assert user_msg["output_language"] == "en"
    assert user_msg["presentation_type"] == "technical_proposal"
    assert user_msg["approved_report"] == _SAMPLE_REPORT_MARKDOWN


@pytest.mark.asyncio
@patch("src.agents.slide_architect.structure.agent.call_llm", new_callable=AsyncMock)
async def test_structure_outline_has_slides(mock_call_llm: AsyncMock) -> None:
    """Compatibility SlideOutline is derived from template blueprint."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.structure.agent import run

    result = await run(state)

    outline = result.slide_outline
    assert outline is not None
    assert len(outline.slides) == 3
    assert outline.slides[0].slide_id == "S-001"
    assert outline.slides[0].title == "Renewal of Support for SAP Systems"
    assert outline.slides[0].layout_type == LayoutType.TITLE
    assert outline.slides[0].report_section_ref == "S01"
    assert outline.slides[1].layout_type == LayoutType.CONTENT_1COL
    assert "CLM-0001" in outline.slides[1].source_claims
    assert outline.slides[2].layout_type == LayoutType.AGENDA


@pytest.mark.asyncio
@patch("src.agents.slide_architect.structure.agent.call_llm", new_callable=AsyncMock)
async def test_structure_slide_count_matches(mock_call_llm: AsyncMock) -> None:
    """slide_outline.slide_count matches len(slide_outline.slides)."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.structure.agent import run

    result = await run(state)

    outline = result.slide_outline
    assert outline is not None
    assert outline.slide_count == len(outline.slides)
    assert outline.slide_count == 3
    assert "template_locked_contract" in outline.weight_allocation
