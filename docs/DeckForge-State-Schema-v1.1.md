# DECKFORGE — State Schema

**Pydantic Models for All Pipeline Data Structures**

Version 1.1 — March 2026 — CONFIDENTIAL
Companion to: DeckForge v3.1 Architecture + Prompt Library v1.4

**v1.1 Changes:** Added source_claims to SlideObject. Aligned ChartSpec (added note field). Fixed SlideMove to use alias for "from". Introduced DeckForgeBaseModel with extra="forbid". Replaced weak dicts with UploadedDocument/ConversationTurn models. Narrowed action field types with Literal constraints. Replaced IndexingOutput.date_range dict with IndexedDateRange model. Timezone-aware timestamps throughout.

---

## How to Use This Document

Each section below maps to a file in `src/models/`. Copy the code directly into the corresponding file. All models use Pydantic v2 with strict type hints.

**File mapping:**

| Document Section | Target File |
|-----------------|-------------|
| Section 1: Enums | `src/models/enums.py` |
| Section 2: Bilingual & Common | `src/models/common.py` |
| Section 3: RFP Context | `src/models/rfp.py` |
| Section 4: Claims & Reference Index | `src/models/claims.py` |
| Section 5: Research Report | `src/models/report.py` |
| Section 6: Slides | `src/models/slides.py` |
| Section 7: Actions | `src/models/actions.py` |
| Section 8: Waivers | `src/models/waiver.py` |
| Section 9: QA | `src/models/qa.py` |
| Section 10: Indexing | `src/models/indexing.py` |
| Section 11: Master State | `src/models/state.py` |

---

## 1. Enums — `src/models/enums.py`

All canonical enum values from Prompt Library Appendix A. Use these exact strings — no variations.

```python
"""Canonical enums for the DeckForge pipeline."""

from enum import StrEnum


class LayoutType(StrEnum):
    TITLE = "TITLE"
    AGENDA = "AGENDA"
    SECTION = "SECTION"
    CONTENT_1COL = "CONTENT_1COL"
    CONTENT_2COL = "CONTENT_2COL"
    DATA_CHART = "DATA_CHART"
    FRAMEWORK = "FRAMEWORK"
    COMPARISON = "COMPARISON"
    STAT_CALLOUT = "STAT_CALLOUT"
    TEAM = "TEAM"
    TIMELINE = "TIMELINE"
    COMPLIANCE_MATRIX = "COMPLIANCE_MATRIX"
    CLOSING = "CLOSING"


class SensitivityTag(StrEnum):
    COMPLIANCE = "compliance"
    FINANCIAL = "financial"
    CLIENT_SPECIFIC = "client_specific"
    CAPABILITY = "capability"
    GENERAL = "general"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    MEDIUM = "medium"
    LOW = "low"


class QAIssueType(StrEnum):
    UNGROUNDED_CLAIM = "UNGROUNDED_CLAIM"
    INCONSISTENCY = "INCONSISTENCY"
    EMBELLISHMENT = "EMBELLISHMENT"
    TEMPLATE_VIOLATION = "TEMPLATE_VIOLATION"
    TEXT_OVERFLOW = "TEXT_OVERFLOW"
    UNCOVERED_CRITERION = "UNCOVERED_CRITERION"
    CRITICAL_GAP_UNRESOLVED = "CRITICAL_GAP_UNRESOLVED"


class QASlideStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class ActionScope(StrEnum):
    SLIDE_ONLY = "slide_only"
    REQUIRES_REPORT_UPDATE = "requires_report_update"
    FULL_RERENDER = "full_rerender"
    AWAITING_USER_INPUT = "awaiting_user_input"
    SYSTEM_EXPORT = "system_export"


class ActionType(StrEnum):
    REWRITE_SLIDE = "rewrite_slide"
    ADD_SLIDE = "add_slide"
    REMOVE_SLIDE = "remove_slide"
    REORDER_SLIDES = "reorder_slides"
    ADDITIONAL_RETRIEVAL = "additional_retrieval"
    SHOW_SOURCES = "show_sources"
    CHANGE_LANGUAGE = "change_language"
    EXPORT = "export"
    FILL_GAP = "fill_gap"
    WAIVE_GAP = "waive_gap"
    UPDATE_REPORT = "update_report"


class Language(StrEnum):
    EN = "en"
    AR = "ar"
    BILINGUAL = "bilingual"
    MIXED = "mixed"


class DocumentType(StrEnum):
    PROPOSAL = "proposal"
    CASE_STUDY = "case_study"
    CAPABILITY_STATEMENT = "capability_statement"
    TECHNICAL_REPORT = "technical_report"
    CLIENT_PRESENTATION = "client_presentation"
    INTERNAL_FRAMEWORK = "internal_framework"
    RFP_RESPONSE = "rfp_response"
    FINANCIAL_REPORT = "financial_report"
    TEAM_PROFILE = "team_profile"
    METHODOLOGY_DOCUMENT = "methodology_document"
    CERTIFICATE = "certificate"
    OTHER = "other"


class ClaimCategory(StrEnum):
    PROJECT_REFERENCE = "project_reference"
    TEAM_PROFILE = "team_profile"
    CERTIFICATION = "certification"
    METHODOLOGY = "methodology"
    FINANCIAL_DATA = "financial_data"
    COMPLIANCE_EVIDENCE = "compliance_evidence"
    COMPANY_METRIC = "company_metric"


class SearchStrategy(StrEnum):
    RFP_ALIGNED = "rfp_aligned"
    CAPABILITY_MATCH = "capability_match"
    SIMILAR_RFP = "similar_rfp"
    TEAM_RESOURCE = "team_resource"
    FRAMEWORK = "framework"


class QueryPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PipelineStage(StrEnum):
    """Current stage of the pipeline — used for session state."""
    INTAKE = "intake"
    CONTEXT_REVIEW = "context_review"
    SOURCE_REVIEW = "source_review"
    ANALYSIS = "analysis"
    REPORT_REVIEW = "report_review"
    OUTLINE_REVIEW = "outline_review"
    CONTENT_GENERATION = "content_generation"
    QA = "qa"
    DECK_REVIEW = "deck_review"
    FINALIZED = "finalized"
    ERROR = "error"


class PresentationType(StrEnum):
    TECHNICAL_PROPOSAL = "technical_proposal"
    COMMERCIAL_PROPOSAL = "commercial_proposal"
    CAPABILITY_STATEMENT = "capability_statement"
    EXECUTIVE_SUMMARY = "executive_summary"
    CUSTOM = "custom"


class UserRole(StrEnum):
    VIEWER = "viewer"
    CONSULTANT = "consultant"
    ADMIN = "admin"


class ApprovalLevel(StrEnum):
    CONSULTANT = "consultant"
    PILLAR_LEAD = "pillar_lead"
    PRACTICE_LEAD = "practice_lead"
    EXECUTIVE = "executive"


class ConfidentialityLevel(StrEnum):
    CLIENT_CONFIDENTIAL = "client_confidential"
    INTERNAL_ONLY = "internal_only"
    PUBLIC = "public"
    UNKNOWN = "unknown"


class ExtractionQuality(StrEnum):
    CLEAN = "clean"
    PARTIAL_OCR = "partial_ocr"
    DEGRADED = "degraded"
    MANUAL_REVIEW_NEEDED = "manual_review_needed"


class RenderStatus(StrEnum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
```

---

## 2. Bilingual & Common — `src/models/common.py`

Shared types used across multiple model files.

```python
"""Common types shared across the DeckForge pipeline."""

from datetime import UTC, datetime
from pydantic import BaseModel, ConfigDict, Field


class DeckForgeBaseModel(BaseModel):
    """
    Strict base model for all DeckForge data structures.
    - extra="forbid": rejects unexpected fields (catches schema drift)
    - validate_assignment=True: validates on field assignment, not just init
    - use_enum_values=True: serializes enums as their string values
    """
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=True,
    )


class BilingualText(DeckForgeBaseModel):
    """Text field supporting English and Arabic."""
    en: str
    ar: str | None = None


class DateRange(DeckForgeBaseModel):
    """Flexible date range — supports YYYY-MM-DD, YYYY-MM, or YYYY."""
    start: str | None = None  # YYYY-MM-DD, YYYY-MM, or YYYY
    end: str | None = None


class ChangeLogEntry(DeckForgeBaseModel):
    """Log entry for tracking modifications to any object."""
    agent: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    description: str
```

---

## 3. RFP Context — `src/models/rfp.py`

Output of the Context Agent. Represents the fully parsed RFP.

```python
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
```

---

## 4. Claims & Reference Index — `src/models/claims.py`

Output of the Analysis Agent. The Reference Index is the single source of truth for all downstream content.

```python
"""Claim objects and Reference Index — output of the Analysis Agent."""

from datetime import UTC, datetime
from pydantic import Field

from .common import DateRange, DeckForgeBaseModel
from .enums import (
    ClaimCategory, GapSeverity, SensitivityTag,
)


class ClaimObject(DeckForgeBaseModel):
    """
    Atomic factual claim extracted from a source document.
    Each claim represents ONE fact — never bundled.
    Confidence rubric (rule-based, not self-assessed):
      0.95-1.00: Exact explicit statement (verbatim or near-verbatim)
      0.80-0.94: Strong explicit evidence with minor normalization
      0.60-0.79: Partial evidence requiring inference
      Below 0.60: Do NOT emit — flag as gap instead
    """
    claim_id: str  # CLM-NNNN
    claim_text: str
    source_doc_id: str  # DOC-NNN
    source_location: str  # "Slide 8", "Page 3", "Section 2.1"
    evidence_span: str  # Exact text from source supporting the claim
    sensitivity_tag: SensitivityTag
    category: ClaimCategory
    confidence: float = Field(ge=0.6, le=1.0)


class GapObject(DeckForgeBaseModel):
    """Evidence gap identified during analysis."""
    gap_id: str  # GAP-NNN
    description: str
    rfp_criterion: str  # Which evaluation criterion this gap affects
    severity: GapSeverity
    action_required: str


class Contradiction(DeckForgeBaseModel):
    """Contradictory claims found across source documents."""
    claim_a_id: str
    claim_b_id: str
    description: str
    resolution_note: str | None = None


class CaseStudy(DeckForgeBaseModel):
    """Structured project reference assembled from atomic claims."""
    project_name: str
    client: str
    dates: DateRange | None = None
    scope: str
    outcomes: str | None = None
    team_size: int | None = None
    value: str | None = None  # Contract value, if known
    geography: str | None = None
    domain_tags: list[str] = Field(default_factory=list)
    source_claims: list[str] = Field(default_factory=list)  # CLM-NNNN refs


class TeamProfile(DeckForgeBaseModel):
    """Individual team member or role profile."""
    name_or_role: str  # Named person or role title
    qualifications: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    years_experience: int | None = None
    nationality: str | None = None
    current_role: str | None = None
    source_claims: list[str] = Field(default_factory=list)


class ComplianceEvidence(DeckForgeBaseModel):
    """Evidence for a specific compliance requirement."""
    requirement_id: str  # Maps to COMP-NNN from RFP
    certificate_name: str
    issuing_body: str | None = None
    date_issued: str | None = None
    expiry_date: str | None = None
    scope_level: str | None = None
    source_claims: list[str] = Field(default_factory=list)


class FrameworkReference(DeckForgeBaseModel):
    """Reusable methodology or framework from past work."""
    framework_name: str
    description: str
    applied_in: str | None = None  # Project/context where it was used
    source_claims: list[str] = Field(default_factory=list)


class SourceManifestEntry(DeckForgeBaseModel):
    """Metadata for a source document used in the Reference Index."""
    doc_id: str  # DOC-NNN
    title: str
    sharepoint_path: str
    version_id: str | None = None
    last_modified: str | None = None  # YYYY-MM-DD
    retrieval_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str | None = None  # sha256 hash for auditability


class ReferenceIndex(DeckForgeBaseModel):
    """
    The single source of truth for all downstream content generation.
    Output of the Analysis Agent. Input to the Research Agent.
    """
    claims: list[ClaimObject] = Field(default_factory=list)
    case_studies: list[CaseStudy] = Field(default_factory=list)
    team_profiles: list[TeamProfile] = Field(default_factory=list)
    compliance_evidence: list[ComplianceEvidence] = Field(default_factory=list)
    frameworks: list[FrameworkReference] = Field(default_factory=list)
    gaps: list[GapObject] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    source_manifest: list[SourceManifestEntry] = Field(default_factory=list)
```

---

## 5. Research Report — `src/models/report.py`

Output of the Research Agent. The canonical content source approved by humans at Gate 3.

```python
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
```

---

## 6. Slides — `src/models/slides.py`

Slide objects used by Structure, Content, QA, and Design agents.

```python
"""Slide models — used across Structure, Content, QA, and Design agents."""

from typing import Literal
from pydantic import Field

from .common import ChangeLogEntry, DeckForgeBaseModel
from .enums import LayoutType, SensitivityTag


class ChartSpec(DeckForgeBaseModel):
    """
    Chart specification for DATA_CHART slides.
    Colors are NOT specified here — inherited from template theme.
    """
    type: Literal["bar", "line", "pie", "doughnut", "radar", "scatter"]
    title: str
    x_axis: dict | None = None  # {"label": str, "values": list}
    y_axis: dict | None = None  # {"label": str, "values": list}
    legend: bool = False
    note: str = ""  # e.g., "Colors inherited from template theme — do not specify"


class BodyContent(DeckForgeBaseModel):
    """Structured body content for a slide."""
    text_elements: list[str] = Field(default_factory=list)  # Bullet points / text blocks
    chart_data: dict | None = None  # Optional raw data for charts


class SlideObject(DeckForgeBaseModel):
    """
    Complete slide representation used throughout the pipeline.
    
    - Structure Agent: populates title, layout_type, report_section_ref, content_guidance, source_claims
    - Content Agent: populates body_content, speaker_notes, chart_spec, source_refs
    - QA Agent: validates all fields
    - Design Agent: renders to PPTX
    
    source_claims: claim IDs assigned by Structure Agent (from the report)
    source_refs: complete union of ALL claim IDs supporting body + notes (populated by Content Agent)
    No inline [Ref:] tags in body_content or speaker_notes — refs are structural metadata only.
    """
    slide_id: str  # S-NNN
    title: str  # Insight-led headline
    key_message: str = ""
    layout_type: LayoutType
    body_content: BodyContent | None = None
    chart_spec: ChartSpec | None = None
    source_claims: list[str] = Field(default_factory=list)  # CLM-NNNN — from Structure Agent
    source_refs: list[str] = Field(default_factory=list)  # CLM-NNNN — complete union from Content Agent
    report_section_ref: str = ""  # Section of approved report this derives from
    rfp_criterion_ref: str | None = None  # Evaluation criterion addressed
    speaker_notes: str = ""  # No Free Facts applies
    sensitivity_tags: list[SensitivityTag] = Field(default_factory=list)
    content_guidance: str = ""  # Structural only: claim IDs + layout instructions, no factual wording
    change_history: list[ChangeLogEntry] = Field(default_factory=list)


class SlideOutline(DeckForgeBaseModel):
    """Output of the Structure Agent — ordered list of slide outlines."""
    slides: list[SlideObject]
    slide_count: int = 0
    weight_allocation: dict[str, str] = Field(default_factory=dict)


class WrittenSlides(DeckForgeBaseModel):
    """Output of the Content Agent — fully written slides."""
    slides: list[SlideObject]
    notes: str | None = None  # Issues found during writing
```

---

## 7. Actions — `src/models/actions.py`

Discriminated union for Conversation Manager actions. Each action type has a specific payload.

```python
"""Conversation Manager action models — discriminated union by action type."""

from typing import Annotated, Literal, Union

from pydantic import ConfigDict, Field

from .common import DeckForgeBaseModel
from .enums import ActionScope, ActionType, Language


class RewriteSlideAction(DeckForgeBaseModel):
    type: Literal[ActionType.REWRITE_SLIDE] = ActionType.REWRITE_SLIDE
    target: str  # S-NNN
    scope: Literal[ActionScope.SLIDE_ONLY, ActionScope.REQUIRES_REPORT_UPDATE]
    instruction: str = ""


class AddSlideAction(DeckForgeBaseModel):
    type: Literal[ActionType.ADD_SLIDE] = ActionType.ADD_SLIDE
    after: str | None = None  # S-NNN or None for beginning
    topic: str
    scope: Literal[ActionScope.REQUIRES_REPORT_UPDATE] = ActionScope.REQUIRES_REPORT_UPDATE


class RemoveSlideAction(DeckForgeBaseModel):
    type: Literal[ActionType.REMOVE_SLIDE] = ActionType.REMOVE_SLIDE
    target: str  # S-NNN
    requires_confirmation: bool = True


class SlideMove(DeckForgeBaseModel):
    """Matches prompt contract: {"from": "S-004", "to": "S-005"}."""
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from")  # S-NNN
    to: str  # S-NNN


class ReorderSlidesAction(DeckForgeBaseModel):
    type: Literal[ActionType.REORDER_SLIDES] = ActionType.REORDER_SLIDES
    moves: list[SlideMove]


class AdditionalRetrievalAction(DeckForgeBaseModel):
    type: Literal[ActionType.ADDITIONAL_RETRIEVAL] = ActionType.ADDITIONAL_RETRIEVAL
    query: str
    scope: Literal[ActionScope.REQUIRES_REPORT_UPDATE] = ActionScope.REQUIRES_REPORT_UPDATE


class ShowSourcesAction(DeckForgeBaseModel):
    type: Literal[ActionType.SHOW_SOURCES] = ActionType.SHOW_SOURCES
    target: str  # S-NNN


class ChangeLanguageAction(DeckForgeBaseModel):
    type: Literal[ActionType.CHANGE_LANGUAGE] = ActionType.CHANGE_LANGUAGE
    language: Literal[Language.EN, Language.AR, Language.BILINGUAL]
    scope: Literal[ActionScope.FULL_RERENDER] = ActionScope.FULL_RERENDER


class ExportAction(DeckForgeBaseModel):
    type: Literal[ActionType.EXPORT] = ActionType.EXPORT
    format: Literal["pptx", "docx", "both"] = "pptx"
    scope: Literal[ActionScope.SYSTEM_EXPORT] = ActionScope.SYSTEM_EXPORT


class FillGapAction(DeckForgeBaseModel):
    type: Literal[ActionType.FILL_GAP] = ActionType.FILL_GAP
    gap_id: str  # GAP-NNN
    scope: Literal[ActionScope.AWAITING_USER_INPUT] = ActionScope.AWAITING_USER_INPUT


class WaiveGapAction(DeckForgeBaseModel):
    type: Literal[ActionType.WAIVE_GAP] = ActionType.WAIVE_GAP
    gap_id: str  # GAP-NNN
    requires_confirmation: bool = True


class UpdateReportAction(DeckForgeBaseModel):
    type: Literal[ActionType.UPDATE_REPORT] = ActionType.UPDATE_REPORT
    section: str | None = None
    scope: Literal[ActionScope.REQUIRES_REPORT_UPDATE] = ActionScope.REQUIRES_REPORT_UPDATE


# Discriminated union — Pydantic resolves by the `type` field
ConversationAction = Annotated[
    Union[
        RewriteSlideAction,
        AddSlideAction,
        RemoveSlideAction,
        ReorderSlidesAction,
        AdditionalRetrievalAction,
        ShowSourcesAction,
        ChangeLanguageAction,
        ExportAction,
        FillGapAction,
        WaiveGapAction,
        UpdateReportAction,
    ],
    Field(discriminator="type"),
]


class ConversationResponse(DeckForgeBaseModel):
    """Complete output of the Conversation Manager."""
    response_to_user: str
    action: ConversationAction
```

---

## 8. Waivers — `src/models/waiver.py`

Waiver governance objects from Prompt Library Appendix B.

```python
"""Waiver governance models."""

from datetime import UTC, datetime
from pydantic import Field

from .common import DeckForgeBaseModel
from .enums import ApprovalLevel, GapSeverity


class WaiverObject(DeckForgeBaseModel):
    """
    Created when a human waives a gap.
    Waivers are logged, visible in export, and require explicit confirmation for critical gaps.
    
    Permissions by severity:
      - low: consultant or admin may waive
      - medium: consultant or admin with approval_level >= pillar_lead
      - critical: admin with approval_level >= pillar_lead
    """
    waiver_id: str  # WVR-NNN
    gap_id: str  # GAP-NNN
    gap_description: str
    rfp_criterion: str
    severity: GapSeverity
    waived_by: str  # User email
    waiver_reason: str  # Required for critical gaps
    waiver_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approval_level: ApprovalLevel
    scope: str = ""  # e.g., "This RFP only"
    visible_in_export: bool = True
    export_note: str = ""
```

---

## 9. QA — `src/models/qa.py`

QA Agent validation results.

```python
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
    fail_close: bool = False
    fail_close_reason: str = ""


class QAResult(DeckForgeBaseModel):
    """Complete output of the QA Agent."""
    slide_validations: list[SlideValidation] = Field(default_factory=list)
    deck_summary: DeckValidationSummary = Field(default_factory=DeckValidationSummary)
```

---

## 10. Indexing — `src/models/indexing.py`

SharePoint document classification models.

```python
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
```

---

## 11. Master State — `src/models/state.py`

The LangGraph state object. Every agent reads from and writes to this. This is the backbone of the pipeline.

```python
"""DeckForgeState — the master LangGraph state passed between all agents."""

from datetime import UTC, datetime
from typing import Literal
from pydantic import Field

from .common import DeckForgeBaseModel
from .enums import Language, PipelineStage, PresentationType, UserRole
from .rfp import RFPContext
from .claims import ReferenceIndex
from .report import ResearchReport
from .slides import SlideObject, SlideOutline, WrittenSlides
from .qa import QAResult
from .waiver import WaiverObject
from .actions import ConversationResponse


class UploadedDocument(DeckForgeBaseModel):
    """A document uploaded by the user as part of the RFP intake."""
    filename: str
    content_text: str
    language: Language = Language.EN


class ConversationTurn(DeckForgeBaseModel):
    """A single turn in the conversation history."""
    role: Literal["user", "assistant"]
    content: str


class GateDecision(DeckForgeBaseModel):
    """Record of a human decision at an approval gate."""
    gate_number: int  # 1-5
    approved: bool
    feedback: str = ""  # User's feedback or rejection reason
    decided_by: str = ""  # User identity
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RetrievedSource(DeckForgeBaseModel):
    """A source document retrieved and ranked by the Retrieval Agent."""
    doc_id: str  # DOC-NNN
    title: str
    relevance_score: int = 0  # 0-100
    summary: str = ""
    matched_criteria: list[str] = Field(default_factory=list)
    is_duplicate: bool = False
    duplicate_of: str | None = None
    recommendation: Literal["include", "exclude"] = "include"


class SessionMetadata(DeckForgeBaseModel):
    """Session-level metadata for tracking and auditing."""
    session_id: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    user_id: str = ""
    user_role: UserRole = UserRole.CONSULTANT
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0


class ErrorInfo(DeckForgeBaseModel):
    """Error state when an agent fails."""
    agent: str
    error_type: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    retries_attempted: int = 0


class DeckForgeState(DeckForgeBaseModel):
    """
    Master state for the DeckForge pipeline.
    
    Every agent reads from and writes to this object.
    LangGraph manages state transitions between agents.
    State is persisted after each agent:
      - Local dev: JSON file at ./state/session.json
      - Production: Redis with TTL (72 hours)
    """

    # ─── Session ───
    session: SessionMetadata = Field(default_factory=SessionMetadata)
    current_stage: PipelineStage = PipelineStage.INTAKE

    # ─── Inputs ───
    ai_assist_summary: str = ""  # Raw input from BD Station
    uploaded_documents: list[UploadedDocument] = Field(default_factory=list)
    user_notes: str = ""
    output_language: Language = Language.EN
    presentation_type: PresentationType = PresentationType.TECHNICAL_PROPOSAL

    # ─── Gate 1: Context ───
    rfp_context: RFPContext | None = None
    gate_1: GateDecision | None = None

    # ─── Gate 2: Retrieval ───
    retrieved_sources: list[RetrievedSource] = Field(default_factory=list)
    approved_source_ids: list[str] = Field(default_factory=list)  # DOC-NNN ids user approved
    gate_2: GateDecision | None = None

    # ─── Analysis ───
    reference_index: ReferenceIndex | None = None

    # ─── Gate 3: Research Report ───
    research_report: ResearchReport | None = None
    report_markdown: str = ""  # The full approved report as markdown
    gate_3: GateDecision | None = None

    # ─── Gate 4: Slide Outline ───
    slide_outline: SlideOutline | None = None
    gate_4: GateDecision | None = None

    # ─── Content + QA ───
    written_slides: WrittenSlides | None = None
    qa_result: QAResult | None = None

    # ─── Gate 5: Final Deck ───
    final_slides: list[SlideObject] = Field(default_factory=list)
    gate_5: GateDecision | None = None

    # ─── Waivers ───
    waivers: list[WaiverObject] = Field(default_factory=list)

    # ─── Output ───
    pptx_path: str | None = None  # Path to rendered PPTX
    report_docx_path: str | None = None  # Path to exported report
    source_index_path: str | None = None  # Path to source index document

    # ─── Conversation ───
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    last_action: ConversationResponse | None = None

    # ─── Error ───
    errors: list[ErrorInfo] = Field(default_factory=list)
    last_error: ErrorInfo | None = None
```

---

## 12. ID Generators — `src/utils/ids.py`

Utility functions for generating sequential, zero-padded IDs per Appendix C rules.

```python
"""ID generators following Appendix C patterns. IDs are immutable once assigned."""

from threading import Lock

_counters: dict[str, int] = {}
_lock = Lock()


def _next_id(prefix: str, width: int) -> str:
    """Generate the next sequential ID for a given prefix."""
    with _lock:
        current = _counters.get(prefix, 0) + 1
        _counters[prefix] = current
        return f"{prefix}-{str(current).zfill(width)}"


def next_claim_id() -> str:
    """CLM-NNNN — unique per Reference Index."""
    return _next_id("CLM", 4)


def next_gap_id() -> str:
    """GAP-NNN — unique per Reference Index."""
    return _next_id("GAP", 3)


def next_doc_id() -> str:
    """DOC-NNN — unique per SharePoint index."""
    return _next_id("DOC", 3)


def next_slide_id() -> str:
    """S-NNN — unique per deck session."""
    return _next_id("S", 3)


def next_scope_id() -> str:
    """SCOPE-NNN — unique per RFP object."""
    return _next_id("SCOPE", 3)


def next_deliverable_id() -> str:
    """DEL-NNN — unique per RFP object."""
    return _next_id("DEL", 3)


def next_compliance_id() -> str:
    """COMP-NNN — unique per RFP object."""
    return _next_id("COMP", 3)


def next_waiver_id() -> str:
    """WVR-NNN — unique per deck session."""
    return _next_id("WVR", 3)


def next_section_id() -> str:
    """SEC-NN — unique per Research Report."""
    return _next_id("SEC", 2)


def reset_counters() -> None:
    """Reset all counters — call at session start."""
    with _lock:
        _counters.clear()
```

---

## 13. Models `__init__.py` — `src/models/__init__.py`

Central re-export for convenient imports.

```python
"""DeckForge models — central re-export."""

from .enums import *  # noqa: F401, F403
from .common import BilingualText, DateRange, ChangeLogEntry, DeckForgeBaseModel
from .rfp import RFPContext, EvaluationCriteria, ScopeItem, Deliverable, ComplianceRequirement
from .claims import ClaimObject, GapObject, ReferenceIndex, CaseStudy, SourceManifestEntry
from .report import ResearchReport, ReportSection
from .slides import SlideObject, SlideOutline, WrittenSlides, ChartSpec, BodyContent
from .actions import ConversationAction, ConversationResponse
from .waiver import WaiverObject
from .qa import QAResult, SlideValidation, DeckValidationSummary
from .indexing import IndexingInput, IndexingOutput, IndexedDateRange
from .state import (
    DeckForgeState, GateDecision, RetrievedSource, SessionMetadata, ErrorInfo,
    UploadedDocument, ConversationTurn,
)
```

---

*End of Document | DeckForge State Schema v1.1 | March 2026*
