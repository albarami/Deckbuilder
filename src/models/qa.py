"""QA Agent validation models."""

from pydantic import Field

from .common import DeckForgeBaseModel
from .enums import QAIssueType, QASlideStatus


class QAIssue(DeckForgeBaseModel):
    """A single issue found during QA validation."""
    type: QAIssueType
    location: str  # "body_content bullet 3", "speaker_notes", "title"
    claim: str = ""  # The problematic text
    explanation: str
    action: str  # "REMOVE claim and replace with GAP flag" etc.
    evidence_level: str = ""  # "sourced" | "llm_knowledge" | ""


class SlideValidation(DeckForgeBaseModel):
    """QA result for a single slide."""
    slide_id: str  # S-NNN
    status: QASlideStatus
    issues: list[QAIssue] = Field(default_factory=list)


class DeckValidationSummary(DeckForgeBaseModel):
    """Overall QA summary for the entire deck."""
    total_slides: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    ungrounded_claims: int = 0
    inconsistencies: int = 0
    embellishments: int = 0
    rfp_criteria_covered: int = 0
    rfp_criteria_total: int = 0
    uncovered_criteria: list[str] = Field(default_factory=list)
    critical_gaps_remaining: int = 0
    critical_gaps: list[str] = Field(default_factory=list)
    fail_close: bool = False
    fail_close_reason: str = ""


class QAResult(DeckForgeBaseModel):
    """Complete output of the QA Agent."""
    slide_validations: list[SlideValidation] = Field(default_factory=list)
    deck_summary: DeckValidationSummary = Field(default_factory=DeckValidationSummary)
