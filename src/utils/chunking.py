"""Hierarchical 3-level document chunking for the Knowledge Layer.

Chunking strategy (from architecture spec):
- Level 1: Full document text (1 embedding per document)
- Level 2: Section-level chunks (logical sections, not arbitrary token splits)
- Level 3: Slide-level chunks (for PPTX, each slide with parent deck context)

Each chunk carries parent document metadata for retrieval context.
"""

from pydantic import Field

from src.models.common import DeckForgeBaseModel
from src.models.extraction import ExtractedDocument


class DocumentChunk(DeckForgeBaseModel):
    """A single searchable chunk with parent document context."""

    chunk_id: str  # DOC-001_L1, DOC-001_L2_S03, DOC-001_L3_SLIDE_05
    doc_id: str  # Parent document ID
    doc_title: str  # Parent document title (filename)
    doc_type: str  # pptx, pdf, docx, xlsx
    text: str  # The chunk text
    level: int  # 1=full doc, 2=section/page, 3=slide
    metadata: dict = Field(default_factory=dict)  # slide_number, page_number, heading, etc.
    char_count: int = 0


def chunk_document(doc: ExtractedDocument, doc_id: str) -> list[DocumentChunk]:
    """Hierarchical 3-level chunking of a single document.

    Returns:
        List of DocumentChunk objects at appropriate levels for the doc type.
    """
    chunks: list[DocumentChunk] = []

    # Level 1: Full document text (always 1 chunk)
    chunks.append(DocumentChunk(
        chunk_id=f"{doc_id}_L1",
        doc_id=doc_id,
        doc_title=doc.filename,
        doc_type=doc.file_type,
        text=doc.full_text,
        level=1,
        metadata={"content_hash": doc.content_hash, "file_size_bytes": doc.file_size_bytes},
        char_count=len(doc.full_text),
    ))

    # Level 2 + Level 3: format-specific
    if doc.file_type == "pptx" and doc.slides:
        _chunk_pptx(doc, doc_id, chunks)
    elif doc.file_type == "pdf" and doc.pages:
        _chunk_pdf(doc, doc_id, chunks)
    elif doc.file_type == "docx" and doc.sections:
        _chunk_docx(doc, doc_id, chunks)
    elif doc.file_type == "xlsx" and doc.sheets:
        _chunk_xlsx(doc, doc_id, chunks)

    return chunks


def _chunk_pptx(doc: ExtractedDocument, doc_id: str, chunks: list[DocumentChunk]) -> None:
    """Chunk PPTX: Level 2 = all slides combined per deck, Level 3 = per slide."""
    # Level 2: Each slide as a section-level chunk
    for slide in doc.slides:
        num = f"{slide.slide_number:02d}"
        parts = [p for p in [slide.title, slide.body_text, slide.speaker_notes] if p]
        text = "\n".join(parts)
        chunks.append(DocumentChunk(
            chunk_id=f"{doc_id}_L2_S{num}",
            doc_id=doc_id,
            doc_title=doc.filename,
            doc_type=doc.file_type,
            text=text,
            level=2,
            metadata={
                "slide_number": slide.slide_number,
                "title": slide.title,
                "layout_type": slide.layout_type,
            },
            char_count=len(text),
        ))

    # Level 3: Per slide with deck title prefix for context
    for slide in doc.slides:
        num = f"{slide.slide_number:02d}"
        parts = [p for p in [slide.title, slide.body_text, slide.speaker_notes] if p]
        slide_text = "\n".join(parts)
        # Prefix with deck filename for retrieval context
        text = f"[{doc.filename}] " + slide_text
        chunks.append(DocumentChunk(
            chunk_id=f"{doc_id}_L3_SLIDE_{num}",
            doc_id=doc_id,
            doc_title=doc.filename,
            doc_type=doc.file_type,
            text=text,
            level=3,
            metadata={
                "slide_number": slide.slide_number,
                "title": slide.title,
                "layout_type": slide.layout_type,
                "has_speaker_notes": bool(slide.speaker_notes),
            },
            char_count=len(text),
        ))


def _chunk_pdf(doc: ExtractedDocument, doc_id: str, chunks: list[DocumentChunk]) -> None:
    """Chunk PDF: Level 2 = per page."""
    for page in doc.pages:
        if not page.text.strip():
            continue
        num = f"{page.page_number:02d}"
        chunks.append(DocumentChunk(
            chunk_id=f"{doc_id}_L2_P{num}",
            doc_id=doc_id,
            doc_title=doc.filename,
            doc_type=doc.file_type,
            text=page.text,
            level=2,
            metadata={"page_number": page.page_number},
            char_count=len(page.text),
        ))


def _chunk_docx(doc: ExtractedDocument, doc_id: str, chunks: list[DocumentChunk]) -> None:
    """Chunk DOCX: Level 2 = per section."""
    for idx, section in enumerate(doc.sections, start=1):
        num = f"{idx:02d}"
        parts = [p for p in [section.heading, section.text] if p]
        text = "\n".join(parts)
        if not text.strip():
            continue
        chunks.append(DocumentChunk(
            chunk_id=f"{doc_id}_L2_S{num}",
            doc_id=doc_id,
            doc_title=doc.filename,
            doc_type=doc.file_type,
            text=text,
            level=2,
            metadata={"heading": section.heading, "level": section.level},
            char_count=len(text),
        ))


def _chunk_xlsx(doc: ExtractedDocument, doc_id: str, chunks: list[DocumentChunk]) -> None:
    """Chunk XLSX: Level 2 = per sheet."""
    for idx, sheet in enumerate(doc.sheets, start=1):
        num = f"{idx:02d}"
        text = sheet.text
        if not text.strip():
            continue
        chunks.append(DocumentChunk(
            chunk_id=f"{doc_id}_L2_SH{num}",
            doc_id=doc_id,
            doc_title=doc.filename,
            doc_type=doc.file_type,
            text=text,
            level=2,
            metadata={
                "sheet_name": sheet.sheet_name,
                "headers": sheet.headers,
                "row_count": sheet.row_count,
            },
            char_count=len(text),
        ))


def chunk_directory(docs: list[ExtractedDocument]) -> list[DocumentChunk]:
    """Chunk all extracted documents. Assigns sequential DOC-NNN IDs.

    Args:
        docs: List of ExtractedDocument objects from extractors.

    Returns:
        Flat list of all DocumentChunk objects across all documents.
    """
    all_chunks: list[DocumentChunk] = []
    for idx, doc in enumerate(docs, start=1):
        doc_id = f"DOC-{idx:03d}"
        all_chunks.extend(chunk_document(doc, doc_id))
    return all_chunks
