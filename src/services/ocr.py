"""OCR service with backend abstraction for PDF text extraction.

Architecture:
- PyPDF2Backend: Fast text extraction for digitally-born PDFs (no OCR)
- TesseractBackend: Local OCR for scanned PDFs (requires tesseract + poppler)
- AzureDocIntelligenceBackend: Production OCR stub (implemented in M12)
- extract_pdf_with_ocr(): Smart dispatcher — tries PyPDF2 first, falls
  back to OCR if text is sparse

System requirements for Tesseract:
- Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki
- Arabic language pack (ara) selected during install
- Poppler for pdf2image: https://github.com/oschwartz10612/poppler-windows/releases/
- Both must be on system PATH
"""

import logging
from typing import Protocol

from pydantic import Field

from src.models.common import DeckForgeBaseModel

logger = logging.getLogger(__name__)

# Minimum average chars per page before we consider a PDF "sparse"
# and trigger OCR fallback
_SPARSE_THRESHOLD = 50


# ──────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────


class OCRResult(DeckForgeBaseModel):
    """Result from OCR processing of a single page."""

    page_number: int
    text: str = ""
    confidence: float = 0.0  # 0.0-1.0
    language_detected: str | None = None
    engine: str = ""  # "pypdf2" | "tesseract" | "azure_doc_intelligence"


class OCRDocumentResult(DeckForgeBaseModel):
    """Full OCR result for a document."""

    filepath: str
    pages: list[OCRResult] = Field(default_factory=list)
    full_text: str = ""
    average_confidence: float = 0.0
    engine_used: str = ""
    needs_human_review: bool = False  # True if avg confidence < 0.7


# ──────────────────────────────────────────────────────────────
# Backend Protocol
# ──────────────────────────────────────────────────────────────


class OCRBackend(Protocol):
    """Abstract OCR backend — swap local for Azure without changing callers."""

    async def extract_pdf(
        self,
        filepath: str,
        languages: list[str] | None = None,
    ) -> OCRDocumentResult: ...


# ──────────────────────────────────────────────────────────────
# PyPDF2 Backend — fast, free, no OCR
# ──────────────────────────────────────────────────────────────


class PyPDF2Backend:
    """Fast text extraction for digitally-born PDFs. No OCR."""

    async def extract_pdf(
        self,
        filepath: str,
        languages: list[str] | None = None,
    ) -> OCRDocumentResult:
        from PyPDF2 import PdfReader

        reader = PdfReader(filepath)
        pages: list[OCRResult] = []
        full_parts: list[str] = []

        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            text = text.strip()
            pages.append(OCRResult(
                page_number=idx,
                text=text,
                confidence=0.95 if text else 0.0,
                engine="pypdf2",
            ))
            if text:
                full_parts.append(text)

        full_text = "\n\n".join(full_parts)
        total_conf = sum(p.confidence for p in pages)
        avg_conf = total_conf / len(pages) if pages else 0.0

        return OCRDocumentResult(
            filepath=filepath,
            pages=pages,
            full_text=full_text,
            average_confidence=avg_conf,
            engine_used="pypdf2",
            needs_human_review=avg_conf < 0.7,
        )


# ──────────────────────────────────────────────────────────────
# Tesseract Backend — local OCR for scanned PDFs
# ──────────────────────────────────────────────────────────────


def _is_tesseract_available() -> bool:
    """Check if Tesseract is installed and accessible."""
    try:
        import pytesseract  # type: ignore[import-untyped]

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _is_poppler_available() -> bool:
    """Check if Poppler (pdf2image dependency) is installed."""
    import importlib.util

    return importlib.util.find_spec("pdf2image") is not None


class TesseractBackend:
    """Local OCR for scanned PDFs. Requires tesseract + poppler installed."""

    async def extract_pdf(
        self,
        filepath: str,
        languages: list[str] | None = None,
    ) -> OCRDocumentResult:
        if languages is None:
            languages = ["eng", "ara"]

        if not _is_tesseract_available():
            logger.warning("Tesseract not available — returning empty result")
            return OCRDocumentResult(
                filepath=filepath,
                engine_used="tesseract",
                needs_human_review=True,
            )

        if not _is_poppler_available():
            logger.warning("Poppler not available — cannot convert PDF to images")
            return OCRDocumentResult(
                filepath=filepath,
                engine_used="tesseract",
                needs_human_review=True,
            )

        import pytesseract  # type: ignore[import-untyped]
        from pdf2image import convert_from_path  # type: ignore[import-untyped]

        lang_str = "+".join(languages)

        try:
            images = convert_from_path(filepath, dpi=200)
        except Exception as e:
            logger.warning("pdf2image failed for %s: %s", filepath, e)
            return OCRDocumentResult(
                filepath=filepath,
                engine_used="tesseract",
                needs_human_review=True,
            )

        pages: list[OCRResult] = []
        full_parts: list[str] = []

        for idx, image in enumerate(images, start=1):
            try:
                # Get OCR data with confidence
                data = pytesseract.image_to_data(
                    image, lang=lang_str, output_type=pytesseract.Output.DICT
                )

                # Extract text
                text = pytesseract.image_to_string(image, lang=lang_str).strip()

                # Calculate confidence from word-level confidences
                confidences = [
                    int(c)
                    for c in data.get("conf", [])
                    if str(c).lstrip("-").isdigit() and int(c) > 0
                ]
                avg_conf = (
                    sum(confidences) / len(confidences) / 100.0
                    if confidences
                    else 0.0
                )

                # Detect language from script
                lang_detected = None
                if text:
                    arabic_chars = sum(
                        1 for c in text if "\u0600" <= c <= "\u06FF"
                    )
                    if arabic_chars > len(text) * 0.3:
                        lang_detected = "ara"
                    else:
                        lang_detected = "eng"

                pages.append(OCRResult(
                    page_number=idx,
                    text=text,
                    confidence=round(avg_conf, 3),
                    language_detected=lang_detected,
                    engine="tesseract",
                ))
                if text:
                    full_parts.append(text)

            except Exception as e:
                logger.warning("OCR failed for page %d of %s: %s", idx, filepath, e)
                pages.append(OCRResult(
                    page_number=idx,
                    confidence=0.0,
                    engine="tesseract",
                ))

        full_text = "\n\n".join(full_parts)
        total_conf = sum(p.confidence for p in pages)
        avg_conf = total_conf / len(pages) if pages else 0.0

        return OCRDocumentResult(
            filepath=filepath,
            pages=pages,
            full_text=full_text,
            average_confidence=round(avg_conf, 3),
            engine_used="tesseract",
            needs_human_review=avg_conf < 0.7,
        )


# ──────────────────────────────────────────────────────────────
# Azure Document Intelligence Backend — production stub
# ──────────────────────────────────────────────────────────────


class AzureDocIntelligenceBackend:
    """Production OCR — Azure Document Intelligence Read API.

    Stub implementation — raises NotImplementedError until M12.
    """

    async def extract_pdf(
        self,
        filepath: str,
        languages: list[str] | None = None,
    ) -> OCRDocumentResult:
        raise NotImplementedError(
            "Azure Document Intelligence backend not yet implemented. "
            "Planned for M12 (Azure integration milestone)."
        )


# ──────────────────────────────────────────────────────────────
# Smart Dispatcher
# ──────────────────────────────────────────────────────────────


async def extract_pdf_with_ocr(
    filepath: str,
    backend: str = "auto",
) -> OCRDocumentResult:
    """Smart PDF extraction: try PyPDF2 first, fall back to OCR if sparse.

    Args:
        filepath: Path to the PDF file.
        backend: OCR backend to use.
            "auto" — PyPDF2 first, Tesseract fallback if sparse
            "pypdf2" — PyPDF2 only (no OCR)
            "tesseract" — Tesseract only
            "azure" — Azure Document Intelligence

    Returns:
        OCRDocumentResult with per-page confidence scores.
    """
    if backend == "azure":
        return await AzureDocIntelligenceBackend().extract_pdf(filepath)

    if backend == "tesseract":
        return await TesseractBackend().extract_pdf(filepath)

    # "auto" or "pypdf2" — start with PyPDF2
    pypdf2_result = await PyPDF2Backend().extract_pdf(filepath)

    if backend == "pypdf2":
        return pypdf2_result

    # "auto" mode — check if text is sparse
    total_chars = sum(len(p.text) for p in pypdf2_result.pages)
    num_pages = len(pypdf2_result.pages) or 1
    avg_chars_per_page = total_chars / num_pages

    if avg_chars_per_page >= _SPARSE_THRESHOLD:
        # Enough text — PyPDF2 result is good
        return pypdf2_result

    # Sparse text — try Tesseract fallback
    logger.info(
        "Sparse text in %s (%.0f chars/page) — attempting OCR fallback",
        filepath,
        avg_chars_per_page,
    )

    if not _is_tesseract_available() or not _is_poppler_available():
        logger.warning(
            "OCR fallback unavailable (tesseract=%s, poppler=%s) — "
            "returning degraded PyPDF2 result for %s",
            _is_tesseract_available(),
            _is_poppler_available(),
            filepath,
        )
        pypdf2_result.needs_human_review = True
        return pypdf2_result

    return await TesseractBackend().extract_pdf(filepath)
