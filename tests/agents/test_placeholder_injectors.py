"""Tests for Phase 11 — placeholder_injectors.py.

Tests semantic-layout-driven injection into existing placeholders:
- Title/body injection with bold key phrase formatting
- Center title injection
- Proposal cover injection
- ToC table injection
- Multi-body injection (methodology, case study, intro)
- Team member injection
- Contract validation before injection
- Layout family classification
- No shape creation guardrail
- All resolution by semantic layout ID only
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.placeholder_contracts import PlaceholderContract
from src.services.placeholder_injectors import (
    InjectedPlaceholder,
    InjectionError,
    InjectionResult,
    _find_bold_break,
    get_layout_family,
    inject_center_title,
    inject_multi_body,
    inject_proposal_cover,
    inject_team_members,
    inject_title_body,
    inject_toc_table,
)

# ── Mock helpers ─────────────────────────────────────────────────────────


def _make_run(text: str = ""):
    run = MagicMock()
    run.text = text
    run.font = MagicMock()
    run.font.bold = None
    return run


def _make_paragraph(text: str = ""):
    para = MagicMock()
    run = _make_run(text)
    para.runs = [run]
    para.text = text

    def mock_add_run():
        new_run = _make_run("")
        para.runs.append(new_run)
        return new_run

    para.add_run = mock_add_run
    return para


def _make_text_frame(text: str = ""):
    tf = MagicMock()
    para = _make_paragraph(text)
    tf.paragraphs = [para]
    tf.text = text
    return tf


def _make_placeholder(idx: int, ph_type_str: str = "BODY", text: str = "",
                       has_table: bool = False, table_rows: int = 3, table_cols: int = 2):
    ph = MagicMock()
    ph.placeholder_format = MagicMock()
    ph.placeholder_format.idx = idx
    ph.placeholder_format.type = ph_type_str
    ph.has_text_frame = not has_table
    ph.has_table = has_table
    ph.name = f"Placeholder {idx}"

    if has_table:
        table = MagicMock()
        rows = []
        for _ in range(table_rows):
            row = MagicMock()
            cells = [MagicMock() for _ in range(table_cols)]
            for c in cells:
                c.text = ""
            row.cells = cells
            rows.append(row)
        table.rows = rows
        ph.table = table
    else:
        ph.text_frame = _make_text_frame(text)

    return ph


def _make_slide_with_placeholders(placeholder_specs: list[tuple[int, str, str]]):
    """Create mock slide with specified placeholders.

    Each spec is (idx, type_str, initial_text).
    """
    phs = []
    for idx, ph_type, text in placeholder_specs:
        has_table = ph_type == "TABLE"
        ph = _make_placeholder(idx, ph_type, text, has_table=has_table)
        phs.append(ph)

    slide = MagicMock()
    slide.placeholders = phs
    return slide


def _contract(semantic_id: str, placeholders: dict[int, str]) -> PlaceholderContract:
    return PlaceholderContract(
        semantic_layout_id=semantic_id,
        required_placeholders=placeholders,
    )


# ── InjectedPlaceholder ────────────────────────────────────────────────


class TestInjectedPlaceholder:
    def test_frozen(self):
        ip = InjectedPlaceholder(
            placeholder_idx=0, placeholder_type="TITLE",
            content_preview="test",
        )
        with pytest.raises(AttributeError):
            ip.content_preview = "x"  # type: ignore[misc]

    def test_fields(self):
        ip = InjectedPlaceholder(
            placeholder_idx=0, placeholder_type="TITLE",
            content_preview="My Title", bold_applied=True,
        )
        assert ip.placeholder_idx == 0
        assert ip.bold_applied is True


# ── InjectionResult ─────────────────────────────────────────────────────


class TestInjectionResult:
    def test_frozen(self):
        r = InjectionResult(semantic_layout_id="test")
        with pytest.raises(AttributeError):
            r.semantic_layout_id = "x"  # type: ignore[misc]

    def test_default_empty(self):
        r = InjectionResult(semantic_layout_id="test")
        assert r.injected == ()
        assert r.skipped == ()
        assert r.errors == []


# ── _find_bold_break ────────────────────────────────────────────────────


class TestFindBoldBreak:
    def test_colon_separator(self):
        assert _find_bold_break("Key Finding: details here") == 13

    def test_em_dash_separator(self):
        pos = _find_bold_break("Banking Sector — significant growth")
        assert pos > 0

    def test_first_sentence(self):
        pos = _find_bold_break("Revenue grew 15%. This was driven by new clients.")
        assert pos == 18  # after "Revenue grew 15%."

    def test_no_natural_break(self):
        assert _find_bold_break("short") == 0

    def test_long_text_no_early_break(self):
        text = "A" * 100
        assert _find_bold_break(text) == 0


# ── get_layout_family ───────────────────────────────────────────────────


class TestGetLayoutFamily:
    def test_proposal_cover(self):
        assert get_layout_family("proposal_cover") == "proposal_cover"

    def test_toc_table(self):
        assert get_layout_family("toc_table") == "toc_table"

    def test_team_two_members(self):
        assert get_layout_family("team_two_members") == "team_two_members"

    def test_title_body_layouts(self):
        for lid in ["content_heading_desc", "section_divider_01",
                     "section_divider_06", "methodology_detail"]:
            assert get_layout_family(lid) == "title_body", f"Failed for {lid}"

    def test_center_title(self):
        assert get_layout_family("content_heading_only") == "center_title"

    def test_multi_body_layouts(self):
        for lid in ["intro_message", "methodology_overview_4",
                     "methodology_focused_3", "case_study_detailed",
                     "content_heading_content"]:
            assert get_layout_family(lid) == "multi_body", f"Failed for {lid}"

    def test_unknown_layout(self):
        assert get_layout_family("nonexistent_layout") == "unknown"

    def test_all_section_dividers_are_title_body(self):
        for i in range(1, 10):
            lid = f"section_divider_{i:02d}"
            assert get_layout_family(lid) == "title_body", f"Failed for {lid}"


# ── inject_title_body ───────────────────────────────────────────────────


class TestInjectTitleBody:
    def test_basic_injection(self):
        slide = _make_slide_with_placeholders([
            (0, "TITLE", ""),
            (13, "BODY", ""),
        ])
        contract = _contract("content_heading_desc", {0: "TITLE", 13: "BODY"})

        result = inject_title_body(
            slide, "content_heading_desc", contract,
            title="Understanding the Challenge",
            body="The client faces three key challenges.",
        )
        assert len(result.injected) == 2
        assert result.semantic_layout_id == "content_heading_desc"

    def test_title_injected(self):
        slide = _make_slide_with_placeholders([(0, "TITLE", "")])
        contract = _contract("content_heading_desc", {0: "TITLE"})

        result = inject_title_body(
            slide, "content_heading_desc", contract,
            title="My Title",
        )
        assert result.injected[0].placeholder_type == "TITLE"
        assert result.injected[0].content_preview == "My Title"

    def test_body_with_bold_lead(self):
        slide = _make_slide_with_placeholders([(13, "BODY", "")])
        contract = _contract("content_heading_desc", {13: "BODY"})

        result = inject_title_body(
            slide, "content_heading_desc", contract,
            body="Key Finding: details about the sector growth trend",
            bold_body_lead=True,
        )
        assert len(result.injected) == 1
        assert result.injected[0].bold_applied is True

    def test_section_divider_injection(self):
        slide = _make_slide_with_placeholders([
            (0, "TITLE", ""),
            (10, "BODY", ""),
        ])
        contract = _contract("section_divider_01", {0: "TITLE", 10: "BODY"})

        result = inject_title_body(
            slide, "section_divider_01", contract,
            title="Understanding",
            body="Client challenges and context",
        )
        assert len(result.injected) == 2

    def test_empty_content_skipped(self):
        slide = _make_slide_with_placeholders([
            (0, "TITLE", ""),
            (13, "BODY", ""),
        ])
        contract = _contract("content_heading_desc", {0: "TITLE", 13: "BODY"})

        result = inject_title_body(
            slide, "content_heading_desc", contract,
            title="",
            body="",
        )
        assert len(result.injected) == 0
        assert len(result.skipped) == 2

    def test_contract_violation_raises(self):
        slide = _make_slide_with_placeholders([(0, "TITLE", "")])
        # Contract requires idx 13 BODY which is missing
        contract = _contract("content_heading_desc", {0: "TITLE", 13: "BODY"})

        with pytest.raises(InjectionError, match="Contract violation"):
            inject_title_body(slide, "content_heading_desc", contract, title="X")


# ── inject_center_title ─────────────────────────────────────────────────


class TestInjectCenterTitle:
    def test_basic_injection(self):
        slide = _make_slide_with_placeholders([(0, "CENTER_TITLE", "")])
        contract = _contract("content_heading_only", {0: "CENTER_TITLE"})

        result = inject_center_title(
            slide, "content_heading_only", contract,
            title="Strategic Framework",
        )
        assert len(result.injected) == 1
        assert result.injected[0].placeholder_type == "CENTER_TITLE"

    def test_empty_title_skipped(self):
        slide = _make_slide_with_placeholders([(0, "CENTER_TITLE", "")])
        contract = _contract("content_heading_only", {0: "CENTER_TITLE"})

        result = inject_center_title(
            slide, "content_heading_only", contract,
            title="",
        )
        assert len(result.injected) == 0


# ── inject_proposal_cover ───────────────────────────────────────────────


class TestInjectProposalCover:
    def test_basic_injection(self):
        slide = _make_slide_with_placeholders([
            (1, "SUBTITLE", ""),
            (10, "BODY", ""),
            (11, "BODY", ""),
            (12, "PICTURE", ""),
        ])
        contract = _contract("proposal_cover", {
            1: "SUBTITLE", 10: "BODY", 11: "BODY", 12: "PICTURE",
        })

        result = inject_proposal_cover(
            slide, contract,
            subtitle="Digital Transformation Strategy",
            client_name="Saudi Banking Corporation",
            date_text="March 2026",
        )
        assert result.semantic_layout_id == "proposal_cover"
        assert len(result.injected) == 3
        types = {ip.placeholder_type for ip in result.injected}
        assert "SUBTITLE" in types
        assert "BODY" in types

    def test_picture_skipped(self):
        slide = _make_slide_with_placeholders([
            (12, "PICTURE", ""),
        ])
        contract = _contract("proposal_cover", {12: "PICTURE"})

        result = inject_proposal_cover(slide, contract)
        assert len(result.skipped) == 1


# ── inject_toc_table ────────────────────────────────────────────────────


class TestInjectTocTable:
    def test_title_and_table(self):
        ph_title = _make_placeholder(0, "TITLE")
        ph_table = _make_placeholder(10, "TABLE", has_table=True)
        slide = MagicMock()
        slide.placeholders = [ph_title, ph_table]

        contract = _contract("toc_table", {0: "TITLE", 10: "TABLE"})

        result = inject_toc_table(
            slide, contract,
            title="Agenda",
            rows=[["1", "Understanding"], ["2", "Why Strategic Gears"]],
        )
        assert len(result.injected) == 2
        assert result.injected[1].placeholder_type == "TABLE"
        assert "2 rows" in result.injected[1].content_preview

    def test_empty_rows_skipped(self):
        ph_table = _make_placeholder(10, "TABLE", has_table=True)
        slide = MagicMock()
        slide.placeholders = [ph_table]

        contract = _contract("toc_table", {10: "TABLE"})

        result = inject_toc_table(slide, contract, rows=None)
        assert len(result.skipped) == 1


# ── inject_multi_body ───────────────────────────────────────────────────


class TestInjectMultiBody:
    def test_methodology_overview(self):
        specs = [(13, "BODY", ""), (23, "BODY", ""), (33, "BODY", "")]
        slide = _make_slide_with_placeholders(specs)
        contract = _contract("methodology_overview_4", {
            13: "BODY", 23: "BODY", 33: "BODY",
        })

        result = inject_multi_body(
            slide, "methodology_overview_4", contract,
            body_contents={13: "Phase overview", 23: "Activities", 33: "Deliverables"},
        )
        assert len(result.injected) == 3

    def test_with_title_and_bodies(self):
        specs = [(0, "TITLE", ""), (13, "BODY", ""), (23, "BODY", "")]
        slide = _make_slide_with_placeholders(specs)
        contract = _contract("methodology_focused_4", {
            0: "TITLE", 13: "BODY", 23: "BODY",
        })

        result = inject_multi_body(
            slide, "methodology_focused_4", contract,
            title="Phase 1: Discovery",
            body_contents={13: "Key activities", 23: "Deliverables"},
        )
        assert len(result.injected) == 3

    def test_bold_leads(self):
        specs = [(13, "BODY", "")]
        slide = _make_slide_with_placeholders(specs)
        contract = _contract("case_study_detailed", {13: "BODY"})

        result = inject_multi_body(
            slide, "case_study_detailed", contract,
            body_contents={13: "Revenue Growth: 25% increase over baseline"},
            bold_leads=True,
        )
        assert result.injected[0].bold_applied is True

    def test_missing_body_content_skipped(self):
        specs = [(13, "BODY", ""), (23, "BODY", "")]
        slide = _make_slide_with_placeholders(specs)
        contract = _contract("intro_message", {13: "BODY", 23: "BODY"})

        result = inject_multi_body(
            slide, "intro_message", contract,
            body_contents={13: "Only first body"},
        )
        assert len(result.injected) == 1
        assert 23 in result.skipped

    def test_case_study_detailed(self):
        specs = [
            (0, "TITLE", ""), (43, "BODY", ""),
            (44, "BODY", ""), (45, "BODY", ""), (46, "BODY", ""),
            (20, "PICTURE", ""),
        ]
        slide = _make_slide_with_placeholders(specs)
        contract = _contract("case_study_detailed", {
            0: "TITLE", 43: "BODY", 44: "BODY", 45: "BODY", 46: "BODY", 20: "PICTURE",
        })

        result = inject_multi_body(
            slide, "case_study_detailed", contract,
            title="Banking Transformation",
            body_contents={43: "Client", 44: "Challenge", 45: "Solution", 46: "Result"},
        )
        assert len(result.injected) == 5  # title + 4 bodies
        assert 20 in result.skipped  # picture skipped


# ── inject_team_members ─────────────────────────────────────────────────


class TestInjectTeamMembers:
    def test_basic_injection(self):
        specs = [
            (14, "BODY", ""), (15, "BODY", ""), (16, "BODY", ""),
            (19, "BODY", ""), (20, "BODY", ""), (36, "BODY", ""),
            (13, "PICTURE", ""), (17, "PICTURE", ""),
        ]
        slide = _make_slide_with_placeholders(specs)
        contract = _contract("team_two_members", {
            14: "BODY", 15: "BODY", 16: "BODY",
            19: "BODY", 20: "BODY", 36: "BODY",
            13: "PICTURE", 17: "PICTURE",
        })

        result = inject_team_members(
            slide, contract,
            member1_name="Ahmed Al-Rashid",
            member1_role="Senior Partner",
            member1_bio="15 years in strategy consulting",
            member2_name="Sarah Khan",
            member2_role="Practice Lead",
            member2_bio="Digital transformation expert",
        )
        assert result.semantic_layout_id == "team_two_members"
        assert len(result.injected) == 6
        # Names should have bold applied
        name_injections = [ip for ip in result.injected if ip.placeholder_idx in (14, 19)]
        for ni in name_injections:
            assert ni.bold_applied is True

    def test_single_member(self):
        specs = [(14, "BODY", ""), (15, "BODY", ""), (16, "BODY", "")]
        slide = _make_slide_with_placeholders(specs)
        contract = _contract("team_two_members", {14: "BODY", 15: "BODY", 16: "BODY"})

        result = inject_team_members(
            slide, contract,
            member1_name="Ahmed",
            member1_role="Partner",
            member1_bio="Expert",
        )
        assert len(result.injected) == 3


# ── Contract validation integration ─────────────────────────────────────


class TestContractValidation:
    def test_missing_required_placeholder_raises(self):
        """Injectors must validate contracts before injecting."""
        slide = _make_slide_with_placeholders([(0, "TITLE", "")])
        contract = _contract("content_heading_desc", {0: "TITLE", 13: "BODY"})

        with pytest.raises(InjectionError, match="Contract violation"):
            inject_title_body(slide, "content_heading_desc", contract, title="X")

    def test_valid_contract_succeeds(self):
        slide = _make_slide_with_placeholders([
            (0, "TITLE", ""),
            (13, "BODY", ""),
        ])
        contract = _contract("content_heading_desc", {0: "TITLE", 13: "BODY"})

        result = inject_title_body(
            slide, "content_heading_desc", contract,
            title="Test",
        )
        assert len(result.errors) == 0


# ── Semantic-ID-only resolution ─────────────────────────────────────────


class TestSemanticIDOnly:
    def test_result_uses_semantic_id(self):
        slide = _make_slide_with_placeholders([(0, "TITLE", "")])
        contract = _contract("content_heading_desc", {0: "TITLE"})

        result = inject_title_body(
            slide, "content_heading_desc", contract,
            title="Test",
        )
        assert result.semantic_layout_id == "content_heading_desc"

    def test_no_raw_indices_in_result(self):
        """InjectionResult identifies by semantic_layout_id, not slide index."""
        slide = _make_slide_with_placeholders([(0, "TITLE", "")])
        contract = _contract("section_divider_03", {0: "TITLE"})

        result = inject_title_body(
            slide, "section_divider_03", contract,
            title="Methodology",
        )
        assert result.semantic_layout_id == "section_divider_03"
        # No slide_idx field on InjectionResult
        assert not hasattr(result, "slide_idx")


# ── Zero-shape-creation guardrail ───────────────────────────────────────


class TestZeroShapeCreation:
    def test_source_has_no_shape_creation_calls(self):
        """placeholder_injectors.py must never call shape creation methods."""
        source_path = Path(__file__).resolve().parent.parent.parent / "src" / "services" / "placeholder_injectors.py"
        source = source_path.read_text(encoding="utf-8")
        assert ".add_shape(" not in source
        assert ".add_textbox(" not in source
        assert ".add_table(" not in source
        assert ".add_picture(" not in source
