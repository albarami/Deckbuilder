"""SharePoint indexing and classification models."""

from typing import Literal

from pydantic import ConfigDict, Field

from .common import DeckForgeBaseModel
from .enums import ConfidentialityLevel, DocumentType, ExtractionQuality, Language


class QualityBreakdown(DeckForgeBaseModel):
    has_client_name: bool = False
    has_outcomes: bool = False
    has_methodology: bool = False
    has_data: bool = False
    is_complete_current: bool = False


class IndexedDateRange(DeckForgeBaseModel):
    """Date range extracted from document content."""
    model_config = ConfigDict(populate_by_name=True)
    from_date: str | None = Field(default=None, alias="from")
    to_date: str | None = Field(default=None, alias="to")


class IndexingInput(DeckForgeBaseModel):
    """Input to the Indexing Classifier."""
    doc_id: str  # DOC-NNN
    filename: str
    sharepoint_path: str
    content_text: str
    content_type: str  # "pptx", "pdf", "docx", "xlsx"
    file_size_bytes: int = 0
    last_modified: str | None = None


class IndexingOutput(DeckForgeBaseModel):
    """Output of the Indexing Classifier — structured metadata for one document."""
    doc_type: DocumentType
    domain_tags: list[str] = Field(default_factory=list)
    client_entity: str | None = None
    geography: list[str] = Field(default_factory=list)
    date_range: IndexedDateRange = Field(default_factory=IndexedDateRange)
    frameworks_mentioned: list[str] = Field(default_factory=list)
    key_people: list[str] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    quality_score: int = Field(ge=0, le=5, default=0)
    quality_breakdown: QualityBreakdown = Field(default_factory=QualityBreakdown)
    confidentiality_level: ConfidentialityLevel = ConfidentialityLevel.UNKNOWN
    extraction_quality: ExtractionQuality = ExtractionQuality.CLEAN
    duplicate_likelihood: Literal["none", "possible_duplicate", "likely_duplicate"] = "none"
    summary: str = ""
