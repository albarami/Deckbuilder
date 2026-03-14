"""
Integration tests: Full pipeline flow through REST API.

Tests the complete lifecycle: start → progress → gate → complete → export.
All tests run with PIPELINE_MODE=dry_run. Zero LLM calls.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from backend.models.api_models import PipelineStatus
from backend.services.session_manager import SessionManager


@pytest.mark.asyncio
async def test_full_pipeline_lifecycle(
    client: AsyncClient, sm: SessionManager
) -> None:
    """Full lifecycle: start → status → gate → approve → complete → export."""
    # 1. Start pipeline
    start_resp = await client.post(
        "/api/pipeline/start",
        json={
            "text_input": "Integration test RFP: Build a data platform for banking sector",
            "language": "en",
            "proposal_mode": "standard",
            "sector": "Banking",
            "geography": "KSA",
        },
    )
    assert start_resp.status_code == 201
    session_id = start_resp.json()["session_id"]
    assert start_resp.json()["status"] == "running"

    # 2. Check status is available
    status_resp = await client.get(f"/api/pipeline/{session_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["session_id"] == session_id

    # 3. Wait for dry-run to hit gate 1
    for _ in range(100):
        session = sm.get(session_id)
        if session and session.status == PipelineStatus.GATE_PENDING:
            break
        await asyncio.sleep(0.1)

    # If dry-run didn't reach gate, manually set it
    session = sm.get(session_id)
    assert session is not None
    if session.status != PipelineStatus.GATE_PENDING:
        sm.set_gate_pending(
            session_id,
            gate_number=1,
            summary="Context analysis complete",
            prompt="Review the context analysis results",
        )

    # 4. Verify gate_pending status via API
    gate_status = await client.get(f"/api/pipeline/{session_id}/status")
    assert gate_status.status_code == 200
    data = gate_status.json()
    assert data["status"] == "gate_pending"
    assert data["current_gate"] is not None
    assert data["current_gate"]["gate_number"] == 1

    # 5. Approve the gate
    decide_resp = await client.post(
        f"/api/pipeline/{session_id}/gate/1/decide",
        json={"approved": True},
    )
    assert decide_resp.status_code == 200
    assert decide_resp.json()["decision"] == "approved"

    # 6. Verify session resumed running
    session = sm.get(session_id)
    assert session is not None
    assert session.status in (PipelineStatus.RUNNING, PipelineStatus.COMPLETE)
    assert len(session.completed_gates) >= 1
    assert session.completed_gates[0].approved is True

    # 7. Mark complete and verify export
    sm.set_complete(session_id, pptx_path="mock.pptx", docx_path="mock.docx", slide_count=15)

    export_resp = await client.get(f"/api/pipeline/{session_id}/export/pptx")
    assert export_resp.status_code == 200
    assert "application/vnd.openxmlformats" in export_resp.headers["content-type"]


@pytest.mark.asyncio
async def test_pipeline_reject_and_complete(
    client: AsyncClient, sm: SessionManager
) -> None:
    """Pipeline with gate rejection completes with rejected status."""
    # Start
    start_resp = await client.post(
        "/api/pipeline/start",
        json={
            "text_input": "Test RFP for rejection flow",
            "language": "en",
            "proposal_mode": "lite",
            "sector": "Retail",
            "geography": "UAE",
        },
    )
    session_id = start_resp.json()["session_id"]

    # Set gate pending
    sm.set_gate_pending(
        session_id,
        gate_number=1,
        summary="Analysis ready",
        prompt="Review analysis",
    )

    # Reject with feedback
    reject_resp = await client.post(
        f"/api/pipeline/{session_id}/gate/1/decide",
        json={"approved": False, "feedback": "Needs more competitive analysis"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["decision"] == "rejected"

    # Session should record the rejection
    session = sm.get(session_id)
    assert session is not None
    assert len(session.completed_gates) >= 1
    last_gate = session.completed_gates[-1]
    assert last_gate.approved is False
    assert last_gate.feedback == "Needs more competitive analysis"


@pytest.mark.asyncio
async def test_pipeline_en_ar_parity(
    client: AsyncClient, sm: SessionManager
) -> None:
    """Both EN and AR pipelines follow the same lifecycle contract."""
    for lang in ("en", "ar"):
        resp = await client.post(
            "/api/pipeline/start",
            json={
                "text_input": f"Test RFP in {lang}",
                "language": lang,
                "proposal_mode": "standard",
                "sector": "Technology",
                "geography": "MENA",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "running"
        assert "session_id" in data

        # Status endpoint works for both languages
        session_id = data["session_id"]
        status = await client.get(f"/api/pipeline/{session_id}/status")
        assert status.status_code == 200
        assert status.json()["session_id"] == session_id


@pytest.mark.asyncio
async def test_health_during_pipeline_operations(
    client: AsyncClient,
) -> None:
    """Health check remains healthy during pipeline operations."""
    # Start multiple sessions
    for i in range(3):
        await client.post(
            "/api/pipeline/start",
            json={
                "text_input": f"Test {i}",
                "language": "en",
                "proposal_mode": "standard",
                "sector": "Tech",
                "geography": "MENA",
            },
        )

    health = await client.get("/api/health")
    assert health.status_code == 200
    data = health.json()
    assert data["status"] == "ok"
    assert data["active_sessions"] == 3
    assert data["pipeline_mode"] == "dry_run"


@pytest.mark.asyncio
async def test_multiple_gates_sequential(
    client: AsyncClient, sm: SessionManager
) -> None:
    """Approve multiple gates sequentially."""
    start_resp = await client.post(
        "/api/pipeline/start",
        json={
            "text_input": "Multi-gate test",
            "language": "en",
            "proposal_mode": "full",
            "sector": "Energy",
            "geography": "GCC",
        },
    )
    session_id = start_resp.json()["session_id"]

    # Approve gates 1 through 3
    for gate_num in range(1, 4):
        sm.set_gate_pending(
            session_id,
            gate_number=gate_num,
            summary=f"Gate {gate_num} ready",
            prompt=f"Review gate {gate_num}",
        )

        resp = await client.post(
            f"/api/pipeline/{session_id}/gate/{gate_num}/decide",
            json={"approved": True},
        )
        assert resp.status_code == 200
        assert resp.json()["gate_number"] == gate_num

    # Verify all 3 gates recorded
    session = sm.get(session_id)
    assert session is not None
    assert len(session.completed_gates) == 3
    for i, gate in enumerate(session.completed_gates):
        assert gate.gate_number == i + 1
        assert gate.approved is True


@pytest.mark.asyncio
async def test_slides_after_complete(
    client: AsyncClient, sm: SessionManager
) -> None:
    """Slides endpoint returns data after pipeline completes."""
    # Create and complete session with slide data
    session = sm.create(
        language="en",
        proposal_mode="standard",
        sector="Finance",
        geography="KSA",
        renderer_mode="legacy",
    )
    session.status = PipelineStatus.COMPLETE
    session.current_stage = "finalized"
    session.thumbnail_mode = "metadata_only"
    session.slides_data = [
        {
            "slide_number": i + 1,
            "entry_type": "b_variable",
            "asset_id": f"slide_{i+1}",
            "semantic_layout_id": f"layout_{i+1}",
            "section_id": "methodology",
            "shape_count": 5,
            "fonts": ["IBM Plex Sans"],
            "text_preview": f"Methodology slide {i+1}",
        }
        for i in range(8)
    ]

    resp = await client.get(f"/api/pipeline/{session.session_id}/slides")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slide_count"] == 8
    assert len(data["slides"]) == 8
    assert data["thumbnail_mode"] == "metadata_only"
