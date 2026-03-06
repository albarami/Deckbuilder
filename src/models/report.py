"""Research Report models — output of the Research Agent."""

from pydantic import Field

from .common import DeckForgeBaseModel
from .enums import GapSeverity, Language, SensitivityTag


class ReportSection(DeckForgeBaseModel):
    """A single section of the Research Report."""
    section_id: str  # SEC-NN
    heading: str
    content_markdown: str  # Full markdown with [Ref: CLM-xxxx] tags
    claims_referenced: list[str] = Field(default_factory=list)  # CLM-NNNN
    gaps_flagged: list[str] = Field(default_factory=list)  # GAP-NNN
    sensitivity_tags: list[SensitivityTag] = Field(default_factory=list)


class ReportGap(DeckForgeBaseModel):
    """Gap entry in the consolidated gap list."""
    gap_id: str
    description: str
    rfp_criterion: str
    severity: GapSeverity
    action_required: str


class ReportSourceEntry(DeckForgeBaseModel):
    """Source reference in the report's source index."""
    claim_id: str
    document_title: str
    sharepoint_path: str
    date: str | None = None


class ResearchReport(DeckForgeBaseModel):
    """
    The comprehensive, fully-cited Research Report.
    Approved by humans at Gate 3. Sole content source for the deck.
    """
    title: str
    language: Language
    sections: list[ReportSection] = Field(default_factory=list)
    all_gaps: list[ReportGap] = Field(default_factory=list)
    source_index: list[ReportSourceEntry] = Field(default_factory=list)
    full_markdown: str = ""  # The complete report as a single markdown string
