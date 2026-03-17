"""
Tests for export endpoint:
- GET /api/pipeline/{id}/export/{format}

All tests run with PIPELINE_MODE=dry_run. Zero LLM calls.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from httpx import AsyncClient

from backend.models.api_models import DeliverableInfo, PipelineStatus
from backend.services.session_manager import SessionManager


def _create_completed_session(
    sm: SessionManager,
    *,
    language: str = "en",
    tmp_dir: Path | None = None,
) -> str:
    """Helper: create a session in COMPLETE state with real temp files."""
    session = sm.create(
        language=language,
        proposal_mode="standard",
        sector="Tech",
        geography="MENA",
        renderer_mode="legacy",
    )
    session.status = PipelineStatus.COMPLETE
    session.current_stage = "finalized"

    sid = session.session_id
    short = sid[:6]

    if tmp_dir is not None:
        # Create real temp files so the export endpoint can serve them
        pptx_file = tmp_dir / f"proposal_{short}_{language}.pptx"
        docx_file = tmp_dir / f"research_report_{short}_{language}.docx"
        source_file = tmp_dir / f"source_index_{short}.docx"
        gap_file = tmp_dir / f"gap_report_{short}.docx"

        for f in [pptx_file, docx_file, source_file, gap_file]:
            f.write_bytes(b"PK\x03\x04" + b"test content for " + f.name.encode())

        sm.set_deliverables(
            sid,
            [
                DeliverableInfo(
                    key="pptx",
                    label="Presentation deck",
                    ready=True,
                    filename=pptx_file.name,
                    download_url=f"/api/pipeline/{sid}/export/pptx",
                    path=str(pptx_file),
                ),
                DeliverableInfo(
                    key="docx",
                    label="Research report",
                    ready=True,
                    filename=docx_file.name,
                    download_url=f"/api/pipeline/{sid}/export/docx",
                    path=str(docx_file),
                ),
                DeliverableInfo(
                    key="source_index",
                    label="Source index",
                    ready=True,
                    filename=source_file.name,
                    download_url=f"/api/pipeline/{sid}/export/source_index",
                    path=str(source_file),
                ),
                DeliverableInfo(
                    key="gap_report",
                    label="Gap report",
                    ready=True,
                    filename=gap_file.name,
                    download_url=f"/api/pipeline/{sid}/export/gap_report",
                    path=str(gap_file),
                ),
            ],
        )

    return sid


@pytest.fixture
def tmp_export_dir():
    """Provide a temporary directory for export test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_export_pptx(
    client: AsyncClient, sm: SessionManager, tmp_export_dir: Path
) -> None:
    """GET /export/pptx returns the actual PPTX file."""
    session_id = _create_completed_session(sm, tmp_dir=tmp_export_dir)

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
async def test_export_docx(
    client: AsyncClient, sm: SessionManager, tmp_export_dir: Path
) -> None:
    """GET /export/docx returns the actual DOCX file."""
    session_id = _create_completed_session(sm, tmp_dir=tmp_export_dir)

    resp = await client.get(f"/api/pipeline/{session_id}/export/docx")
    assert resp.status_code == 200

    assert "application/vnd.openxmlformats" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert "research_report_" in resp.headers["content-disposition"]
    assert "_en.docx" in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_export_ar_language(
    client: AsyncClient, sm: SessionManager, tmp_export_dir: Path
) -> None:
    """Export filename reflects Arabic language."""
    session_id = _create_completed_session(
        sm, language="ar", tmp_dir=tmp_export_dir
    )

    resp = await client.get(f"/api/pipeline/{session_id}/export/pptx")
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
    client: AsyncClient, sm: SessionManager, tmp_export_dir: Path
) -> None:
    """GET /export with invalid format returns 422."""
    session_id = _create_completed_session(sm, tmp_dir=tmp_export_dir)

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
async def test_export_no_file_returns_404(
    client: AsyncClient, sm: SessionManager
) -> None:
    """GET /export when session is complete but no file on disk returns 404."""
    session_id = _create_completed_session(sm)  # No tmp_dir = no files

    resp = await client.get(f"/api/pipeline/{session_id}/export/pptx")
    assert resp.status_code == 404
    data = resp.json()
    assert data["detail"]["error"]["code"] == "FILE_NOT_FOUND"


@pytest.mark.asyncio
async def test_export_filename_uses_session_short(
    client: AsyncClient, sm: SessionManager, tmp_export_dir: Path
) -> None:
    """Export filename uses first 6 chars of session_id."""
    session_id = _create_completed_session(sm, tmp_dir=tmp_export_dir)
    session_short = session_id[:6]

    resp = await client.get(f"/api/pipeline/{session_id}/export/pptx")
    assert resp.status_code == 200
    assert session_short in resp.headers["content-disposition"]
