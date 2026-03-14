"""
Tests for export endpoint:
- GET /api/pipeline/{id}/export/{format}

All tests run with PIPELINE_MODE=dry_run. Zero LLM calls.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.models.api_models import PipelineStatus
from backend.services.session_manager import SessionManager


def _create_completed_session(sm: SessionManager) -> str:
    """Helper: create a session in COMPLETE state."""
    session = sm.create(
        language="en",
        proposal_mode="standard",
        sector="Tech",
        geography="MENA",
        renderer_mode="legacy",
    )
    session.status = PipelineStatus.COMPLETE
    session.current_stage = "finalized"
    return session.session_id


@pytest.mark.asyncio
async def test_export_pptx(client: AsyncClient, sm: SessionManager) -> None:
    """GET /export/pptx returns a mock PPTX file in dry_run mode."""
    session_id = _create_completed_session(sm)

    resp = await client.get(f"/api/pipeline/{session_id}/export/pptx")
    assert resp.status_code == 200

    # Check headers
    assert "application/vnd.openxmlformats" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert "proposal_" in resp.headers["content-disposition"]
    assert "_en.pptx" in resp.headers["content-disposition"]

    # Check content is non-empty
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_export_docx(client: AsyncClient, sm: SessionManager) -> None:
    """GET /export/docx returns a mock DOCX file in dry_run mode."""
    session_id = _create_completed_session(sm)

    resp = await client.get(f"/api/pipeline/{session_id}/export/docx")
    assert resp.status_code == 200

    assert "application/vnd.openxmlformats" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert "research_report_" in resp.headers["content-disposition"]
    assert "_en.docx" in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_export_ar_language(
    client: AsyncClient, sm: SessionManager
) -> None:
    """Export filename reflects Arabic language."""
    session = sm.create(
        language="ar",
        proposal_mode="standard",
        sector="Tech",
        geography="MENA",
        renderer_mode="legacy",
    )
    session.status = PipelineStatus.COMPLETE
    session.current_stage = "finalized"

    resp = await client.get(
        f"/api/pipeline/{session.session_id}/export/pptx"
    )
    assert resp.status_code == 200
    assert "_ar.pptx" in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_export_not_ready_409(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /export when pipeline not complete returns 409."""
    session = sm.create(
        language="en",
        proposal_mode="standard",
        sector="Tech",
        geography="MENA",
        renderer_mode="legacy",
    )
    session.status = PipelineStatus.RUNNING

    resp = await client.get(
        f"/api/pipeline/{session.session_id}/export/pptx"
    )
    assert resp.status_code == 409
    data = resp.json()
    assert data["detail"]["error"]["code"] == "EXPORT_NOT_READY"


@pytest.mark.asyncio
async def test_export_invalid_format_422(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /export with invalid format returns 422."""
    session_id = _create_completed_session(sm)

    resp = await client.get(f"/api/pipeline/{session_id}/export/xlsx")
    assert resp.status_code == 422
    data = resp.json()
    assert data["detail"]["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_export_not_found_404(client: AsyncClient) -> None:
    """GET /export for missing session returns 404."""
    resp = await client.get("/api/pipeline/nonexistent/export/pptx")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_export_filename_uses_session_short(
    client: AsyncClient, sm: SessionManager
) -> None:
    """Export filename uses first 6 chars of session_id."""
    session_id = _create_completed_session(sm)
    session_short = session_id[:6]

    resp = await client.get(f"/api/pipeline/{session_id}/export/pptx")
    assert resp.status_code == 200
    assert session_short in resp.headers["content-disposition"]
