"""Deduplication service — exact and near-duplicate detection.

Exact duplicates: SHA-256 content_hash comparison.
Near duplicates: Cosine similarity > threshold on Level 1 embeddings.
"""

import logging
import re

import numpy as np

from src.models.common import DeckForgeBaseModel
from src.models.extraction import ExtractedDocument

logger = logging.getLogger(__name__)


class DeduplicationResult(DeckForgeBaseModel):
    """Result of duplicate detection for a single document."""

    doc_id: str
    duplicate_of: str | None = None  # DOC-NNN if exact duplicate
    near_duplicate_of: str | None = None  # DOC-NNN if cosine > threshold
    similarity_score: float = 0.0
    action: str = "keep"  # "keep" | "skip_exact" | "flag_near"


def detect_exact_duplicates(
    docs: list[ExtractedDocument],
) -> list[DeduplicationResult]:
    """SHA-256 hash comparison. Same hash = exact duplicate.

    The first occurrence of each hash is kept. Subsequent duplicates
    are marked skip_exact with duplicate_of pointing to the first occurrence.

    Args:
        docs: List of ExtractedDocument objects to check.

    Returns:
        List of DeduplicationResult, one per document.
    """
    results: list[DeduplicationResult] = []
    hash_to_first_id: dict[str, str] = {}

    for idx, doc in enumerate(docs, start=1):
        doc_id = f"DOC-{idx:03d}"

        if not doc.content_hash:
            results.append(DeduplicationResult(doc_id=doc_id, action="keep"))
            continue

        if doc.content_hash in hash_to_first_id:
            first_id = hash_to_first_id[doc.content_hash]
            results.append(DeduplicationResult(
                doc_id=doc_id,
                duplicate_of=first_id,
                similarity_score=1.0,
                action="skip_exact",
            ))
            logger.info(
                "Exact duplicate: %s (%s) == %s",
                doc_id, doc.filename, first_id,
            )
        else:
            hash_to_first_id[doc.content_hash] = doc_id
            results.append(DeduplicationResult(doc_id=doc_id, action="keep"))

    return results


def detect_near_duplicates(
    embeddings: np.ndarray,
    chunk_ids: list[str],
    threshold: float = 0.95,
) -> list[DeduplicationResult]:
    """Cosine similarity on Level 1 embeddings. > threshold = near duplicate.

    Only considers L1 (full-document) embeddings. Filters chunk_ids
    to those ending in _L1.

    Args:
        embeddings: Full embedding matrix (all levels).
        chunk_ids: Corresponding chunk IDs.
        threshold: Cosine similarity threshold (default 0.95).

    Returns:
        List of DeduplicationResult for L1 chunks only.
    """
    # Filter to L1 embeddings only
    l1_indices = [i for i, cid in enumerate(chunk_ids) if cid.endswith("_L1")]

    if not l1_indices:
        return []

    l1_embeddings = embeddings[l1_indices]
    l1_ids = [chunk_ids[i] for i in l1_indices]

    # Extract doc_ids from chunk_ids (DOC-001_L1 → DOC-001)
    doc_ids = [re.sub(r"_L1$", "", cid) for cid in l1_ids]

    # Normalize embeddings
    norms = np.linalg.norm(l1_embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normed = l1_embeddings / norms

    # Compute pairwise cosine similarity matrix
    sim_matrix = normed @ normed.T

    results: list[DeduplicationResult] = []
    flagged: set[int] = set()

    for i in range(len(doc_ids)):
        if i in flagged:
            continue

        # Check if this doc is a near-duplicate of any earlier doc
        best_sim = 0.0
        best_match: int | None = None

        for j in range(i):
            if j in flagged:
                continue
            sim = float(sim_matrix[i, j])
            if sim > threshold and sim > best_sim:
                best_sim = sim
                best_match = j

        if best_match is not None:
            results.append(DeduplicationResult(
                doc_id=doc_ids[i],
                near_duplicate_of=doc_ids[best_match],
                similarity_score=round(best_sim, 4),
                action="flag_near",
            ))
            flagged.add(i)
            logger.info(
                "Near duplicate: %s ~ %s (cosine=%.4f)",
                doc_ids[i], doc_ids[best_match], best_sim,
            )
        else:
            results.append(DeduplicationResult(
                doc_id=doc_ids[i],
                action="keep",
            ))

    return results
