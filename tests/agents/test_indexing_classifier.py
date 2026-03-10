"""Tests for the Indexing Classifier agent."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.indexing.classifier import classify_directory, classify_document
from src.agents.indexing.prompts import SYSTEM_PROMPT
from src.config.models import MODEL_MAP
from src.models.enums import (
    ConfidentialityLevel,
    DocumentType,
    ExtractionQuality,
    Language,
)
from src.models.extraction import ExtractedDocument, ExtractedSlide
from src.models.indexing import IndexingOutput, QualityBreakdown
from src.services.llm import LLMError, LLMResponse

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


def _make_test_doc() -> ExtractedDocument:
    """Create a test document for classification."""
    return ExtractedDocument(
        filepath="/test/sap_migration.pptx",
        filename="sap_migration.pptx",
        file_type="pptx",
        file_size_bytes=5000,
        content_hash="abc123",
        slides=[
            ExtractedSlide(
                slide_number=1,
                title="SAP HANA Migration",
                body_text="Strategic Gears delivered SAP HANA migration for SIDF.",
            ),
        ],
        full_text="SAP HANA Migration\nStrategic Gears delivered SAP HANA migration for SIDF.",
    )


def _make_indexing_output() -> IndexingOutput:
    """Create a sample IndexingOutput for mocking."""
    return IndexingOutput(
        doc_type=DocumentType.CASE_STUDY,
        domain_tags=["SAP", "Digital Transformation"],
        client_entity="Saudi Industrial Development Fund",
        geography=["KSA"],
        frameworks_mentioned=["SAP Activate"],
        key_people=["Ahmed (PM)"],
        languages=[Language.EN],
        quality_score=4,
        quality_breakdown=QualityBreakdown(
            has_client_name=True,
            has_outcomes=True,
            has_methodology=True,
            has_data=True,
            is_complete_current=False,
        ),
        confidentiality_level=ConfidentialityLevel.CLIENT_CONFIDENTIAL,
        extraction_quality=ExtractionQuality.CLEAN,
        duplicate_likelihood="none",
        summary="SAP HANA migration case study for SIDF.",
    )


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classifier_uses_model_map() -> None:
    """Classifier uses MODEL_MAP['indexing_classifier'] (GPT-5.4)."""
    doc = _make_test_doc()
    mock_output = _make_indexing_output()

    with patch("src.agents.indexing.classifier.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = LLMResponse(
            parsed=mock_output,
            input_tokens=100,
            output_tokens=200,
            model=MODEL_MAP["indexing_classifier"],
            latency_ms=500.0,
        )
        await classify_document(doc, "DOC-001")

        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args
        assert call_kwargs.kwargs["model"] == MODEL_MAP["indexing_classifier"]


@pytest.mark.asyncio
async def test_classifier_returns_indexing_output() -> None:
    """classify_document returns a valid IndexingOutput."""
    doc = _make_test_doc()
    mock_output = _make_indexing_output()

    with patch("src.agents.indexing.classifier.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = LLMResponse(
            parsed=mock_output,
            input_tokens=100,
            output_tokens=200,
            model="gpt-5.4",
            latency_ms=500.0,
        )
        result = await classify_document(doc, "DOC-001")

    assert isinstance(result, IndexingOutput)
    assert result.doc_type == DocumentType.CASE_STUDY
    assert result.quality_score == 4
    assert "SAP" in result.domain_tags


@pytest.mark.asyncio
async def test_classifier_uses_system_prompt() -> None:
    """Classifier passes the correct system prompt."""
    doc = _make_test_doc()
    mock_output = _make_indexing_output()

    with patch("src.agents.indexing.classifier.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = LLMResponse(
            parsed=mock_output,
            input_tokens=100,
            output_tokens=200,
            model="gpt-5.4",
            latency_ms=500.0,
        )
        await classify_document(doc, "DOC-001")

        call_kwargs = mock_llm.call_args
        system = call_kwargs.kwargs["system_prompt"]
        assert system.startswith("You are classifying a document")
        assert "RULES:" in system
        assert system == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_classifier_handles_llm_error() -> None:
    """classify_document returns fallback IndexingOutput on LLM failure."""
    doc = _make_test_doc()

    with patch("src.agents.indexing.classifier.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = LLMError(
            model="gpt-5.4",
            attempts=4,
            last_error=Exception("API timeout"),
        )
        result = await classify_document(doc, "DOC-001")

    # Should return a fallback, not crash
    assert isinstance(result, IndexingOutput)
    assert result.doc_type == DocumentType.OTHER
    assert result.quality_score == 0
    assert "classification failed" in result.summary.lower()


@pytest.mark.asyncio
async def test_classifier_builds_user_message() -> None:
    """User message contains doc_id, filename, content_type, and content text."""
    doc = _make_test_doc()
    mock_output = _make_indexing_output()

    with patch("src.agents.indexing.classifier.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = LLMResponse(
            parsed=mock_output,
            input_tokens=100,
            output_tokens=200,
            model="gpt-5.4",
            latency_ms=500.0,
        )
        await classify_document(doc, "DOC-001")

        call_kwargs = mock_llm.call_args
        user_msg = call_kwargs.kwargs["user_message"]
        assert "DOC-001" in user_msg
        assert "sap_migration.pptx" in user_msg
        assert "pptx" in user_msg
        assert "SAP HANA" in user_msg


@pytest.mark.asyncio
async def test_classify_directory_processes_all_docs() -> None:
    """classify_directory processes all documents and returns tuples."""
    docs = [_make_test_doc(), _make_test_doc()]
    mock_output = _make_indexing_output()

    with patch("src.agents.indexing.classifier.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = LLMResponse(
            parsed=mock_output,
            input_tokens=100,
            output_tokens=200,
            model="gpt-5.4",
            latency_ms=500.0,
        )
        results = await classify_directory(docs)

    assert len(results) == 2
    for doc, output in results:
        assert isinstance(doc, ExtractedDocument)
        assert isinstance(output, IndexingOutput)
