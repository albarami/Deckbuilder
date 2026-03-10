"""Document extraction models for the Knowledge Layer.

Holds structured content extracted from PPTX, PDF, DOCX, and XLSX files.
Each format populates its relevant field (slides, pages, or sections).
"""

from datetime import UTC, datetime

from pydantic import Field

from .common import DeckForgeBaseModel
from .enums import ExtractionQuality


class ExtractedTable(DeckForgeBaseModel):
    """A table extracted from a document — rows of cells."""

    rows: list[list[str]] = Field(default_factory=list)


class ExtractedSlide(DeckForgeBaseModel):
    """One slide extracted from a PPTX file."""

    slide_number: int
    title: str = ""
    body_text: str = ""
    speaker_notes: str = ""
    layout_type: str = ""
    tables: list[ExtractedTable] = Field(default_factory=list)


class ExtractedPage(DeckForgeBaseModel):
    """One page extracted from a PDF file."""

    page_number: int
    text: str = ""


class ExtractedSection(DeckForgeBaseModel):
    """One section extracted from a DOCX file."""

    heading: str = ""
    text: str = ""
    level: int = 1


class ExtractedSheet(DeckForgeBaseModel):
    """One sheet extracted from an XLSX file."""

    sheet_name: str = ""
    headers: list[str] = Field(default_factory=list)
    row_count: int = 0
    text: str = ""


class ExtractedDocument(DeckForgeBaseModel):
    """Unified extraction result from any supported document format.

    Each format populates its relevant field:
    - PPTX → slides
    - PDF → pages
    - DOCX → sections
    - XLSX → sheets
    All formats produce full_text (concatenated plain text).
    """

    filepath: str
    filename: str
    file_type: str  # pptx, pdf, docx, xlsx
    file_size_bytes: int = 0
    content_hash: str = ""  # SHA-256 of full_text
    slides: list[ExtractedSlide] = Field(default_factory=list)
    pages: list[ExtractedPage] = Field(default_factory=list)
    sections: list[ExtractedSection] = Field(default_factory=list)
    sheets: list[ExtractedSheet] = Field(default_factory=list)
    full_text: str = ""
    extraction_quality: ExtractionQuality = ExtractionQuality.CLEAN
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None
