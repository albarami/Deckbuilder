"""
DeckForge Backend — Export Router

Endpoint:
- GET /api/pipeline/{id}/export/{format} → Download PPTX or DOCX
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from backend.models.api_models import (
    APIErrorDetail,
    APIErrorResponse,
    ExportFormat,
    PipelineStatus,
)
from backend.services.session_manager import SessionManager

router = APIRouter(prefix="/api/pipeline", tags=["export"])

# MIME types per format
MIME_TYPES = {
    ExportFormat.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/{session_id}/export/{format}")
async def export_file(
    session_id: str,
    format: str,
    request: Request,
) -> Response:
    """Download an exported deliverable file."""
    sm: SessionManager = request.app.state.session_manager
    pipeline_mode: str = request.app.state.pipeline_mode

    # Validate format
    try:
        export_format = ExportFormat(format)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="INVALID_INPUT",
                    message=f"Invalid export format: {format}. Use 'pptx' or 'docx'.",
                )
            ).model_dump(),
        )

    # Find session
    session = sm.get(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="SESSION_NOT_FOUND",
                    message=f"Session {session_id} not found.",
                )
            ).model_dump(),
        )

    # Check pipeline completion
    if session.status != PipelineStatus.COMPLETE:
        raise HTTPException(
            status_code=409,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="EXPORT_NOT_READY",
                    message=f"Pipeline has not completed rendering. Current status: {session.status} ({session.current_stage}).",
                )
            ).model_dump(),
        )

    # Build filename per contract
    session_short = session.session_id[:6]
    language = session.language

    if export_format == ExportFormat.PPTX:
        filename = f"proposal_{session_short}_{language}.pptx"
        file_path = session.pptx_path
    else:
        filename = f"research_report_{session_short}_{language}.docx"
        file_path = session.docx_path

    # In dry_run mode, return a minimal mock file
    if pipeline_mode == "dry_run":
        mime_type = MIME_TYPES[export_format]
        # Return a small placeholder binary
        mock_content = b"PK\x03\x04" + b"\x00" * 26 + filename.encode()

        return Response(
            content=mock_content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(mock_content)),
            },
        )

    # Live mode: serve actual file
    if not file_path or not Path(file_path).is_file():
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="FILE_NOT_FOUND",
                    message=f"Export file not found on disk: {filename}",
                )
            ).model_dump(),
        )

    return FileResponse(
        path=file_path,
        media_type=MIME_TYPES[export_format],
        filename=filename,
    )
