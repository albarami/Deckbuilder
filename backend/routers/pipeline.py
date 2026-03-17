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
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.models.api_models import (
    APIErrorDetail,
    APIErrorResponse,
    AgentRunInfo,
    AgentRunStatus,
    DeliverableInfo,
    Gate1ContextData,
    Gate2SourceReviewData,
    Gate3ReportReviewData,
    Gate4SlideReviewData,
    Gate5QaReviewData,
    GatePayloadType,
    GapItem,
    PipelineStatus,
    PipelineStatusResponse,
    ReadinessStatus,
    ReportSectionSummary,
    RfpBriefInput,
    SSEEvent,
    SensitivitySummary,
    SessionHistoryResponse,
    SlidePreviewItem,
    SourceIndexItem,
    SourceReviewItem,
    StartPipelineRequest,
    StartPipelineResponse,
    ThumbnailMode,
)
from backend.services.pipeline_runtime import advance_pipeline_session
from backend.services.session_manager import PipelineSession, SessionManager
from backend.services.sse_broadcaster import SSEBroadcaster

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

STAGE_META = {
    "context_analysis": ("Context Understanding", 2),
    "source_research": ("Knowledge Retrieval", 3),
    "analysis": ("Deep Analysis", 4),
    "report_generation": ("Research Report Generation", 5),
    "slide_rendering": ("Iterative Slide Builder", 6),
    "preview_rendering": ("Preview Rendering", 9),
    "quality_assurance": ("Quality Assurance", 8),
    "finalized": ("Finalization & Export", 10),
}


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

    rfp_brief = body.rfp_brief or _build_fallback_brief(body)

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
    session.text_input = body.text_input
    sm.set_agent_runs(session.session_id, _build_initial_agent_runs())
    sm.set_deliverables(session.session_id, _build_deliverables(session.session_id, ready=False))

    asyncio.create_task(
        advance_pipeline_session(
            session.session_id,
            graph=graph,
            session_manager=sm,
            broadcaster=broadcaster,
            pipeline_mode=pipeline_mode,
        )
    )

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


async def _simulate_dry_run_pipeline(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
) -> None:
    """Simulate a production-like end-to-end journey in dry_run mode."""

    session = sm.get(session_id)
    if session is None:
        return

    agent_runs = _build_initial_agent_runs()
    sm.set_agent_runs(session_id, agent_runs)

    await _run_context_phase(session_id, sm, broadcaster, agent_runs)
    await _wait_for_gate_resolution(
        session_id,
        sm,
        broadcaster,
        gate_number=1,
        payload_type=GatePayloadType.CONTEXT_REVIEW,
        gate_data_factory=lambda current: _build_gate1_data(current),
    )

    await _run_retrieval_phase(session_id, sm, broadcaster, agent_runs)
    await _wait_for_gate_resolution(
        session_id,
        sm,
        broadcaster,
        gate_number=2,
        payload_type=GatePayloadType.SOURCE_REVIEW,
        gate_data_factory=lambda current: _build_gate2_data(current),
    )

    await _run_analysis_phase(session_id, sm, broadcaster, agent_runs)
    await _run_research_phase(session_id, sm, broadcaster, agent_runs)
    await _wait_for_gate_resolution(
        session_id,
        sm,
        broadcaster,
        gate_number=3,
        payload_type=GatePayloadType.REPORT_REVIEW,
        gate_data_factory=lambda current: _build_gate3_data(current),
    )

    await _run_slide_phase(session_id, sm, broadcaster, agent_runs)
    await _wait_for_gate_resolution(
        session_id,
        sm,
        broadcaster,
        gate_number=4,
        payload_type=GatePayloadType.SLIDE_REVIEW,
        gate_data_factory=lambda current: _build_gate4_data(current),
    )

    await _run_qa_and_preview_phase(session_id, sm, broadcaster, agent_runs)
    await _wait_for_gate_resolution(
        session_id,
        sm,
        broadcaster,
        gate_number=5,
        payload_type=GatePayloadType.QA_REVIEW,
        gate_data_factory=lambda current: _build_gate5_data(current),
    )

    await _finalize_outputs(session_id, sm, broadcaster, agent_runs)


async def _run_context_phase(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    agent_runs: list[AgentRunInfo],
) -> None:
    await _emit_stage_change(
        session_id,
        sm,
        broadcaster,
        stage_key="context_analysis",
        message="Parsing the RFP brief and preparing the review package.",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "context_agent",
        metric_value="10 fields parsed",
    )


async def _run_retrieval_phase(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    agent_runs: list[AgentRunInfo],
) -> None:
    await _emit_stage_change(
        session_id,
        sm,
        broadcaster,
        stage_key="source_research",
        message="Searching Strategic Gears knowledge sources and ranking evidence.",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "retrieval_planner",
        metric_value="5 search strategies",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "retrieval_ranker",
        metric_value="5 shortlisted sources",
    )


async def _run_analysis_phase(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    agent_runs: list[AgentRunInfo],
) -> None:
    await _emit_stage_change(
        session_id,
        sm,
        broadcaster,
        stage_key="analysis",
        message="Extracting claims, evidence, and reusable delivery patterns.",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "analysis_agent",
        metric_value="42 sourced claims",
    )


async def _run_research_phase(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    agent_runs: list[AgentRunInfo],
) -> None:
    await _emit_stage_change(
        session_id,
        sm,
        broadcaster,
        stage_key="report_generation",
        message="Generating the cited research report for consultant review.",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "research_agent",
        metric_value="2,450 word report",
    )


async def _run_slide_phase(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    agent_runs: list[AgentRunInfo],
) -> None:
    await _emit_stage_change(
        session_id,
        sm,
        broadcaster,
        stage_key="slide_rendering",
        message="Converting the approved report into a reviewable draft deck.",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "draft_agent",
        metric_value="12-slide draft",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "review_agent",
        metric_value="7 review notes",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "refine_agent",
        metric_value="4 revisions applied",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "final_review_agent",
        metric_value="coherence cleared",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "presentation_agent",
        metric_value="12 previews ready",
    )

    session = sm.get(session_id)
    if session:
        sm.set_preview_assets(
            session_id,
            slides_data=_build_slide_data(session_id),
            thumbnail_mode=ThumbnailMode.RENDERED,
            preview_kind=ThumbnailMode.DRAFT,
        )


async def _run_qa_and_preview_phase(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    agent_runs: list[AgentRunInfo],
) -> None:
    await _emit_stage_change(
        session_id,
        sm,
        broadcaster,
        stage_key="quality_assurance",
        message="Running fail-close QA and preparing the final deck preview.",
    )
    await _run_agent(
        session_id,
        sm,
        broadcaster,
        agent_runs,
        "qa_agent",
        metric_value="10 passed · 0 failed",
    )

    for slide_index in range(1, 13):
        render_event = _build_event(
            "render_progress",
            session_id=session_id,
            stage_key="quality_assurance",
            stage_label="Preview Rendering",
            step_number=9,
            slide_index=slide_index,
            total=12,
            message=f"Rendering slide {slide_index} of 12",
        )
        sm.push_event(session_id, render_event)
        await broadcaster.broadcast(session_id, render_event)
        await asyncio.sleep(0.04)

    session = sm.get(session_id)
    if session:
        sm.set_preview_assets(
            session_id,
            slides_data=_build_slide_data(session_id),
            thumbnail_mode=ThumbnailMode.RENDERED,
            preview_kind=ThumbnailMode.RENDERED,
        )


async def _finalize_outputs(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    agent_runs: list[AgentRunInfo],
) -> None:
    sm.set_agent_runs(session_id, _mark_all_complete(agent_runs))
    deliverables = _build_deliverables(session_id, ready=True)
    sm.set_complete(
        session_id,
        slide_count=12,
        deliverables=deliverables,
    )

    complete_event = _build_event(
        "pipeline_complete",
        session_id=session_id,
        stage_key="finalized",
        stage_label="Finalization & Export",
        step_number=10,
        slide_count=12,
        message="Deck, report, source index, and gap report are ready.",
    )
    sm.push_event(session_id, complete_event)
    await broadcaster.broadcast(session_id, complete_event)
    await broadcaster.close_session(session_id)


async def _wait_for_gate_resolution(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    *,
    gate_number: int,
    payload_type: GatePayloadType,
    gate_data_factory: Any,
) -> None:
    while True:
        session = sm.get(session_id)
        if session is None:
            return

        gate_summary = _gate_summary_for(session, gate_number)
        gate_data = gate_data_factory(session)

        sm.set_gate_pending(
            session_id,
            gate_number=gate_number,
            summary=gate_summary,
            prompt=f"Gate {gate_number}: review, approve, or reject with feedback.",
            payload_type=payload_type,
            gate_data=gate_data,
        )

        gate_event = _build_event(
            "gate_pending",
            session_id=session_id,
            stage_key=session.current_stage,
            stage_label=session.current_stage_label,
            step_number=session.current_step_number,
            gate_number=gate_number,
            gate_payload_type=payload_type,
            summary=gate_summary,
            prompt=f"Gate {gate_number}: review, approve, or reject with feedback.",
            gate_data=gate_data.model_dump() if hasattr(gate_data, "model_dump") else gate_data,
            message=gate_summary,
        )
        sm.push_event(session_id, gate_event)
        await broadcaster.broadcast(session_id, gate_event)

        previous_count = len(session.completed_gates)

        while True:
            await asyncio.sleep(0.1)
            current = sm.get(session_id)
            if current is None:
                return
            if len(current.completed_gates) > previous_count:
                break

        current = sm.get(session_id)
        if current is None:
            return

        latest = current.completed_gates[-1]
        if latest.approved:
            return

        await _emit_stage_change(
            session_id,
            sm,
            broadcaster,
            stage_key=current.current_stage,
            message=f"Revision requested for Gate {gate_number}. Rebuilding with feedback.",
        )
        await asyncio.sleep(0.25)


async def _emit_stage_change(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    *,
    stage_key: str,
    message: str,
) -> None:
    stage_label, step_number = STAGE_META.get(
        stage_key, (stage_key.replace("_", " ").title(), None)
    )
    sm.update_stage(
        session_id,
        stage_key,
        stage_label=stage_label,
        step_number=step_number,
    )
    event = _build_event(
        "stage_change",
        session_id=session_id,
        stage=stage_key,
        stage_key=stage_key,
        stage_label=stage_label,
        step_number=step_number,
        message=message,
    )
    sm.push_event(session_id, event)
    await broadcaster.broadcast(session_id, event)
    await asyncio.sleep(0.18)


async def _run_agent(
    session_id: str,
    sm: SessionManager,
    broadcaster: SSEBroadcaster,
    agent_runs: list[AgentRunInfo],
    agent_key: str,
    *,
    metric_value: str,
) -> None:
    run = next(run for run in agent_runs if run.agent_key == agent_key)
    now_iso = datetime.now(timezone.utc).isoformat()
    run.status = AgentRunStatus.RUNNING
    run.started_at = now_iso
    run.metric_value = metric_value
    sm.set_agent_runs(session_id, agent_runs)

    start_event = _build_event(
        "agent_start",
        session_id=session_id,
        agent=agent_key,
        agent_key=run.agent_key,
        agent_label=run.agent_label,
        model=run.model,
        metric_label=run.metric_label,
        metric_value=run.metric_value,
        step_number=run.step_number,
        message=f"{run.agent_label} started",
    )
    sm.push_event(session_id, start_event)
    await broadcaster.broadcast(session_id, start_event)
    await asyncio.sleep(0.2)

    completed_at = datetime.now(timezone.utc).isoformat()
    run.status = AgentRunStatus.COMPLETE
    run.completed_at = completed_at
    run.duration_ms = 200
    sm.set_agent_runs(session_id, agent_runs)

    complete_event = _build_event(
        "agent_complete",
        session_id=session_id,
        agent=agent_key,
        agent_key=run.agent_key,
        agent_label=run.agent_label,
        model=run.model,
        metric_label=run.metric_label,
        metric_value=run.metric_value,
        duration_ms=run.duration_ms,
        step_number=run.step_number,
        message=f"{run.agent_label} completed",
    )
    sm.push_event(session_id, complete_event)
    await broadcaster.broadcast(session_id, complete_event)


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


def _mark_all_complete(agent_runs: list[AgentRunInfo]) -> list[AgentRunInfo]:
    for run in agent_runs:
        if run.status != AgentRunStatus.COMPLETE:
            run.status = AgentRunStatus.COMPLETE
            run.duration_ms = run.duration_ms or 200
            run.started_at = run.started_at or datetime.now(timezone.utc).isoformat()
            run.completed_at = run.completed_at or datetime.now(timezone.utc).isoformat()
            run.metric_value = run.metric_value or "ready"
    return agent_runs


def _build_event(event_type: str, **kwargs: Any) -> SSEEvent:
    return SSEEvent(
        event_id=str(uuid.uuid4()),
        type=event_type,
        timestamp=datetime.now(timezone.utc).isoformat(),
        **kwargs,
    )


def _build_fallback_brief(body: StartPipelineRequest) -> RfpBriefInput:
    summary = (body.text_input or "").strip()
    if not summary:
        summary = (
            f"Proposal request for the {body.sector or 'general'} sector in "
            f"{body.geography or 'KSA'}."
        )

    return RfpBriefInput(
        rfp_name={"en": "Mock RFP", "ar": ""},
        issuing_entity="Mock Government Entity",
        procurement_platform="BD Station",
        mandate_summary=summary,
        scope_requirements=[
            "Deliver a transformation roadmap",
            "Recommend implementation governance",
            "Define milestones and success metrics",
        ],
        deliverables=[
            "Proposal deck",
            "Research report",
            "Source index",
        ],
        mandatory_compliance=[
            "Arabic/English delivery support",
            "Government-ready governance model",
        ],
    )


def _gate_summary_for(session: PipelineSession, gate_number: int) -> str:
    match gate_number:
        case 1:
            return f"RFP context parsed for {session.issuing_entity or 'the issuing entity'}."
        case 2:
            return "Retrieved and ranked evidence sources are ready for review."
        case 3:
            return "Cited research report ready for report-first approval."
        case 4:
            return "Draft slide structure and previews are ready for review."
        case 5:
            return "QA is complete and the rendered deck preview is ready for final approval."
        case _:
            return "Review required."


def _build_gate1_data(session: PipelineSession) -> Gate1ContextData:
    brief = session.rfp_brief or RfpBriefInput()
    missing_fields = []
    if not brief.issuing_entity:
        missing_fields.append("issuing_entity")
    if not brief.mandate_summary:
        missing_fields.append("mandate_summary")
    if not brief.scope_requirements:
        missing_fields.append("scope_requirements")

    return Gate1ContextData(
        rfp_brief=brief,
        missing_fields=missing_fields,
        selected_output_language=session.language,
        user_notes=session.user_notes,
        evaluation_highlights=[
            "Technical evaluation weighted at 70%",
            "Financial evaluation weighted at 30%",
            "Compliance evidence required before finalization",
        ],
    )


def _build_gate2_data(session: PipelineSession) -> Gate2SourceReviewData:
    sources = [
        SourceReviewItem(
            source_id="DOC-001",
            title="ERP Modernization Case Study",
            url="sharepoint://projects/erp-modernization",
            relevance_score=0.94,
            snippet="Strategic Gears delivered an ERP modernization roadmap for a Saudi public-sector entity.",
            matched_criteria=["ERP transformation", "governance"],
        ),
        SourceReviewItem(
            source_id="DOC-014",
            title="Digital Transformation Delivery Framework",
            url="sharepoint://frameworks/digital-transformation",
            relevance_score=0.88,
            snippet="Reusable governance framework covering mobilization, PMO, and benefits realization.",
            matched_criteria=["delivery methodology", "governance"],
        ),
        SourceReviewItem(
            source_id="DOC-021",
            title="Arabic Government Proposal Library",
            url="sharepoint://proposals/government-arabic",
            relevance_score=0.81,
            snippet="Bilingual proposal patterns and sector-specific compliance content.",
            matched_criteria=["Arabic delivery", "government proposals"],
        ),
        SourceReviewItem(
            source_id="DOC-033",
            title="Saudi Delivery Team Profiles",
            url="sharepoint://people/ksa-delivery",
            relevance_score=0.78,
            snippet="Named team profiles with transformation, PMO, and ERP delivery backgrounds.",
            matched_criteria=["team composition", "delivery roles"],
        ),
        SourceReviewItem(
            source_id="DOC-047",
            title="Compliance and Quality Control Matrix",
            url="sharepoint://compliance/quality-matrix",
            relevance_score=0.73,
            snippet="Template-aligned compliance matrix and QA standards used in past bids.",
            matched_criteria=["compliance", "quality assurance"],
        ),
    ]

    return Gate2SourceReviewData(
        sources=sources,
        retrieval_strategies=[
            "RFP-aligned retrieval",
            "Capability match",
            "Similar proposal reuse",
            "Team profile search",
            "Framework search",
        ],
        source_count=len(sources),
    )


def _build_gate3_data(session: PipelineSession) -> Gate3ReportReviewData:
    report_markdown = (
        "# Executive Summary\n"
        "Strategic Gears proposes a phased ERP modernization program for the issuing entity, "
        "grounded in source-backed delivery experience and reusable governance frameworks.\n\n"
        "## Requirements Analysis\n"
        "- Governance model aligned to the RFP [Ref: DOC-014]\n"
        "- ERP modernization delivery pattern [Ref: DOC-001]\n"
        "- Arabic/English delivery support [Ref: DOC-021]\n\n"
        "## Relevant Experience\n"
        "- ERP modernization roadmap for a Saudi public-sector entity [Ref: DOC-001]\n"
        "- Government proposal operating model and bilingual delivery [Ref: DOC-021]\n\n"
        "## Gaps\n"
        "- GAP: current client-specific compliance certificate copy required.\n"
    )

    return Gate3ReportReviewData(
        report_markdown=report_markdown,
        sections=[
            ReportSectionSummary(
                section_id="executive_summary",
                title="Executive Summary",
                claim_count=5,
                gap_count=0,
            ),
            ReportSectionSummary(
                section_id="requirements_analysis",
                title="Requirements Analysis",
                claim_count=7,
                gap_count=0,
            ),
            ReportSectionSummary(
                section_id="relevant_experience",
                title="Relevant Experience",
                claim_count=6,
                gap_count=1,
            ),
        ],
        gaps=[
            GapItem(
                gap_id="GAP-001",
                label="Compliance evidence",
                description="Client-specific certificate evidence is still required before final sign-off.",
                severity="critical",
                status="open",
            )
        ],
        sensitivity_summary=[
            SensitivitySummary(tag="capability", count=6),
            SensitivitySummary(tag="compliance", count=2),
            SensitivitySummary(tag="general", count=10),
        ],
        source_index=[
            SourceIndexItem(
                source_id="DOC-001",
                title="ERP Modernization Case Study",
                location="Section 3",
                url="sharepoint://projects/erp-modernization",
            ),
            SourceIndexItem(
                source_id="DOC-014",
                title="Digital Transformation Delivery Framework",
                location="Section 5",
                url="sharepoint://frameworks/digital-transformation",
            ),
            SourceIndexItem(
                source_id="DOC-021",
                title="Arabic Government Proposal Library",
                location="Section 2",
                url="sharepoint://proposals/government-arabic",
            ),
        ],
    )


def _build_gate4_data(session: PipelineSession) -> Gate4SlideReviewData:
    slides = [
        SlidePreviewItem(
            slide_id=slide.get("slide_id", f"S-{slide['slide_number']:03d}"),
            slide_number=slide["slide_number"],
            title=slide.get("title", f"Slide {slide['slide_number']}"),
            key_message=slide.get("key_message", ""),
            layout_type=slide.get("layout_type", ""),
            body_content_preview=slide.get("body_content_preview", []),
            source_claims=slide.get("source_claims", []),
            source_refs=slide.get("source_refs", []),
            section=slide.get("section_id", "section"),
            slide_type=slide.get("entry_type", "content"),
            report_section_ref=slide.get("report_section_ref"),
            rfp_criterion_ref=slide.get("rfp_criterion_ref"),
            speaker_notes_preview=slide.get("speaker_notes_preview", ""),
            sensitivity_tags=slide.get("sensitivity_tags", []),
            content_guidance=slide.get("content_guidance", ""),
            change_history_count=slide.get("change_history_count", 0),
            thumbnail_url=slide.get("thumbnail_url"),
            preview_kind=ThumbnailMode.DRAFT,
        )
        for slide in session.slides_data
    ]
    return Gate4SlideReviewData(
        slides=slides,
        slide_count=len(slides),
        thumbnail_mode=session.thumbnail_mode,
        preview_ready=session.outputs.preview_ready,
    )


def _build_gate5_data(session: PipelineSession) -> Gate5QaReviewData:
    return Gate5QaReviewData(
        submission_readiness=ReadinessStatus.READY,
        fail_close=False,
        critical_gaps=[],
        lint_status=ReadinessStatus.READY,
        density_status=ReadinessStatus.READY,
        template_compliance=ReadinessStatus.READY,
        language_status=ReadinessStatus.READY,
        coverage_status=ReadinessStatus.READY,
        waivers=[],
        results=[
            {
                "slide_index": 1,
                "check": "No Free Facts coverage",
                "status": "pass",
                "details": "All claims map to approved sources.",
            },
            {
                "slide_index": 3,
                "check": "Template compliance",
                "status": "pass",
                "details": "Colors, typography, and layout match the template system.",
            },
            {
                "slide_index": 7,
                "check": "Density control",
                "status": "warning",
                "details": "Slide 7 is close to the density threshold but still acceptable.",
            },
        ],
        deliverables=_build_deliverables(session.session_id, ready=False),
    )


def _build_slide_data(session_id: str) -> list[dict[str, Any]]:
    return [
        {
            "slide_id": f"S-{index+1:03d}",
            "slide_number": index + 1,
            "entry_type": "content" if index else "title",
            "asset_id": f"slide_{index+1}",
            "semantic_layout_id": f"layout_{(index % 4) + 1}",
            "section_id": f"Section {(index // 3) + 1}",
            "title": title,
            "key_message": f"Key message for {title}",
            "layout_type": "CONTENT_2COL" if index % 3 else "FRAMEWORK",
            "body_content_preview": [
                f"Approved point {index + 1}.1",
                f"Approved point {index + 1}.2",
            ],
            "source_claims": [f"CLM-{index+1:04d}"],
            "source_refs": [f"CLM-{index+1:04d}", f"CLM-{index+13:04d}"],
            "shape_count": 5 + (index % 3),
            "fonts": ["IBM Plex Sans", "IBM Plex Mono"] if index % 2 else ["IBM Plex Sans"],
            "text_preview": f"{title} — source-backed delivery content for the live proposal draft.",
            "thumbnail_url": f"/api/pipeline/{session_id}/slides/{index+1}/thumbnail.png?preview_kind=draft",
            "report_section_ref": f"section_{(index // 3) + 1}",
            "rfp_criterion_ref": f"criterion_{(index % 4) + 1}",
            "speaker_notes_preview": f"Speaker notes for {title}.",
            "sensitivity_tags": ["capability"] if index % 4 else ["compliance"],
            "content_guidance": f"Derived from approved report section {(index // 3) + 1}.",
            "change_history_count": 2,
        }
        for index, title in enumerate(
            [
                "Executive Summary",
                "Client Mandate",
                "Transformation Opportunity",
                "Approach Overview",
                "Workstreams",
                "Delivery Governance",
                "Team Composition",
                "Roadmap & Timeline",
                "Compliance Matrix",
                "Benefits & KPIs",
                "Implementation Risks",
                "Closing & Next Steps",
            ]
        )
    ]


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
