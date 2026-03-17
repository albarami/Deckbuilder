"""
DeckForge Backend — Slides router.

Endpoints:
- GET /api/pipeline/{id}/slides
- GET /api/pipeline/{id}/slides/{n}/thumbnail.png
"""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from PIL import Image, ImageDraw

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
    """Get slide metadata for preview or final review sessions."""

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

    if session.status not in (PipelineStatus.COMPLETE, PipelineStatus.GATE_PENDING):
        raise HTTPException(
            status_code=409,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="EXPORT_NOT_READY",
                    message=(
                        f"Slides are not available yet. "
                        f"Current status: {session.status} ({session.current_stage})."
                    ),
                )
            ).model_dump(),
        )

    if not session.slides_data:
        raise HTTPException(
            status_code=409,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="EXPORT_NOT_READY",
                    message="Slide previews are not ready yet.",
                )
            ).model_dump(),
        )

    slides = [
        SlideInfo(
            slide_id=slide.get("slide_id", f"S-{index + 1:03d}"),
            slide_number=slide.get("slide_number", index + 1),
            entry_type=slide.get("entry_type", "unknown"),
            asset_id=slide.get("asset_id", ""),
            semantic_layout_id=slide.get("semantic_layout_id", ""),
            section_id=slide.get("section_id", ""),
            title=slide.get("title", f"Slide {index + 1}"),
            key_message=slide.get("key_message", ""),
            layout_type=slide.get("layout_type", ""),
            body_content_preview=slide.get("body_content_preview", []),
            source_claims=slide.get("source_claims", []),
            source_refs=slide.get("source_refs", []),
            report_section_ref=slide.get("report_section_ref"),
            rfp_criterion_ref=slide.get("rfp_criterion_ref"),
            speaker_notes_preview=slide.get("speaker_notes_preview", ""),
            sensitivity_tags=slide.get("sensitivity_tags", []),
            content_guidance=slide.get("content_guidance", ""),
            change_history_count=slide.get("change_history_count", 0),
            thumbnail_url=(
                slide.get("thumbnail_url")
                or (
                    f"/api/pipeline/{session_id}/slides/{slide.get('slide_number', index + 1)}/thumbnail.png"
                    if session.thumbnail_mode == ThumbnailMode.RENDERED
                    else None
                )
            ),
            shape_count=slide.get("shape_count", 0),
            fonts=slide.get("fonts", []),
            text_preview=slide.get("text_preview", ""),
            preview_kind=session.preview_kind,
        )
        for index, slide in enumerate(session.slides_data)
    ]

    return SlidesResponse(
        session_id=session_id,
        slide_count=len(slides),
        thumbnail_mode=session.thumbnail_mode,
        session_status=session.status,
        preview_kind=session.preview_kind,
        slides=slides,
    )


@router.get("/{session_id}/slides/{slide_number}/thumbnail.png")
async def get_thumbnail(
    session_id: str,
    slide_number: int,
    request: Request,
    preview_kind: str = Query("rendered"),
) -> Response:
    """Get a generated thumbnail PNG for a slide."""

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

    if session.thumbnail_mode == ThumbnailMode.METADATA_ONLY:
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="FILE_NOT_FOUND",
                    message="Thumbnails are not available in metadata_only mode.",
                )
            ).model_dump(),
        )

    slide = next(
        (entry for entry in session.slides_data if entry.get("slide_number") == slide_number),
        None,
    )
    if slide is None:
        raise HTTPException(
            status_code=404,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="FILE_NOT_FOUND",
                    message=f"Thumbnail for slide {slide_number} was not found.",
                )
            ).model_dump(),
        )

    png_bytes = _render_thumbnail(
        title=slide.get("title", f"Slide {slide_number}"),
        section=slide.get("section_id", "Section"),
        preview_kind=preview_kind,
        slide_number=slide_number,
    )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _render_thumbnail(
    *,
    title: str,
    section: str,
    preview_kind: str,
    slide_number: int,
) -> bytes:
    image = Image.new("RGB", (1280, 720), "#F3F7FB")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 1280, 110), fill="#0E2841")
    draw.text((44, 34), "Strategic Gears | DeckForge", fill="#FFFFFF")
    draw.text((44, 138), section, fill="#156082")
    draw.text((44, 198), title, fill="#0E2841")
    draw.rounded_rectangle((44, 280, 1236, 640), radius=18, outline="#D2D6DC", width=3)
    draw.text((74, 320), f"Preview kind: {preview_kind}", fill="#467886")
    draw.text((74, 374), "Source-backed slide preview", fill="#2D3748")
    draw.rounded_rectangle((1040, 38, 1210, 86), radius=18, fill="#156082")
    draw.text((1074, 52), f"Slide {slide_number}", fill="#FFFFFF")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
