"""Design Agent — deterministic PPTX renderer and DOCX exporter.

No LLM involvement. Loads the Strategic Gears master template
(Presentation6.pptx) and populates slides from validated SlideObjects.

Template layouts (Presentation6.pptx):
  0: Title Slide       — CENTER_TITLE(0) + SUBTITLE(1)
  1: Title and Content  — TITLE(0) + OBJECT(1)
  2: Section Header     — TITLE(0) + BODY(1)
  3: Two Content        — TITLE(0) + OBJECT(1) + OBJECT(2)
  4: Comparison         — TITLE(0) + BODY(1) + OBJECT(2) + BODY(3) + OBJECT(4)
  5: Title Only         — TITLE(0)
  6: Blank              — (footer only)
  7: Content with Caption — TITLE(0) + OBJECT(1) + BODY(2)
  8: Picture with Caption — TITLE(0) + PICTURE(1) + BODY(2)
  9: Title and Vertical Text
 10: Vertical Title and Text
 11: Proposal Cover     — SUBTITLE(1) + BODY(10,11) + PICTURE(12)
 12: ToC / Agenda       — TITLE(0) + TABLE(10)
"""

from pathlib import Path
from typing import Any

from docx import Document
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

from src.models.enums import Language, LayoutType, RenderStatus
from src.models.report import ResearchReport
from src.models.slides import SlideObject

# ──────────────────────────────────────────────────────────────
# Layout mapping — DeckForge LayoutType → template layout index
# ──────────────────────────────────────────────────────────────

LAYOUT_MAP: dict[LayoutType, int] = {
    LayoutType.TITLE: 0,
    LayoutType.AGENDA: 12,
    LayoutType.SECTION: 2,
    LayoutType.CONTENT_1COL: 1,
    LayoutType.CONTENT_2COL: 3,
    LayoutType.DATA_CHART: 1,
    LayoutType.FRAMEWORK: 7,
    LayoutType.COMPARISON: 4,
    LayoutType.STAT_CALLOUT: 5,
    LayoutType.TEAM: 1,
    LayoutType.TIMELINE: 1,
    LayoutType.COMPLIANCE_MATRIX: 1,
    LayoutType.CLOSING: 0,
}

_DEFAULT_LAYOUT_IDX = 1  # "Title and Content" as fallback


# ──────────────────────────────────────────────────────────────
# RenderResult — output of render_pptx()
# ──────────────────────────────────────────────────────────────


class RenderResult:
    """Result of PPTX rendering."""

    def __init__(
        self,
        pptx_path: str,
        slide_count: int,
        render_log: list[dict[str, Any]],
    ) -> None:
        self.pptx_path = pptx_path
        self.slide_count = slide_count
        self.render_log = render_log


# ──────────────────────────────────────────────────────────────
# PPTX Renderer
# ──────────────────────────────────────────────────────────────


def _get_layout_index(layout_type: LayoutType) -> int:
    """Get template layout index for a LayoutType."""
    return LAYOUT_MAP.get(layout_type, _DEFAULT_LAYOUT_IDX)


def _populate_title(slide: Any, title: str) -> None:
    """Set the title placeholder text."""
    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        if idx == 0:
            ph.text = title
            return
    # Layout 11 (Proposal Cover) has no idx=0, use subtitle (idx=1)
    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        if idx == 1:
            ph.text = title
            return


def _find_body_placeholder(slide: Any) -> Any | None:
    """Find the best placeholder for body content.

    Priority:
      1. idx=1 with type BODY (2) or OBJECT (7) — standard content layouts
      2. idx=1 with type SUBTITLE (4) — Title Slide layout (used for TITLE/CLOSING)
      3. idx=1 with any text frame — catch-all for non-standard layouts

    Returns None if no suitable placeholder is found (e.g. Title Only, Agenda).
    """
    # Pass 1: standard BODY/OBJECT at idx=1
    for ph in slide.placeholders:
        if ph.placeholder_format.idx == 1 and ph.placeholder_format.type in (2, 7):
            return ph

    # Pass 2: SUBTITLE at idx=1 (Title Slide layout)
    for ph in slide.placeholders:
        if ph.placeholder_format.idx == 1 and ph.has_text_frame:
            return ph

    return None


def _fill_text_frame(tf: Any, elements: list[str]) -> None:
    """Fill a text frame with bullet-point elements."""
    tf.clear()
    for i, text in enumerate(elements):
        if i == 0:
            tf.paragraphs[0].text = text
        else:
            p = tf.add_paragraph()
            p.text = text


def _add_body_textbox(
    slide: Any,
    elements: list[str],
) -> None:
    """Add a text box with body content when no placeholder exists.

    Used for layouts like Title Only (STAT_CALLOUT) and ToC/Agenda
    that have no body/content placeholder.
    """
    left = Inches(0.7)
    top = Inches(1.8)
    width = Inches(8.6)
    height = Inches(5.0)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    _fill_text_frame(tf, elements)


def _populate_body(
    slide: Any,
    slide_obj: SlideObject,
    log_entry: dict[str, Any],
) -> None:
    """Populate body content placeholder with text elements.

    Falls back to a text box for layouts without a body placeholder
    (Title Only, ToC/Agenda). Body content is never silently dropped.
    """
    if not slide_obj.body_content or not slide_obj.body_content.text_elements:
        return

    elements = slide_obj.body_content.text_elements
    body_ph = _find_body_placeholder(slide)

    if body_ph is not None:
        _fill_text_frame(body_ph.text_frame, elements)
        return

    # No placeholder — add a textbox fallback
    _add_body_textbox(slide, elements)
    log_entry["message"] += " Used textbox fallback for body content."


def _populate_two_col(
    slide: Any,
    slide_obj: SlideObject,
) -> None:
    """Populate two-column layout (idx=1 and idx=2)."""
    if not slide_obj.body_content or not slide_obj.body_content.text_elements:
        return

    elements = slide_obj.body_content.text_elements
    mid = len(elements) // 2

    col_phs: dict[int, Any] = {}
    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        if idx in (1, 2) and ph.placeholder_format.type in (2, 7):
            col_phs[idx] = ph

    for col_idx, items in [(1, elements[:mid]), (2, elements[mid:])]:
        ph = col_phs.get(col_idx)
        if ph is None or not items:
            continue
        _fill_text_frame(ph.text_frame, items)


def _add_speaker_notes(slide: Any, notes: str) -> None:
    """Add speaker notes to the slide."""
    if not notes:
        return
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = notes


def _apply_rtl(slide: Any) -> None:
    """Apply RTL text direction to all paragraphs in the slide."""
    ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for paragraph in shape.text_frame.paragraphs:
            pPr = paragraph._p.get_or_add_pPr()
            pPr.set(f"{{{ns}}}rtl", "1")


def _add_chart(
    slide: Any,
    slide_obj: SlideObject,
    log_entry: dict[str, Any],
) -> None:
    """Add a chart to the slide from chart_spec."""
    if not slide_obj.chart_spec:
        return

    spec = slide_obj.chart_spec
    supported = {"bar", "line", "pie"}

    if spec.type not in supported:
        log_entry["status"] = RenderStatus.WARNING
        log_entry["message"] += (
            f" Chart type '{spec.type}' not yet supported — skipped."
        )
        return

    # Charts require data — if no y_axis data, skip
    if not spec.y_axis or not spec.y_axis.get("values"):
        log_entry["status"] = RenderStatus.WARNING
        log_entry["message"] += " Chart has no data — skipped."
        return

    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE

    chart_type_map = {
        "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
        "line": XL_CHART_TYPE.LINE,
        "pie": XL_CHART_TYPE.PIE,
    }

    chart_data = CategoryChartData()
    categories = spec.x_axis.get("values", []) if spec.x_axis else []
    chart_data.categories = categories
    chart_data.add_series(
        spec.y_axis.get("label", "Data"),
        spec.y_axis["values"],
    )

    # Place chart in center of slide
    x = Inches(1.5)
    y = Inches(2.0)
    cx = Inches(8.0)
    cy = Inches(4.5)

    slide.shapes.add_chart(
        chart_type_map[spec.type],
        x, y, cx, cy,
        chart_data,
    )


async def render_pptx(
    slides: list[SlideObject],
    template_path: str,
    output_path: str,
    language: Language = Language.EN,
) -> RenderResult:
    """Render validated slides into branded PPTX using the SG template.

    Args:
        slides: QA-validated SlideObjects from the pipeline.
        template_path: Path to Presentation6.pptx master template.
        output_path: Path to write the rendered .pptx file.
        language: Output language (EN or AR for RTL).

    Returns:
        RenderResult with pptx_path, slide_count, and per-slide render_log.
    """
    prs = Presentation(template_path)

    # Remove existing slides from template
    for sldId in list(prs.slides._sldIdLst):
        rId = sldId.get(qn("r:id"))
        if rId:
            prs.part.drop_rel(rId)
        prs.slides._sldIdLst.remove(sldId)

    render_log: list[dict[str, Any]] = []

    for slide_obj in slides:
        log_entry: dict[str, Any] = {
            "slide_id": slide_obj.slide_id,
            "status": RenderStatus.SUCCESS,
            "message": f"Rendered {slide_obj.layout_type} slide.",
        }

        # Select layout
        layout_idx = _get_layout_index(slide_obj.layout_type)
        layout = prs.slide_layouts[layout_idx]
        slide = prs.slides.add_slide(layout)

        # Populate title
        _populate_title(slide, slide_obj.title)

        # Populate body content
        if slide_obj.layout_type in (
            LayoutType.CONTENT_2COL,
            LayoutType.COMPARISON,
        ):
            _populate_two_col(slide, slide_obj)
        else:
            _populate_body(slide, slide_obj, log_entry)

        # Add chart if specified
        _add_chart(slide, slide_obj, log_entry)

        # Add speaker notes
        _add_speaker_notes(slide, slide_obj.speaker_notes)

        # Apply RTL for Arabic
        if language == Language.AR:
            _apply_rtl(slide)

        render_log.append(log_entry)

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Save
    prs.save(output_path)

    # Verification: reopen and confirm slide count matches
    verify_prs = Presentation(output_path)
    actual_count = len(verify_prs.slides)
    if actual_count != len(slides):
        import logging

        logging.getLogger(__name__).error(
            "PPTX verification failed: expected %d slides, found %d in %s",
            len(slides),
            actual_count,
            output_path,
        )

    return RenderResult(
        pptx_path=output_path,
        slide_count=actual_count,
        render_log=render_log,
    )


# ──────────────────────────────────────────────────────────────
# DOCX Exporter — Research Report
# ──────────────────────────────────────────────────────────────


async def export_report_docx(
    report: ResearchReport,
    output_path: str,
    language: Language = Language.EN,
) -> str:
    """Export Research Report as .docx file.

    Args:
        report: Approved ResearchReport from the pipeline.
        output_path: Path to write the .docx file.
        language: Output language.

    Returns:
        The output file path.
    """
    doc = Document()

    # Title
    doc.add_heading(report.title, level=0)

    # Sections
    for section in report.sections:
        doc.add_heading(section.heading, level=1)
        # Split markdown content into paragraphs
        for para_text in section.content_markdown.split("\n\n"):
            stripped = para_text.strip()
            if stripped:
                doc.add_paragraph(stripped)

    # Gaps table
    if report.all_gaps:
        doc.add_heading("Evidence Gaps", level=1)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Gap ID"
        hdr[1].text = "Description"
        hdr[2].text = "Severity"
        hdr[3].text = "Action Required"

        for gap in report.all_gaps:
            row = table.add_row().cells
            row[0].text = gap.gap_id
            row[1].text = gap.description
            row[2].text = str(gap.severity)
            row[3].text = gap.action_required

    # Source index
    if report.source_index:
        doc.add_heading("Source Index", level=1)
        table = doc.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Claim ID"
        hdr[1].text = "Document"
        hdr[2].text = "Path"

        for src in report.source_index:
            row = table.add_row().cells
            row[0].text = src.claim_id
            row[1].text = src.document_title
            row[2].text = src.sharepoint_path

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    doc.save(output_path)
    return output_path
