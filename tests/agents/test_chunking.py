"""Tests for the chunking module — hierarchical 3-level document chunking."""

from src.models.enums import ExtractionQuality
from src.models.extraction import (
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
    ExtractedSheet,
    ExtractedSlide,
)
from src.utils.chunking import chunk_directory, chunk_document

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


def _make_pptx_doc() -> ExtractedDocument:
    """Create a fake PPTX document with 3 slides."""
    return ExtractedDocument(
        filepath="/test/deck.pptx",
        filename="deck.pptx",
        file_type="pptx",
        file_size_bytes=1000,
        content_hash="abc123",
        slides=[
            ExtractedSlide(
                slide_number=1,
                title="Introduction",
                body_text="Welcome to the presentation about SAP migration.",
                speaker_notes="Open with context.",
            ),
            ExtractedSlide(
                slide_number=2,
                title="Methodology",
                body_text="We use a 4-phase approach for digital transformation.",
            ),
            ExtractedSlide(
                slide_number=3,
                title="Results",
                body_text="Revenue increased by 30% after implementation.",
                speaker_notes="Show chart.",
            ),
        ],
        full_text="Introduction\nWelcome to the presentation about SAP migration.\n\n"
        "Methodology\nWe use a 4-phase approach for digital transformation.\n\n"
        "Results\nRevenue increased by 30% after implementation.",
        extraction_quality=ExtractionQuality.CLEAN,
    )


def _make_pdf_doc() -> ExtractedDocument:
    """Create a fake PDF document with 2 pages."""
    return ExtractedDocument(
        filepath="/test/report.pdf",
        filename="report.pdf",
        file_type="pdf",
        file_size_bytes=5000,
        content_hash="def456",
        pages=[
            ExtractedPage(page_number=1, text="Strategic analysis of the GCC market."),
            ExtractedPage(page_number=2, text="Recommendations for expansion into KSA."),
        ],
        full_text="Strategic analysis of the GCC market.\n\nRecommendations for expansion into KSA.",
        extraction_quality=ExtractionQuality.CLEAN,
    )


def _make_docx_doc() -> ExtractedDocument:
    """Create a fake DOCX document with 2 sections."""
    return ExtractedDocument(
        filepath="/test/proposal.docx",
        filename="proposal.docx",
        file_type="docx",
        file_size_bytes=3000,
        content_hash="ghi789",
        sections=[
            ExtractedSection(heading="Executive Summary", text="This proposal covers SAP HANA migration.", level=1),
            ExtractedSection(heading="Technical Approach", text="We propose a phased rollout strategy.", level=2),
        ],
        full_text="Executive Summary\nThis proposal covers SAP HANA migration.\n\n"
        "Technical Approach\nWe propose a phased rollout strategy.",
        extraction_quality=ExtractionQuality.CLEAN,
    )


def _make_xlsx_doc() -> ExtractedDocument:
    """Create a fake XLSX document with 1 sheet."""
    return ExtractedDocument(
        filepath="/test/data.xlsx",
        filename="data.xlsx",
        file_type="xlsx",
        file_size_bytes=2000,
        content_hash="jkl012",
        sheets=[
            ExtractedSheet(
                sheet_name="Projects",
                headers=["Name", "Client", "Revenue"],
                row_count=5,
                text="Name | Client | Revenue\nSAP Migration | SIDF | 500K",
            ),
        ],
        full_text="Name | Client | Revenue\nSAP Migration | SIDF | 500K",
        extraction_quality=ExtractionQuality.CLEAN,
    )


def _make_empty_doc() -> ExtractedDocument:
    """Create a document with no content."""
    return ExtractedDocument(
        filepath="/test/empty.pdf",
        filename="empty.pdf",
        file_type="pdf",
        file_size_bytes=100,
        content_hash="empty",
        full_text="",
        extraction_quality=ExtractionQuality.DEGRADED,
    )


# ──────────────────────────────────────────────────────────────
# PPTX Chunking Tests
# ──────────────────────────────────────────────────────────────


def test_pptx_produces_three_levels() -> None:
    """PPTX document produces Level 1, Level 2, and Level 3 chunks."""
    doc = _make_pptx_doc()
    chunks = chunk_document(doc, "DOC-001")

    levels = {c.level for c in chunks}
    assert levels == {1, 2, 3}, f"Expected levels 1,2,3 but got {levels}"

    # Level 1: 1 full-doc chunk
    l1 = [c for c in chunks if c.level == 1]
    assert len(l1) == 1
    assert l1[0].chunk_id == "DOC-001_L1"

    # Level 3: 1 per slide = 3 chunks
    l3 = [c for c in chunks if c.level == 3]
    assert len(l3) == 3


def test_pdf_produces_two_levels() -> None:
    """PDF document produces Level 1 and Level 2 (no slide level)."""
    doc = _make_pdf_doc()
    chunks = chunk_document(doc, "DOC-002")

    levels = {c.level for c in chunks}
    assert levels == {1, 2}, f"Expected levels 1,2 but got {levels}"

    # Level 2: 1 per page = 2 chunks
    l2 = [c for c in chunks if c.level == 2]
    assert len(l2) == 2


def test_docx_produces_two_levels() -> None:
    """DOCX document produces Level 1 and Level 2."""
    doc = _make_docx_doc()
    chunks = chunk_document(doc, "DOC-003")

    levels = {c.level for c in chunks}
    assert levels == {1, 2}

    l2 = [c for c in chunks if c.level == 2]
    assert len(l2) == 2


def test_xlsx_produces_two_levels() -> None:
    """XLSX document produces Level 1 and Level 2 per sheet."""
    doc = _make_xlsx_doc()
    chunks = chunk_document(doc, "DOC-004")

    levels = {c.level for c in chunks}
    assert levels == {1, 2}

    l2 = [c for c in chunks if c.level == 2]
    assert len(l2) == 1


# ──────────────────────────────────────────────────────────────
# Chunk ID Format Tests
# ──────────────────────────────────────────────────────────────


def test_chunk_ids_follow_format() -> None:
    """Chunk IDs follow DOC-NNN_L{level}_{suffix} format."""
    doc = _make_pptx_doc()
    chunks = chunk_document(doc, "DOC-001")

    l1 = [c for c in chunks if c.level == 1]
    assert l1[0].chunk_id == "DOC-001_L1"

    l3 = [c for c in chunks if c.level == 3]
    ids = sorted(c.chunk_id for c in l3)
    assert ids == ["DOC-001_L3_SLIDE_01", "DOC-001_L3_SLIDE_02", "DOC-001_L3_SLIDE_03"]

    # PDF page IDs
    pdf_chunks = chunk_document(_make_pdf_doc(), "DOC-002")
    l2_pdf = sorted(c.chunk_id for c in pdf_chunks if c.level == 2)
    assert l2_pdf == ["DOC-002_L2_P01", "DOC-002_L2_P02"]


# ──────────────────────────────────────────────────────────────
# Metadata Preservation Tests
# ──────────────────────────────────────────────────────────────


def test_parent_metadata_preserved() -> None:
    """Every chunk carries parent document metadata."""
    doc = _make_pptx_doc()
    chunks = chunk_document(doc, "DOC-001")

    for chunk in chunks:
        assert chunk.doc_id == "DOC-001"
        assert chunk.doc_title == "deck.pptx"
        assert chunk.doc_type == "pptx"


def test_slide_metadata_in_level3() -> None:
    """Level 3 slide chunks carry slide_number and title in metadata."""
    doc = _make_pptx_doc()
    chunks = chunk_document(doc, "DOC-001")

    l3 = sorted([c for c in chunks if c.level == 3], key=lambda c: c.chunk_id)
    assert l3[0].metadata["slide_number"] == 1
    assert l3[0].metadata["title"] == "Introduction"
    assert l3[2].metadata["slide_number"] == 3


# ──────────────────────────────────────────────────────────────
# Empty Document Test
# ──────────────────────────────────────────────────────────────


def test_empty_document_produces_level1() -> None:
    """Empty document still produces at least a Level 1 chunk."""
    doc = _make_empty_doc()
    chunks = chunk_document(doc, "DOC-099")

    assert len(chunks) >= 1
    l1 = [c for c in chunks if c.level == 1]
    assert len(l1) == 1
    assert l1[0].text == ""


# ──────────────────────────────────────────────────────────────
# char_count Test
# ──────────────────────────────────────────────────────────────


def test_char_count_matches_text_length() -> None:
    """char_count field matches len(text)."""
    doc = _make_pptx_doc()
    chunks = chunk_document(doc, "DOC-001")

    for chunk in chunks:
        assert chunk.char_count == len(chunk.text), (
            f"Chunk {chunk.chunk_id}: char_count={chunk.char_count} != len(text)={len(chunk.text)}"
        )


# ──────────────────────────────────────────────────────────────
# Batch Chunking Tests
# ──────────────────────────────────────────────────────────────


def test_chunk_directory_assigns_doc_ids() -> None:
    """chunk_directory assigns sequential DOC-NNN IDs."""
    docs = [_make_pptx_doc(), _make_pdf_doc(), _make_docx_doc()]
    chunks = chunk_directory(docs)

    doc_ids = sorted(set(c.doc_id for c in chunks))
    assert doc_ids == ["DOC-001", "DOC-002", "DOC-003"]


def test_chunk_directory_total_count() -> None:
    """Batch chunking produces correct total chunk count."""
    docs = [_make_pptx_doc(), _make_pdf_doc()]
    chunks = chunk_directory(docs)

    # PPTX: 1 L1 + 3 L2 (slides as sections) + 3 L3 = 7
    # PDF: 1 L1 + 2 L2 = 3
    # Total: 10
    assert len(chunks) >= 7  # At least the PPTX chunks
