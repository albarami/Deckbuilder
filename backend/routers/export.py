"""
DeckForge Backend — Export router.

Endpoint:
- GET /api/pipeline/{id}/export/{format}
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

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
}

# Map export format keys to DeckForgeState path attributes
_STATE_PATH_ATTRS = {
    ExportFormat.PPTX: "pptx_path",
    ExportFormat.DOCX: "report_docx_path",
    ExportFormat.SOURCE_INDEX: "source_index_path",
    ExportFormat.GAP_REPORT: "gap_report_path",
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

    # Fallback: session-level path fields (set by set_deliverables)
    session_path_map = {
        ExportFormat.PPTX: session.pptx_path,
        ExportFormat.DOCX: session.docx_path,
        ExportFormat.SOURCE_INDEX: session.source_index_path,
        ExportFormat.GAP_REPORT: session.gap_report_path,
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
