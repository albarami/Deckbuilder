"""
Tests for session resume contract.

Verifies that GET /api/pipeline/{id}/status returns the correct state
for resume-from-refresh scenarios: gate_pending, running, complete, error.
All tests run with PIPELINE_MODE=dry_run. Zero LLM calls.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.models.api_models import PipelineStatus
from backend.services.session_manager import SessionManager


def _create_session(
    sm: SessionManager,
    status: PipelineStatus = PipelineStatus.RUNNING,
    language: str = "en",
) -> str:
    """Helper: create a session with given status."""
    session = sm.create(
        language=language,
        proposal_mode="standard",
        sector="Tech",
        geography="MENA",
        renderer_mode="legacy",
    )
    session.status = status
    return session.session_id


@pytest.mark.asyncio
async def test_resume_running_state(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /status for a running session returns running state with stage."""
    session_id = _create_session(sm, PipelineStatus.RUNNING)
    session = sm.get(session_id)
    assert session is not None
    session.current_stage = "source_research"

    resp = await client.get(f"/api/pipeline/{session_id}/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["session_id"] == session_id
    assert data["status"] == "running"
    assert data["current_stage"] == "source_research"
    assert data["current_gate"] is None
    assert data["started_at"] is not None
    assert data["elapsed_ms"] >= 0
    assert data["error"] is None


@pytest.mark.asyncio
async def test_resume_gate_pending_state(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /status for a gate_pending session returns gate info."""
    session_id = _create_session(sm, PipelineStatus.RUNNING)

    # Set gate pending
    sm.set_gate_pending(
        session_id,
        gate_number=3,
        summary="Report generation complete",
        prompt="Review the generated report before proceeding",
        gate_data={"report_preview": "# Executive Summary\n\nKey findings..."},
    )

    resp = await client.get(f"/api/pipeline/{session_id}/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "gate_pending"
    assert data["current_gate"] is not None
    assert data["current_gate"]["gate_number"] == 3
    assert data["current_gate"]["summary"] == "Report generation complete"
    assert data["current_gate"]["prompt"] == "Review the generated report before proceeding"
    assert data["current_gate"]["gate_data"] is not None


@pytest.mark.asyncio
async def test_resume_complete_state(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /status for a complete session returns outputs."""
    session_id = _create_session(sm, PipelineStatus.RUNNING)
    sm.set_complete(
        session_id,
        pptx_path="proposals/output.pptx",
        docx_path="proposals/output.docx",
        slide_count=25,
    )

    resp = await client.get(f"/api/pipeline/{session_id}/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "complete"
    assert data["current_stage"] == "finalized"
    assert data["outputs"] is not None
    assert data["outputs"]["pptx_ready"] is True
    assert data["outputs"]["docx_ready"] is True
    assert data["outputs"]["slide_count"] == 25


@pytest.mark.asyncio
async def test_resume_error_state(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /status for an error session returns error details."""
    session_id = _create_session(sm, PipelineStatus.RUNNING)
    sm.set_error(session_id, agent="renderer", message="Template not found")

    resp = await client.get(f"/api/pipeline/{session_id}/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "error"
    assert data["current_stage"] == "error"
    assert data["error"] is not None
    assert data["error"]["agent"] == "renderer"
    assert data["error"]["message"] == "Template not found"


@pytest.mark.asyncio
async def test_resume_with_completed_gates(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /status includes previously completed gates."""
    session_id = _create_session(sm, PipelineStatus.RUNNING)

    # Record two gate approvals
    sm.record_gate_decision(session_id, gate_number=1, approved=True)
    sm.record_gate_decision(session_id, gate_number=2, approved=True, feedback="Looks good")

    # Set gate 3 pending
    sm.set_gate_pending(
        session_id,
        gate_number=3,
        summary="Ready for review",
        prompt="Review results",
    )

    resp = await client.get(f"/api/pipeline/{session_id}/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "gate_pending"
    assert len(data["completed_gates"]) == 2
    assert data["completed_gates"][0]["gate_number"] == 1
    assert data["completed_gates"][0]["approved"] is True
    assert data["completed_gates"][1]["gate_number"] == 2
    assert data["completed_gates"][1]["approved"] is True
    assert data["current_gate"]["gate_number"] == 3


@pytest.mark.asyncio
async def test_resume_expired_session_404(
    client: AsyncClient,
) -> None:
    """GET /status for non-existent session returns 404."""
    resp = await client.get("/api/pipeline/expired-session-id/status")
    assert resp.status_code == 404

    data = resp.json()
    assert data["detail"]["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_resume_includes_metadata(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /status includes session metadata (LLM call counts, cost)."""
    session_id = _create_session(sm, PipelineStatus.RUNNING)
    session = sm.get(session_id)
    assert session is not None

    # Update metadata
    session.metadata.total_llm_calls = 15
    session.metadata.total_input_tokens = 50000
    session.metadata.total_output_tokens = 20000
    session.metadata.total_cost_usd = 1.25

    resp = await client.get(f"/api/pipeline/{session_id}/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["session_metadata"] is not None
    assert data["session_metadata"]["total_llm_calls"] == 15
    assert data["session_metadata"]["total_input_tokens"] == 50000
    assert data["session_metadata"]["total_output_tokens"] == 20000
    assert data["session_metadata"]["total_cost_usd"] == 1.25


@pytest.mark.asyncio
async def test_resume_arabic_session(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /status works for Arabic language sessions."""
    session_id = _create_session(sm, PipelineStatus.RUNNING, language="ar")
    session = sm.get(session_id)
    assert session is not None
    session.current_stage = "context_analysis"

    resp = await client.get(f"/api/pipeline/{session_id}/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["session_id"] == session_id
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_resume_multiple_sessions_independent(
    client: AsyncClient, sm: SessionManager
) -> None:
    """Multiple sessions are independent — status for one doesn't affect another."""
    s1 = _create_session(sm, PipelineStatus.RUNNING)
    s2 = _create_session(sm, PipelineStatus.RUNNING)

    sm.set_gate_pending(s1, gate_number=2, summary="Gate 2", prompt="Review")
    sm.set_complete(s2, pptx_path="out.pptx", slide_count=10)

    r1 = await client.get(f"/api/pipeline/{s1}/status")
    r2 = await client.get(f"/api/pipeline/{s2}/status")

    assert r1.json()["status"] == "gate_pending"
    assert r2.json()["status"] == "complete"
    assert r1.json()["session_id"] != r2.json()["session_id"]
