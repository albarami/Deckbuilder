"""Tests for the PPTX renderer and DOCX exporter (Design Agent)."""

import asyncio
import os
import tempfile

from docx import Document
from pptx import Presentation

from src.models.enums import GapSeverity, Language, LayoutType
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


def _sample_report_multi_section() -> ResearchReport:
    """8-section report matching real E2E output size."""
    sections = []
    for i in range(1, 9):
        sections.append(
            ReportSection(
                section_id=f"SEC-{i:02d}",
                heading=f"Section {i}: {'ABCDEFGH'[i-1]} Topic",
                content_markdown=(
                    f"## Section {i}\n\n"
                    f"First paragraph of section {i} with content.\n\n"
                    f"Second paragraph with **bold** and analysis.\n\n"
                    f"Third paragraph with more detail for section {i}."
                ),
                gaps_flagged=[f"GAP-{i:03d}"],
            )
        )
    gaps = [
        ReportGap(
            gap_id=f"GAP-{i:03d}",
            description=f"Gap {i} description",
            rfp_criterion="Criterion",
            severity=GapSeverity.CRITICAL,
            action_required=f"Fix gap {i}",
        )
        for i in range(1, 9)
    ]
    return ResearchReport(
        title="Multi-Section Test Report",
        language=Language.EN,
        sections=sections,
        all_gaps=gaps,
        full_markdown="Full markdown content here.",
    )


def _all_layout_slides() -> list[SlideObject]:
    """One slide per layout type — tests that body content is never lost."""
    layouts = [
        (LayoutType.TITLE, "Title Slide"),
        (LayoutType.AGENDA, "Agenda Slide"),
        (LayoutType.SECTION, "Section Header"),
        (LayoutType.CONTENT_1COL, "One Column"),
        (LayoutType.CONTENT_2COL, "Two Columns"),
        (LayoutType.DATA_CHART, "Chart Slide"),
        (LayoutType.FRAMEWORK, "Framework"),
        (LayoutType.COMPARISON, "Comparison"),
        (LayoutType.STAT_CALLOUT, "Key Stat"),
        (LayoutType.TEAM, "Team Slide"),
        (LayoutType.TIMELINE, "Timeline"),
        (LayoutType.COMPLIANCE_MATRIX, "Compliance"),
        (LayoutType.CLOSING, "Thank You"),
    ]
    slides = []
    for i, (lt, label) in enumerate(layouts, 1):
        slides.append(
            SlideObject(
                slide_id=f"S-{i:03d}",
                title=f"{label} — Test Title",
                layout_type=lt,
                body_content=BodyContent(
                    text_elements=[
                        f"Bullet 1 for {label}",
                        f"Bullet 2 for {label}",
                        f"Bullet 3 for {label}",
                    ],
                ),
                speaker_notes=f"Notes for {label}.",
            )
        )
    return slides


def _get_slide_body_text(slide) -> str:
    """Extract all body text from a slide (placeholders + textboxes)."""
    texts = []
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        try:
            pf = shape.placeholder_format
            if pf.idx == 0:  # title
                continue
        except (ValueError, AttributeError):
            pass  # Not a placeholder — textbox fallback
        txt = shape.text_frame.text.strip()
        if txt:
            texts.append(txt)
    return "\n".join(texts)


# ──────────────────────────────────────────────────────────────
# PPTX Tests
# ──────────────────────────────────────────────────────────────


def test_render_pptx_creates_file() -> None:
    """Render 3 SlideObjects → .pptx file exists, correct slide count."""
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


def test_render_stat_callout_body_not_skipped() -> None:
    """STAT_CALLOUT body content is rendered via textbox fallback, not dropped."""
    from src.services.renderer import render_pptx

    bullets = ["Key insight number one", "Critical metric here"]
    slides = [
        SlideObject(
            slide_id="S-001",
            title="42%",
            layout_type=LayoutType.STAT_CALLOUT,
            body_content=BodyContent(text_elements=bullets),
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "stat_test.pptx")
        result = asyncio.run(
            render_pptx(slides, TEMPLATE_PATH, output)
        )

        assert result.slide_count == 1
        prs = Presentation(output)
        body = _get_slide_body_text(prs.slides[0])
        assert "Key insight number one" in body
        assert "Critical metric here" in body


def test_render_all_layout_types_have_body() -> None:
    """Every LayoutType renders body content — no silent drops.

    This is the key regression test: the original renderer silently
    skipped body content for TITLE, AGENDA, STAT_CALLOUT, and CLOSING
    layouts because they lack a BODY/OBJECT placeholder.
    """
    from src.services.renderer import render_pptx

    slides = _all_layout_slides()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "all_layouts.pptx")
        result = asyncio.run(
            render_pptx(slides, TEMPLATE_PATH, output)
        )

        assert result.slide_count == len(slides)

        prs = Presentation(output)
        assert len(prs.slides) == len(slides)

        for i, slide in enumerate(prs.slides):
            body = _get_slide_body_text(slide)
            layout_name = str(slides[i].layout_type)
            assert body, (
                f"Slide {i+1} ({layout_name}) has no body text — "
                f"body content was silently dropped"
            )


def test_render_20_slides_exact_count() -> None:
    """Render 20 slides and verify exactly 20 in the saved PPTX.

    Regression test for the stale-file bug: renderer reported N slides
    but the saved file contained fewer.
    """
    from src.services.renderer import render_pptx

    slides = []
    layouts = list(LayoutType)
    for i in range(20):
        lt = layouts[i % len(layouts)]
        slides.append(
            SlideObject(
                slide_id=f"S-{i+1:03d}",
                title=f"Slide {i+1} Title",
                layout_type=lt,
                body_content=BodyContent(
                    text_elements=[f"Bullet {j+1}" for j in range(3)],
                ),
            )
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "twenty_slides.pptx")
        result = asyncio.run(
            render_pptx(slides, TEMPLATE_PATH, output)
        )

        # RenderResult.slide_count now comes from verification
        assert result.slide_count == 20

        # Double-check by reopening
        prs = Presentation(output)
        assert len(prs.slides) == 20


def test_render_result_has_log() -> None:
    """RenderResult contains per-slide status entries."""
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


def test_render_title_slide_uses_subtitle_for_body() -> None:
    """TITLE layout puts body content in subtitle placeholder."""
    from src.services.renderer import render_pptx

    slides = [
        SlideObject(
            slide_id="S-001",
            title="Company Name",
            layout_type=LayoutType.TITLE,
            body_content=BodyContent(
                text_elements=["Strategic consulting for the GCC"],
            ),
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "title_body_test.pptx")
        asyncio.run(render_pptx(slides, TEMPLATE_PATH, output))

        prs = Presentation(output)
        slide = prs.slides[0]
        # Subtitle placeholder (idx=1) should have body text
        for ph in slide.placeholders:
            if ph.placeholder_format.idx == 1:
                assert "Strategic consulting" in ph.text
                return
        raise AssertionError("No subtitle placeholder found")


# ──────────────────────────────────────────────────────────────
# DOCX Tests
# ──────────────────────────────────────────────────────────────


def test_export_docx_creates_file() -> None:
    """ResearchReport → .docx file exists with sections."""
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


def test_export_docx_all_sections_present() -> None:
    """All 8 sections of a multi-section report appear in the DOCX.

    Regression test: the original export wrote only the first paragraph
    of the first section, dropping 7 entire sections.
    """
    from src.services.renderer import export_report_docx

    report = _sample_report_multi_section()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "multi_section.docx")
        asyncio.run(export_report_docx(report, output))

        doc = Document(output)
        all_text = "\n".join(p.text for p in doc.paragraphs)

        # All 8 section headings must appear
        for sec in report.sections:
            assert sec.heading in all_text, (
                f"Section '{sec.heading}' missing from DOCX"
            )

        # All section content must appear (not just first paragraph)
        for sec in report.sections:
            # Each section has 3 paragraphs — check they're all there
            assert "First paragraph of section" in all_text
            assert "Second paragraph with" in all_text
            assert "Third paragraph with" in all_text

        # Gaps table should exist
        assert len(doc.tables) >= 1
        gap_table = doc.tables[0]
        assert gap_table.rows[0].cells[0].text == "Gap ID"


def test_export_docx_gaps_table() -> None:
    """Gaps table has correct structure and all entries."""
    from src.services.renderer import export_report_docx

    report = _sample_report()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "gaps_test.docx")
        asyncio.run(export_report_docx(report, output))

        doc = Document(output)
        assert len(doc.tables) >= 1

        gap_table = doc.tables[0]
        # Header row
        assert gap_table.rows[0].cells[0].text == "Gap ID"
        assert gap_table.rows[0].cells[1].text == "Description"
        # Data row
        assert gap_table.rows[1].cells[0].text == "GAP-001"
        assert "ISO 27001" in gap_table.rows[1].cells[1].text


def test_export_docx_paragraph_count() -> None:
    """DOCX has more than just title + 1 heading + 1 line.

    Regression test: original export produced only 3 paragraphs
    from an 8-section report.
    """
    from src.services.renderer import export_report_docx

    report = _sample_report_multi_section()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "count_test.docx")
        asyncio.run(export_report_docx(report, output))

        doc = Document(output)
        # 8 sections × ~4 paragraphs each + title + headings = at least 30
        non_empty = [p for p in doc.paragraphs if p.text.strip()]
        assert len(non_empty) >= 20, (
            f"Expected 20+ paragraphs, got {len(non_empty)} — "
            f"DOCX exporter is truncating content"
        )
