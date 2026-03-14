"""
DeckForge Backend — Gates Router

Endpoint:
- POST /api/pipeline/{id}/gate/{n}/decide → Submit gate decision
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.models.api_models import (
    APIErrorDetail,
    APIErrorResponse,
    GateDecisionRequest,
    GateDecisionResponse,
    PipelineStatus,
)
from backend.services.session_manager import SessionManager

router = APIRouter(prefix="/api/pipeline", tags=["gates"])


@router.post("/{session_id}/gate/{gate_number}/decide")
async def decide_gate(
    session_id: str,
    gate_number: int,
    body: GateDecisionRequest,
    request: Request,
) -> GateDecisionResponse:
    """Submit a gate approval or rejection decision."""
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

    # Validate gate state
    if session.status != PipelineStatus.GATE_PENDING:
        raise HTTPException(
            status_code=409,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="GATE_NOT_PENDING",
                    message=f"Session is not waiting at a gate. Current status: {session.status}.",
                )
            ).model_dump(),
        )

    if session.current_gate is None or session.current_gate.gate_number != gate_number:
        raise HTTPException(
            status_code=409,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="GATE_NOT_PENDING",
                    message=f"Gate {gate_number} is not the current pending gate.",
                )
            ).model_dump(),
        )

    # Validate rejection requires feedback
    if not body.approved and not body.feedback:
        raise HTTPException(
            status_code=422,
            detail=APIErrorResponse(
                error=APIErrorDetail(
                    code="INVALID_INPUT",
                    message="Feedback is required when rejecting a gate.",
                )
            ).model_dump(),
        )

    # Record the decision
    sm.record_gate_decision(
        session_id=session_id,
        gate_number=gate_number,
        approved=body.approved,
        feedback=body.feedback or "",
    )

    # Determine post-decision status
    if body.approved:
        pipeline_status = PipelineStatus.RUNNING
    else:
        pipeline_status = PipelineStatus.COMPLETE  # Rejected = pipeline ends

    return GateDecisionResponse(
        gate_number=gate_number,
        decision="approved" if body.approved else "rejected",
        pipeline_status=pipeline_status,
    )
