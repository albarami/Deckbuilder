"""
DeckForge Backend — Upload Router

Endpoint:
- POST /api/upload → Upload RFP documents (PDF, DOCX, TXT)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from backend.models.api_models import (
    APIErrorDetail,
    APIErrorResponse,
    UploadedFileInfo,
    UploadResponse,
)
from backend.services.session_manager import SessionManager

router = APIRouter(prefix="/api", tags=["upload"])

# Accepted MIME types
ACCEPTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Max file sizes
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB per file
MAX_TOTAL_SIZE_BYTES = 200 * 1024 * 1024  # 200MB total


@router.post("/upload")
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    """Upload one or more RFP documents."""
    sm: SessionManager = request.app.state.session_manager
    pipeline_mode: str = request.app.state.pipeline_mode

    uploaded: list[UploadedFileInfo] = []
    total_size = 0

    for file in files:
        # Validate MIME type
        content_type = file.content_type or ""
        if content_type not in ACCEPTED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=APIErrorResponse(
                    error=APIErrorDetail(
                        code="INVALID_INPUT",
                        message=f"Unsupported file type: {content_type}. Accepted: PDF, DOCX, TXT.",
                    )
                ).model_dump(),
            )

        # Read content and check size
        content = await file.read()
        file_size = len(content)
        total_size += file_size

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=APIErrorResponse(
                    error=APIErrorDetail(
                        code="FILE_TOO_LARGE",
                        message=f"File {file.filename} exceeds 50MB limit.",
                    )
                ).model_dump(),
            )

        if total_size > MAX_TOTAL_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=APIErrorResponse(
                    error=APIErrorDetail(
                        code="FILE_TOO_LARGE",
                        message="Total upload size exceeds 200MB limit.",
                    )
                ).model_dump(),
            )

        # Generate upload ID and extract text (dry_run = mock)
        upload_id = str(uuid.uuid4())

        if pipeline_mode == "dry_run":
            # Mock text extraction
            extracted_text_length = min(file_size, 5000)
            detected_language = "en"
        else:
            # Real text extraction would happen here
            extracted_text_length = len(content)
            detected_language = "unknown"

        # Store upload metadata
        sm.store_upload(
            upload_id,
            {
                "filename": file.filename or "unnamed",
                "size_bytes": file_size,
                "content_type": content_type,
                "content": content,  # In-memory only (M11)
                "extracted_text_length": extracted_text_length,
                "detected_language": detected_language,
            },
        )

        uploaded.append(
            UploadedFileInfo(
                upload_id=upload_id,
                filename=file.filename or "unnamed",
                size_bytes=file_size,
                content_type=content_type,
                extracted_text_length=extracted_text_length,
                detected_language=detected_language,
            )
        )

    return UploadResponse(uploads=uploaded)
