"""
DeckForge Backend — Pipeline router.

Endpoints:
- POST /api/pipeline/start              → Start a new pipeline session
- GET  /api/pipeline/sessions           → List current sessions
- GET  /api/pipeline/{id}/status        → Get session status
- GET  /api/pipeline/{id}/stream        → SSE event stream
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.models.api_models import (
    AgentRunInfo,
    AgentRunStatus,
    APIErrorDetail,
    APIErrorResponse,
    DeliverableInfo,
    PipelineStatus,
    PipelineStatusResponse,
    RfpBriefInput,
    SessionHistoryResponse,
    SSEEvent,
    StartPipelineRequest,
    StartPipelineResponse,
)
from backend.models.api_models import ProposalMode
from backend.services.pipeline_runtime import advance_pipeline_session, advance_source_book_session
from backend.services.session_manager import SessionManager
from backend.services.sse_broadcaster import SSEBroadcaster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


AGENT_CATALOG = [
    {
        "agent_key": "context_agent",
        "agent_label": "Context Agent",
        "model": "GPT-5.4",
        "metric_label": "Context package",
        "step_key": "context_understanding",
        "step_number": 2,
    },
    {
        "agent_key": "retrieval_planner",
        "agent_label": "Retrieval Planner",
        "model": "GPT-5.4",
        "metric_label": "Search plan",
        "step_key": "knowledge_retrieval",
        "step_number": 3,
    },
    {
        "agent_key": "retrieval_ranker",
        "agent_label": "Ranker Agent",
        "model": "GPT-5.4",
        "metric_label": "Source shortlist",
        "step_key": "knowledge_retrieval",
        "step_number": 3,
    },
    {
        "agent_key": "analysis_agent",
        "agent_label": "Analysis Agent",
        "model": "Claude Opus 4.6",
        "metric_label": "Analysis memo",
        "step_key": "deep_analysis",
        "step_number": 4,
    },
    {
        "agent_key": "research_agent",
        "agent_label": "Research Agent",
        "model": "Claude Opus 4.6",
        "metric_label": "Research synthesis",
        "step_key": "report_generation",
        "step_number": 5,
    },
    {
        "agent_key": "draft_agent",
        "agent_label": "Draft Agent",
        "model": "Claude Opus 4.6",
        "metric_label": "Draft report",
        "step_key": "slide_structure",
        "step_number": 6,
    },
    {
        "agent_key": "review_agent",
        "agent_label": "Review Agent",
        "model": "GPT-5.4",
        "metric_label": "Review checks",
        "step_key": "slide_content_review",
        "step_number": 7,
    },
    {
        "agent_key": "final_review_agent",
        "agent_label": "Final Review Agent",
        "model": "GPT-5.4",
        "metric_label": "Final coherence check",
        "step_key": "final_slide_review",
        "step_number": 9,
    },
    {
        "agent_key": "refine_agent",
        "agent_label": "Refine Agent",
        "model": "Claude Opus 4.6",
        "metric_label": "Revision pass",
        "step_key": "slide_refinement",
        "step_number": 8,
    },
    {
        "agent_key": "presentation_agent",
        "agent_label": "Presentation Agent",
        "model": "Claude Opus 4.6",
        "metric_label": "Slide package",
        "step_key": "presentation_package",
        "step_number": 10,
    },
    {
        "agent_key": "qa_agent",
        "agent_label": "QA Agent",
        "model": "GPT-5.4",
        "metric_label": "Submission QA",
        "step_key": "quality_assurance",
        "step_number": 8,
    },
]


def _get_services(request: Request) -> tuple[SessionManager, SSEBroadcaster]:
    return request.app.state.session_manager, request.app.state.sse_broadcaster


def _get_pipeline_mode(request: Request) -> str:
    return request.app.state.pipeline_mode


@router.post("/start", status_code=201)
async def start_pipeline(
    body: StartPipelineRequest,
    request: Request,
) -> StartPipelineResponse:
    """Start a new pipeline session."""

    sm, broadcaster = _get_services(request)
    pipeline_mode = _get_pipeline_mode(request)
    graph = request.app.state.pipeline_graph

    if not body.documents and not body.text_input and body.rfp_brief is None:
        raise HTTPException(
            status_code=422,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="INVALID_INPUT",
                    message="At least one document, text input, or structured RFP brief is required.",
                )
            ).model_dump(),
        )

    rfp_brief = body.rfp_brief

    try:
        session = sm.create(
            language=body.language,
            proposal_mode=body.proposal_mode.value,
            sector=body.sector,
            geography=body.geography,
            renderer_mode=body.renderer_mode.value,
            rfp_brief=rfp_brief,
            user_notes=body.user_notes,
            text_input=body.text_input,
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

    session.upload_ids = [document.upload_id for document in body.documents]
    session.upload_filenames = [document.filename for document in body.documents]
    session.text_input = body.text_input
    sm.set_agent_runs(session.session_id, _build_initial_agent_runs())
    sm.set_deliverables(session.session_id, _build_deliverables(session.session_id, ready=False))

    # Select the correct pipeline function based on proposal_mode
    is_source_book = body.proposal_mode == ProposalMode.SOURCE_BOOK_ONLY
    advance_fn = advance_source_book_session if is_source_book else advance_pipeline_session

    async def _run_pipeline_with_logging() -> None:
        try:
            await advance_fn(
                session.session_id,
                graph=graph,
                session_manager=sm,
                broadcaster=broadcaster,
                pipeline_mode=pipeline_mode,
            )
        except Exception:
            logger.exception("Pipeline task crashed for session %s", session.session_id)
            sm.set_error(session.session_id, "pipeline", "Internal pipeline error")
            await broadcaster.broadcast(
                session.session_id,
                _build_event(
                    "pipeline_error",
                    session_id=session.session_id,
                    stage_key="error",
                    stage_label="Pipeline Error",
                    step_number=None,
                    message="Internal pipeline error.",
                ),
            )
            await broadcaster.close_session(session.session_id)

    asyncio.create_task(_run_pipeline_with_logging())

    return StartPipelineResponse(
        session_id=session.session_id,
        status=PipelineStatus.RUNNING,
        created_at=session.created_at.isoformat(),
        stream_url=f"/api/pipeline/{session.session_id}/stream",
        pipeline_url=f"/{body.language}/pipeline/{session.session_id}",
    )


@router.get("/sessions")
async def list_sessions(request: Request) -> SessionHistoryResponse:
    """List active and recent sessions for dashboard/history views."""

    sm, _ = _get_services(request)
    return sm.list_sessions()


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




def _build_initial_agent_runs() -> list[AgentRunInfo]:
    return [
        AgentRunInfo(
            agent_key=agent["agent_key"],
            agent_label=agent["agent_label"],
            model=agent["model"],
            status=AgentRunStatus.WAITING,
            metric_label=agent["metric_label"],
            metric_value="pending",
            step_key=agent["step_key"],
            step_number=agent["step_number"],
        )
        for agent in AGENT_CATALOG
    ]



def _build_event(event_type: str, **kwargs: Any) -> SSEEvent:
    return SSEEvent(
        event_id=str(uuid.uuid4()),
        type=event_type,
        timestamp=datetime.now(UTC).isoformat(),
        **kwargs,
    )





def _build_deliverables(session_id: str, *, ready: bool) -> list[DeliverableInfo]:
    return [
        DeliverableInfo(
            key="pptx",
            label="Presentation deck",
            ready=ready,
            filename=f"proposal_{session_id[:6]}_en.pptx",
            download_url=f"/api/pipeline/{session_id}/export/pptx" if ready else None,
        ),
        DeliverableInfo(
            key="docx",
            label="Research report",
            ready=ready,
            filename=f"research_report_{session_id[:6]}_en.docx",
            download_url=f"/api/pipeline/{session_id}/export/docx" if ready else None,
        ),
        DeliverableInfo(
            key="source_index",
            label="Source index",
            ready=ready,
            filename=f"source_index_{session_id[:6]}.docx",
            download_url=f"/api/pipeline/{session_id}/export/source_index"
            if ready
            else None,
        ),
        DeliverableInfo(
            key="gap_report",
            label="Gap report",
            ready=ready,
            filename=f"gap_report_{session_id[:6]}.docx",
            download_url=f"/api/pipeline/{session_id}/export/gap_report"
            if ready
            else None,
        ),
    ]
