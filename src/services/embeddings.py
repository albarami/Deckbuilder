"""Embedding service with caching and batching.

Uses OpenAI text-embedding-3-large (3072 dimensions) for multilingual
(English + Arabic) embeddings. Supports incremental re-embedding by
tracking chunk content hashes.

Cache format: .npz file with embeddings array + chunk_ids list + hashes.
"""

import hashlib
import json
import logging
import os
from pathlib import Path

import numpy as np

from src.config.settings import get_settings
from src.utils.chunking import DocumentChunk

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072
BATCH_SIZE = 100
# text-embedding-3-large has 8191 token max.
# Arabic UTF-8 text tokenizes at ~0.6 chars/token (each Arabic char
# becomes multiple byte-pair tokens). 4000 chars * 1.67 tokens/char
# ≈ 6680 tokens — safely under the 8191 limit.
MAX_TEXT_CHARS = 4000


def _hash_text(text: str) -> str:
    """SHA-256 hash of text for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingService:
    """Manages embeddings with caching and batching."""

    async def _call_api(self, texts: list[str]) -> np.ndarray:
        """Call OpenAI embedding API. Override in tests via mock.

        Sends texts one at a time to avoid exceeding per-request token limits
        when batching long texts. The API token limit is per-request total.
        """
        from openai import AsyncOpenAI

        api_key = get_settings().openai_api_key.get_secret_value()
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        client = AsyncOpenAI(api_key=api_key)

        all_embeddings: list[list[float]] = []
        for text in texts:
            response = await client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
            )
            all_embeddings.append(response.data[0].embedding)

        return np.array(all_embeddings, dtype=np.float32)

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed texts using text-embedding-3-large. Batch in groups of 100.

        Truncates texts exceeding MAX_TEXT_CHARS. Replaces empty texts
        with a placeholder to avoid API errors.

        Returns:
            numpy array of shape (len(texts), 3072).
        """
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

        # Sanitize: truncate long texts, replace empty with placeholder
        sanitized = []
        for t in texts:
            if not t.strip():
                sanitized.append("[empty]")
            elif len(t) > MAX_TEXT_CHARS:
                sanitized.append(t[:MAX_TEXT_CHARS])
            else:
                sanitized.append(t)

        all_embeddings: list[np.ndarray] = []

        for i in range(0, len(sanitized), BATCH_SIZE):
            batch = sanitized[i : i + BATCH_SIZE]
            batch_embeddings = await self._call_api(batch)
            all_embeddings.append(batch_embeddings)

        return np.vstack(all_embeddings)

    async def embed_and_cache(
        self,
        chunks: list[DocumentChunk],
        cache_path: str,
    ) -> np.ndarray:
        """Embed chunks, cache to disk. Skip unchanged chunks on re-index.

        Cache files:
        - {cache_path}.npz — embeddings array
        - {cache_path}_meta.json — chunk IDs and content hashes

        Returns:
            numpy array of shape (len(chunks), 3072).
        """
        cache_npz = f"{cache_path}.npz"
        cache_meta = f"{cache_path}_meta.json"

        # Compute current hashes
        current_hashes = {c.chunk_id: _hash_text(c.text) for c in chunks}
        current_ids = [c.chunk_id for c in chunks]

        # Load existing cache if available
        cached_embeddings: dict[str, np.ndarray] = {}
        cached_hashes: dict[str, str] = {}

        if os.path.exists(cache_npz) and os.path.exists(cache_meta):
            try:
                data = np.load(cache_npz)
                with open(cache_meta, encoding="utf-8") as f:
                    meta = json.load(f)
                old_ids = meta.get("chunk_ids", [])
                old_hashes = meta.get("hashes", {})
                old_embeddings = data["embeddings"]

                for idx, cid in enumerate(old_ids):
                    if idx < len(old_embeddings):
                        cached_embeddings[cid] = old_embeddings[idx]
                        cached_hashes[cid] = old_hashes.get(cid, "")
            except Exception as e:
                logger.warning("Failed to load cache: %s", e)

        # Find chunks that need embedding
        texts_to_embed: list[str] = []
        indices_to_embed: list[int] = []

        for idx, chunk in enumerate(chunks):
            cached_hash = cached_hashes.get(chunk.chunk_id, "")
            if cached_hash == current_hashes[chunk.chunk_id] and chunk.chunk_id in cached_embeddings:
                # Unchanged — will reuse cached embedding
                continue
            texts_to_embed.append(chunk.text)
            indices_to_embed.append(idx)

        # Embed new/changed chunks
        new_embeddings: np.ndarray | None = None
        if texts_to_embed:
            logger.info("Embedding %d new/changed chunks", len(texts_to_embed))
            new_embeddings = await self.embed_texts(texts_to_embed)

        # Assemble full embedding matrix
        result = np.zeros((len(chunks), EMBEDDING_DIM), dtype=np.float32)
        new_embed_idx = 0

        for idx, chunk in enumerate(chunks):
            if idx in indices_to_embed and new_embeddings is not None:
                result[idx] = new_embeddings[new_embed_idx]
                new_embed_idx += 1
            elif chunk.chunk_id in cached_embeddings:
                result[idx] = cached_embeddings[chunk.chunk_id]

        # Save cache
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache_npz, embeddings=result)
        with open(cache_meta, "w", encoding="utf-8") as f:
            json.dump({
                "chunk_ids": current_ids,
                "hashes": current_hashes,
            }, f)

        return result

    def load_cache(self, cache_path: str) -> tuple[np.ndarray, list[str]]:
        """Load cached embeddings + chunk IDs from .npz file.

        Returns:
            Tuple of (embeddings array, list of chunk IDs).
        """
        cache_npz = f"{cache_path}.npz"
        cache_meta = f"{cache_path}_meta.json"

        data = np.load(cache_npz)
        with open(cache_meta, encoding="utf-8") as f:
            meta = json.load(f)

        return data["embeddings"], meta["chunk_ids"]
