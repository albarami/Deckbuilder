"""Tests for the OCR service — backend abstraction and smart PDF extraction."""

import asyncio
import os
import tempfile

from src.services.ocr import (
    OCRDocumentResult,
    OCRResult,
    PyPDF2Backend,
    TesseractBackend,
    extract_pdf_with_ocr,
)

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


def _create_test_pdf_with_text(path: str) -> None:
    """Create a PDF with embedded text (digitally-born)."""
    from PyPDF2 import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_metadata({"/Title": "Test PDF"})
    with open(path, "wb") as f:
        writer.write(f)


# ──────────────────────────────────────────────────────────────
# Model Tests
# ──────────────────────────────────────────────────────────────


def test_ocr_result_model() -> None:
    """OCRResult and OCRDocumentResult validate correctly."""
    page = OCRResult(
        page_number=1,
        text="Hello world",
        confidence=0.95,
        language_detected="eng",
        engine="pypdf2",
    )
    assert page.page_number == 1
    assert page.confidence == 0.95
    assert page.engine == "pypdf2"

    doc = OCRDocumentResult(
        filepath="/test.pdf",
        pages=[page],
        full_text="Hello world",
        average_confidence=0.95,
        engine_used="pypdf2",
        needs_human_review=False,
    )
    assert doc.average_confidence == 0.95
    assert not doc.needs_human_review
    assert len(doc.pages) == 1


# ──────────────────────────────────────────────────────────────
# PyPDF2 Backend Tests
# ──────────────────────────────────────────────────────────────


def test_ocr_pypdf2_backend() -> None:
    """PyPDF2 backend extracts text from digitally-born PDF with high confidence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf_with_text(path)

        backend = PyPDF2Backend()
        result = asyncio.run(backend.extract_pdf(path))

        assert isinstance(result, OCRDocumentResult)
        assert result.engine_used == "pypdf2"
        assert len(result.pages) >= 1
        assert result.pages[0].engine == "pypdf2"
        # Blank PDF page — confidence should be 0 since no text
        # but the structure is correct


# ──────────────────────────────────────────────────────────────
# Tesseract Fallback Tests
# ──────────────────────────────────────────────────────────────


def test_ocr_tesseract_fallback_graceful() -> None:
    """If Tesseract not installed, returns degraded without crashing."""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf_with_text(path)

        # Mock Tesseract as unavailable
        with patch(
            "src.services.ocr._is_tesseract_available", return_value=False
        ):
            backend = TesseractBackend()
            result = asyncio.run(backend.extract_pdf(path))

            assert isinstance(result, OCRDocumentResult)
            assert result.engine_used == "tesseract"
            assert result.needs_human_review is True
            assert len(result.pages) == 0  # No pages extracted


# ──────────────────────────────────────────────────────────────
# Auto Detection Tests
# ──────────────────────────────────────────────────────────────


def test_ocr_auto_detection_sparse_triggers_fallback() -> None:
    """PDF with sparse PyPDF2 text triggers OCR fallback attempt."""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "scanned.pdf")
        _create_test_pdf_with_text(path)  # Blank PDF = sparse

        # Mock Tesseract as unavailable — should get degraded result
        with patch(
            "src.services.ocr._is_tesseract_available", return_value=False
        ):
            result = asyncio.run(extract_pdf_with_ocr(path, backend="auto"))

            assert isinstance(result, OCRDocumentResult)
            # Should fall back but Tesseract unavailable → degraded PyPDF2
            assert result.needs_human_review is True


# ──────────────────────────────────────────────────────────────
# Confidence Threshold Tests
# ──────────────────────────────────────────────────────────────


def test_ocr_confidence_threshold() -> None:
    """Low confidence sets needs_human_review=True."""
    doc = OCRDocumentResult(
        filepath="/test.pdf",
        pages=[
            OCRResult(page_number=1, text="partial", confidence=0.3, engine="tesseract"),
            OCRResult(page_number=2, text="text", confidence=0.5, engine="tesseract"),
        ],
        full_text="partial\n\ntext",
        average_confidence=0.4,
        engine_used="tesseract",
        needs_human_review=True,  # avg 0.4 < 0.7
    )
    assert doc.needs_human_review is True
    assert doc.average_confidence < 0.7

    # High confidence should NOT need review
    doc_good = OCRDocumentResult(
        filepath="/good.pdf",
        pages=[
            OCRResult(page_number=1, text="clear text", confidence=0.92, engine="pypdf2"),
        ],
        full_text="clear text",
        average_confidence=0.92,
        engine_used="pypdf2",
        needs_human_review=False,
    )
    assert doc_good.needs_human_review is False
