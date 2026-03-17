"""Search service with backend abstraction for vector search.

Architecture:
- SearchBackend Protocol: swap local numpy for Azure AI Search
- NumpySearchBackend: Local cosine similarity search (dev/test)
- AzureAISearchBackend: Production stub (implemented in M12)
- index_documents(): Full 9-step pipeline with manifest output
- semantic_search(): Query the index, return Retrieval Ranker format

Backward compatibility: local_search() and load_documents() preserved.
"""

import json
import logging
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import numpy as np
from pydantic import Field

from src.agents.indexing.classifier import classify_directory
from src.agents.indexing.entity_extractor import (
    extract_entities_batch,
    merge_into_knowledge_graph,
    save_knowledge_graph,
)
from src.config.settings import get_settings
from src.models.common import DeckForgeBaseModel
from src.models.knowledge import KnowledgeGraph
from src.models.retrieval import SearchQuery
from src.services.deduplication import (
    detect_exact_duplicates,
    detect_near_duplicates,
)
from src.services.embeddings import EMBEDDING_DIM, EMBEDDING_MODEL, EmbeddingService
from src.utils.chunking import DocumentChunk, chunk_directory
from src.utils.extractors import extract_directory

logger = logging.getLogger(__name__)

DEFAULT_DOCS_PATH = os.environ.get(
    "KNOWLEDGE_DOCS_PATH",
    get_settings().local_docs_path,
)
DEFAULT_CACHE_PATH = os.environ.get(
    "KNOWLEDGE_CACHE_PATH",
    "./state/index/",
)


# ──────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────


class SearchResult(DeckForgeBaseModel):
    """A single search result with relevance score."""

    doc_id: str
    chunk_id: str
    title: str
    excerpt: str
    score: float
    metadata: dict = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# Backend Protocol
# ──────────────────────────────────────────────────────────────


class SearchBackend(Protocol):
    """Abstract search backend — local numpy or Azure AI Search."""

    async def index(
        self,
        chunks: list[DocumentChunk],
        embeddings: np.ndarray,
    ) -> int: ...

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]: ...


# ──────────────────────────────────────────────────────────────
# Numpy Search Backend — local vector search
# ──────────────────────────────────────────────────────────────


class NumpySearchBackend:
    """Local vector search using numpy cosine similarity.

    Stores embeddings in memory, chunk metadata alongside.
    Supports vector similarity search AND metadata filtering.
    """

    def __init__(self) -> None:
        self._embeddings: np.ndarray | None = None
        self._chunks: list[DocumentChunk] = []
        self._embedding_service = EmbeddingService()

    async def _embed_query(self, query: str) -> np.ndarray:
        """Embed a query string. Override in tests via mock."""
        result = await self._embedding_service.embed_texts([query])
        return np.asarray(result[0])

    async def index(
        self,
        chunks: list[DocumentChunk],
        embeddings: np.ndarray,
    ) -> int:
        """Index chunks with their embeddings.

        Args:
            chunks: Document chunks to index.
            embeddings: Numpy array of shape (len(chunks), dim).

        Returns:
            Number of chunks indexed.
        """
        self._chunks = list(chunks)
        self._embeddings = embeddings.copy()
        logger.info("Indexed %d chunks", len(chunks))
        return len(chunks)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """Search indexed chunks by cosine similarity.

        Args:
            query: Search query text.
            top_k: Maximum results to return.
            filters: Optional metadata filters (e.g., {"doc_type": "pdf"}).

        Returns:
            List of SearchResult sorted by score descending.
        """
        if self._embeddings is None or len(self._chunks) == 0:
            return []

        query_embedding = await self._embed_query(query)

        # Cosine similarity: dot product of normalized vectors
        # Normalize stored embeddings
        norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)  # avoid division by zero
        normed_embeddings = self._embeddings / norms

        # Normalize query
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm

        # Compute similarities
        similarities = normed_embeddings @ query_embedding

        # Apply filters
        valid_indices = list(range(len(self._chunks)))
        if filters:
            valid_indices = [
                i for i in valid_indices
                if self._matches_filters(self._chunks[i], filters)
            ]

        if not valid_indices:
            return []

        # Get top_k from valid indices
        valid_sims = [(i, float(similarities[i])) for i in valid_indices]
        valid_sims.sort(key=lambda x: x[1], reverse=True)
        top_results = valid_sims[:top_k]

        results: list[SearchResult] = []
        for idx, score in top_results:
            chunk = self._chunks[idx]
            results.append(SearchResult(
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                title=chunk.doc_title,
                excerpt=chunk.text[:500],
                score=round(score, 4),
                metadata={
                    "doc_type": chunk.doc_type,
                    "level": chunk.level,
                    **chunk.metadata,
                },
            ))

        return results

    @staticmethod
    def _matches_filters(chunk: DocumentChunk, filters: dict) -> bool:
        """Check if a chunk matches all metadata filters."""
        for key, value in filters.items():
            if key == "doc_type" and chunk.doc_type != value:
                return False
            if key == "level" and chunk.level != value:
                return False
            if key in chunk.metadata and chunk.metadata[key] != value:
                return False
        return True

    def save(self, path: str) -> None:
        """Save index to disk."""
        index_dir = Path(path)
        index_dir.mkdir(parents=True, exist_ok=True)

        if self._embeddings is not None:
            np.save(str(index_dir / "embeddings.npy"), self._embeddings)

        meta = []
        for chunk in self._chunks:
            meta.append(chunk.model_dump())

        with open(index_dir / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, default=str)

    def load(self, path: str) -> None:
        """Load index from disk."""
        index_dir = Path(path)
        self._embeddings = np.load(str(index_dir / "embeddings.npy"))

        with open(index_dir / "chunks.json", encoding="utf-8") as f:
            meta = json.load(f)

        self._chunks = [DocumentChunk(**item) for item in meta]


# ──────────────────────────────────────────────────────────────
# Azure AI Search Backend — production stub
# ──────────────────────────────────────────────────────────────


class AzureAISearchBackend:
    """Production search — Azure AI Search with hybrid retrieval.

    Stub implementation — raises NotImplementedError until M12.
    """

    async def index(
        self,
        chunks: list[DocumentChunk],
        embeddings: np.ndarray,
    ) -> int:
        raise NotImplementedError(
            "Azure AI Search backend not yet implemented. "
            "Planned for M12 (Azure integration milestone)."
        )

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        raise NotImplementedError(
            "Azure AI Search backend not yet implemented. "
            "Planned for M12 (Azure integration milestone)."
        )


# ──────────────────────────────────────────────────────────────
# Pipeline Functions
# ──────────────────────────────────────────────────────────────

# Module-level backend instance for the pipeline
_backend: NumpySearchBackend | None = None


def _get_backend() -> NumpySearchBackend:
    """Get or create the module-level search backend."""
    global _backend  # noqa: PLW0603
    if _backend is None:
        _backend = NumpySearchBackend()
    return _backend


async def index_documents(
    docs_path: str,
    cache_path: str = "./state/index/",
    *,
    skip_entities: bool = False,
) -> dict:
    """Full 9-step indexing pipeline with manifest output.

    Steps:
        1. Extract all documents (PPTX, PDF, DOCX, XLSX)
        2. Detect & skip exact duplicates (SHA-256)
        3. Detect & flag near-duplicates (cosine > 0.95)
        4. Chunk all unique documents (3-level hierarchy)
        5. Embed all chunks (text-embedding-3-large, .npz cache)
        6. Classify each document (GPT-5.4 → IndexingOutput)
        7. Extract entities (GPT-5.4 → KnowledgeGraph)
        8. Merge entities into knowledge graph
        9. Save manifest + knowledge graph + embeddings

    Args:
        docs_path: Path to directory containing documents.
        cache_path: Path to save index artifacts.
        skip_entities: If True, skip entity extraction steps 7-8.

    Returns:
        Manifest dict with pipeline results and per-document details.
    """
    timings: dict[str, float] = {}
    cache_dir = Path(cache_path)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Extract ──────────────────────────────────────
    t0 = time.perf_counter()
    docs = extract_directory(docs_path)
    timings["extract"] = time.perf_counter() - t0

    if not docs:
        logger.warning("No documents found in %s", docs_path)
        manifest = _build_empty_manifest(cache_path)
        _save_manifest(manifest, cache_path)
        return manifest

    logger.info("Step 1: Extracted %d documents from %s", len(docs), docs_path)

    # Build doc_id map
    doc_ids = [f"DOC-{i:03d}" for i in range(1, len(docs) + 1)]
    doc_id_map = dict(zip(doc_ids, docs))

    # ── Step 2: Exact duplicate detection ────────────────────
    t0 = time.perf_counter()
    exact_dedup_results = detect_exact_duplicates(docs)
    timings["exact_dedup"] = time.perf_counter() - t0

    # Map dedup results by doc_id
    dedup_map: dict[str, str] = {}  # doc_id → "keep" | "skip" | "flag"
    for r in exact_dedup_results:
        dedup_map[r.doc_id] = r.action

    # Filter to unique docs only
    skip_ids = {r.doc_id for r in exact_dedup_results if r.action == "skip_exact"}
    unique_doc_ids = [did for did in doc_ids if did not in skip_ids]
    unique_docs = [doc_id_map[did] for did in unique_doc_ids]

    duplicates_skipped = len(skip_ids)
    logger.info(
        "Step 2: %d exact duplicates skipped, %d unique docs",
        duplicates_skipped, len(unique_docs),
    )

    # ── Step 3: Near-duplicate detection ─────────────────────
    # Near-dedup needs Level 1 embeddings. We'll do it after embedding
    # but flag results here for the manifest.

    # ── Step 4: Chunk ────────────────────────────────────────
    t0 = time.perf_counter()
    chunks = chunk_directory(unique_docs)
    timings["chunk"] = time.perf_counter() - t0

    # Count chunks per doc
    chunks_per_doc: Counter[str] = Counter()
    for chunk in chunks:
        chunks_per_doc[chunk.doc_id] += 1

    logger.info(
        "Step 4: Created %d chunks from %d documents",
        len(chunks), len(unique_docs),
    )

    # ── Step 5: Embed ────────────────────────────────────────
    t0 = time.perf_counter()
    service = EmbeddingService()
    embeddings = await service.embed_and_cache(
        chunks, f"{cache_path}/embeddings",
    )
    timings["embed"] = time.perf_counter() - t0

    logger.info(
        "Step 5: Embedded %d chunks (%d dimensions)",
        len(chunks), embeddings.shape[1] if embeddings.ndim > 1 else 0,
    )

    # ── Step 3 (deferred): Near-duplicate detection ──────────
    t0 = time.perf_counter()
    near_dedup_results = detect_near_duplicates(
        embeddings, [c.chunk_id for c in chunks],
    )
    timings["near_dedup"] = time.perf_counter() - t0

    near_duplicates_flagged = sum(
        1 for r in near_dedup_results if r.action == "flag_near"
    )
    for r in near_dedup_results:
        if r.action == "flag_near":
            dedup_map[r.doc_id] = "flag_near"

    logger.info(
        "Step 3: %d near-duplicates flagged", near_duplicates_flagged,
    )

    # ── Step 5b: Index in search backend ─────────────────────
    backend = _get_backend()
    await backend.index(chunks, embeddings)
    backend.save(cache_path)

    # ── Step 6: Classify ─────────────────────────────────────
    t0 = time.perf_counter()
    classifications = await classify_directory(unique_docs)
    timings["classify"] = time.perf_counter() - t0

    # Map classifications by filename
    classification_map: dict[str, object] = {}
    for doc, cls_output in classifications:
        classification_map[doc.filename] = cls_output

    doc_type_counts: Counter[str] = Counter()
    for _, cls_output in classifications:
        doc_type_counts[cls_output.doc_type] += 1

    logger.info(
        "Step 6: Classified %d documents: %s",
        len(classifications), dict(doc_type_counts),
    )

    # ── Steps 7-8: Entity extraction + Knowledge graph ───────
    kg = KnowledgeGraph()
    if not skip_entities:
        t0 = time.perf_counter()
        doc_pairs = [
            (doc_id_map[did], did) for did in unique_doc_ids
        ]
        entity_results = await extract_entities_batch(doc_pairs)
        timings["entity_extraction"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        kg = await merge_into_knowledge_graph(
            kg, entity_results, unique_doc_ids,
        )
        timings["merge_kg"] = time.perf_counter() - t0

        kg_path = f"{cache_path}/knowledge_graph.json"
        save_knowledge_graph(kg, kg_path)

        logger.info(
            "Steps 7-8: Knowledge graph: %d people, %d projects, %d clients",
            len(kg.people), len(kg.projects), len(kg.clients),
        )

    # ── Step 9: Build and save manifest ──────────────────────
    internal_team_count = sum(
        1 for p in kg.people if p.person_type == "internal_team"
    )

    # Build per-document entries
    doc_entries = []
    for i, did in enumerate(doc_ids):
        doc = doc_id_map[did]
        cls_output = classification_map.get(doc.filename)
        doc_type = cls_output.doc_type if cls_output else "other"
        quality_score = cls_output.quality_score if cls_output else 0
        dedup_status = dedup_map.get(did, "keep")

        doc_entries.append({
            "doc_id": did,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size_bytes": doc.file_size_bytes,
            "doc_type": str(doc_type),
            "quality_score": quality_score,
            "chunks": chunks_per_doc.get(did, 0),
            "dedup_status": dedup_status,
            "extraction_quality": str(doc.extraction_quality),
        })

    manifest = {
        "indexed_at": datetime.now(UTC).isoformat(),
        "total_documents": len(docs),
        "unique_documents": len(unique_docs),
        "total_chunks": len(chunks),
        "duplicates_skipped": duplicates_skipped,
        "near_duplicates_flagged": near_duplicates_flagged,
        "classifications": dict(doc_type_counts),
        "knowledge_graph_summary": {
            "people": len(kg.people),
            "internal_team": internal_team_count,
            "projects": len(kg.projects),
            "clients": len(kg.clients),
        },
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EMBEDDING_DIM,
        "timings_seconds": {k: round(v, 2) for k, v in timings.items()},
        "documents": doc_entries,
    }

    _save_manifest(manifest, cache_path)
    logger.info("Step 9: Manifest saved to %s/manifest.json", cache_path)

    return manifest


def _build_empty_manifest(cache_path: str) -> dict:
    """Build an empty manifest for when no documents are found."""
    return {
        "indexed_at": datetime.now(UTC).isoformat(),
        "total_documents": 0,
        "unique_documents": 0,
        "total_chunks": 0,
        "duplicates_skipped": 0,
        "near_duplicates_flagged": 0,
        "classifications": {},
        "knowledge_graph_summary": {
            "people": 0,
            "internal_team": 0,
            "projects": 0,
            "clients": 0,
        },
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EMBEDDING_DIM,
        "timings_seconds": {},
        "documents": [],
    }


def _save_manifest(manifest: dict, cache_path: str) -> None:
    """Save manifest JSON to disk."""
    manifest_path = Path(cache_path) / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, default=str)


async def semantic_search(
    queries: list[str],
    top_k: int = 10,
) -> list[dict]:
    """Search indexed documents. Returns results matching Retrieval Ranker input format.

    Args:
        queries: List of search query strings.
        top_k: Maximum results per query.

    Returns:
        List of result dicts with: doc_id, title, excerpt, metadata, search_score.
    """
    backend = _get_backend()

    all_results: list[dict] = []
    seen_chunk_ids: set[str] = set()

    for query in queries:
        results = await backend.search(query, top_k=top_k)
        for r in results:
            if r.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(r.chunk_id)
                all_results.append({
                    "doc_id": r.doc_id,
                    "title": r.title,
                    "excerpt": r.excerpt,
                    "metadata": r.metadata,
                    "search_score": r.score,
                })

    # Sort by score descending
    all_results.sort(key=lambda x: x["search_score"], reverse=True)
    return all_results[:top_k]


async def _ensure_local_backend(
    docs_path: str,
    cache_path: str = DEFAULT_CACHE_PATH,
) -> None:
    """Ensure the local semantic search backend is indexed and loaded."""
    backend = _get_backend()
    cache_dir = Path(cache_path)
    embeddings_path = cache_dir / "embeddings.npy"
    chunks_path = cache_dir / "chunks.json"

    if backend._embeddings is not None and backend._chunks:
        return

    if embeddings_path.exists() and chunks_path.exists():
        backend.load(cache_path)
        return

    await index_documents(docs_path=docs_path, cache_path=cache_path)


def _list_supported_documents(docs_path: str) -> list[dict]:
    """List supported documents with a stable DOC-NNN mapping."""
    docs_dir = Path(docs_path)
    if not docs_dir.exists():
        return []

    supported_exts = {".pptx", ".pdf", ".docx", ".xlsx"}
    results: list[dict] = []
    doc_counter = 0
    for filepath in sorted(docs_dir.iterdir()):
        if not filepath.is_file():
            continue
        if filepath.name.startswith("."):
            continue
        if filepath.suffix.lower() not in supported_exts:
            continue

        doc_counter += 1
        results.append({
            "doc_id": f"DOC-{doc_counter:03d}",
            "title": filepath.stem,
            "metadata": {
                "filename": filepath.name,
                "path": str(filepath),
                "size_bytes": filepath.stat().st_size if filepath.exists() else 0,
            },
        })
    return results


# ──────────────────────────────────────────────────────────────
# Legacy Functions (backward compatibility)
# ──────────────────────────────────────────────────────────────


async def local_search(
    queries: list[SearchQuery],
    docs_path: str = DEFAULT_DOCS_PATH,
) -> list[dict]:
    """Search local documents and return results for the Retrieval Ranker.

    Legacy function — preserved for backward compatibility with existing
    pipeline nodes. For new code, use semantic_search() instead.
    """
    docs_dir = Path(docs_path)
    if not docs_dir.exists():
        return []

    await _ensure_local_backend(docs_path)

    query_strings = [q.query for q in queries if q.query.strip()]
    if not query_strings:
        return _list_supported_documents(docs_path)

    return await semantic_search(query_strings, top_k=10)


async def load_documents(
    approved_ids: list[str],
    docs_path: str = DEFAULT_DOCS_PATH,
) -> list[dict]:
    """Load full document content for approved source IDs.

    Legacy function — preserved for backward compatibility.
    """
    all_results = _list_supported_documents(docs_path)
    approved = [r for r in all_results if r["doc_id"] in approved_ids][:3]

    from src.utils.extractors import extract_document

    max_chars_per_document = 5_000
    documents: list[dict] = []
    for result in approved:
        filepath = Path(result["metadata"]["path"])
        try:
            extracted = extract_document(str(filepath))
            content = extracted.full_text[:max_chars_per_document] if extracted.full_text else ""
        except Exception:
            content = result["excerpt"]

        documents.append({
            "doc_id": result["doc_id"],
            "title": result["title"],
            "content_text": content,
            "metadata": result["metadata"],
        })

    return documents
