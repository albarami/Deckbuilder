"""
DeckForge Backend — Export router.

Endpoint:
- GET /api/pipeline/{id}/export/{format}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.models.api_models import (
    APIErrorDetail,
    APIErrorResponse,
    DeliverableInfo,
    ExportFormat,
    PipelineStatus,
)
from backend.services.session_manager import PipelineSession, SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["export"])

MIME_TYPES = {
    ExportFormat.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ExportFormat.SOURCE_INDEX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ExportFormat.GAP_REPORT: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Source Book mode artifacts
    ExportFormat.SOURCE_BOOK: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ExportFormat.EVIDENCE_LEDGER: "application/json",
    ExportFormat.SLIDE_BLUEPRINT: "application/json",
    ExportFormat.EXTERNAL_EVIDENCE: "application/json",
    ExportFormat.ROUTING_REPORT: "application/json",
    ExportFormat.RESEARCH_QUERY_LOG: "application/json",
    ExportFormat.QUERY_EXECUTION_LOG: "application/json",
}

# Map export format keys to DeckForgeState path attributes
_STATE_PATH_ATTRS = {
    ExportFormat.PPTX: "pptx_path",
    ExportFormat.DOCX: "report_docx_path",
    ExportFormat.SOURCE_INDEX: "source_index_path",
    ExportFormat.GAP_REPORT: "gap_report_path",
    # Source Book mode: graph state uses source_book_docx_path or report_docx_path
    ExportFormat.SOURCE_BOOK: "source_book_docx_path",
    ExportFormat.EVIDENCE_LEDGER: "evidence_ledger_path",
    ExportFormat.SLIDE_BLUEPRINT: "slide_blueprint_path",
    ExportFormat.EXTERNAL_EVIDENCE: "external_evidence_path",
    ExportFormat.ROUTING_REPORT: "routing_report_path",
    ExportFormat.RESEARCH_QUERY_LOG: "research_query_log_path",
    ExportFormat.QUERY_EXECUTION_LOG: "query_execution_log_path",
}


@router.get("/{session_id}/export/{format}")
async def export_file(
    session_id: str,
    format: str,
    request: Request,
) -> Response:
    """Download a generated deliverable for a completed session."""

    sm: SessionManager = request.app.state.session_manager
    session = sm.get(session_id)

    try:
        export_format = ExportFormat(format)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="INVALID_INPUT",
                    message=f"Invalid export format: {format}.",
                )
            ).model_dump(),
        ) from exc

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="SESSION_NOT_FOUND",
                    message=f"Session {session_id} not found.",
                )
            ).model_dump(),
        )

    if session.status != PipelineStatus.COMPLETE:
        raise HTTPException(
            status_code=409,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="EXPORT_NOT_READY",
                    message=(
                        "Pipeline has not completed finalization. "
                        f"Current status: {session.status} ({session.current_stage})."
                    ),
                )
            ).model_dump(),
        )

    deliverable = _find_deliverable(session.deliverables, export_format.value)
    if deliverable is None or not deliverable.ready:
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="FILE_NOT_FOUND",
                    message=f"Deliverable not ready: {format}.",
                )
            ).model_dump(),
        )

    # Resolve the actual file path from the pipeline graph state
    file_path = _resolve_file_path(session, export_format)
    if file_path is None or not file_path.exists():
        logger.warning(
            "Export file not found on disk for session %s format %s: %s",
            session_id,
            format,
            file_path,
        )
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="FILE_NOT_FOUND",
                    message=f"Rendered file not found on disk for format: {format}.",
                )
            ).model_dump(),
        )

    filename = deliverable.filename or file_path.name

    return FileResponse(
        path=str(file_path),
        media_type=MIME_TYPES[export_format],
        filename=filename,
    )


def _resolve_file_path(session: PipelineSession, export_format: ExportFormat) -> Path | None:
    """Resolve the on-disk path for the requested export format.

    Checks the pipeline graph state first (authoritative source of rendered
    file paths), then falls back to the session-level path fields.
    """
    # Try graph state first (has the full pipeline output paths)
    if session.graph_state is not None:
        attr = _STATE_PATH_ATTRS.get(export_format)
        if attr:
            raw_path = getattr(session.graph_state, attr, None)
            if raw_path:
                resolved = Path(raw_path)
                if resolved.exists():
                    return resolved

    # For source_book export, also try report_docx_path (source_book_node writes there)
    if export_format == ExportFormat.SOURCE_BOOK and session.graph_state is not None:
        for alt_attr in ("report_docx_path",):
            raw_path = getattr(session.graph_state, alt_attr, None)
            if raw_path:
                resolved = Path(raw_path)
                if resolved.exists():
                    return resolved

    # Fallback: session-level path fields (set by set_deliverables)
    session_path_map = {
        ExportFormat.PPTX: session.pptx_path,
        ExportFormat.DOCX: session.docx_path,
        ExportFormat.SOURCE_INDEX: session.source_index_path,
        ExportFormat.GAP_REPORT: session.gap_report_path,
        # Source Book mode
        ExportFormat.SOURCE_BOOK: session.source_book_path,
        ExportFormat.EVIDENCE_LEDGER: session.evidence_ledger_path,
        ExportFormat.SLIDE_BLUEPRINT: session.slide_blueprint_path,
        ExportFormat.EXTERNAL_EVIDENCE: session.external_evidence_path,
        ExportFormat.ROUTING_REPORT: session.routing_report_path,
        ExportFormat.RESEARCH_QUERY_LOG: session.research_query_log_path,
        ExportFormat.QUERY_EXECUTION_LOG: session.query_execution_log_path,
    }
    raw = session_path_map.get(export_format)
    if raw:
        resolved = Path(raw)
        if resolved.exists():
            return resolved

    return None


def _find_deliverable(
    deliverables: list[DeliverableInfo],
    key: str,
) -> DeliverableInfo | None:
    for deliverable in deliverables:
        if deliverable.key == key:
            return deliverable
    return None


# ── Artifact JSON Endpoint ──────────────────────────────────────────────

_ARTIFACT_PATH_MAP = {
    "evidence_ledger": "evidence_ledger_path",
    "slide_blueprint": "slide_blueprint_path",
    "external_evidence": "external_evidence_path",
    "routing_report": "routing_report_path",
    "research_query_log": "research_query_log_path",
    "query_execution_log": "query_execution_log_path",
}


@router.get("/{session_id}/artifact/{artifact_name}")
async def get_artifact_json(
    session_id: str,
    artifact_name: str,
    request: Request,
) -> Response:
    """Return parsed JSON content of a Source Book artifact for viewer rendering.

    Unlike the /export/ endpoint (which streams a file download), this endpoint
    returns the JSON content inline for the frontend to render in artifact viewers.
    """
    sm: SessionManager = request.app.state.session_manager
    session = sm.get(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="SESSION_NOT_FOUND",
                    message=f"Session {session_id} not found.",
                )
            ).model_dump(),
        )

    path_attr = _ARTIFACT_PATH_MAP.get(artifact_name)
    if not path_attr:
        raise HTTPException(
            status_code=422,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="INVALID_INPUT",
                    message=f"Unknown artifact: {artifact_name}. "
                    f"Valid: {', '.join(_ARTIFACT_PATH_MAP.keys())}.",
                )
            ).model_dump(),
        )

    # Try session-level path first, then graph state
    file_path_str = getattr(session, path_attr, None)
    if not file_path_str and session.graph_state:
        file_path_str = getattr(session.graph_state, path_attr, None)

    if not file_path_str:
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="ARTIFACT_NOT_READY",
                    message=f"Artifact '{artifact_name}' has not been generated yet.",
                )
            ).model_dump(),
        )

    file_path = Path(file_path_str)
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="FILE_NOT_FOUND",
                    message=f"Artifact file not found on disk: {artifact_name}.",
                )
            ).model_dump(),
        )

    try:
        with open(file_path, encoding="utf-8") as f:
            content = json.load(f)
        return JSONResponse(content=content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Failed to parse artifact JSON %s: %s", file_path, exc)
        raise HTTPException(
            status_code=500,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="PARSE_ERROR",
                    message=f"Failed to parse artifact '{artifact_name}' as JSON.",
                )
            ).model_dump(),
        ) from exc
