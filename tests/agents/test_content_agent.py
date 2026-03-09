"""Tests for the Content Agent — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
from src.models.enums import LayoutType
from src.models.rfp import RFPContext
from src.models.slides import BodyContent, SlideObject, SlideOutline, WrittenSlides
from src.models.state import DeckForgeState
from src.services.llm import LLMError, LLMResponse


def _make_sample_rfp_context() -> RFPContext:
    """Minimal valid RFPContext for test fixtures."""
    return RFPContext(
        rfp_name=BilingualText(en="Renewal of Support for SAP Systems"),
        issuing_entity=BilingualText(en="Saudi Industrial Development Fund"),
        mandate=BilingualText(en="Renew and supply SAP licenses for 24 months."),
    )


_SAMPLE_REPORT_MARKDOWN = """\
# Research Report: Renewal of Support for SAP Systems

## 1. Executive Summary

Strategic Gears has delivered SAP projects for government entities [Ref: CLM-0001].

## 3. Relevant Experience

SAP HANA migration for SIDF: 8 consultants, 12 modules, 9-month delivery [Ref: CLM-0001].
"""


def _make_sample_slide_outline() -> SlideOutline:
    """Sample SlideOutline as input from Structure Agent."""
    return SlideOutline(
        slides=[
            SlideObject(
                slide_id="S-001",
                title="Renewal of Support for SAP Systems",
                layout_type=LayoutType.TITLE,
                report_section_ref="SEC-01",
                content_guidance="Cover slide: RFP name, entity, date",
                source_claims=[],
            ),
            SlideObject(
                slide_id="S-002",
                title="Strategic Gears SAP Expertise",
                layout_type=LayoutType.CONTENT_1COL,
                report_section_ref="SEC-03",
                content_guidance="Use CLM-0001 for SAP experience summary",
                source_claims=["CLM-0001"],
            ),
        ],
        slide_count=2,
        weight_allocation={"Previous Experience": "40% — 1 slide"},
    )


def _make_sample_written_slides() -> WrittenSlides:
    """Sample WrittenSlides with body_content, speaker_notes, source_refs populated."""
    return WrittenSlides(
        slides=[
            SlideObject(
                slide_id="S-001",
                title="Renewal of Support for SAP Systems",
                layout_type=LayoutType.TITLE,
                report_section_ref="SEC-01",
                body_content=BodyContent(
                    text_elements=["Saudi Industrial Development Fund", "24-Month SAP License Renewal"],
                ),
                speaker_notes="This proposal addresses SIDF's requirement to renew SAP licenses.",
                source_refs=[],
            ),
            SlideObject(
                slide_id="S-002",
                title="12-Module SAP Migration Delivered On Schedule for SIDF",
                layout_type=LayoutType.CONTENT_1COL,
                report_section_ref="SEC-03",
                body_content=BodyContent(
                    text_elements=[
                        "8 consultants deployed across 12 SAP modules",
                        "9-month delivery timeline met on schedule",
                        "Full HANA migration for SIDF completed",
                    ],
                ),
                speaker_notes=(
                    "Strategic Gears delivered an SAP HANA migration for SIDF"
                    " involving 8 consultants across 12 modules over 9 months."
                ),
                source_refs=["CLM-0001"],
            ),
        ],
    )


def _make_success_response() -> LLMResponse:
    """LLMResponse wrapping valid WrittenSlides."""
    return LLMResponse(
        parsed=_make_sample_written_slides(),
        input_tokens=7000,
        output_tokens=3500,
        model="gpt-5.4",
        latency_ms=50000.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with slide_outline and report_markdown for Content Agent."""
    return DeckForgeState(
        rfp_context=_make_sample_rfp_context(),
        slide_outline=_make_sample_slide_outline(),
        report_markdown=_SAMPLE_REPORT_MARKDOWN,
        output_language="en",
    )


@pytest.mark.asyncio
@patch("src.agents.content.agent.call_llm", new_callable=AsyncMock)
async def test_content_happy_path(mock_call_llm: AsyncMock) -> None:
    """Slide outline + report → state.written_slides populated, stage updated."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.content.agent import run

    result = await run(state)

    assert result.written_slides is not None
    assert isinstance(result.written_slides, WrittenSlides)
    assert result.current_stage == "content_generation"
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.content.agent.call_llm", new_callable=AsyncMock)
async def test_content_uses_model_map(mock_call_llm: AsyncMock) -> None:
    """Agent uses MODEL_MAP['content_agent'], resolves to GPT-5.4, not Claude."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.content.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["content_agent"]
    assert "gpt" in MODEL_MAP["content_agent"]


@pytest.mark.asyncio
@patch("src.agents.content.agent.call_llm", new_callable=AsyncMock)
async def test_content_uses_system_prompt(mock_call_llm: AsyncMock) -> None:
    """Agent passes SYSTEM_PROMPT starting with 'You are the Content Agent'."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.content.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith(
        "You are the Content Agent"
    )


@pytest.mark.asyncio
@patch("src.agents.content.agent.call_llm", new_callable=AsyncMock)
async def test_content_handles_llm_error(mock_call_llm: AsyncMock) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="gpt-5.4",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.content.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "content_agent"
    assert result.written_slides is None


@pytest.mark.asyncio
@patch("src.agents.content.agent.call_llm", new_callable=AsyncMock)
async def test_content_updates_token_counts(mock_call_llm: AsyncMock) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.content.agent import run

    result = await run(state)

    assert result.session.total_input_tokens == 7000
    assert result.session.total_output_tokens == 3500
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.content.agent.call_llm", new_callable=AsyncMock)
async def test_content_builds_user_message(mock_call_llm: AsyncMock) -> None:
    """User message includes slide_outline, approved_report, output_language."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.content.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "slide_outline" in user_msg
    assert "approved_report" in user_msg
    assert "output_language" in user_msg
    assert user_msg["output_language"] == "en"
    assert user_msg["approved_report"] == _SAMPLE_REPORT_MARKDOWN
    # slide_outline should be a dict (serialized from SlideOutline)
    assert isinstance(user_msg["slide_outline"], dict)
    assert "slides" in user_msg["slide_outline"]


@pytest.mark.asyncio
@patch("src.agents.content.agent.call_llm", new_callable=AsyncMock)
async def test_content_slides_have_body_content(mock_call_llm: AsyncMock) -> None:
    """Slides in WrittenSlides have body_content, speaker_notes, source_refs populated."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.content.agent import run

    result = await run(state)

    ws = result.written_slides
    assert ws is not None
    assert len(ws.slides) == 2

    # Slide 1: Title slide
    s1 = ws.slides[0]
    assert s1.slide_id == "S-001"
    assert s1.body_content is not None
    assert len(s1.body_content.text_elements) >= 1
    assert s1.speaker_notes != ""

    # Slide 2: Content slide with source_refs
    s2 = ws.slides[1]
    assert s2.slide_id == "S-002"
    assert s2.body_content is not None
    assert len(s2.body_content.text_elements) >= 2
    assert s2.speaker_notes != ""
    assert "CLM-0001" in s2.source_refs
