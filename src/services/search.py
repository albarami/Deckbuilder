"""Search service with backend abstraction for vector search.

Architecture:
- SearchBackend Protocol: swap local numpy for Azure AI Search
- NumpySearchBackend: Local cosine similarity search (dev/test)
- AzureAISearchBackend: Production stub (implemented in M12)
- index_documents(): Full pipeline: extract → chunk → embed → index
- semantic_search(): Query the index, return Retrieval Ranker format

Backward compatibility: local_search() and load_documents() preserved.
"""

import json
import logging
from pathlib import Path
from typing import Protocol

import numpy as np
from pydantic import Field

from src.models.common import DeckForgeBaseModel
from src.models.retrieval import SearchQuery
from src.services.embeddings import EmbeddingService
from src.utils.chunking import DocumentChunk, chunk_directory

logger = logging.getLogger(__name__)


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
) -> int:
    """Full indexing pipeline: extract → chunk → embed → index.

    Args:
        docs_path: Path to directory containing documents.
        cache_path: Path to cache embeddings.

    Returns:
        Number of documents indexed.
    """
    from src.utils.extractors import extract_directory

    # Step 1: Extract
    docs = extract_directory(docs_path)
    if not docs:
        logger.warning("No documents found in %s", docs_path)
        return 0

    logger.info("Extracted %d documents from %s", len(docs), docs_path)

    # Step 2: Chunk
    chunks = chunk_directory(docs)
    logger.info("Created %d chunks from %d documents", len(chunks), len(docs))

    # Step 3: Embed
    service = EmbeddingService()
    embeddings = await service.embed_and_cache(chunks, f"{cache_path}/embeddings")

    # Step 4: Index
    backend = _get_backend()
    await backend.index(chunks, embeddings)

    # Save index to disk
    backend.save(cache_path)

    return len(docs)


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


# ──────────────────────────────────────────────────────────────
# Legacy Functions (backward compatibility)
# ──────────────────────────────────────────────────────────────


async def local_search(
    queries: list[SearchQuery],
    docs_path: str = "./test_docs",
) -> list[dict]:
    """Search local documents and return results for the Retrieval Ranker.

    Legacy function — preserved for backward compatibility with existing
    pipeline nodes. For new code, use semantic_search() instead.
    """
    docs_dir = Path(docs_path)
    if not docs_dir.exists():
        return []

    results: list[dict] = []
    doc_counter = 0

    for filepath in sorted(docs_dir.iterdir()):
        if not filepath.is_file():
            continue
        if filepath.name.startswith("."):
            continue

        doc_counter += 1
        doc_id = f"DOC-{doc_counter:03d}"

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            content = ""

        excerpt = content[:500] if content else ""

        results.append({
            "doc_id": doc_id,
            "title": filepath.stem,
            "excerpt": excerpt,
            "metadata": {
                "filename": filepath.name,
                "path": str(filepath),
                "size_bytes": filepath.stat().st_size if filepath.exists() else 0,
            },
            "search_score": 0.8,
        })

    return results


async def load_documents(
    approved_ids: list[str],
    docs_path: str = "./test_docs",
) -> list[dict]:
    """Load full document content for approved source IDs.

    Legacy function — preserved for backward compatibility.
    """
    all_results = await local_search([], docs_path)
    approved = [r for r in all_results if r["doc_id"] in approved_ids]

    documents: list[dict] = []
    for result in approved:
        filepath = Path(result["metadata"]["path"])
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            content = result["excerpt"]

        documents.append({
            "doc_id": result["doc_id"],
            "title": result["title"],
            "content_text": content,
            "metadata": result["metadata"],
        })

    return documents
