"""Integration tests for the search service — index, search, and retrieve."""

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from src.models.extraction import (
    ExtractedDocument,
    ExtractedPage,
    ExtractedSlide,
)
from src.services.embeddings import EMBEDDING_DIM
from src.services.search import NumpySearchBackend, SearchResult
from src.utils.chunking import chunk_document

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


def _make_docs() -> list[ExtractedDocument]:
    """Create test documents for indexing."""
    return [
        ExtractedDocument(
            filepath="/test/sap_migration.pptx",
            filename="sap_migration.pptx",
            file_type="pptx",
            content_hash="hash1",
            slides=[
                ExtractedSlide(
                    slide_number=1,
                    title="SAP HANA Migration",
                    body_text="Strategic Gears delivered SAP HANA migration for SIDF.",
                ),
                ExtractedSlide(
                    slide_number=2,
                    title="Results",
                    body_text="Migration completed in 6 months with zero downtime.",
                ),
            ],
            full_text="SAP HANA Migration\nStrategic Gears delivered SAP HANA migration for SIDF.\n\n"
            "Results\nMigration completed in 6 months with zero downtime.",
        ),
        ExtractedDocument(
            filepath="/test/team_profiles.pdf",
            filename="team_profiles.pdf",
            file_type="pdf",
            content_hash="hash2",
            pages=[
                ExtractedPage(
                    page_number=1,
                    text="Team profile: Ahmed is a senior SAP consultant with 10 years experience.",
                ),
                ExtractedPage(
                    page_number=2,
                    text="Team profile: Sarah specializes in digital transformation strategy.",
                ),
            ],
            full_text="Team profile: Ahmed is a senior SAP consultant with 10 years experience.\n\n"
            "Team profile: Sarah specializes in digital transformation strategy.",
        ),
    ]


def _make_fake_embeddings(n: int) -> np.ndarray:
    """Create fake embeddings with enough variation for similarity tests."""
    rng = np.random.default_rng(42)
    embeddings = rng.random((n, EMBEDDING_DIM)).astype(np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / norms


# ──────────────────────────────────────────────────────────────
# NumpySearchBackend Tests
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_numpy_backend_indexes_and_retrieves() -> None:
    """NumpySearchBackend can index chunks and retrieve by query."""
    docs = _make_docs()
    chunks = []
    for idx, doc in enumerate(docs, start=1):
        chunks.extend(chunk_document(doc, f"DOC-{idx:03d}"))

    embeddings = _make_fake_embeddings(len(chunks))
    backend = NumpySearchBackend()

    # Index
    count = await backend.index(chunks, embeddings)
    assert count == len(chunks)

    # Search (mock the query embedding)
    query_embedding = _make_fake_embeddings(1)

    with patch.object(backend, "_embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = query_embedding[0]
        results = await backend.search("SAP migration", top_k=5)

    assert len(results) > 0
    assert len(results) <= 5
    assert all(isinstance(r, SearchResult) for r in results)
    # Results should be sorted by score descending
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_search_returns_ranked_results() -> None:
    """Search results are ranked by cosine similarity score."""
    docs = _make_docs()
    chunks = []
    for idx, doc in enumerate(docs, start=1):
        chunks.extend(chunk_document(doc, f"DOC-{idx:03d}"))

    embeddings = _make_fake_embeddings(len(chunks))
    backend = NumpySearchBackend()
    await backend.index(chunks, embeddings)

    # Create a query embedding that's more similar to the first chunk
    query_embedding = embeddings[0] + np.random.default_rng(99).random(EMBEDDING_DIM).astype(np.float32) * 0.1
    query_embedding = query_embedding / np.linalg.norm(query_embedding)

    with patch.object(backend, "_embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = query_embedding
        results = await backend.search("test query", top_k=3)

    assert len(results) <= 3
    assert results[0].score >= results[-1].score
    # First result should be highly similar since we biased toward chunk 0
    assert results[0].score > 0.5


@pytest.mark.asyncio
async def test_search_result_format() -> None:
    """Search results match Retrieval Ranker expected format."""
    docs = _make_docs()
    chunks = []
    for idx, doc in enumerate(docs, start=1):
        chunks.extend(chunk_document(doc, f"DOC-{idx:03d}"))

    embeddings = _make_fake_embeddings(len(chunks))
    backend = NumpySearchBackend()
    await backend.index(chunks, embeddings)

    with patch.object(backend, "_embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = _make_fake_embeddings(1)[0]
        results = await backend.search("query", top_k=1)

    r = results[0]
    assert hasattr(r, "doc_id")
    assert hasattr(r, "chunk_id")
    assert hasattr(r, "title")
    assert hasattr(r, "excerpt")
    assert hasattr(r, "score")
    assert hasattr(r, "metadata")
    assert isinstance(r.metadata, dict)


@pytest.mark.asyncio
async def test_keyword_filtering() -> None:
    """Search with doc_type filter returns only matching documents."""
    docs = _make_docs()
    chunks = []
    for idx, doc in enumerate(docs, start=1):
        chunks.extend(chunk_document(doc, f"DOC-{idx:03d}"))

    embeddings = _make_fake_embeddings(len(chunks))
    backend = NumpySearchBackend()
    await backend.index(chunks, embeddings)

    with patch.object(backend, "_embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = _make_fake_embeddings(1)[0]
        results = await backend.search("query", top_k=20, filters={"doc_type": "pdf"})

    # All results should be from PDF documents
    for r in results:
        assert r.metadata.get("doc_type") == "pdf", f"Expected pdf but got {r.metadata.get('doc_type')}"


@pytest.mark.asyncio
async def test_empty_index_returns_empty() -> None:
    """Searching an empty index returns empty results."""
    backend = NumpySearchBackend()

    with patch.object(backend, "_embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = _make_fake_embeddings(1)[0]
        results = await backend.search("anything", top_k=5)

    assert results == []
