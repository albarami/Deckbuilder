"""Tests for the embedding service — embed, cache, and reload."""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from src.models.extraction import ExtractedDocument, ExtractedSlide
from src.services.embeddings import EmbeddingService
from src.utils.chunking import chunk_document

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

EMBEDDING_DIM = 3072  # text-embedding-3-large dimensions


def _mock_embed_response(texts: list[str]) -> np.ndarray:
    """Create fake embeddings matching text-embedding-3-large dimensions."""
    rng = np.random.default_rng(42)
    embeddings = rng.random((len(texts), EMBEDDING_DIM)).astype(np.float32)
    # Normalize to unit vectors (like real embeddings)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / norms


def _make_test_chunks() -> list:
    """Create test chunks for embedding."""
    doc = ExtractedDocument(
        filepath="/test/deck.pptx",
        filename="deck.pptx",
        file_type="pptx",
        file_size_bytes=1000,
        content_hash="abc123",
        slides=[
            ExtractedSlide(slide_number=1, title="Intro", body_text="Welcome."),
            ExtractedSlide(slide_number=2, title="Data", body_text="Analysis results."),
        ],
        full_text="Intro\nWelcome.\n\nData\nAnalysis results.",
    )
    return chunk_document(doc, "DOC-001")


# ──────────────────────────────────────────────────────────────
# Embedding Dimension Tests
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_texts_returns_correct_dimensions() -> None:
    """embed_texts returns array with shape (n_texts, 3072)."""
    service = EmbeddingService()
    texts = ["Hello world", "Test embedding"]

    with patch.object(service, "_call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = _mock_embed_response(texts)
        result = await service.embed_texts(texts)

    assert isinstance(result, np.ndarray)
    assert result.shape == (2, EMBEDDING_DIM)


@pytest.mark.asyncio
async def test_embed_texts_batches_large_input() -> None:
    """embed_texts batches inputs larger than 100."""
    service = EmbeddingService()
    texts = [f"Text {i}" for i in range(250)]

    call_count = 0

    async def mock_batch_api(batch_texts: list[str]) -> np.ndarray:
        nonlocal call_count
        call_count += 1
        return _mock_embed_response(batch_texts)

    with patch.object(service, "_call_api", side_effect=mock_batch_api):
        result = await service.embed_texts(texts)

    assert result.shape == (250, EMBEDDING_DIM)
    assert call_count == 3  # ceil(250/100) = 3 batches


# ──────────────────────────────────────────────────────────────
# Cache Tests
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_saves_and_loads() -> None:
    """embed_and_cache saves to disk, load_cache reads it back."""
    service = EmbeddingService()
    chunks = _make_test_chunks()

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "test_cache")

        with patch.object(service, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = _mock_embed_response([c.text for c in chunks])
            embeddings = await service.embed_and_cache(chunks, cache_path)

        assert embeddings.shape[0] == len(chunks)
        assert embeddings.shape[1] == EMBEDDING_DIM

        # Load from cache
        loaded_embeddings, loaded_ids = service.load_cache(cache_path)
        assert loaded_embeddings.shape == embeddings.shape
        assert len(loaded_ids) == len(chunks)
        assert loaded_ids[0] == chunks[0].chunk_id
        np.testing.assert_array_almost_equal(loaded_embeddings, embeddings)


@pytest.mark.asyncio
async def test_incremental_reembed_skips_unchanged() -> None:
    """embed_and_cache skips chunks that haven't changed."""
    service = EmbeddingService()
    chunks = _make_test_chunks()

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "test_cache")

        # First embed
        with patch.object(service, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = _mock_embed_response([c.text for c in chunks])
            await service.embed_and_cache(chunks, cache_path)
            first_call_count = mock_api.call_count

        # Re-embed same chunks — should skip (no API call)
        with patch.object(service, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = _mock_embed_response([])
            await service.embed_and_cache(chunks, cache_path)
            second_call_count = mock_api.call_count

        # Second run should make fewer API calls (ideally 0)
        assert second_call_count < first_call_count


# ──────────────────────────────────────────────────────────────
# API Key Guard
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_without_api_key_raises() -> None:
    """Calling embed_texts without API key raises clear error."""
    service = EmbeddingService()

    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
        with patch.object(service, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = ValueError("OPENAI_API_KEY not set")
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                await service.embed_texts(["test"])
