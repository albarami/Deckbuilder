"""
DeckForge Backend — Slides Router

Endpoints:
- GET /api/pipeline/{id}/slides                → Slide metadata list
- GET /api/pipeline/{id}/slides/{n}/thumbnail.png → Slide thumbnail image
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from backend.models.api_models import (
    APIErrorDetail,
    APIErrorResponse,
    PipelineStatus,
    SlideInfo,
    SlidesResponse,
    ThumbnailMode,
)
from backend.services.session_manager import SessionManager

router = APIRouter(prefix="/api/pipeline", tags=["slides"])


@router.get("/{session_id}/slides")
async def get_slides(
    session_id: str,
    request: Request,
) -> SlidesResponse:
    """Get slide metadata for a completed pipeline session."""
    sm: SessionManager = request.app.state.session_manager
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

    if session.status != PipelineStatus.COMPLETE:
        raise HTTPException(
            status_code=409,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="EXPORT_NOT_READY",
                    message=f"Pipeline has not completed. Current status: {session.status} ({session.current_stage}).",
                )
            ).model_dump(),
        )

    # Build slide list from cached data
    slides = [
        SlideInfo(
            slide_number=sd.get("slide_number", i + 1),
            entry_type=sd.get("entry_type", "unknown"),
            asset_id=sd.get("asset_id", ""),
            semantic_layout_id=sd.get("semantic_layout_id", ""),
            section_id=sd.get("section_id", ""),
            thumbnail_url=(
                f"/api/pipeline/{session_id}/slides/{sd.get('slide_number', i+1)}/thumbnail.png"
                if session.thumbnail_mode == "rendered"
                else None
            ),
            shape_count=sd.get("shape_count", 0),
            fonts=sd.get("fonts", []),
            text_preview=sd.get("text_preview", ""),
        )
        for i, sd in enumerate(session.slides_data)
    ]

    return SlidesResponse(
        session_id=session_id,
        slide_count=len(slides),
        thumbnail_mode=ThumbnailMode(session.thumbnail_mode),
        slides=slides,
    )


@router.get("/{session_id}/slides/{slide_number}/thumbnail.png")
async def get_thumbnail(
    session_id: str,
    slide_number: int,
    request: Request,
) -> Response:
    """Get a slide thumbnail PNG image."""
    sm: SessionManager = request.app.state.session_manager
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

    if session.thumbnail_mode != "rendered":
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="FILE_NOT_FOUND",
                    message="Thumbnails not available. Thumbnail mode is metadata_only.",
                )
            ).model_dump(),
        )

    # In dry_run mode, return a 1x1 placeholder PNG
    # In live mode, this would read from output/{session_id}/thumbnails/
    placeholder_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    return Response(
        content=placeholder_png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
        },
    )
