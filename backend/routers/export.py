"""
DeckForge Backend — Export router.

Endpoint:
- GET /api/pipeline/{id}/export/{format}
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from backend.models.api_models import (
    APIErrorDetail,
    APIErrorResponse,
    DeliverableInfo,
    ExportFormat,
    PipelineStatus,
)
from backend.services.session_manager import SessionManager

router = APIRouter(prefix="/api/pipeline", tags=["export"])

MIME_TYPES = {
    ExportFormat.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ExportFormat.SOURCE_INDEX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ExportFormat.GAP_REPORT: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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

    filename = deliverable.filename or f"{export_format.value}_{session_id[:6]}.bin"
    payload = _mock_content(export_format, filename)

    return Response(
        content=payload,
        media_type=MIME_TYPES[export_format],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(payload)),
        },
    )


def _find_deliverable(
    deliverables: list[DeliverableInfo],
    key: str,
) -> DeliverableInfo | None:
    for deliverable in deliverables:
        if deliverable.key == key:
            return deliverable
    return None


def _mock_content(export_format: ExportFormat, filename: str) -> bytes:
    header = b"PK\x03\x04"
    if export_format == ExportFormat.PPTX:
        body = b"Mock PPTX content for " + filename.encode("utf-8")
    elif export_format == ExportFormat.DOCX:
        body = b"Mock DOCX content for " + filename.encode("utf-8")
    elif export_format == ExportFormat.SOURCE_INDEX:
        body = b"Mock source index for " + filename.encode("utf-8")
    else:
        body = b"Mock gap report for " + filename.encode("utf-8")
    return header + body
