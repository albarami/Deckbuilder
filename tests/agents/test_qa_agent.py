"""Tests for the QA Agent — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.claims import (
    ClaimObject,
    GapObject,
    ReferenceIndex,
    SourceManifestEntry,
)
from src.models.common import BilingualText
from src.models.enums import LayoutType
from src.models.qa import (
    DeckValidationSummary,
    QAIssue,
    QAResult,
    SlideValidation,
)
from src.models.rfp import RFPContext
from src.models.slides import (
    BodyContent,
    SlideObject,
    WrittenSlides,
)
from src.models.state import DeckForgeState
from src.services.llm import LLMError, LLMResponse


def _make_sample_rfp_context() -> RFPContext:
    """Minimal valid RFPContext for test fixtures."""
    return RFPContext(
        rfp_name=BilingualText(en="Renewal of Support for SAP Systems"),
        issuing_entity=BilingualText(en="Saudi Industrial Development Fund"),
        mandate=BilingualText(en="Renew and supply SAP licenses for 24 months."),
    )


def _make_sample_reference_index() -> ReferenceIndex:
    """Sample ReferenceIndex with claims and gaps for QA validation."""
    return ReferenceIndex(
        claims=[
            ClaimObject(
                claim_id="CLM-0001",
                claim_text="Strategic Gears delivered an SAP HANA migration for SIDF",
                source_doc_id="DOC-047",
                source_location="Slide 8",
                evidence_span="Project: SAP HANA Migration — Client: SIDF",
                sensitivity_tag="client_specific",
                category="project_reference",
                confidence=0.99,
            ),
        ],
        gaps=[
            GapObject(
                gap_id="GAP-001",
                description="No NCA cybersecurity compliance evidence",
                rfp_criterion="Compliance > NCA Cybersecurity",
                severity="critical",
                action_required="Provide NCA compliance certificate",
            ),
        ],
        source_manifest=[
            SourceManifestEntry(
                doc_id="DOC-047",
                title="SIDF SAP Migration Report",
                sharepoint_path="/sites/proposals/2023/SIDF-SAP.pptx",
            ),
        ],
    )


_SAMPLE_REPORT_MARKDOWN = """\
# Research Report: Renewal of Support for SAP Systems

## 1. Executive Summary

Strategic Gears has delivered SAP projects [Ref: CLM-0001].
"""


def _make_sample_written_slides() -> WrittenSlides:
    """Sample WrittenSlides for QA input."""
    return WrittenSlides(
        slides=[
            SlideObject(
                slide_id="S-001",
                title="SAP License Renewal for SIDF",
                layout_type=LayoutType.TITLE,
                report_section_ref="SEC-01",
                body_content=BodyContent(
                    text_elements=["Saudi Industrial Development Fund"],
                ),
                speaker_notes="Cover slide for SAP renewal proposal.",
                source_refs=[],
            ),
            SlideObject(
                slide_id="S-002",
                title="SAP HANA Migration Delivered for SIDF",
                layout_type=LayoutType.CONTENT_1COL,
                report_section_ref="SEC-03",
                body_content=BodyContent(
                    text_elements=[
                        "8 consultants across 12 SAP modules",
                        "9-month delivery on schedule",
                    ],
                ),
                speaker_notes="Detailed SAP migration experience.",
                source_refs=["CLM-0001"],
            ),
        ],
    )


def _make_sample_qa_result(fail_close: bool = False) -> QAResult:
    """Sample QAResult with one PASS and one FAIL slide."""
    return QAResult(
        slide_validations=[
            SlideValidation(
                slide_id="S-001",
                status="PASS",
                issues=[],
            ),
            SlideValidation(
                slide_id="S-002",
                status="FAIL",
                issues=[
                    QAIssue(
                        type="UNGROUNDED_CLAIM",
                        location="body_content bullet 1",
                        claim="8 consultants across 12 SAP modules",
                        explanation=(
                            "Specific numbers not in approved report"
                        ),
                        action="Verify against CLM-0001 evidence span",
                    ),
                ],
            ),
        ],
        deck_summary=DeckValidationSummary(
            total_slides=2,
            passed=1,
            failed=1,
            warnings=0,
            ungrounded_claims=1,
            inconsistencies=0,
            embellishments=0,
            rfp_criteria_covered=1,
            rfp_criteria_total=2,
            uncovered_criteria=["Financial Proposal"],
            critical_gaps_remaining=1 if fail_close else 0,
            fail_close=fail_close,
            fail_close_reason=(
                "Unresolved critical gap: GAP-001" if fail_close else ""
            ),
        ),
    )


def _make_success_response(
    fail_close: bool = False,
) -> LLMResponse:
    """LLMResponse wrapping valid QAResult."""
    return LLMResponse(
        parsed=_make_sample_qa_result(fail_close=fail_close),
        input_tokens=9000,
        output_tokens=4500,
        model="gpt-5.4",
        latency_ms=60000.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with written_slides, report, and claims for QA."""
    return DeckForgeState(
        rfp_context=_make_sample_rfp_context(),
        reference_index=_make_sample_reference_index(),
        written_slides=_make_sample_written_slides(),
        report_markdown=_SAMPLE_REPORT_MARKDOWN,
        output_language="en",
    )


@pytest.mark.asyncio
@patch("src.agents.qa.agent.call_llm", new_callable=AsyncMock)
async def test_qa_happy_path(mock_call_llm: AsyncMock) -> None:
    """Written slides + report + claims → state.qa_result populated, stage = qa."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.qa.agent import run

    result = await run(state)

    assert result.qa_result is not None
    assert isinstance(result.qa_result, QAResult)
    assert result.current_stage == "qa"
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.qa.agent.call_llm", new_callable=AsyncMock)
async def test_qa_uses_model_map(mock_call_llm: AsyncMock) -> None:
    """Agent uses MODEL_MAP['qa_agent'], resolves to GPT-5.4, not Claude."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.qa.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["qa_agent"]
    assert "gpt" in MODEL_MAP["qa_agent"]


@pytest.mark.asyncio
@patch("src.agents.qa.agent.call_llm", new_callable=AsyncMock)
async def test_qa_uses_system_prompt(mock_call_llm: AsyncMock) -> None:
    """Agent passes SYSTEM_PROMPT starting with 'You are the QA Agent'."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.qa.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith(
        "You are the QA Agent"
    )


@pytest.mark.asyncio
@patch("src.agents.qa.agent.call_llm", new_callable=AsyncMock)
async def test_qa_handles_llm_error(mock_call_llm: AsyncMock) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="gpt-5.4",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.qa.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "qa_agent"
    assert result.qa_result is None


@pytest.mark.asyncio
@patch("src.agents.qa.agent.call_llm", new_callable=AsyncMock)
async def test_qa_updates_token_counts(mock_call_llm: AsyncMock) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.qa.agent import run

    result = await run(state)

    assert result.session.total_input_tokens == 9000
    assert result.session.total_output_tokens == 4500
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.qa.agent.call_llm", new_callable=AsyncMock)
async def test_qa_builds_user_message(mock_call_llm: AsyncMock) -> None:
    """User message includes all QA inputs."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.qa.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "slides" in user_msg
    assert "approved_report" in user_msg
    assert "claim_index" in user_msg
    assert "unresolved_gaps" in user_msg
    assert "waived_gaps" in user_msg
    assert "evaluation_criteria" in user_msg
    assert "template_constraints" in user_msg
    assert user_msg["approved_report"] == _SAMPLE_REPORT_MARKDOWN
    assert isinstance(user_msg["slides"], list)
    assert isinstance(user_msg["claim_index"], list)
    assert isinstance(user_msg["template_constraints"], dict)
    assert user_msg["template_constraints"]["max_title_chars"] == 80


@pytest.mark.asyncio
@patch("src.agents.qa.agent.call_llm", new_callable=AsyncMock)
async def test_qa_result_has_validations(mock_call_llm: AsyncMock) -> None:
    """QAResult has slide_validations list and deck_summary."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.qa.agent import run

    result = await run(state)

    qa = result.qa_result
    assert qa is not None
    assert len(qa.slide_validations) == 2
    assert qa.slide_validations[0].slide_id == "S-001"
    assert qa.slide_validations[0].status == "PASS"
    assert qa.slide_validations[1].slide_id == "S-002"
    assert qa.slide_validations[1].status == "FAIL"
    assert len(qa.slide_validations[1].issues) == 1
    assert qa.slide_validations[1].issues[0].type == "UNGROUNDED_CLAIM"
    assert qa.deck_summary.total_slides == 2
    assert qa.deck_summary.passed == 1
    assert qa.deck_summary.failed == 1


@pytest.mark.asyncio
@patch("src.agents.qa.agent.call_llm", new_callable=AsyncMock)
async def test_qa_fail_close_preserved(mock_call_llm: AsyncMock) -> None:
    """If mock returns fail_close=True, it's preserved in state."""
    mock_call_llm.return_value = _make_success_response(fail_close=True)
    state = _make_input_state()

    from src.agents.qa.agent import run

    result = await run(state)

    qa = result.qa_result
    assert qa is not None
    assert qa.deck_summary.fail_close is True
    assert qa.deck_summary.critical_gaps_remaining == 1
    assert "GAP-001" in qa.deck_summary.fail_close_reason
    # Stage is still QA — pipeline node checks fail_close separately
    assert result.current_stage == "qa"
