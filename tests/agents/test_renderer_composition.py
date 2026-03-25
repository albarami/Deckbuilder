"""M10.8R Renderer Composition Regression Tests.

Each test renders a real PPTX through the actual renderer, extracts shapes
via composition scorer Layer 1, and evaluates rules via Layer 2.
No mocked ShapeInfo geometry — these are end-to-end through python-pptx.

All Step 11 tests run against the final post-fix renderer state,
after conditional Step 10 if Step 10 was triggered.
"""

from __future__ import annotations

import os

import pytest

from src.models.enums import LayoutType
from src.models.slides import BodyContent, SlideObject
from src.services.composition_scorer import extract_shapes, score_composition
from src.services.renderer import render_pptx

TEMPLATE_PATH = "templates/Presentation6.pptx"

if not os.path.exists(TEMPLATE_PATH):
    pytestmark = pytest.mark.skip(
        reason="templates/Presentation6.pptx is missing in this workspace"
    )


def _slide(
    sid: str,
    layout: LayoutType,
    title: str = "Test Slide",
    elements: list[str] | None = None,
    key_message: str = "",
) -> SlideObject:
    """Helper to build a SlideObject with minimal body content."""
    bc = BodyContent(text_elements=elements or [])
    return SlideObject(
        slide_id=sid,
        title=title,
        layout_type=layout,
        body_content=bc,
        key_message=key_message,
    )


def _violations_for_rule(
    comp_result,
    rule: str,
) -> list:
    """Extract violations matching a specific rule ID."""
    return [
        v
        for s in comp_result.slide_scores
        for v in s.violations
        if v.rule == rule
    ]


# ──────────────────────────────────────────────────────────────
# Test 1: TEAM card no overlap blockers (Defect #1)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_team_card_no_overlap_blockers(tmp_path):
    """TEAM slide with 3+ 'Role — Quals' elements triggers add_team_cards().
    No overlap_severe violations should remain after M10.8R fixes.
    """
    slide_obj = _slide(
        "T-TEAM",
        LayoutType.TEAM,
        title="Key Personnel",
        elements=[
            "Project Manager — 10+ years SAP S/4HANA, PMP certified",
            "Technical Lead — 8 years ABAP/Fiori, SAP Certified",
            "Quality Assurance — 5 years testing, ISTQB certified",
        ],
    )
    output = str(tmp_path / "test.pptx")
    result = await render_pptx([slide_obj], TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, [slide_obj])
    violations = _violations_for_rule(comp, "overlap_severe")
    assert len(violations) == 0, f"overlap_severe: {[v.message for v in violations]}"


# ──────────────────────────────────────────────────────────────
# Test 2: CLOSING title/subtitle no overlap (Defect #2)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_closing_title_subtitle_no_overlap(tmp_path):
    """CLOSING slide with title + body — no overlap_severe between idx=0 and idx=1."""
    slide_obj = _slide(
        "T-CLOSE",
        LayoutType.CLOSING,
        title="Thank You",
        elements=[
            "Contact — info@example.com",
            "Next Steps — Schedule follow-up meeting",
        ],
    )
    output = str(tmp_path / "test.pptx")
    result = await render_pptx([slide_obj], TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, [slide_obj])
    violations = _violations_for_rule(comp, "overlap_severe")
    assert len(violations) == 0, f"overlap_severe: {[v.message for v in violations]}"


# ──────────────────────────────────────────────────────────────
# Test 3: TITLE footer overflow fixed (Defect #11)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_title_footer_overflow_fixed(tmp_path):
    """TITLE slide with project name, client, date — no title_no_overflow."""
    slide_obj = _slide(
        "T-TITLE",
        LayoutType.TITLE,
        title="RFP Response — Enterprise SAP Transformation",
        elements=[
            "RFP Reference — RFP-2024-001",
            "Issuing Entity — SIDF Corporation",
            "Submission Date — 15 March 2025",
        ],
    )
    output = str(tmp_path / "test.pptx")
    result = await render_pptx([slide_obj], TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, [slide_obj])
    violations = _violations_for_rule(comp, "title_no_overflow")
    assert len(violations) == 0, f"title_no_overflow: {[v.message for v in violations]}"


# ──────────────────────────────────────────────────────────────
# Test 4: CONTENT_1COL body below bar (Defect #3)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_content_1col_body_below_bar(tmp_path):
    """CONTENT_1COL with key_message — no content1_body_below_bar on ENTIRE slide.

    The key_message TextBox at 1.55in must be excluded by _is_key_message_shape().
    The body placeholder is at 2.00in from tokens. Neither should trigger the rule.
    """
    slide_obj = _slide(
        "T-C1COL",
        LayoutType.CONTENT_1COL,
        title="Executive Summary",
        elements=[
            "Our approach delivers transformative results",
            "Phase 1 — Discovery and assessment of current landscape",
            "Phase 2 — Design and architecture of target state",
            "Phase 3 — Implementation and go-live support",
        ],
        key_message="Transforming enterprise SAP landscape",
    )
    output = str(tmp_path / "test.pptx")
    result = await render_pptx([slide_obj], TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, [slide_obj])

    # ALL content1_body_below_bar violations must be 0 — including key_message TextBox
    violations = _violations_for_rule(comp, "content1_body_below_bar")
    assert len(violations) == 0, (
        f"content1_body_below_bar: {[v.message for v in violations]}"
    )


# ──────────────────────────────────────────────────────────────
# Test 5: CONTENT_2COL balanced columns (Defect #4)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_content_2col_balanced_columns(tmp_path):
    """CONTENT_2COL with key_message — no content2_column_balance on ENTIRE slide.

    The full-width key_message TextBox (11.5in) must be excluded by
    _is_key_message_shape() from the column balance computation.
    """
    slide_obj = _slide(
        "T-C2COL",
        LayoutType.CONTENT_2COL,
        title="Current vs Future State",
        elements=[
            "Legacy System — Fragmented SAP ECC landscape",
            "Challenges — Multiple custom interfaces",
            "Target State — Unified SAP S/4HANA platform",
            "Benefits — Streamlined operations and reporting",
        ],
        key_message="Modernizing the enterprise technology stack",
    )
    output = str(tmp_path / "test.pptx")
    result = await render_pptx([slide_obj], TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, [slide_obj])

    # ALL content2_column_balance violations must be 0 — including key_message
    violations = _violations_for_rule(comp, "content2_column_balance")
    assert len(violations) == 0, (
        f"content2_column_balance: {[v.message for v in violations]}"
    )


# ──────────────────────────────────────────────────────────────
# Test 6: FRAMEWORK font min 10pt (Defect #5)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_framework_font_min_10pt(tmp_path):
    """FRAMEWORK slide with key-detail pairs — no font_min_soft (< 10pt)."""
    slide_obj = _slide(
        "T-FRAME",
        LayoutType.FRAMEWORK,
        title="Implementation Methodology",
        elements=[
            "Discovery — Assess current state and requirements",
            "Design — Architect target SAP S/4HANA solution",
            "Build — Configure and develop custom extensions",
            "Test — Execute integration and UAT testing",
        ],
    )
    output = str(tmp_path / "test.pptx")
    result = await render_pptx([slide_obj], TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, [slide_obj])
    violations = _violations_for_rule(comp, "font_min_soft")
    assert len(violations) == 0, f"font_min_soft: {[v.message for v in violations]}"


# ──────────────────────────────────────────────────────────────
# Test 7: FRAMEWORK height consistency (Defect #6)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_framework_height_consistency_fixed(tmp_path):
    """FRAMEWORK slide with key-detail pairs (some long text) — no height inconsistency.

    Verifies MSO_AUTO_SIZE.NONE prevents text auto-resize on flow boxes AND
    the scorer's F2 grouping correctly compares flow boxes at similar top
    without being skewed by the detail TextBox below.
    """
    slide_obj = _slide(
        "T-FRMHT",
        LayoutType.FRAMEWORK,
        title="Delivery Phases",
        elements=[
            "Discover — Short phase",
            "Design — Medium length design phase with extra detail",
            "Build — This is a much longer build phase description that tests auto-resize",
            "Test — Final testing phase for quality assurance and sign-off procedures",
        ],
    )
    output = str(tmp_path / "test.pptx")
    result = await render_pptx([slide_obj], TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, [slide_obj])
    violations = _violations_for_rule(comp, "framework_height_consistency")
    assert len(violations) == 0, (
        f"framework_height_consistency: {[v.message for v in violations]}"
    )


# ──────────────────────────────────────────────────────────────
# Test 8: COMPARISON both sides populated (Defect #7)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_comparison_both_sides_populated(tmp_path):
    """COMPARISON slide with pipe-table elements — no comparison_two_areas.

    Pipe-table data renders as a single full-width Table shape (11.5in).
    The scorer's full-width table recognition must prevent false violations.
    """
    slide_obj = _slide(
        "T-COMP",
        LayoutType.COMPARISON,
        title="Solution Comparison",
        elements=[
            "Approach | Risk Level | Timeline",
            "Cloud-First | Low risk | 6 months",
            "Hybrid | Medium risk | 12 months",
        ],
    )
    output = str(tmp_path / "test.pptx")
    result = await render_pptx([slide_obj], TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, [slide_obj])
    violations = _violations_for_rule(comp, "comparison_two_areas")
    assert len(violations) == 0, (
        f"comparison_two_areas: {[v.message for v in violations]}"
    )


# ──────────────────────────────────────────────────────────────
# Test 9: TIMELINE detail below threshold (Defect #10)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeline_detail_below_threshold(tmp_path):
    """TIMELINE slide with non-phase elements (table fallback) — table at >= 3.2in."""
    slide_obj = _slide(
        "T-TMLN",
        LayoutType.TIMELINE,
        title="Project Timeline",
        elements=[
            "Q1 2025 — Discovery and Assessment",
            "Q2 2025 — Design and Build",
        ],
    )
    output = str(tmp_path / "test.pptx")
    result = await render_pptx([slide_obj], TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, [slide_obj])
    violations = _violations_for_rule(comp, "timeline_detail_below")
    assert len(violations) == 0, (
        f"timeline_detail_below: {[v.message for v in violations]}"
    )


# ──────────────────────────────────────────────────────────────
# Test 10: Multi-layout mini-deck zero blockers
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multi_layout_mini_deck_zero_blockers(tmp_path):
    """Compact 8-slide mini-deck through real renderer — zero blockers.

    Covers: TITLE, CONTENT_1COL, CONTENT_2COL, FRAMEWORK, COMPARISON,
    TEAM, TIMELINE, CLOSING. Guards against token drift and regressions.
    """
    slides = [
        _slide("M-001", LayoutType.TITLE, "RFP Response — SAP Transformation", [
            "Issuing Entity — SIDF Corporation",
            "Submission Date — 15 March 2025",
        ]),
        _slide("M-002", LayoutType.CONTENT_1COL, "Executive Summary", [
            "Our firm brings 15+ years of SAP expertise",
            "Phase 1 — Discovery and assessment",
            "Phase 2 — Design and architecture",
        ]),
        _slide("M-003", LayoutType.CONTENT_2COL, "Current vs Future", [
            "Legacy — SAP ECC with custom modules",
            "Challenges — Fragmented processes",
            "Target — SAP S/4HANA unified platform",
            "Benefits — Streamlined operations",
        ]),
        _slide("M-004", LayoutType.FRAMEWORK, "Methodology", [
            "Discover — Assess current landscape",
            "Design — Architect target state",
            "Build — Configure and develop",
            "Deploy — Go-live and support",
        ]),
        _slide("M-005", LayoutType.COMPARISON, "Option Analysis", [
            "Approach | Risk Level | Timeline",
            "Cloud-First | Low risk | 6 months",
            "Hybrid | Medium risk | 12 months",
        ]),
        _slide("M-006", LayoutType.TEAM, "Key Personnel", [
            "Project Manager — 10+ years SAP, PMP certified",
            "Technical Lead — 8 years ABAP/Fiori expert",
            "QA Manager — 5 years testing, ISTQB certified",
        ]),
        _slide("M-007", LayoutType.TIMELINE, "Project Timeline", [
            "Q1 — Discovery and Assessment",
            "Q2 — Design and Build",
        ]),
        _slide("M-008", LayoutType.CLOSING, "Thank You", [
            "Contact — team@example.com",
            "Next Steps — Schedule follow-up",
        ]),
    ]
    output = str(tmp_path / "mini_deck.pptx")
    result = await render_pptx(slides, TEMPLATE_PATH, output)
    shapes = extract_shapes(result.pptx_path)
    comp = score_composition(shapes, slides)

    assert comp.blocker_count == 0, (
        f"Mini-deck has {comp.blocker_count} blockers: "
        f"{[(v.slide_id, v.rule) for s in comp.slide_scores for v in s.violations if str(v.severity) == 'blocker']}"
    )
