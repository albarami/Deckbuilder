"""Indexing Classifier — classifies documents using GPT-5.4.

Reads extracted content and produces structured metadata for each document.
Uses the Indexing Agent system prompt from the Prompt Library.
"""

from __future__ import annotations

import asyncio
import logging

from src.agents.indexing.prompts import SYSTEM_PROMPT
from src.config.models import MODEL_MAP
from src.models.enums import DocumentType, ExtractionQuality
from src.models.extraction import ExtractedDocument
from src.models.indexing import IndexingOutput
from src.services.llm import LLMError, call_llm

logger = logging.getLogger(__name__)

# Max content length sent to classifier (GPT-5.4 context window)
_MAX_CONTENT_CHARS = 30000

# Concurrency limit for parallel classification
_MAX_CONCURRENT = 5


async def classify_document(
    doc: ExtractedDocument,
    doc_id: str,
) -> IndexingOutput:
    """Classify a single document using GPT-5.4.

    Builds an IndexingInput from the ExtractedDocument, calls the LLM,
    and returns the structured IndexingOutput.

    On LLM failure, returns a fallback IndexingOutput with doc_type=OTHER.
    """
    # Build user message from extracted content
    content_text = doc.full_text[:_MAX_CONTENT_CHARS] if doc.full_text else ""
    user_message = (
        f"Document ID: {doc_id}\n"
        f"Filename: {doc.filename}\n"
        f"Content Type: {doc.file_type}\n"
        f"File Size: {doc.file_size_bytes} bytes\n"
        f"Extraction Quality: {doc.extraction_quality}\n"
        f"\n--- CONTENT ---\n\n"
        f"{content_text}"
    )

    try:
        response = await call_llm(
            model=MODEL_MAP["indexing_classifier"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=IndexingOutput,
            temperature=0.0,
            max_tokens=2000,
        )
        logger.info(
            "Classified %s (%s): type=%s, quality=%d, domains=%s",
            doc_id,
            doc.filename,
            response.parsed.doc_type,
            response.parsed.quality_score,
            response.parsed.domain_tags,
        )
        return response.parsed

    except LLMError as e:
        logger.warning(
            "Classification failed for %s (%s): %s",
            doc_id, doc.filename, e,
        )
        # Return a safe fallback
        return IndexingOutput(
            doc_type=DocumentType.OTHER,
            extraction_quality=ExtractionQuality(doc.extraction_quality),
            summary=f"Classification failed: {e.last_error}",
        )


async def classify_directory(
    docs: list[ExtractedDocument],
) -> list[tuple[ExtractedDocument, IndexingOutput]]:
    """Classify all documents with concurrency limit.

    Returns list of (document, classification) tuples.
    """
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    results: list[tuple[ExtractedDocument, IndexingOutput]] = []

    async def _classify_one(idx: int, doc: ExtractedDocument) -> tuple[ExtractedDocument, IndexingOutput]:
        async with semaphore:
            doc_id = f"DOC-{idx:03d}"
            output = await classify_document(doc, doc_id)
            return doc, output

    tasks = [_classify_one(idx, doc) for idx, doc in enumerate(docs, start=1)]
    completed = await asyncio.gather(*tasks)
    results.extend(completed)

    return results
