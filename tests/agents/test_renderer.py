"""Tests for the PPTX renderer and DOCX exporter (Design Agent)."""

import os
import tempfile

from pptx import Presentation

from src.models.enums import GapSeverity, Language, LayoutType, RenderStatus
from src.models.report import ReportGap, ReportSection, ResearchReport
from src.models.slides import BodyContent, SlideObject

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "templates", "Presentation6.pptx"
)


def _sample_slides() -> list[SlideObject]:
    """Three slides covering different layout types."""
    return [
        SlideObject(
            slide_id="S-001",
            title="Executive Summary",
            layout_type=LayoutType.TITLE,
            body_content=BodyContent(
                text_elements=["Strategic Gears — SAP expertise"],
            ),
            speaker_notes="This is the opening slide.",
        ),
        SlideObject(
            slide_id="S-002",
            title="Our Approach",
            layout_type=LayoutType.CONTENT_1COL,
            body_content=BodyContent(
                text_elements=[
                    "Phase 1: Discovery and assessment",
                    "Phase 2: Implementation and migration",
                    "Phase 3: Knowledge transfer and handover",
                ],
            ),
            speaker_notes="Walk through each phase.",
        ),
        SlideObject(
            slide_id="S-003",
            title="Market Overview",
            layout_type=LayoutType.SECTION,
            body_content=BodyContent(
                text_elements=["SAP market in the GCC region"],
            ),
        ),
    ]


def _sample_report() -> ResearchReport:
    """Minimal research report for docx export."""
    return ResearchReport(
        title="SAP Support Renewal — Research Report",
        language=Language.EN,
        sections=[
            ReportSection(
                section_id="SEC-001",
                heading="Executive Summary",
                content_markdown="Strategic Gears has deep SAP expertise.",
            ),
            ReportSection(
                section_id="SEC-002",
                heading="Technical Approach",
                content_markdown="Our methodology covers three phases.",
            ),
        ],
        all_gaps=[
            ReportGap(
                gap_id="GAP-001",
                description="No ISO 27001 evidence",
                rfp_criterion="Compliance",
                severity=GapSeverity.MEDIUM,
                action_required="Request certification docs",
            ),
        ],
        full_markdown="# SAP Support Renewal\n\nResearch content.",
    )


# ──────────────────────────────────────────────────────────────
# PPTX Tests
# ──────────────────────────────────────────────────────────────


def test_render_pptx_creates_file() -> None:
    """Render 3 SlideObjects → .pptx file exists, correct slide count."""
    import asyncio

    from src.services.renderer import render_pptx

    slides = _sample_slides()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_output.pptx")
        result = asyncio.run(
            render_pptx(slides, TEMPLATE_PATH, output)
        )

        assert os.path.exists(output)
        assert result.slide_count == 3
        assert result.pptx_path == output

        # Verify actual PPTX slide count
        prs = Presentation(output)
        assert len(prs.slides) == 3


def test_render_maps_layout_types() -> None:
    """Each LayoutType maps to a valid template layout."""
    from src.services.renderer import LAYOUT_MAP

    for layout_type in LayoutType:
        assert layout_type in LAYOUT_MAP, (
            f"LayoutType.{layout_type.name} missing from LAYOUT_MAP"
        )
        idx = LAYOUT_MAP[layout_type]
        assert isinstance(idx, int)
        assert 0 <= idx <= 12


def test_render_populates_title() -> None:
    """Slide title text matches SlideObject.title."""
    import asyncio

    from src.services.renderer import render_pptx

    slides = [
        SlideObject(
            slide_id="S-001",
            title="My Custom Title",
            layout_type=LayoutType.CONTENT_1COL,
            body_content=BodyContent(text_elements=["Content"]),
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "title_test.pptx")
        asyncio.run(render_pptx(slides, TEMPLATE_PATH, output))

        prs = Presentation(output)
        slide = prs.slides[0]
        # Find title placeholder
        title_text = None
        for shape in slide.shapes:
            if shape.has_text_frame and shape.shape_id <= 2:
                title_text = shape.text_frame.text
                break
        # Fallback: check placeholders directly
        if title_text is None:
            for ph in slide.placeholders:
                if ph.placeholder_format.idx == 0:
                    title_text = ph.text
                    break

        assert title_text == "My Custom Title"


def test_render_populates_body() -> None:
    """Bullet points from body_content appear in slide."""
    import asyncio

    from src.services.renderer import render_pptx

    bullets = ["First point", "Second point", "Third point"]
    slides = [
        SlideObject(
            slide_id="S-001",
            title="Test",
            layout_type=LayoutType.CONTENT_1COL,
            body_content=BodyContent(text_elements=bullets),
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "body_test.pptx")
        asyncio.run(render_pptx(slides, TEMPLATE_PATH, output))

        prs = Presentation(output)
        slide = prs.slides[0]
        # Find content placeholder (idx=1)
        body_text = ""
        for ph in slide.placeholders:
            if ph.placeholder_format.idx == 1:
                body_text = ph.text
                break

        for bullet in bullets:
            assert bullet in body_text


def test_render_adds_speaker_notes() -> None:
    """Notes section contains speaker_notes text."""
    import asyncio

    from src.services.renderer import render_pptx

    slides = [
        SlideObject(
            slide_id="S-001",
            title="Test",
            layout_type=LayoutType.CONTENT_1COL,
            body_content=BodyContent(text_elements=["Content"]),
            speaker_notes="Important presenter note here.",
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "notes_test.pptx")
        asyncio.run(render_pptx(slides, TEMPLATE_PATH, output))

        prs = Presentation(output)
        slide = prs.slides[0]
        notes = slide.notes_slide.notes_text_frame.text
        assert "Important presenter note here." in notes


def test_render_handles_missing_layout() -> None:
    """Unknown layout falls back to default, logs warning."""
    import asyncio

    from src.services.renderer import render_pptx

    # STAT_CALLOUT uses Title Only — no body placeholder
    slides = [
        SlideObject(
            slide_id="S-001",
            title="42%",
            layout_type=LayoutType.STAT_CALLOUT,
            body_content=BodyContent(
                text_elements=["This text has no body placeholder"],
            ),
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "fallback_test.pptx")
        result = asyncio.run(
            render_pptx(slides, TEMPLATE_PATH, output)
        )

        # Should render successfully despite no body PH
        assert os.path.exists(output)
        assert result.slide_count == 1
        # Should have a warning in the render log
        warnings = [
            e for e in result.render_log
            if e["status"] == RenderStatus.WARNING
        ]
        assert len(warnings) >= 1


def test_render_result_has_log() -> None:
    """RenderResult contains per-slide status entries."""
    import asyncio

    from src.services.renderer import render_pptx

    slides = _sample_slides()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "log_test.pptx")
        result = asyncio.run(
            render_pptx(slides, TEMPLATE_PATH, output)
        )

        assert len(result.render_log) == 3
        for entry in result.render_log:
            assert "slide_id" in entry
            assert "status" in entry
            assert "message" in entry


# ──────────────────────────────────────────────────────────────
# DOCX Tests
# ──────────────────────────────────────────────────────────────


def test_export_docx_creates_file() -> None:
    """ResearchReport → .docx file exists with sections."""
    import asyncio

    from docx import Document

    from src.services.renderer import export_report_docx

    report = _sample_report()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_report.docx")
        result_path = asyncio.run(
            export_report_docx(report, output)
        )

        assert os.path.exists(result_path)
        assert result_path == output

        # Verify document structure
        doc = Document(output)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # Title should be present
        assert any("SAP Support Renewal" in p for p in paragraphs)
        # Section headings should be present
        assert any("Executive Summary" in p for p in paragraphs)
        assert any("Technical Approach" in p for p in paragraphs)
