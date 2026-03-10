"""Tests for the deduplication service — exact and near-duplicate detection."""

import numpy as np

from src.models.extraction import ExtractedDocument
from src.services.deduplication import (
    DeduplicationResult,
    detect_exact_duplicates,
    detect_near_duplicates,
)

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


def _make_doc(filename: str, content_hash: str, full_text: str = "") -> ExtractedDocument:
    return ExtractedDocument(
        filepath=f"/test/{filename}",
        filename=filename,
        file_type="pptx",
        file_size_bytes=1000,
        content_hash=content_hash,
        full_text=full_text,
    )


# ──────────────────────────────────────────────────────────────
# Exact Duplicate Tests
# ──────────────────────────────────────────────────────────────


def test_exact_duplicate_detection() -> None:
    """Documents with same content_hash are flagged as exact duplicates."""
    docs = [
        _make_doc("original.pptx", "hash_A", "Some content"),
        _make_doc("copy.pptx", "hash_A", "Some content"),  # Same hash
        _make_doc("different.pptx", "hash_B", "Different content"),
    ]

    results = detect_exact_duplicates(docs)
    assert len(results) == 3

    # First occurrence should be "keep"
    r0 = next(r for r in results if r.doc_id == "DOC-001")
    assert r0.action == "keep"
    assert r0.duplicate_of is None

    # Second occurrence (same hash) should be "skip_exact"
    r1 = next(r for r in results if r.doc_id == "DOC-002")
    assert r1.action == "skip_exact"
    assert r1.duplicate_of == "DOC-001"
    assert r1.similarity_score == 1.0

    # Different hash should be "keep"
    r2 = next(r for r in results if r.doc_id == "DOC-003")
    assert r2.action == "keep"
    assert r2.duplicate_of is None


def test_exact_duplicate_multiple_copies() -> None:
    """Multiple copies of same doc all point to first occurrence."""
    docs = [
        _make_doc("v1.pptx", "same_hash"),
        _make_doc("v2.pptx", "same_hash"),
        _make_doc("v3.pptx", "same_hash"),
    ]

    results = detect_exact_duplicates(docs)
    keeps = [r for r in results if r.action == "keep"]
    skips = [r for r in results if r.action == "skip_exact"]

    assert len(keeps) == 1
    assert len(skips) == 2
    assert all(r.duplicate_of == "DOC-001" for r in skips)


# ──────────────────────────────────────────────────────────────
# Near-Duplicate Tests
# ──────────────────────────────────────────────────────────────


def test_near_duplicate_detection() -> None:
    """Embeddings with cosine > 0.95 are flagged as near duplicates."""
    rng = np.random.default_rng(42)
    dim = 3072

    # Create 3 embeddings: first two are near-identical, third is different
    base = rng.random(dim).astype(np.float32)
    base = base / np.linalg.norm(base)

    # Near duplicate: add tiny noise
    near_dup = base + rng.random(dim).astype(np.float32) * 0.01
    near_dup = near_dup / np.linalg.norm(near_dup)

    # Different vector
    different = rng.random(dim).astype(np.float32)
    different = different / np.linalg.norm(different)

    embeddings = np.vstack([base, near_dup, different])
    chunk_ids = ["DOC-001_L1", "DOC-002_L1", "DOC-003_L1"]

    results = detect_near_duplicates(embeddings, chunk_ids, threshold=0.95)

    # DOC-002 should be flagged as near-duplicate of DOC-001
    r1 = next(r for r in results if r.doc_id == "DOC-002")
    assert r1.action == "flag_near"
    assert r1.near_duplicate_of == "DOC-001"
    assert r1.similarity_score > 0.95

    # DOC-003 should be "keep"
    r2 = next(r for r in results if r.doc_id == "DOC-003")
    assert r2.action == "keep"


def test_unique_documents_kept() -> None:
    """All unique documents are marked 'keep'."""
    rng = np.random.default_rng(42)
    dim = 3072

    # Create 3 truly different embeddings
    embeddings = np.vstack([
        rng.random(dim).astype(np.float32),
        rng.random(dim).astype(np.float32),
        rng.random(dim).astype(np.float32),
    ])
    # Normalize
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms

    chunk_ids = ["DOC-001_L1", "DOC-002_L1", "DOC-003_L1"]
    results = detect_near_duplicates(embeddings, chunk_ids, threshold=0.95)

    assert all(r.action == "keep" for r in results)
    assert all(r.near_duplicate_of is None for r in results)


def test_deduplication_result_model() -> None:
    """DeduplicationResult model validates correctly."""
    result = DeduplicationResult(
        doc_id="DOC-001",
        duplicate_of=None,
        near_duplicate_of="DOC-002",
        similarity_score=0.97,
        action="flag_near",
    )
    assert result.doc_id == "DOC-001"
    assert result.action == "flag_near"
    assert result.similarity_score == 0.97
