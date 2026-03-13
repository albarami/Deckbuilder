"""
DeckForge Backend — Pydantic API Models

All request/response schemas matching the M11 API Contract exactly.
These are the data-transfer objects between frontend and backend.
They do NOT import from src/ (frontend/backend boundary rule).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────


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


class ExportFormat(StrEnum):
    PPTX = "pptx"
    DOCX = "docx"


# ── Error Response ─────────────────────────────────────────────────────


class APIErrorDetail(BaseModel):
    """Standardized error shape for all 4xx/5xx responses."""
    code: str  # SESSION_NOT_FOUND | GATE_NOT_PENDING | INVALID_INPUT | PIPELINE_FAILED | EXPORT_NOT_READY
    message: str
    details: Any | None = None


class APIErrorResponse(BaseModel):
    """Wrapper for error responses."""
    error: APIErrorDetail


# ── Upload ─────────────────────────────────────────────────────────────


class UploadedFileInfo(BaseModel):
    """Metadata for a single uploaded file."""
    upload_id: str
    filename: str
    size_bytes: int
    content_type: str
    extracted_text_length: int
    detected_language: str  # "en" | "ar" | "unknown"


class UploadResponse(BaseModel):
    """Response from POST /api/upload."""
    uploads: list[UploadedFileInfo]


# ── Pipeline Start ─────────────────────────────────────────────────────


class UploadedDocumentRef(BaseModel):
    """Reference to a previously uploaded file."""
    upload_id: str
    filename: str


class StartPipelineRequest(BaseModel):
    """Request body for POST /api/pipeline/start."""
    documents: list[UploadedDocumentRef] = Field(default_factory=list)
    text_input: str | None = None
    language: str = "en"  # "en" | "ar"
    proposal_mode: ProposalMode = ProposalMode.STANDARD
    sector: str = ""
    geography: str = ""
    renderer_mode: RendererMode = RendererMode.LEGACY


class StartPipelineResponse(BaseModel):
    """Response from POST /api/pipeline/start."""
    session_id: str
    status: PipelineStatus = PipelineStatus.RUNNING
    created_at: str  # ISO 8601
    stream_url: str


# ── Pipeline Status ────────────────────────────────────────────────────


class GateInfo(BaseModel):
    """Current gate information when pipeline is at a gate."""
    gate_number: int
    summary: str
    prompt: str
    gate_data: Any = None


class GateRecord(BaseModel):
    """Record of a completed gate decision."""
    gate_number: int
    approved: bool
    feedback: str = ""
    decided_at: str  # ISO 8601


class SessionMetadataInfo(BaseModel):
    """Pipeline usage metadata."""
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0


class PipelineOutputs(BaseModel):
    """Output file availability."""
    pptx_ready: bool = False
    docx_ready: bool = False
    slide_count: int = 0


class PipelineStatusResponse(BaseModel):
    """Response from GET /api/pipeline/{id}/status."""
    session_id: str
    status: PipelineStatus
    current_stage: str
    current_gate: GateInfo | None = None
    completed_gates: list[GateRecord] = Field(default_factory=list)
    started_at: str  # ISO 8601
    elapsed_ms: int = 0
    error: dict[str, str] | None = None
    outputs: PipelineOutputs | None = None
    session_metadata: SessionMetadataInfo = Field(
        default_factory=SessionMetadataInfo
    )


# ── Gate Decision ──────────────────────────────────────────────────────


class GateDecisionRequest(BaseModel):
    """Request body for POST /api/pipeline/{id}/gate/{n}/decide."""
    approved: bool
    feedback: str | None = None
    modifications: Any | None = None


class GateDecisionResponse(BaseModel):
    """Response from POST /api/pipeline/{id}/gate/{n}/decide."""
    gate_number: int
    decision: str  # "approved" | "rejected"
    pipeline_status: PipelineStatus


# ── Slides ─────────────────────────────────────────────────────────────


class SlideInfo(BaseModel):
    """Metadata for a single slide."""
    slide_number: int
    entry_type: str
    asset_id: str = ""
    semantic_layout_id: str = ""
    section_id: str = ""
    thumbnail_url: str | None = None
    shape_count: int = 0
    fonts: list[str] = Field(default_factory=list)
    text_preview: str = ""


class SlidesResponse(BaseModel):
    """Response from GET /api/pipeline/{id}/slides."""
    session_id: str
    slide_count: int
    thumbnail_mode: ThumbnailMode
    slides: list[SlideInfo] = Field(default_factory=list)


# ── SSE Events ─────────────────────────────────────────────────────────


class SSEEvent(BaseModel):
    """Union type for all SSE event shapes."""
    type: str  # stage_change | agent_start | agent_complete | gate_pending | render_progress | pipeline_complete | pipeline_error | heartbeat
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    # Optional fields depending on type
    stage: str | None = None
    agent: str | None = None
    duration_ms: int | None = None
    gate_number: int | None = None
    summary: str | None = None
    prompt: str | None = None
    gate_data: Any | None = None
    slide_index: int | None = None
    total: int | None = None
    session_id: str | None = None
    slide_count: int | None = None
    error: str | None = None


# ── Health ─────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response from GET /api/health."""
    status: str = "ok"
    pipeline_mode: str  # "dry_run" | "live"
    active_sessions: int = 0
    version: str = "0.1.0"
