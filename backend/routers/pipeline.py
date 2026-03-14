"""
DeckForge Backend — Pipeline Router

Endpoints:
- POST /api/pipeline/start        → Start a new pipeline session
- GET  /api/pipeline/{id}/status  → Get session status
- GET  /api/pipeline/{id}/stream  → SSE event stream
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.models.api_models import (
    APIErrorDetail,
    APIErrorResponse,
    PipelineStatus,
    PipelineStatusResponse,
    SSEEvent,
    StartPipelineRequest,
    StartPipelineResponse,
)
from backend.services.session_manager import SessionManager
from backend.services.sse_broadcaster import SSEBroadcaster

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _get_services(request: Request) -> tuple[SessionManager, SSEBroadcaster]:
    """Extract shared services from app state."""
    return request.app.state.session_manager, request.app.state.sse_broadcaster


def _get_pipeline_mode(request: Request) -> str:
    """Get current pipeline mode."""
    return request.app.state.pipeline_mode


# ── POST /api/pipeline/start ──────────────────────────────────────


@router.post("/start", status_code=201)
async def start_pipeline(
    body: StartPipelineRequest,
    request: Request,
) -> StartPipelineResponse:
    """Start a new pipeline session."""
    sm, broadcaster = _get_services(request)
    pipeline_mode = _get_pipeline_mode(request)

    # Validate input: must have documents or text
    if not body.documents and not body.text_input:
        raise HTTPException(
            status_code=422,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="INVALID_INPUT",
                    message="At least one document or text input is required.",
                )
            ).model_dump(),
        )

    # Check capacity
    try:
        session = sm.create(
            language=body.language,
            proposal_mode=body.proposal_mode.value,
            sector=body.sector,
            geography=body.geography,
            renderer_mode=body.renderer_mode.value,
        )
    except ValueError:
        raise HTTPException(
            status_code=503,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="CAPACITY_EXCEEDED",
                    message="Maximum concurrent sessions reached. Try again later.",
                )
            ).model_dump(),
        )

    # Store upload references
    session.upload_ids = [d.upload_id for d in body.documents]
    session.text_input = body.text_input

    # In dry_run mode, simulate pipeline progress in background
    if pipeline_mode == "dry_run":
        asyncio.create_task(
            _simulate_dry_run_pipeline(session.session_id, sm, broadcaster)
        )

    return StartPipelineResponse(
        session_id=session.session_id,
        status=PipelineStatus.RUNNING,
        created_at=session.created_at.isoformat(),
        stream_url=f"/api/pipeline/{session.session_id}/stream",
    )


# ── GET /api/pipeline/{id}/status ─────────────────────────────────


@router.get("/{session_id}/status")
async def get_status(
    session_id: str,
    request: Request,
) -> PipelineStatusResponse:
    """Get the current status of a pipeline session."""
    sm, _ = _get_services(request)
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

    return session.to_status_response()


# ── GET /api/pipeline/{id}/stream ─────────────────────────────────


@router.get("/{session_id}/stream")
async def stream_events(
    session_id: str,
    request: Request,
) -> StreamingResponse:
    """SSE event stream for a pipeline session."""
    sm, broadcaster = _get_services(request)
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

    if session.status in (PipelineStatus.COMPLETE, PipelineStatus.ERROR):
        raise HTTPException(
            status_code=410,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="SESSION_EXPIRED",
                    message=f"Session {session_id} has already ended.",
                )
            ).model_dump(),
        )

    return StreamingResponse(
        broadcaster.event_generator(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Dry-run pipeline simulation ───────────────────────────────────


async def _simulate_dry_run_pipeline(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
) -> None:
    """
    Simulate pipeline progress with mock events in dry_run mode.
    This produces realistic SSE events without any real LLM calls.
    """
    now = lambda: datetime.now(timezone.utc).isoformat()

    stages = [
        ("intake", "context_agent"),
        ("context_review", None),  # Gate 1
        ("source_review", "retrieval_agent"),
        ("analysis", "analysis_agent"),
        ("report_review", "research_agent"),
        ("slide_building", "draft_agent"),
        ("content_generation", "presentation_agent"),
        ("qa", "qa_agent"),
        ("deck_review", None),  # Gate 5 (simplified)
    ]

    gate_number = 0

    for stage_name, agent_name in stages:
        await asyncio.sleep(0.3)  # Simulate processing time

        # Stage change event
        sm.update_stage(session_id, stage_name)
        stage_event = SSEEvent(
            type="stage_change", stage=stage_name, timestamp=now()
        )
        sm.push_event(session_id, stage_event)
        await broadcaster.broadcast(session_id, stage_event)

        if agent_name:
            # Agent start
            start_event = SSEEvent(
                type="agent_start", agent=agent_name, timestamp=now()
            )
            sm.push_event(session_id, start_event)
            await broadcaster.broadcast(session_id, start_event)

            await asyncio.sleep(0.2)  # Simulate agent work

            # Agent complete
            complete_event = SSEEvent(
                type="agent_complete",
                agent=agent_name,
                duration_ms=200,
                timestamp=now(),
            )
            sm.push_event(session_id, complete_event)
            await broadcaster.broadcast(session_id, complete_event)

        # Check if this stage triggers a gate
        gate_stages = {
            "context_review": (1, "RFP context parsed: Mock RFP"),
            "source_review": (2, "Retrieved 5 sources"),
            "report_review": (3, "Report ready (2500 chars)"),
            "slide_building": (4, "12 slides built (legacy)"),
            "deck_review": (5, "10 passed, 0 failed"),
        }

        if stage_name in gate_stages:
            gate_num, summary = gate_stages[stage_name]
            gate_number = gate_num

            # Set gate pending
            sm.set_gate_pending(
                session_id,
                gate_number=gate_num,
                summary=summary,
                prompt=f"Gate {gate_num}: Review and approve?",
            )

            gate_event = SSEEvent(
                type="gate_pending",
                gate_number=gate_num,
                summary=summary,
                prompt=f"Gate {gate_num}: Review and approve?",
                timestamp=now(),
            )
            sm.push_event(session_id, gate_event)
            await broadcaster.broadcast(session_id, gate_event)

            # Wait for gate decision (poll session status)
            while True:
                session = sm.get(session_id)
                if not session:
                    return
                if session.status != PipelineStatus.GATE_PENDING:
                    break
                # Check if gate was rejected
                if session.completed_gates and not session.completed_gates[-1].approved:
                    # Pipeline rejected — set error and stop
                    sm.set_error(
                        session_id,
                        agent=f"gate_{gate_num}",
                        message=f"Pipeline rejected at gate {gate_num}",
                    )
                    error_event = SSEEvent(
                        type="pipeline_error",
                        error=f"Rejected at gate {gate_num}",
                        agent=f"gate_{gate_num}",
                        timestamp=now(),
                    )
                    sm.push_event(session_id, error_event)
                    await broadcaster.broadcast(session_id, error_event)
                    await broadcaster.close_session(session_id)
                    return
                await asyncio.sleep(0.1)

    # Render progress
    for i in range(12):
        render_event = SSEEvent(
            type="render_progress",
            slide_index=i + 1,
            total=12,
            timestamp=now(),
        )
        sm.push_event(session_id, render_event)
        await broadcaster.broadcast(session_id, render_event)
        await asyncio.sleep(0.05)

    # Pipeline complete
    sm.set_complete(session_id, slide_count=12)

    # Store mock slide data
    session = sm.get(session_id)
    if session:
        session.slides_data = [
            {
                "slide_number": i + 1,
                "entry_type": "b_variable" if i > 0 else "a1_clone",
                "asset_id": f"slide_{i+1}",
                "semantic_layout_id": f"layout_{(i % 4) + 1}",
                "section_id": f"section_{(i // 3) + 1}",
                "shape_count": 5 + (i % 3),
                "fonts": ["IBM Plex Sans"],
                "text_preview": f"Mock slide {i+1} content preview text",
            }
            for i in range(12)
        ]

    complete_event = SSEEvent(
        type="pipeline_complete",
        session_id=session_id,
        slide_count=12,
        timestamp=now(),
    )
    sm.push_event(session_id, complete_event)
    await broadcaster.broadcast(session_id, complete_event)
    await broadcaster.close_session(session_id)
