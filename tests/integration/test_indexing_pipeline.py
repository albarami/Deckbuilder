"""Integration tests for the full indexing pipeline.

Tests the complete flow: extract → dedup → chunk → embed → index →
classify → extract entities → manifest. All LLM + embedding calls mocked.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.models.enums import (
    ConfidentialityLevel,
    DocumentType,
    ExtractionQuality,
    Language,
)
from src.models.extraction import ExtractedDocument, ExtractedSlide
from src.models.indexing import IndexingOutput, QualityBreakdown
from src.services.search import index_documents

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


def _make_test_docs_dir(tmp_path: Path) -> Path:
    """Create a temp directory with minimal test files."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    # We don't need real files — we mock extract_directory
    return docs_dir


def _make_fake_docs(n: int = 3) -> list[ExtractedDocument]:
    """Create fake ExtractedDocument objects for testing."""
    docs = []
    for i in range(n):
        docs.append(ExtractedDocument(
            filepath=f"/fake/doc{i + 1}.pptx",
            filename=f"doc{i + 1}.pptx",
            file_type="pptx",
            file_size_bytes=1000 * (i + 1),
            content_hash=f"hash_{i:03d}",
            full_text=f"Document {i + 1} full text content about strategy and consulting.",
            slides=[
                ExtractedSlide(
                    slide_number=1,
                    title=f"Doc {i + 1} Title",
                    body_text=f"Content for document {i + 1}",
                    speaker_notes="",
                    layout_type="Title Slide",
                ),
            ],
            extraction_quality=ExtractionQuality.CLEAN,
        ))
    # Add an exact duplicate (same hash as doc1)
    docs.append(ExtractedDocument(
        filepath="/fake/doc1_copy.pptx",
        filename="doc1_copy.pptx",
        file_type="pptx",
        file_size_bytes=1000,
        content_hash="hash_000",  # Same as doc1
        full_text="Document 1 full text content about strategy and consulting.",
        slides=[],
        extraction_quality=ExtractionQuality.CLEAN,
    ))
    return docs


def _make_fake_classification() -> IndexingOutput:
    """Create a fake classification output."""
    return IndexingOutput(
        doc_type=DocumentType.PROPOSAL,
        domain_tags=["strategy", "consulting"],
        client_entity="Test Client",
        geography=["Saudi Arabia"],
        languages=[Language.EN],
        quality_score=4,
        quality_breakdown=QualityBreakdown(
            has_client_name=True,
            has_outcomes=True,
            has_methodology=True,
        ),
        confidentiality_level=ConfidentialityLevel.INTERNAL_ONLY,
        extraction_quality=ExtractionQuality.CLEAN,
        summary="A strategy consulting proposal.",
    )


def _make_fake_entity_result():
    """Create a fake EntityExtractionResult."""
    from src.agents.indexing.entity_extractor import EntityExtractionResult
    return EntityExtractionResult(
        people=[{
            "name": "Test Person",
            "person_type": "internal_team",
            "current_role": "Consultant",
            "company": "Strategic Gears",
        }],
        projects=[{
            "project_name": "Test Project",
            "client": "Test Client",
        }],
        clients=[{
            "name": "Test Client",
            "client_type": "government",
            "country": "Saudi Arabia",
        }],
    )


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_indexing_pipeline_end_to_end(tmp_path):
    """Full pipeline: extract → dedup → chunk → embed → index → classify → entities → manifest."""
    docs_dir = _make_test_docs_dir(tmp_path)
    cache_path = str(tmp_path / "index")
    fake_docs = _make_fake_docs(3)  # 3 unique + 1 duplicate = 4 total

    # Mock extract_directory
    with (
        patch("src.services.search.extract_directory", return_value=fake_docs),
        patch("src.services.search.EmbeddingService") as mock_embed_cls,
        patch("src.services.search.detect_exact_duplicates") as mock_exact_dedup,
        patch("src.services.search.detect_near_duplicates") as mock_near_dedup,
        patch("src.services.search.classify_directory") as mock_classify,
        patch("src.services.search.extract_entities_batch") as mock_entities,
        patch("src.services.search.merge_into_knowledge_graph") as mock_merge_kg,
        patch("src.services.search.save_knowledge_graph") as mock_save_kg,
    ):
        # Setup embedding mock
        mock_embed = MagicMock()
        mock_embed_cls.return_value = mock_embed
        # 3 unique docs → some chunks each; fake embeddings
        n_chunks = 9  # ~3 chunks per doc
        mock_embed.embed_and_cache = AsyncMock(
            return_value=np.random.randn(n_chunks, 3072).astype(np.float32)
        )

        # Setup dedup mocks
        from src.services.deduplication import DeduplicationResult
        mock_exact_dedup.return_value = [
            DeduplicationResult(doc_id="DOC-001", action="keep"),
            DeduplicationResult(doc_id="DOC-002", action="keep"),
            DeduplicationResult(doc_id="DOC-003", action="keep"),
            DeduplicationResult(
                doc_id="DOC-004", duplicate_of="DOC-001",
                similarity_score=1.0, action="skip_exact",
            ),
        ]
        mock_near_dedup.return_value = [
            DeduplicationResult(
                doc_id="DOC-003", near_duplicate_of="DOC-001",
                similarity_score=0.96, action="flag_near",
            ),
        ]

        # Setup classification mock
        fake_classification = _make_fake_classification()
        mock_classify.return_value = [
            (fake_docs[0], fake_classification),
            (fake_docs[1], fake_classification),
            (fake_docs[2], fake_classification),
        ]

        # Setup entity extraction mock
        fake_entity = _make_fake_entity_result()
        mock_entities.return_value = [fake_entity, fake_entity, fake_entity]

        # Setup knowledge graph merge mock
        from src.models.knowledge import KnowledgeGraph, PersonProfile
        mock_kg = KnowledgeGraph(
            people=[PersonProfile(
                person_id="PER-001", name="Test Person",
                person_type="internal_team",
            )],
            document_count=3,
        )
        mock_merge_kg.return_value = mock_kg

        # Run the pipeline
        manifest = await index_documents(
            docs_path=str(docs_dir),
            cache_path=cache_path,
        )

        # Verify manifest was returned (dict)
        assert isinstance(manifest, dict), "index_documents should return manifest dict"
        assert manifest["total_documents"] == 4
        assert manifest["duplicates_skipped"] == 1
        assert manifest["near_duplicates_flagged"] == 1
        assert "indexed_at" in manifest
        assert "total_chunks" in manifest
        assert "embedding_model" in manifest
        assert manifest["embedding_dimensions"] == 3072
        assert "knowledge_graph_summary" in manifest

        # Verify manifest file was saved
        manifest_path = Path(cache_path) / "manifest.json"
        assert manifest_path.exists()
        saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert saved_manifest["total_documents"] == manifest["total_documents"]

        # Verify knowledge graph was saved
        mock_save_kg.assert_called_once()

        # Verify dedup was called
        mock_exact_dedup.assert_called_once()

        # Verify classification was called with unique docs only
        mock_classify.assert_called_once()

        # Verify entities extracted
        mock_entities.assert_called_once()


@pytest.mark.asyncio
async def test_indexing_pipeline_empty_directory(tmp_path):
    """Pipeline handles empty directory gracefully."""
    docs_dir = _make_test_docs_dir(tmp_path)
    cache_path = str(tmp_path / "index")

    with patch("src.services.search.extract_directory", return_value=[]):
        result = await index_documents(
            docs_path=str(docs_dir),
            cache_path=cache_path,
        )
        # Empty dir returns empty manifest
        assert isinstance(result, dict)
        assert result["total_documents"] == 0


@pytest.mark.asyncio
async def test_indexing_pipeline_skip_entities(tmp_path):
    """Pipeline with skip_entities=True skips entity extraction."""
    docs_dir = _make_test_docs_dir(tmp_path)
    cache_path = str(tmp_path / "index")
    # _make_fake_docs(1) returns 1 unique + 1 duplicate = 2 total
    fake_docs = _make_fake_docs(1)

    with (
        patch("src.services.search.extract_directory", return_value=fake_docs),
        patch("src.services.search.EmbeddingService") as mock_embed_cls,
        patch("src.services.search.detect_exact_duplicates") as mock_dedup,
        patch("src.services.search.detect_near_duplicates") as mock_near,
        patch("src.services.search.classify_directory") as mock_classify,
    ):
        mock_embed = MagicMock()
        mock_embed_cls.return_value = mock_embed
        mock_embed.embed_and_cache = AsyncMock(
            return_value=np.random.randn(3, 3072).astype(np.float32)
        )

        from src.services.deduplication import DeduplicationResult
        mock_dedup.return_value = [
            DeduplicationResult(doc_id="DOC-001", action="keep"),
            DeduplicationResult(
                doc_id="DOC-002", duplicate_of="DOC-001",
                similarity_score=1.0, action="skip_exact",
            ),
        ]
        mock_near.return_value = []

        fake_cls = _make_fake_classification()
        mock_classify.return_value = [(fake_docs[0], fake_cls)]

        manifest = await index_documents(
            docs_path=str(docs_dir),
            cache_path=cache_path,
            skip_entities=True,
        )

        assert isinstance(manifest, dict)
        assert manifest["total_documents"] == 2  # Total including duplicates
        assert manifest["unique_documents"] == 1
        assert manifest["duplicates_skipped"] == 1
        # Knowledge graph should be empty since we skipped entities
        assert manifest["knowledge_graph_summary"]["people"] == 0


@pytest.mark.asyncio
async def test_manifest_has_per_document_entries(tmp_path):
    """Manifest includes per-document entries with classification details."""
    docs_dir = _make_test_docs_dir(tmp_path)
    cache_path = str(tmp_path / "index")
    fake_docs = _make_fake_docs(2)[:2]  # 2 unique docs

    with (
        patch("src.services.search.extract_directory", return_value=fake_docs),
        patch("src.services.search.EmbeddingService") as mock_embed_cls,
        patch("src.services.search.detect_exact_duplicates") as mock_dedup,
        patch("src.services.search.detect_near_duplicates") as mock_near,
        patch("src.services.search.classify_directory") as mock_classify,
        patch("src.services.search.extract_entities_batch") as mock_entities,
        patch("src.services.search.merge_into_knowledge_graph") as mock_merge_kg,
        patch("src.services.search.save_knowledge_graph"),
    ):
        mock_embed = MagicMock()
        mock_embed_cls.return_value = mock_embed
        mock_embed.embed_and_cache = AsyncMock(
            return_value=np.random.randn(6, 3072).astype(np.float32)
        )

        from src.services.deduplication import DeduplicationResult
        mock_dedup.return_value = [
            DeduplicationResult(doc_id="DOC-001", action="keep"),
            DeduplicationResult(doc_id="DOC-002", action="keep"),
        ]
        mock_near.return_value = []

        fake_cls = _make_fake_classification()
        mock_classify.return_value = [
            (fake_docs[0], fake_cls),
            (fake_docs[1], fake_cls),
        ]

        mock_entities.return_value = [
            _make_fake_entity_result(), _make_fake_entity_result(),
        ]
        from src.models.knowledge import KnowledgeGraph
        mock_merge_kg.return_value = KnowledgeGraph(document_count=2)

        manifest = await index_documents(
            docs_path=str(docs_dir),
            cache_path=cache_path,
        )

        assert "documents" in manifest
        assert len(manifest["documents"]) == 2
        doc_entry = manifest["documents"][0]
        assert "doc_id" in doc_entry
        assert "filename" in doc_entry
        assert "doc_type" in doc_entry
        assert "quality_score" in doc_entry
        assert "chunks" in doc_entry
        assert "dedup_status" in doc_entry


@pytest.mark.asyncio
async def test_manifest_classifications_summary(tmp_path):
    """Manifest has classification summary with doc type counts."""
    docs_dir = _make_test_docs_dir(tmp_path)
    cache_path = str(tmp_path / "index")
    fake_docs = _make_fake_docs(2)[:2]

    with (
        patch("src.services.search.extract_directory", return_value=fake_docs),
        patch("src.services.search.EmbeddingService") as mock_embed_cls,
        patch("src.services.search.detect_exact_duplicates") as mock_dedup,
        patch("src.services.search.detect_near_duplicates") as mock_near,
        patch("src.services.search.classify_directory") as mock_classify,
        patch("src.services.search.extract_entities_batch") as mock_entities,
        patch("src.services.search.merge_into_knowledge_graph") as mock_merge_kg,
        patch("src.services.search.save_knowledge_graph"),
    ):
        mock_embed = MagicMock()
        mock_embed_cls.return_value = mock_embed
        mock_embed.embed_and_cache = AsyncMock(
            return_value=np.random.randn(6, 3072).astype(np.float32)
        )

        from src.services.deduplication import DeduplicationResult
        mock_dedup.return_value = [
            DeduplicationResult(doc_id="DOC-001", action="keep"),
            DeduplicationResult(doc_id="DOC-002", action="keep"),
        ]
        mock_near.return_value = []

        fake_cls = _make_fake_classification()
        mock_classify.return_value = [
            (fake_docs[0], fake_cls),
            (fake_docs[1], fake_cls),
        ]

        mock_entities.return_value = [
            _make_fake_entity_result(), _make_fake_entity_result(),
        ]
        from src.models.knowledge import KnowledgeGraph
        mock_merge_kg.return_value = KnowledgeGraph(document_count=2)

        manifest = await index_documents(
            docs_path=str(docs_dir),
            cache_path=cache_path,
        )

        assert "classifications" in manifest
        assert manifest["classifications"]["proposal"] == 2
