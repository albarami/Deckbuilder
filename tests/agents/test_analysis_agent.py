"""Tests for the Analysis Agent — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.claims import (
    CaseStudy,
    ClaimObject,
    GapObject,
    ReferenceIndex,
    SourceManifestEntry,
)
from src.models.common import BilingualText
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


def _make_sample_approved_sources() -> list[dict]:
    """Sample approved source documents with full content."""
    return [
        {
            "doc_id": "DOC-047",
            "title": "SIDF SAP Migration — Project Completion Report",
            "content_text": "Project: SAP HANA Enterprise Migration. Client: SIDF. Timeline: Feb 2023 — Nov 2023.",
            "content_type": "pptx",
            "slide_data": None,
            "metadata": {
                "doc_type": "case_study",
                "domain_tags": ["SAP", "migration"],
                "quality_score": 4,
                "last_modified": "2023-12-15",
            },
        },
    ]


def _make_sample_reference_index() -> ReferenceIndex:
    """Sample ReferenceIndex with claims, gaps, and source manifest."""
    return ReferenceIndex(
        claims=[
            ClaimObject(
                claim_id="CLM-0001",
                claim_text="Strategic Gears delivered an SAP HANA migration project for SIDF",
                source_doc_id="DOC-047",
                source_location="Slide 8",
                evidence_span="Project: SAP HANA Enterprise Migration — Client: SIDF",
                sensitivity_tag="client_specific",
                category="project_reference",
                confidence=0.99,
            ),
            ClaimObject(
                claim_id="CLM-0002",
                claim_text="The SIDF SAP project ran from February 2023 to November 2023",
                source_doc_id="DOC-047",
                source_location="Slide 8",
                evidence_span="Timeline: Feb 2023 — Nov 2023",
                sensitivity_tag="client_specific",
                category="project_reference",
                confidence=0.99,
            ),
        ],
        case_studies=[
            CaseStudy(
                project_name="SAP HANA Enterprise Migration",
                client="SIDF",
                scope="Migration of 12 SAP modules",
                source_claims=["CLM-0001", "CLM-0002"],
            ),
        ],
        gaps=[
            GapObject(
                gap_id="GAP-001",
                description="No evidence found for NCA cybersecurity compliance",
                rfp_criterion="Compliance > NCA Cybersecurity",
                severity="critical",
                action_required="Provide NCA compliance certificate",
            ),
        ],
        source_manifest=[
            SourceManifestEntry(
                doc_id="DOC-047",
                title="SIDF SAP Migration — Project Completion Report",
                sharepoint_path="/sites/proposals/2023/SIDF-SAP-Migration.pptx",
            ),
        ],
    )


def _make_success_response() -> LLMResponse:
    """LLMResponse wrapping valid ReferenceIndex."""
    return LLMResponse(
        parsed=_make_sample_reference_index(),
        input_tokens=5000,
        output_tokens=2000,
        model="claude-opus-4-6",
        latency_ms=15000.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with rfp_context populated for Analysis Agent input."""
    return DeckForgeState(
        rfp_context=_make_sample_rfp_context(),
        approved_source_ids=["DOC-047"],
    )


@pytest.mark.asyncio
@patch("src.agents.analysis.agent.call_llm", new_callable=AsyncMock)
async def test_analysis_happy_path(mock_call_llm: AsyncMock) -> None:
    """Approved sources + rfp_context produces ReferenceIndex in state."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.analysis.agent import run

    result = await run(state, _make_sample_approved_sources())

    assert result.reference_index is not None
    assert result.current_stage == "analysis"
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.analysis.agent.call_llm", new_callable=AsyncMock)
async def test_analysis_uses_model_map(mock_call_llm: AsyncMock) -> None:
    """Agent calls call_llm with MODEL_MAP['analysis_agent'], not a hardcoded string."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.analysis.agent import run
    from src.config.models import MODEL_MAP

    await run(state, _make_sample_approved_sources())

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["analysis_agent"]
    # Verify it resolves to a Claude model, not GPT
    assert "claude" in MODEL_MAP["analysis_agent"]


@pytest.mark.asyncio
@patch("src.agents.analysis.agent.call_llm", new_callable=AsyncMock)
async def test_analysis_uses_system_prompt(mock_call_llm: AsyncMock) -> None:
    """Agent passes SYSTEM_PROMPT starting with 'You are the Analysis Agent'."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.analysis.agent import run

    await run(state, _make_sample_approved_sources())

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith(
        "You are the Analysis Agent"
    )


@pytest.mark.asyncio
@patch("src.agents.analysis.agent.call_llm", new_callable=AsyncMock)
async def test_analysis_falls_back_on_raw_request_too_large_error(
    mock_call_llm: AsyncMock,
) -> None:
    """Raw provider request-too-large errors trigger the GPT fallback instead of crashing."""
    mock_call_llm.side_effect = [
        RuntimeError(
            "Error code: 413 - {'error': {'type': 'request_too_large', 'message': 'Request exceeds the maximum size'}}"
        ),
        _make_success_response(),
    ]
    state = _make_input_state()

    from src.agents.analysis.agent import run
    from src.config.models import MODEL_MAP

    result = await run(state, _make_sample_approved_sources())

    assert result.current_stage == "analysis"
    assert result.reference_index is not None
    assert result.session.total_llm_calls == 1
    assert mock_call_llm.await_count == 2
    assert mock_call_llm.await_args_list[0].kwargs["model"] == MODEL_MAP["analysis_agent"]
    assert mock_call_llm.await_args_list[1].kwargs["model"] == MODEL_MAP["context_agent"]


@pytest.mark.asyncio
@patch("src.agents.analysis.agent.call_llm", new_callable=AsyncMock)
async def test_analysis_handles_llm_error(mock_call_llm: AsyncMock) -> None:
    """LLMError is caught, state.errors populated, stage set to ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="claude-opus-4-6",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.analysis.agent import run

    result = await run(state, _make_sample_approved_sources())

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "analysis_agent"
    assert result.reference_index is None


@pytest.mark.asyncio
@patch("src.agents.analysis.agent.call_llm", new_callable=AsyncMock)
async def test_analysis_updates_token_counts(mock_call_llm: AsyncMock) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.analysis.agent import run

    result = await run(state, _make_sample_approved_sources())

    assert result.session.total_input_tokens == 5000
    assert result.session.total_output_tokens == 2000
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.analysis.agent.call_llm", new_callable=AsyncMock)
async def test_analysis_builds_user_message(mock_call_llm: AsyncMock) -> None:
    """User message includes approved_sources, rfp_context, and evaluation_criteria."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.analysis.agent import run

    await run(state, _make_sample_approved_sources())

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "approved_sources" in user_msg
    assert "rfp_context" in user_msg
    assert "evaluation_criteria" in user_msg
    assert len(user_msg["approved_sources"]) == 1
    assert user_msg["approved_sources"][0]["doc_id"] == "DOC-047"


@pytest.mark.asyncio
@patch("src.agents.analysis.agent.call_llm", new_callable=AsyncMock)
async def test_analysis_reference_index_has_claims(mock_call_llm: AsyncMock) -> None:
    """Parsed ReferenceIndex has claims, gaps, and source_manifest populated."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.analysis.agent import run

    result = await run(state, _make_sample_approved_sources())

    ri = result.reference_index
    assert ri is not None
    assert len(ri.claims) == 2
    assert ri.claims[0].claim_id == "CLM-0001"
    assert ri.claims[1].claim_id == "CLM-0002"
    assert ri.claims[0].confidence == 0.99
    assert ri.claims[0].category == "project_reference"
    assert len(ri.gaps) == 1
    assert ri.gaps[0].gap_id == "GAP-001"
    assert ri.gaps[0].severity == "critical"
    assert len(ri.source_manifest) == 1
    assert ri.source_manifest[0].doc_id == "DOC-047"
    assert len(ri.case_studies) == 1
