"""
Tests for pipeline endpoints:
- POST /api/pipeline/start
- GET  /api/pipeline/{id}/status
- GET  /api/health

All tests run with PIPELINE_MODE=dry_run. Zero LLM calls.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """GET /api/health returns ok with dry_run mode."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "ok"
    assert data["pipeline_mode"] == "dry_run"
    assert data["active_sessions"] == 0
    assert "version" in data


@pytest.mark.asyncio
async def test_start_pipeline(client: AsyncClient) -> None:
    """POST /api/pipeline/start creates a session."""
    resp = await client.post(
        "/api/pipeline/start",
        json={
            "text_input": "Mock RFP content for testing",
            "language": "en",
            "proposal_mode": "standard",
            "sector": "Technology",
            "geography": "Middle East",
        },
    )
    assert resp.status_code == 201

    data = resp.json()
    assert data["status"] == "running"
    assert "session_id" in data
    assert "created_at" in data
    assert data["stream_url"].startswith("/api/pipeline/")
    assert data["stream_url"].endswith("/stream")


@pytest.mark.asyncio
async def test_start_pipeline_with_documents(client: AsyncClient) -> None:
    """POST /api/pipeline/start with document references."""
    resp = await client.post(
        "/api/pipeline/start",
        json={
            "documents": [
                {"upload_id": "test-upload-1", "filename": "rfp.pdf"}
            ],
            "language": "ar",
            "proposal_mode": "full",
            "sector": "Healthcare",
            "geography": "GCC",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_start_pipeline_no_input_422(client: AsyncClient) -> None:
    """POST /api/pipeline/start with no input returns 422."""
    resp = await client.post(
        "/api/pipeline/start",
        json={
            "language": "en",
            "proposal_mode": "standard",
            "sector": "Tech",
            "geography": "MENA",
        },
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["detail"]["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_get_status(client: AsyncClient) -> None:
    """GET /api/pipeline/{id}/status returns session status."""
    # Start a session
    start_resp = await client.post(
        "/api/pipeline/start",
        json={
            "text_input": "Test RFP",
            "language": "en",
            "proposal_mode": "standard",
            "sector": "Finance",
            "geography": "UAE",
        },
    )
    session_id = start_resp.json()["session_id"]

    # Give dry-run simulation a moment to begin
    await asyncio.sleep(0.5)

    resp = await client.get(f"/api/pipeline/{session_id}/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["session_id"] == session_id
    assert data["status"] in ("running", "gate_pending", "complete")
    assert "current_stage" in data
    assert "started_at" in data
    assert "elapsed_ms" in data
    assert "session_metadata" in data


@pytest.mark.asyncio
async def test_get_status_not_found(client: AsyncClient) -> None:
    """GET /api/pipeline/{id}/status for missing session returns 404."""
    resp = await client.get("/api/pipeline/nonexistent-id/status")
    assert resp.status_code == 404
    data = resp.json()
    assert data["detail"]["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_health_shows_active_sessions(client: AsyncClient) -> None:
    """Health check reflects active session count."""
    # Start a session
    await client.post(
        "/api/pipeline/start",
        json={
            "text_input": "Test",
            "language": "en",
            "proposal_mode": "lite",
            "sector": "Retail",
            "geography": "KSA",
        },
    )

    resp = await client.get("/api/health")
    data = resp.json()
    assert data["active_sessions"] == 1


@pytest.mark.asyncio
async def test_start_pipeline_returns_different_session_ids(
    client: AsyncClient,
) -> None:
    """Each pipeline start returns a unique session ID."""
    payload = {
        "text_input": "Test",
        "language": "en",
        "proposal_mode": "standard",
        "sector": "Energy",
        "geography": "GCC",
    }
    resp1 = await client.post("/api/pipeline/start", json=payload)
    resp2 = await client.post("/api/pipeline/start", json=payload)

    assert resp1.json()["session_id"] != resp2.json()["session_id"]
