"""
Tests for slides endpoints:
- GET /api/pipeline/{id}/slides
- GET /api/pipeline/{id}/slides/{n}/thumbnail.png

All tests run with PIPELINE_MODE=dry_run. Zero LLM calls.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.models.api_models import PipelineStatus
from backend.services.session_manager import SessionManager


async def _create_completed_session(sm: SessionManager) -> str:
    """Helper: create a session in COMPLETE state with mock slide data."""
    session = sm.create(
        language="en",
        proposal_mode="standard",
        sector="Tech",
        geography="MENA",
        renderer_mode="legacy",
    )
    session.status = PipelineStatus.COMPLETE
    session.current_stage = "finalized"
    session.thumbnail_mode = "metadata_only"
    session.slides_data = [
        {
            "slide_number": i + 1,
            "entry_type": "b_variable" if i > 0 else "a1_clone",
            "asset_id": f"slide_{i+1}",
            "semantic_layout_id": f"layout_{(i % 4) + 1}",
            "section_id": f"section_{(i // 3) + 1}",
            "shape_count": 5 + (i % 3),
            "fonts": ["IBM Plex Sans"],
            "text_preview": f"Slide {i+1} content preview",
        }
        for i in range(12)
    ]
    return session.session_id


@pytest.mark.asyncio
async def test_get_slides_complete(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /api/pipeline/{id}/slides returns slide list when complete."""
    session_id = await _create_completed_session(sm)

    resp = await client.get(f"/api/pipeline/{session_id}/slides")
    assert resp.status_code == 200

    data = resp.json()
    assert data["session_id"] == session_id
    assert data["slide_count"] == 12
    assert data["thumbnail_mode"] == "metadata_only"
    assert len(data["slides"]) == 12

    # Check first slide structure
    slide = data["slides"][0]
    assert slide["slide_number"] == 1
    assert slide["entry_type"] == "a1_clone"
    assert slide["thumbnail_url"] is None  # metadata_only mode
    assert "fonts" in slide
    assert "text_preview" in slide


@pytest.mark.asyncio
async def test_get_slides_rendered_mode(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /slides with rendered mode returns thumbnail URLs."""
    session_id = await _create_completed_session(sm)
    session = sm.get(session_id)
    assert session is not None
    session.thumbnail_mode = "rendered"

    resp = await client.get(f"/api/pipeline/{session_id}/slides")
    data = resp.json()

    assert data["thumbnail_mode"] == "rendered"
    # Slides should have thumbnail URLs
    for slide in data["slides"]:
        assert slide["thumbnail_url"] is not None
        assert "thumbnail.png" in slide["thumbnail_url"]


@pytest.mark.asyncio
async def test_get_slides_not_complete_409(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /slides when pipeline not complete returns 409."""
    session = sm.create(
        language="en",
        proposal_mode="standard",
        sector="Tech",
        geography="MENA",
        renderer_mode="legacy",
    )
    session.status = PipelineStatus.RUNNING

    resp = await client.get(f"/api/pipeline/{session.session_id}/slides")
    assert resp.status_code == 409
    data = resp.json()
    assert data["detail"]["error"]["code"] == "EXPORT_NOT_READY"


@pytest.mark.asyncio
async def test_get_slides_not_found(client: AsyncClient) -> None:
    """GET /slides for missing session returns 404."""
    resp = await client.get("/api/pipeline/nonexistent/slides")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_thumbnail_metadata_mode_404(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET thumbnail in metadata_only mode returns 404."""
    session_id = await _create_completed_session(sm)

    resp = await client.get(
        f"/api/pipeline/{session_id}/slides/1/thumbnail.png"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_thumbnail_rendered_mode(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET thumbnail in rendered mode returns PNG."""
    session_id = await _create_completed_session(sm)
    session = sm.get(session_id)
    assert session is not None
    session.thumbnail_mode = "rendered"

    resp = await client.get(
        f"/api/pipeline/{session_id}/slides/1/thumbnail.png"
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    # PNG magic bytes
    assert resp.content[:4] == b"\x89PNG"
