"""RFP context models — output of the Context Agent."""

from pydantic import Field

from .common import BilingualText, DeckForgeBaseModel
from .enums import GapSeverity, Language


class EvaluationSubItem(DeckForgeBaseModel):
    name: str
    weight_pct: float | None = None


class EvaluationSubCriterion(DeckForgeBaseModel):
    name: str
    weight_pct: float | None = None
    sub_items: list[EvaluationSubItem] = Field(default_factory=list)


class EvaluationCategory(DeckForgeBaseModel):
    weight_pct: float | None = None
    sub_criteria: list[EvaluationSubCriterion] = Field(default_factory=list)


class EvaluationCriteria(DeckForgeBaseModel):
    technical: EvaluationCategory | None = None
    financial: EvaluationCategory | None = None
    passing_score: float | None = None


class ScopeItem(DeckForgeBaseModel):
    id: str  # SCOPE-NNN
    description: BilingualText
    category: str


class Deliverable(DeckForgeBaseModel):
    id: str  # DEL-NNN
    description: BilingualText
    mandatory: bool = True


class ComplianceRequirement(DeckForgeBaseModel):
    id: str  # COMP-NNN
    requirement: BilingualText
    mandatory: bool = True
    evidence_type: str | None = None


class KeyDates(DeckForgeBaseModel):
    inquiry_deadline: str | None = None   # YYYY-MM-DD
    submission_deadline: str | None = None
    bid_opening: str | None = None
    expected_award: str | None = None
    service_start: str | None = None


class SubmissionFormat(DeckForgeBaseModel):
    separate_envelopes: bool = False
    technical_envelope: bool = False
    financial_envelope: bool = False
    bank_guarantee_required: bool = False
    additional_requirements: list[str] = Field(default_factory=list)


class RFPGap(DeckForgeBaseModel):
    """Gap identified during RFP parsing — uses full dot-path from root."""
    field: str  # Full dot-path, e.g., "evaluation_criteria.financial.sub_criteria"
    description: str
    severity: GapSeverity


class Completeness(DeckForgeBaseModel):
    """
    Tracks extraction completeness.
    top_level_fields_extracted counts fields present in the output object,
    including null-valued fields when the field exists but source data is missing.
    A field counts as "missing" only if it could not be created at all.
    """
    top_level_fields_total: int = 10
    top_level_fields_extracted: int = 0
    top_level_missing: list[str] = Field(default_factory=list)
    detail_gaps_count: int = 0
    detail_gap_fields: list[str] = Field(default_factory=list)


class RFPContext(DeckForgeBaseModel):
    """Full parsed RFP — output of the Context Agent."""
    rfp_name: BilingualText
    issuing_entity: BilingualText
    procurement_platform: str | None = None
    mandate: BilingualText
    scope_items: list[ScopeItem] = Field(default_factory=list)
    deliverables: list[Deliverable] = Field(default_factory=list)
    evaluation_criteria: EvaluationCriteria | None = None
    compliance_requirements: list[ComplianceRequirement] = Field(default_factory=list)
    key_dates: KeyDates | None = None
    submission_format: SubmissionFormat | None = None
    gaps: list[RFPGap] = Field(default_factory=list)
    source_language: Language = Language.EN
    completeness: Completeness = Field(default_factory=Completeness)
