"""
DeckForge Backend — Pydantic API Models.

These schemas are the stable contract between the backend service layer and
the frontend application. They intentionally avoid importing the main `src/`
package so the UI contract remains decoupled from the internal pipeline
implementation details.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PipelineStatus(StrEnum):
    """Pipeline lifecycle states visible to the frontend."""

    RUNNING = "running"
    GATE_PENDING = "gate_pending"
    COMPLETE = "complete"
    ERROR = "error"


class ProposalMode(StrEnum):
    LITE = "lite"
    STANDARD = "standard"
    FULL = "full"


class RendererMode(StrEnum):
    LEGACY = "legacy"
    TEMPLATE_V2 = "template_v2"


class ThumbnailMode(StrEnum):
    RENDERED = "rendered"
    METADATA_ONLY = "metadata_only"
    DRAFT = "draft"


class ExportFormat(StrEnum):
    PPTX = "pptx"
    DOCX = "docx"
    SOURCE_INDEX = "source_index"
    GAP_REPORT = "gap_report"


class GatePayloadType(StrEnum):
    CONTEXT_REVIEW = "context_review"
    SOURCE_REVIEW = "source_review"
    REPORT_REVIEW = "report_review"
    SLIDE_REVIEW = "slide_review"
    QA_REVIEW = "qa_review"


class AgentRunStatus(StrEnum):
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class ReadinessStatus(StrEnum):
    READY = "ready"
    REVIEW = "review"
    NEEDS_FIXES = "needs_fixes"
    BLOCKED = "blocked"


class APIErrorDetail(BaseModel):
    """Standardized error shape for all 4xx/5xx responses."""

    code: str
    message: str
    details: Any | None = None


class APIErrorResponse(BaseModel):
    """Wrapper for error responses."""

    error: APIErrorDetail


class UploadedFileInfo(BaseModel):
    """Metadata for a single uploaded file."""

    upload_id: str
    filename: str
    size_bytes: int
    content_type: str
    extracted_text_length: int
    detected_language: str


class UploadResponse(BaseModel):
    """Response from POST /api/upload."""

    uploads: list[UploadedFileInfo]


class UploadedDocumentRef(BaseModel):
    """Reference to a previously uploaded file."""

    upload_id: str
    filename: str


class LocalizedTextInput(BaseModel):
    """Localized text pair for bilingual RFP fields."""

    en: str = ""
    ar: str = ""


class EvaluationSubWeightInput(BaseModel):
    """Sub-weight entry inside an evaluation criterion."""

    label: str = ""
    weight: float | None = None


class EvaluationCriterionInput(BaseModel):
    """Evaluation criterion entry for technical and financial scoring."""

    criterion: str = ""
    weight: float | None = None
    sub_weights: list[EvaluationSubWeightInput] = Field(default_factory=list)


class KeyDatesInput(BaseModel):
    """RFP key dates contract."""

    inquiry_deadline: str = ""
    submission_deadline: str = ""
    opening_date: str = ""
    expected_award_date: str = ""
    service_start_date: str = ""


class SubmissionFormatInput(BaseModel):
    """Submission instructions and delivery requirements."""

    format: str = ""
    delivery_method: str = ""
    file_requirements: list[str] = Field(default_factory=list)
    additional_instructions: str = ""


class RfpBriefInput(BaseModel):
    """Structured 10-field RFP brief."""

    rfp_name: LocalizedTextInput = Field(default_factory=LocalizedTextInput)
    issuing_entity: str = ""
    procurement_platform: str = ""
    mandate_summary: str = ""
    scope_requirements: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    technical_evaluation: list[EvaluationCriterionInput] = Field(default_factory=list)
    financial_evaluation: list[EvaluationCriterionInput] = Field(default_factory=list)
    mandatory_compliance: list[str] = Field(default_factory=list)
    key_dates: KeyDatesInput = Field(default_factory=KeyDatesInput)
    submission_format: SubmissionFormatInput = Field(
        default_factory=SubmissionFormatInput
    )


class StartPipelineRequest(BaseModel):
    """Request body for POST /api/pipeline/start."""

    documents: list[UploadedDocumentRef] = Field(default_factory=list)
    text_input: str | None = None
    rfp_brief: RfpBriefInput | None = None
    user_notes: str = ""
    language: str = "en"
    proposal_mode: ProposalMode = ProposalMode.STANDARD
    sector: str = ""
    geography: str = ""
    renderer_mode: RendererMode = RendererMode.LEGACY


class StartPipelineResponse(BaseModel):
    """Response from POST /api/pipeline/start."""

    session_id: str
    status: PipelineStatus = PipelineStatus.RUNNING
    created_at: str
    stream_url: str
    pipeline_url: str | None = None


class GapItem(BaseModel):
    """Structured unresolved or resolved evidence gap."""

    gap_id: str
    label: str
    description: str
    severity: str = "major"
    status: str = "open"


class SourceIndexItem(BaseModel):
    """Source index entry surfaced in governance review and exports."""

    source_id: str
    title: str
    location: str = ""
    url: str | None = None


class SensitivitySummary(BaseModel):
    """Count of claims by sensitivity tag."""

    tag: str
    count: int


class ReportSectionSummary(BaseModel):
    """High-level summary for a report section."""

    section_id: str
    title: str
    claim_count: int = 0
    gap_count: int = 0


class SourceReviewItem(BaseModel):
    """Source row for Gate 2 review."""

    source_id: str
    title: str
    url: str | None = None
    relevance_score: float = 0.0
    snippet: str = ""
    matched_criteria: list[str] = Field(default_factory=list)
    permission_status: str = "accessible"
    owner_hint: str | None = None
    selected: bool = True


class Gate1ContextData(BaseModel):
    """Structured payload for Gate 1 context review."""

    rfp_brief: RfpBriefInput = Field(default_factory=RfpBriefInput)
    missing_fields: list[str] = Field(default_factory=list)
    selected_output_language: str = "en"
    user_notes: str = ""
    evaluation_highlights: list[str] = Field(default_factory=list)


class Gate2SourceReviewData(BaseModel):
    """Structured payload for Gate 2 source review."""

    sources: list[SourceReviewItem] = Field(default_factory=list)
    retrieval_strategies: list[str] = Field(default_factory=list)
    source_count: int = 0


class Gate3ReportReviewData(BaseModel):
    """Structured payload for Gate 3 report review."""

    report_markdown: str = ""
    sections: list[ReportSectionSummary] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    sensitivity_summary: list[SensitivitySummary] = Field(default_factory=list)
    source_index: list[SourceIndexItem] = Field(default_factory=list)


class SlidePreviewItem(BaseModel):
    """Draft or final slide preview entry."""

    slide_id: str
    slide_number: int
    title: str
    key_message: str = ""
    layout_type: str = ""
    body_content_preview: list[str] = Field(default_factory=list)
    source_claims: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    section: str = ""
    slide_type: str = ""
    report_section_ref: str | None = None
    rfp_criterion_ref: str | None = None
    speaker_notes_preview: str = ""
    sensitivity_tags: list[str] = Field(default_factory=list)
    content_guidance: str = ""
    change_history_count: int = 0
    thumbnail_url: str | None = None
    preview_kind: ThumbnailMode = ThumbnailMode.METADATA_ONLY


class Gate4SlideReviewData(BaseModel):
    """Structured payload for Gate 4 slide review."""

    slides: list[SlidePreviewItem] = Field(default_factory=list)
    slide_count: int = 0
    thumbnail_mode: ThumbnailMode = ThumbnailMode.METADATA_ONLY
    preview_ready: bool = False


class QaCheckRow(BaseModel):
    """Single QA finding row."""

    slide_index: int
    check: str
    status: str
    details: str = ""


class WaiverSummaryItem(BaseModel):
    """Waiver surfaced in gate/export summaries."""

    waiver_id: str
    label: str
    status: str = "open"


class DeliverableInfo(BaseModel):
    """Downloadable output artifact."""

    key: str
    label: str
    ready: bool
    filename: str | None = None
    download_url: str | None = None
    path: str | None = Field(default=None, exclude=True)


class Gate5QaReviewData(BaseModel):
    """Structured payload for Gate 5 QA review."""

    submission_readiness: ReadinessStatus = ReadinessStatus.REVIEW
    fail_close: bool = False
    critical_gaps: list[GapItem] = Field(default_factory=list)
    lint_status: ReadinessStatus = ReadinessStatus.REVIEW
    density_status: ReadinessStatus = ReadinessStatus.REVIEW
    template_compliance: ReadinessStatus = ReadinessStatus.REVIEW
    language_status: ReadinessStatus = ReadinessStatus.REVIEW
    coverage_status: ReadinessStatus = ReadinessStatus.REVIEW
    waivers: list[WaiverSummaryItem] = Field(default_factory=list)
    results: list[QaCheckRow] = Field(default_factory=list)
    deliverables: list[DeliverableInfo] = Field(default_factory=list)


class GateInfo(BaseModel):
    """Current gate information when pipeline is awaiting review."""

    gate_number: int
    summary: str
    prompt: str
    payload_type: GatePayloadType
    gate_data: (
        Gate1ContextData
        | Gate2SourceReviewData
        | Gate3ReportReviewData
        | Gate4SlideReviewData
        | Gate5QaReviewData
        | dict[str, Any]
        | None
    ) = None


class GateRecord(BaseModel):
    """Record of a completed gate decision."""

    gate_number: int
    approved: bool
    feedback: str = ""
    decided_at: str
    payload_type: GatePayloadType | None = None


class AgentRunInfo(BaseModel):
    """Frontend-facing runtime state for a single agent."""

    agent_key: str
    agent_label: str
    model: str
    status: AgentRunStatus = AgentRunStatus.WAITING
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    metric_label: str | None = None
    metric_value: str | None = None
    step_key: str | None = None
    step_number: int | None = None


class SessionMetadataInfo(BaseModel):
    """Pipeline usage metadata."""

    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    updated_at: str | None = None


class PipelineOutputs(BaseModel):
    """Output file availability."""

    pptx_ready: bool = False
    docx_ready: bool = False
    source_index_ready: bool = False
    gap_report_ready: bool = False
    slide_count: int = 0
    preview_ready: bool = False
    deliverables: list[DeliverableInfo] = Field(default_factory=list)


class SessionHistoryItem(BaseModel):
    """Compact session list/history entry."""

    session_id: str
    rfp_name: str = ""
    issuing_entity: str = ""
    status: PipelineStatus
    current_stage: str
    current_gate_number: int | None = None
    started_at: str
    updated_at: str
    elapsed_ms: int = 0
    slide_count: int = 0
    llm_calls: int = 0
    cost_usd: float = 0.0
    deliverables: list[DeliverableInfo] = Field(default_factory=list)


class SessionHistoryResponse(BaseModel):
    """Session history list response."""

    sessions: list[SessionHistoryItem] = Field(default_factory=list)


class PipelineStatusResponse(BaseModel):
    """Response from GET /api/pipeline/{id}/status."""

    session_id: str
    status: PipelineStatus
    current_stage: str
    current_stage_label: str = ""
    current_step_number: int | None = None
    current_gate_number: int | None = None
    current_gate: GateInfo | None = None
    completed_gates: list[GateRecord] = Field(default_factory=list)
    started_at: str
    elapsed_ms: int = 0
    error: dict[str, str] | None = None
    outputs: PipelineOutputs | None = None
    session_metadata: SessionMetadataInfo = Field(default_factory=SessionMetadataInfo)
    agent_runs: list[AgentRunInfo] = Field(default_factory=list)
    deliverables: list[DeliverableInfo] = Field(default_factory=list)
    rfp_name: str = ""
    issuing_entity: str = ""


class SourceDecisionModifications(BaseModel):
    """Gate 2 modifications for source review."""

    included_sources: list[str] = Field(default_factory=list)
    excluded_sources: list[str] = Field(default_factory=list)
    prioritized_sources: list[str] = Field(default_factory=list)
    requested_searches: list[str] = Field(default_factory=list)


class GateDecisionRequest(BaseModel):
    """Request body for POST /api/pipeline/{id}/gate/{n}/decide."""

    approved: bool
    feedback: str | None = None
    modifications: SourceDecisionModifications | dict[str, Any] | None = None


class GateDecisionResponse(BaseModel):
    """Response from POST /api/pipeline/{id}/gate/{n}/decide."""

    gate_number: int
    decision: str
    pipeline_status: PipelineStatus


class SlideInfo(BaseModel):
    """Metadata for a single slide."""

    slide_id: str
    slide_number: int
    entry_type: str
    asset_id: str = ""
    semantic_layout_id: str = ""
    section_id: str = ""
    title: str = ""
    key_message: str = ""
    layout_type: str = ""
    body_content_preview: list[str] = Field(default_factory=list)
    source_claims: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    report_section_ref: str | None = None
    rfp_criterion_ref: str | None = None
    speaker_notes_preview: str = ""
    sensitivity_tags: list[str] = Field(default_factory=list)
    content_guidance: str = ""
    change_history_count: int = 0
    thumbnail_url: str | None = None
    shape_count: int = 0
    fonts: list[str] = Field(default_factory=list)
    text_preview: str = ""
    preview_kind: ThumbnailMode = ThumbnailMode.METADATA_ONLY


class SlidesResponse(BaseModel):
    """Response from GET /api/pipeline/{id}/slides."""

    session_id: str
    slide_count: int
    thumbnail_mode: ThumbnailMode
    session_status: PipelineStatus
    preview_kind: ThumbnailMode = ThumbnailMode.METADATA_ONLY
    slides: list[SlideInfo] = Field(default_factory=list)


class SSEEvent(BaseModel):
    """Frontend-facing event for the live pipeline timeline."""

    event_id: str = ""
    type: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    stage: str | None = None
    stage_key: str | None = None
    stage_label: str | None = None
    step_number: int | None = None
    agent: str | None = None
    agent_key: str | None = None
    agent_label: str | None = None
    model: str | None = None
    duration_ms: int | None = None
    metric_label: str | None = None
    metric_value: str | None = None
    gate_number: int | None = None
    gate_payload_type: GatePayloadType | None = None
    summary: str | None = None
    prompt: str | None = None
    gate_data: Any | None = None
    slide_index: int | None = None
    total: int | None = None
    session_id: str | None = None
    slide_count: int | None = None
    error: str | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    """Response from GET /api/health."""

    status: str = "ok"
    pipeline_mode: str
    active_sessions: int = 0
    version: str = "0.1.0"
