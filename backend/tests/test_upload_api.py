"""
Tests for upload endpoint:
- POST /api/upload

All tests run with PIPELINE_MODE=dry_run. Zero LLM calls.
"""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_text_file(client: AsyncClient) -> None:
    """POST /api/upload with a TXT file returns upload metadata."""
    content = b"This is a mock RFP document for testing purposes."

    resp = await client.post(
        "/api/upload",
        files=[
            ("files", ("test_rfp.txt", io.BytesIO(content), "text/plain")),
        ],
    )
    assert resp.status_code == 200

    data = resp.json()
    assert "uploads" in data
    assert len(data["uploads"]) == 1

    upload = data["uploads"][0]
    assert upload["filename"] == "test_rfp.txt"
    assert upload["size_bytes"] == len(content)
    assert upload["content_type"] == "text/plain"
    assert upload["extracted_text_length"] > 0
    assert upload["detected_language"] == "en"
    assert "upload_id" in upload


@pytest.mark.asyncio
async def test_upload_pdf_file(client: AsyncClient) -> None:
    """POST /api/upload with a PDF file succeeds."""
    # Minimal mock PDF-like content
    content = b"%PDF-1.4 mock content for testing"

    resp = await client.post(
        "/api/upload",
        files=[
            ("files", ("proposal.pdf", io.BytesIO(content), "application/pdf")),
        ],
    )
    assert resp.status_code == 200
    assert len(resp.json()["uploads"]) == 1


@pytest.mark.asyncio
async def test_upload_docx_file(client: AsyncClient) -> None:
    """POST /api/upload with a DOCX file succeeds."""
    content = b"PK\x03\x04 mock docx content"

    resp = await client.post(
        "/api/upload",
        files=[
            (
                "files",
                (
                    "requirements.docx",
                    io.BytesIO(content),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
        ],
    )
    assert resp.status_code == 200
    assert len(resp.json()["uploads"]) == 1


@pytest.mark.asyncio
async def test_upload_multiple_files(client: AsyncClient) -> None:
    """POST /api/upload with multiple files returns all metadata."""
    resp = await client.post(
        "/api/upload",
        files=[
            ("files", ("file1.txt", io.BytesIO(b"content 1"), "text/plain")),
            ("files", ("file2.txt", io.BytesIO(b"content 2"), "text/plain")),
        ],
    )
    assert resp.status_code == 200
    assert len(resp.json()["uploads"]) == 2

    ids = [u["upload_id"] for u in resp.json()["uploads"]]
    assert ids[0] != ids[1]  # Unique IDs


@pytest.mark.asyncio
async def test_upload_unsupported_type_400(client: AsyncClient) -> None:
    """POST /api/upload with unsupported MIME type returns 400."""
    resp = await client.post(
        "/api/upload",
        files=[
            ("files", ("image.png", io.BytesIO(b"PNG data"), "image/png")),
        ],
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["detail"]["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_upload_ids_unique(client: AsyncClient) -> None:
    """Each upload generates a unique upload_id."""
    resp1 = await client.post(
        "/api/upload",
        files=[
            ("files", ("a.txt", io.BytesIO(b"aaa"), "text/plain")),
        ],
    )
    resp2 = await client.post(
        "/api/upload",
        files=[
            ("files", ("b.txt", io.BytesIO(b"bbb"), "text/plain")),
        ],
    )

    id1 = resp1.json()["uploads"][0]["upload_id"]
    id2 = resp2.json()["uploads"][0]["upload_id"]
    assert id1 != id2
