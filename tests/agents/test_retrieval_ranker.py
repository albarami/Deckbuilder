"""Tests for the Retrieval Ranker — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
from src.models.retrieval import ExcludedDocument, RankedSourcesOutput
from src.models.rfp import RFPContext
from src.models.state import DeckForgeState, RetrievedSource
from src.services.llm import LLMError, LLMResponse


def _make_sample_rfp_context() -> RFPContext:
    """Minimal valid RFPContext for test fixtures."""
    return RFPContext(
        rfp_name=BilingualText(en="Renewal of Support for SAP Systems"),
        issuing_entity=BilingualText(en="Saudi Industrial Development Fund"),
        mandate=BilingualText(en="Renew and supply SAP licenses for 24 months."),
    )


def _make_sample_search_results() -> list[dict]:
    """Sample raw search results from Azure AI Search."""
    return [
        {
            "doc_id": "DOC-047",
            "title": "SIDF SAP Migration — Project Completion Report",
            "excerpt": "SAP HANA migration for SIDF covering 12 modules, completed 2023.",
            "metadata": {
                "doc_type": "case_study",
                "domain_tags": ["SAP", "migration"],
                "quality_score": 4,
                "last_modified": "2023-12-15",
            },
            "search_score": 0.87,
        },
        {
            "doc_id": "DOC-022",
            "title": "SIDF SAP Migration — Draft v1",
            "excerpt": "Early draft of SAP migration project report.",
            "metadata": {
                "doc_type": "case_study",
                "domain_tags": ["SAP"],
                "quality_score": 2,
                "last_modified": "2022-06-01",
            },
            "search_score": 0.65,
        },
    ]


def _make_ranked_sources_output() -> RankedSourcesOutput:
    """Sample RankedSourcesOutput from LLM."""
    return RankedSourcesOutput(
        ranked_sources=[
            RetrievedSource(
                doc_id="DOC-047",
                title="SIDF SAP Migration — Project Completion Report",
                relevance_score=95,
                summary="Directly relevant: SAP HANA migration for SIDF.",
                matched_criteria=["Technical > Previous Experience"],
                is_duplicate=False,
                duplicate_of=None,
                recommendation="include",
            ),
        ],
        excluded_documents=[
            ExcludedDocument(
                doc_id="DOC-022",
                reason="Duplicate of DOC-047 (older version)",
            ),
        ],
    )


def _make_success_response() -> LLMResponse:
    """LLMResponse wrapping valid RankedSourcesOutput."""
    return LLMResponse(
        parsed=_make_ranked_sources_output(),
        input_tokens=300,
        output_tokens=150,
        model="gpt-5.4",
        latency_ms=700.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with rfp_context populated for Ranker input."""
    return DeckForgeState(
        rfp_context=_make_sample_rfp_context(),
    )


@pytest.mark.asyncio
@patch("src.agents.retrieval.ranker.call_llm", new_callable=AsyncMock)
async def test_ranker_happy_path(mock_call_llm: AsyncMock) -> None:
    """Search results + rfp_context produces ranked sources in state."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.ranker import run

    result = await run(state, _make_sample_search_results())

    assert result.current_stage == "source_review"
    assert len(result.retrieved_sources) == 1
    assert result.retrieved_sources[0].doc_id == "DOC-047"
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.retrieval.ranker.call_llm", new_callable=AsyncMock)
async def test_ranker_uses_model_map(mock_call_llm: AsyncMock) -> None:
    """Agent calls call_llm with MODEL_MAP['retrieval_ranker'], not a hardcoded string."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.ranker import run
    from src.config.models import MODEL_MAP

    await run(state, _make_sample_search_results())

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["retrieval_ranker"]


@pytest.mark.asyncio
@patch("src.agents.retrieval.ranker.call_llm", new_callable=AsyncMock)
async def test_ranker_uses_system_prompt(mock_call_llm: AsyncMock) -> None:
    """Agent passes RANKER_SYSTEM_PROMPT from prompts.py to call_llm."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.ranker import run

    await run(state, _make_sample_search_results())

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith(
        "You are the Retrieval Source Ranker"
    )


@pytest.mark.asyncio
@patch("src.agents.retrieval.ranker.call_llm", new_callable=AsyncMock)
async def test_ranker_handles_llm_error(mock_call_llm: AsyncMock) -> None:
    """LLMError is caught, state.errors populated, stage set to ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="gpt-5.4",
        attempts=4,
        last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.retrieval.ranker import run

    result = await run(state, _make_sample_search_results())

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "retrieval_ranker"
    assert len(result.retrieved_sources) == 0


@pytest.mark.asyncio
@patch("src.agents.retrieval.ranker.call_llm", new_callable=AsyncMock)
async def test_ranker_updates_token_counts(mock_call_llm: AsyncMock) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.ranker import run

    result = await run(state, _make_sample_search_results())

    assert result.session.total_input_tokens == 300
    assert result.session.total_output_tokens == 150
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.retrieval.ranker.call_llm", new_callable=AsyncMock)
async def test_ranker_builds_user_message(mock_call_llm: AsyncMock) -> None:
    """User message sent to LLM includes rfp_context and search_results."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()
    search_results = _make_sample_search_results()

    from src.agents.retrieval.ranker import run

    await run(state, search_results)

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "rfp_context" in user_msg
    assert "search_results" in user_msg
    assert len(user_msg["search_results"]) == 2
    assert user_msg["search_results"][0]["doc_id"] == "DOC-047"


@pytest.mark.asyncio
@patch("src.agents.retrieval.ranker.call_llm", new_callable=AsyncMock)
async def test_ranker_maps_to_retrieved_sources(mock_call_llm: AsyncMock) -> None:
    """ranked_sources correctly mapped to RetrievedSource objects in state."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.retrieval.ranker import run

    result = await run(state, _make_sample_search_results())

    assert len(result.retrieved_sources) == 1
    src = result.retrieved_sources[0]
    assert isinstance(src, RetrievedSource)
    assert src.doc_id == "DOC-047"
    assert src.relevance_score == 95
    assert src.summary == "Directly relevant: SAP HANA migration for SIDF."
    assert "Technical > Previous Experience" in src.matched_criteria
    assert src.is_duplicate is False
    assert src.recommendation == "include"
