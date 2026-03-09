"""Tests for the Research Agent — mock-based, no live API calls."""

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
from src.models.report import (
    ReportGap,
    ReportSection,
    ReportSourceEntry,
    ResearchReport,
)
from src.models.rfp import RFPContext
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
    """Sample ReferenceIndex for Research Agent input."""
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


_SAMPLE_MARKDOWN = """\
# Research Report: Renewal of Support for SAP Systems

## 1. Executive Summary

Strategic Gears has delivered SAP projects for government entities [Ref: CLM-0001].

## 7. Identified Gaps

GAP: No NCA cybersecurity compliance evidence [GAP-001].
"""


def _make_sample_research_report() -> ResearchReport:
    """Sample ResearchReport with sections, gaps, source index, and markdown."""
    return ResearchReport(
        title="Research Report: Renewal of Support for SAP Systems",
        language="en",
        sections=[
            ReportSection(
                section_id="SEC-01",
                heading="Executive Summary",
                content_markdown="Strategic Gears has delivered SAP projects [Ref: CLM-0001].",
                claims_referenced=["CLM-0001"],
                gaps_flagged=[],
                sensitivity_tags=["capability"],
            ),
            ReportSection(
                section_id="SEC-07",
                heading="Identified Gaps",
                content_markdown="GAP: No NCA cybersecurity compliance evidence [GAP-001].",
                claims_referenced=[],
                gaps_flagged=["GAP-001"],
                sensitivity_tags=["compliance"],
            ),
        ],
        all_gaps=[
            ReportGap(
                gap_id="GAP-001",
                description="No NCA cybersecurity compliance evidence",
                rfp_criterion="Compliance > NCA Cybersecurity",
                severity="critical",
                action_required="Provide NCA compliance certificate",
            ),
        ],
        source_index=[
            ReportSourceEntry(
                claim_id="CLM-0001",
                document_title="SIDF SAP Migration Report",
                sharepoint_path="/sites/proposals/2023/SIDF-SAP.pptx",
                date="2023-12-15",
            ),
        ],
        full_markdown=_SAMPLE_MARKDOWN,
    )


def _make_success_response() -> LLMResponse:
    """LLMResponse wrapping valid ResearchReport."""
    return LLMResponse(
        parsed=_make_sample_research_report(),
        input_tokens=8000,
        output_tokens=4000,
        model="claude-opus-4-6",
        latency_ms=120000.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with reference_index and rfp_context for Research Agent."""
    return DeckForgeState(
        rfp_context=_make_sample_rfp_context(),
        reference_index=_make_sample_reference_index(),
        output_language="en",
        user_notes="Focus on SAP experience and compliance readiness.",
    )


@pytest.mark.asyncio
@patch("src.agents.research.agent.call_llm", new_callable=AsyncMock)
async def test_research_happy_path(mock_call_llm: AsyncMock) -> None:
    """Reference index + rfp_context produces report in state, stage = report_review."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.research.agent import run

    result = await run(state)

    assert result.research_report is not None
    assert result.report_markdown != ""
    assert result.current_stage == "report_review"
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.research.agent.call_llm", new_callable=AsyncMock)
async def test_research_uses_model_map(mock_call_llm: AsyncMock) -> None:
    """Agent uses MODEL_MAP['research_agent'], resolves to Claude Opus, not GPT."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.research.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["research_agent"]
    assert "claude" in MODEL_MAP["research_agent"]


@pytest.mark.asyncio
@patch("src.agents.research.agent.call_llm", new_callable=AsyncMock)
async def test_research_uses_system_prompt(mock_call_llm: AsyncMock) -> None:
    """Agent passes SYSTEM_PROMPT starting with 'You are the Research Agent'."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.research.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith(
        "You are the Research Agent"
    )


@pytest.mark.asyncio
@patch("src.agents.research.agent.call_llm", new_callable=AsyncMock)
async def test_research_handles_llm_error(mock_call_llm: AsyncMock) -> None:
    """LLMError is caught, errors populated, stage = ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="claude-opus-4-6",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.research.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "research_agent"
    assert result.research_report is None


@pytest.mark.asyncio
@patch("src.agents.research.agent.call_llm", new_callable=AsyncMock)
async def test_research_updates_token_counts(mock_call_llm: AsyncMock) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.research.agent import run

    result = await run(state)

    assert result.session.total_input_tokens == 8000
    assert result.session.total_output_tokens == 4000
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.research.agent.call_llm", new_callable=AsyncMock)
async def test_research_builds_user_message(mock_call_llm: AsyncMock) -> None:
    """User message includes reference_index, rfp_context, output_language, user_strategic_notes."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.research.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "reference_index" in user_msg
    assert "rfp_context" in user_msg
    assert "output_language" in user_msg
    assert "user_strategic_notes" in user_msg
    assert user_msg["output_language"] == "en"
    assert user_msg["user_strategic_notes"] == "Focus on SAP experience and compliance readiness."


@pytest.mark.asyncio
@patch("src.agents.research.agent.call_llm", new_callable=AsyncMock)
async def test_research_populates_report_markdown(mock_call_llm: AsyncMock) -> None:
    """state.report_markdown is set from result.parsed.full_markdown."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.research.agent import run

    result = await run(state)

    assert result.report_markdown == _SAMPLE_MARKDOWN
    assert "Executive Summary" in result.report_markdown
    assert "[Ref: CLM-0001]" in result.report_markdown


@pytest.mark.asyncio
@patch("src.agents.research.agent.call_llm", new_callable=AsyncMock)
async def test_research_report_has_sections(mock_call_llm: AsyncMock) -> None:
    """Parsed ResearchReport has sections, all_gaps, and source_index populated."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.research.agent import run

    result = await run(state)

    rr = result.research_report
    assert rr is not None
    assert len(rr.sections) == 2
    assert rr.sections[0].section_id == "SEC-01"
    assert rr.sections[0].heading == "Executive Summary"
    assert "CLM-0001" in rr.sections[0].claims_referenced
    assert len(rr.all_gaps) == 1
    assert rr.all_gaps[0].gap_id == "GAP-001"
    assert rr.all_gaps[0].severity == "critical"
    assert len(rr.source_index) == 1
    assert rr.source_index[0].claim_id == "CLM-0001"
