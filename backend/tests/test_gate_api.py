"""
Tests for gate decision endpoint:
- POST /api/pipeline/{id}/gate/{n}/decide

All tests run with PIPELINE_MODE=dry_run. Zero LLM calls.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from backend.models.api_models import GatePayloadType, PipelineStatus
from backend.services.session_manager import SessionManager


async def _create_session_at_gate(
    client: AsyncClient, sm: SessionManager, gate_number: int = 1
) -> str:
    """Helper: create a session and manually set it to a gate."""
    resp = await client.post(
        "/api/pipeline/start",
        json={
            "text_input": "Test RFP for gate testing",
            "language": "en",
            "proposal_mode": "standard",
            "sector": "Tech",
            "geography": "MENA",
        },
    )
    session_id = resp.json()["session_id"]

    # Wait for dry-run to hit the first gate
    for _ in range(50):
        session = sm.get(session_id)
        if session and session.status == PipelineStatus.GATE_PENDING:
            if session.current_gate and session.current_gate.gate_number == gate_number:
                return session_id
        await asyncio.sleep(0.1)

    # If we didn't reach the desired gate, manually set it
    sm.set_gate_pending(
        session_id,
        gate_number=gate_number,
        summary=f"Test gate {gate_number} summary",
        prompt=f"Gate {gate_number}: Approve?",
        payload_type=GatePayloadType.CONTEXT_REVIEW,
    )
    return session_id


@pytest.mark.asyncio
async def test_approve_gate(client: AsyncClient, sm: SessionManager) -> None:
    """POST approve decision resumes pipeline."""
    session_id = await _create_session_at_gate(client, sm, gate_number=1)

    resp = await client.post(
        f"/api/pipeline/{session_id}/gate/1/decide",
        json={"approved": True},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["gate_number"] == 1
    assert data["decision"] == "approved"
    assert data["pipeline_status"] in ("running", "complete")


@pytest.mark.asyncio
async def test_reject_gate_with_feedback(
    client: AsyncClient, sm: SessionManager
) -> None:
    """POST reject decision with feedback ends pipeline."""
    session_id = await _create_session_at_gate(client, sm, gate_number=1)

    resp = await client.post(
        f"/api/pipeline/{session_id}/gate/1/decide",
        json={"approved": False, "feedback": "Needs more context"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["gate_number"] == 1
    assert data["decision"] == "rejected"
    # Gate rejection triggers revision loop, pipeline keeps running
    assert data["pipeline_status"] == "running"


@pytest.mark.asyncio
async def test_reject_gate_without_feedback_422(
    client: AsyncClient, sm: SessionManager
) -> None:
    """POST reject without feedback returns 422."""
    session_id = await _create_session_at_gate(client, sm, gate_number=1)

    resp = await client.post(
        f"/api/pipeline/{session_id}/gate/1/decide",
        json={"approved": False},
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["detail"]["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_gate_not_found_session(client: AsyncClient) -> None:
    """POST gate decide for missing session returns 404."""
    resp = await client.post(
        "/api/pipeline/nonexistent/gate/1/decide",
        json={"approved": True},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_gate_not_pending_409(
    client: AsyncClient, sm: SessionManager
) -> None:
    """POST gate decide when not at gate returns 409."""
    # Create session in RUNNING state (not gate pending)
    session = sm.create(
        language="en",
        proposal_mode="standard",
        sector="Tech",
        geography="MENA",
        renderer_mode="legacy",
    )
    session.status = PipelineStatus.RUNNING

    resp = await client.post(
        f"/api/pipeline/{session.session_id}/gate/1/decide",
        json={"approved": True},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "GATE_NOT_PENDING"


@pytest.mark.asyncio
async def test_wrong_gate_number_409(
    client: AsyncClient, sm: SessionManager
) -> None:
    """POST gate decide for wrong gate number returns 409."""
    session_id = await _create_session_at_gate(client, sm, gate_number=1)

    # Try to decide gate 3 when gate 1 is pending
    resp = await client.post(
        f"/api/pipeline/{session_id}/gate/3/decide",
        json={"approved": True},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_gate_decision_recorded(
    client: AsyncClient, sm: SessionManager
) -> None:
    """Gate decision is recorded in completed_gates list."""
    session_id = await _create_session_at_gate(client, sm, gate_number=1)

    await client.post(
        f"/api/pipeline/{session_id}/gate/1/decide",
        json={"approved": True},
    )

    session = sm.get(session_id)
    assert session is not None
    assert len(session.completed_gates) >= 1
    gate = session.completed_gates[-1]
    assert gate.gate_number == 1
    assert gate.approved is True
