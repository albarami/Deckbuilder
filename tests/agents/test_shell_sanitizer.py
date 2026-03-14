"""Tests for Phase 10 — shell_sanitizer.py.

Tests A2 shell sanitization with allowlist model covering all 9 A2 assets:
- 3 cover shells (proposal_cover, intro_message, toc_agenda)
- 6 section dividers (section_divider_01 .. section_divider_06)

Tests:
- Allowlist loading from catalog lock (both a2_shells and section_dividers)
- Approved placeholder clearing for injection
- Non-approved placeholder clearing
- Non-placeholder text box clearing
- Table clearing
- Speaker notes clearing
- Alt-text clearing
- Comments / hidden metadata clearing
- Preserved region handling
- Fail-closed on unknown text-bearing elements (raises SanitizationError)
- Fail-closed on missing allowlist
- SanitizationReport categorized by type
- Zero-shape-creation guardrail (no shape creation methods in source)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.shell_sanitizer import (
    ClearedElement,
    SanitizationError,
    SanitizationReport,
    ShellAllowlist,
    _classify_shape,
    _is_forbidden_content,
    _sanitize_comments,
    _sanitize_hidden_metadata,
    get_allowlist,
    load_a2_allowlists,
    sanitize_all_shells,
    sanitize_shell,
    validate_sanitization,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "data"
CATALOG_LOCK_EN = DATA_DIR / "catalog_lock_en.json"

pytestmark = pytest.mark.skipif(
    not CATALOG_LOCK_EN.exists(),
    reason="Catalog lock not available",
)


# ── Mock helpers ─────────────────────────────────────────────────────────


def _make_run(text: str = ""):
    run = MagicMock()
    run.text = text
    return run


def _make_paragraph(text: str = ""):
    para = MagicMock()
    run = _make_run(text)
    para.runs = [run]
    return para


def _make_text_frame(text: str = ""):
    tf = MagicMock()
    para = _make_paragraph(text)
    tf.paragraphs = [para]
    tf.text = text
    return tf


def _make_table(rows_data: list[list[str]] | None = None):
    if rows_data is None:
        rows_data = [["cell1", "cell2"], ["cell3", "cell4"]]
    table = MagicMock()
    mock_rows = []
    for row_data in rows_data:
        row = MagicMock()
        cells = []
        for cell_text in row_data:
            cell = MagicMock()
            cell.text = cell_text
            cells.append(cell)
        row.cells = cells
        mock_rows.append(row)
    table.rows = mock_rows
    return table


def _make_placeholder_shape(
    idx: int,
    name: str = "",
    text: str = "",
    has_table: bool = False,
    table_data: list[list[str]] | None = None,
):
    shape = MagicMock()
    shape.name = name or f"Placeholder {idx}"
    shape.is_placeholder = True
    shape.placeholder_format = MagicMock()
    shape.placeholder_format.idx = idx
    shape.has_text_frame = not has_table
    shape.has_table = has_table
    shape._element = MagicMock()
    shape._element.find = MagicMock(return_value=None)
    shape._element.tag = "{http://schemas.openxmlformats.org/presentationml/2006/main}sp"

    if has_table:
        shape.table = _make_table(table_data)
    else:
        shape.text_frame = _make_text_frame(text)

    return shape


def _make_text_box_shape(name: str = "TextBox 1", text: str = ""):
    shape = MagicMock()
    shape.name = name
    shape.is_placeholder = False
    shape.has_text_frame = True
    shape.has_table = False
    shape.text_frame = _make_text_frame(text)
    shape._element = MagicMock()
    shape._element.find = MagicMock(return_value=None)
    shape._element.tag = "{http://schemas.openxmlformats.org/presentationml/2006/main}sp"
    shape.shape_type = None
    return shape


def _make_table_shape(name: str = "Table 1", table_data: list[list[str]] | None = None):
    shape = MagicMock()
    shape.name = name
    shape.is_placeholder = False
    shape.has_text_frame = False
    shape.has_table = True
    shape.table = _make_table(table_data)
    shape._element = MagicMock()
    shape._element.find = MagicMock(return_value=None)
    shape._element.tag = "{http://schemas.openxmlformats.org/presentationml/2006/main}graphicFrame"
    shape.shape_type = None
    return shape


def _make_image_shape(name: str = "Picture 1"):
    shape = MagicMock()
    shape.name = name
    shape.is_placeholder = False
    shape.has_text_frame = False
    shape.has_table = False
    shape._element = MagicMock()
    shape._element.find = MagicMock(return_value=None)
    shape._element.tag = "{http://schemas.openxmlformats.org/presentationml/2006/main}pic"
    shape.shape_type = "PICTURE (13)"
    return shape


def _make_connector_shape(name: str = "Connector 1"):
    shape = MagicMock()
    shape.name = name
    shape.is_placeholder = False
    shape.has_text_frame = False
    shape.has_table = False
    shape._element = MagicMock()
    shape._element.find = MagicMock(return_value=None)
    shape._element.tag = "{http://schemas.openxmlformats.org/presentationml/2006/main}cxnSp"
    shape.shape_type = "CONNECTOR"
    return shape


def _make_unknown_shape(name: str = "Unknown 1"):
    """Create a shape that cannot be classified — should trigger fail-closed."""
    shape = MagicMock()
    shape.name = name
    shape.is_placeholder = False
    shape.has_text_frame = False
    shape.has_table = False
    shape._element = MagicMock()
    shape._element.tag = "unknownTag"
    shape.shape_type = "SOMETHING_WEIRD"
    return shape


def _make_slide(shapes: list, has_notes: bool = False, notes_text: str = ""):
    slide = MagicMock()
    slide.shapes = shapes
    slide.has_notes_slide = has_notes
    slide._element = MagicMock()
    slide._element.iter = MagicMock(return_value=iter([]))

    if has_notes:
        notes_frame = _make_text_frame(notes_text)
        slide.notes_slide = MagicMock()
        slide.notes_slide.notes_text_frame = notes_frame

    # No comment rels by default
    slide.part = MagicMock()
    slide.part.rels = MagicMock()
    slide.part.rels.values = MagicMock(return_value=[])

    return slide


def _standard_allowlist(
    shell_id: str = "proposal_cover",
    approved: set[int] | None = None,
    preserved: set[str] | None = None,
    preserved_tables: set[str] | None = None,
) -> ShellAllowlist:
    return ShellAllowlist(
        shell_id=shell_id,
        approved_placeholder_indices=approved or {1, 10, 11, 12},
        preserved_shape_names=preserved or set(),
        preserved_table_names=preserved_tables or set(),
    )


# ── ShellAllowlist ──────────────────────────────────────────────────────


class TestShellAllowlist:
    def test_frozen(self):
        al = _standard_allowlist()
        with pytest.raises(AttributeError):
            al.shell_id = "hacked"  # type: ignore[misc]

    def test_fields(self):
        al = _standard_allowlist(approved={1, 10})
        assert al.shell_id == "proposal_cover"
        assert al.approved_placeholder_indices == {1, 10}


# ── ClearedElement ──────────────────────────────────────────────────────


class TestClearedElement:
    def test_frozen(self):
        ce = ClearedElement(
            shell_id="pc", element_type="placeholder",
            shape_name="ph1", reason="test", had_content=True,
        )
        with pytest.raises(AttributeError):
            ce.reason = "x"  # type: ignore[misc]

    def test_element_types_include_comment_and_metadata(self):
        """ClearedElement supports comment and hidden_metadata types."""
        ce_comment = ClearedElement(
            shell_id="pc", element_type="comment",
            shape_name="c1", reason="test", had_content=True,
        )
        ce_meta = ClearedElement(
            shell_id="pc", element_type="hidden_metadata",
            shape_name="m1", reason="test", had_content=True,
        )
        assert ce_comment.element_type == "comment"
        assert ce_meta.element_type == "hidden_metadata"


# ── SanitizationReport ─────────────────────────────────────────────────


class TestSanitizationReport:
    def test_frozen(self):
        r = SanitizationReport(
            shell_id="pc", total_cleared=0,
            cleared_by_type={}, cleared_elements=(),
            preserved_count=0,
        )
        with pytest.raises(AttributeError):
            r.total_cleared = 99  # type: ignore[misc]


# ── load_a2_allowlists: coverage for all 9 A2 assets ───────────────────


class TestLoadAllowlists:
    def test_loads_all_9_a2_assets(self):
        """Must load 3 cover shells + 6 section dividers = 9 total."""
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        assert len(allowlists) == 9

    def test_cover_shells_present(self):
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        assert "proposal_cover" in allowlists
        assert "intro_message" in allowlists
        assert "toc_agenda" in allowlists

    def test_all_6_section_dividers_present(self):
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        for i in range(1, 7):
            key = f"section_divider_{i:02d}"
            assert key in allowlists, f"Missing allowlist for '{key}'"

    def test_proposal_cover_allowlist(self):
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        al = allowlists["proposal_cover"]
        assert al.approved_placeholder_indices == {1, 10, 11, 12}

    def test_section_divider_01_allowlist(self):
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        al = allowlists["section_divider_01"]
        assert al.approved_placeholder_indices == {0, 10}

    def test_section_divider_06_allowlist(self):
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        al = allowlists["section_divider_06"]
        assert al.approved_placeholder_indices == {0, 10}

    def test_intro_message_has_preserved_regions(self):
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        al = allowlists["intro_message"]
        assert "Slide Number Placeholder 8" in al.preserved_shape_names

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(SanitizationError, match="not found"):
            load_a2_allowlists(tmp_path / "nonexistent.json")

    def test_empty_lock_raises(self, tmp_path):
        p = tmp_path / "lock.json"
        p.write_text(json.dumps({"a2_shells": {}, "section_dividers": {}}))
        with pytest.raises(SanitizationError, match="no A2 shells"):
            load_a2_allowlists(p)


# ── get_allowlist ───────────────────────────────────────────────────────


class TestGetAllowlist:
    def test_lookup_existing(self):
        als = {"pc": _standard_allowlist("pc")}
        al = get_allowlist(als, "pc")
        assert al.shell_id == "pc"

    def test_lookup_missing_raises(self):
        with pytest.raises(SanitizationError, match="phantom"):
            get_allowlist({}, "phantom")


# ── _is_forbidden_content ───────────────────────────────────────────────


class TestForbiddenContent:
    def test_empty_not_forbidden(self):
        assert _is_forbidden_content("") is False
        assert _is_forbidden_content("   ") is False

    def test_lorem_ipsum_forbidden(self):
        assert _is_forbidden_content("Lorem ipsum dolor sit amet") is True

    def test_click_to_edit_forbidden(self):
        assert _is_forbidden_content("Click to edit master text") is True

    def test_sample_text_forbidden(self):
        assert _is_forbidden_content("This is sample text for the slide") is True

    def test_normal_content_not_forbidden(self):
        assert _is_forbidden_content("Discuss market analysis with client") is False

    def test_insert_text_here_forbidden(self):
        assert _is_forbidden_content("Insert text here") is True


# ── _classify_shape ─────────────────────────────────────────────────────


class TestClassifyShape:
    def test_placeholder(self):
        shape = _make_placeholder_shape(1)
        assert _classify_shape(shape) == "placeholder"

    def test_text_frame(self):
        shape = _make_text_box_shape()
        assert _classify_shape(shape) == "text_frame"

    def test_table(self):
        shape = _make_table_shape()
        assert _classify_shape(shape) == "table"

    def test_picture(self):
        shape = _make_image_shape()
        assert _classify_shape(shape) == "picture"

    def test_connector(self):
        shape = _make_connector_shape()
        assert _classify_shape(shape) == "connector"

    def test_unknown(self):
        shape = _make_unknown_shape()
        assert _classify_shape(shape) == "unknown"


# ── sanitize_shell ──────────────────────────────────────────────────────


class TestSanitizeShell:
    def test_approved_placeholder_cleared_for_injection(self):
        shape = _make_placeholder_shape(1, text="Template Title Here")
        slide = _make_slide([shape])
        al = _standard_allowlist(approved={1})

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("placeholder", 0) == 1
        assert shape.text_frame.paragraphs[0].runs[0].text == ""

    def test_non_approved_placeholder_cleared(self):
        shape = _make_placeholder_shape(99, text="Secret Text")
        slide = _make_slide([shape])
        al = _standard_allowlist(approved={1, 10})

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 1
        cleared = report.cleared_elements[0]
        assert cleared.element_type == "placeholder"
        assert "non-approved" in cleared.reason

    def test_text_box_outside_allowlist_cleared(self):
        shape = _make_text_box_shape("Random TextBox", text="Leftover text")
        slide = _make_slide([shape])
        al = _standard_allowlist(preserved=set())

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("text_box", 0) == 1

    def test_preserved_text_region_kept(self):
        shape = _make_text_box_shape("Slide Number Placeholder 8", text="‹#›")
        slide = _make_slide([shape])
        al = _standard_allowlist(preserved={"Slide Number Placeholder 8"})

        report = sanitize_shell(slide, "intro_message", al)
        assert report.total_cleared == 0
        assert report.preserved_count == 1
        assert shape.text_frame.paragraphs[0].runs[0].text == "‹#›"

    def test_table_outside_allowlist_cleared(self):
        shape = _make_table_shape("Random Table", [["A", "B"], ["C", "D"]])
        slide = _make_slide([shape])
        al = _standard_allowlist(preserved_tables=set())

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("table", 0) == 1

    def test_preserved_table_kept(self):
        shape = _make_table_shape("Approved Table", [["Data"]])
        slide = _make_slide([shape])
        al = _standard_allowlist(preserved_tables={"Approved Table"})

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 0
        assert report.preserved_count == 1

    def test_image_shape_preserved(self):
        shape = _make_image_shape("Logo")
        slide = _make_slide([shape])
        al = _standard_allowlist()

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 0
        assert report.preserved_count == 1

    def test_connector_shape_preserved(self):
        shape = _make_connector_shape("Line 1")
        slide = _make_slide([shape])
        al = _standard_allowlist()

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 0
        assert report.preserved_count == 1

    def test_speaker_notes_with_forbidden_content_cleared(self):
        slide = _make_slide([], has_notes=True, notes_text="Lorem ipsum dolor sit amet")

        report = sanitize_shell(slide, "proposal_cover", _standard_allowlist())
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("speaker_notes", 0) == 1

    def test_speaker_notes_with_normal_content_kept(self):
        slide = _make_slide([], has_notes=True, notes_text="Discuss quarterly results")

        report = sanitize_shell(slide, "proposal_cover", _standard_allowlist())
        notes_cleared = report.cleared_by_type.get("speaker_notes", 0)
        assert notes_cleared == 0

    def test_no_notes_slide_ok(self):
        slide = _make_slide([])
        report = sanitize_shell(slide, "proposal_cover", _standard_allowlist())
        assert report.total_cleared == 0

    def test_approved_table_placeholder_cleared_for_injection(self):
        shape = _make_placeholder_shape(10, has_table=True,
                                        table_data=[["Old", "Data"]])
        slide = _make_slide([shape])
        al = _standard_allowlist(approved={10})

        report = sanitize_shell(slide, "toc_agenda", al)
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("table", 0) == 1

    def test_had_content_flag(self):
        shape_with = _make_placeholder_shape(1, text="Has text")
        shape_without = _make_placeholder_shape(10, text="")
        slide = _make_slide([shape_with, shape_without])
        al = _standard_allowlist(approved={1, 10})

        report = sanitize_shell(slide, "proposal_cover", al)
        elements = {ce.shape_name: ce for ce in report.cleared_elements}
        assert elements["Placeholder 1"].had_content is True
        assert elements["Placeholder 10"].had_content is False

    def test_report_categorized_by_type(self):
        shapes = [
            _make_placeholder_shape(1, text="Title"),
            _make_text_box_shape("TB1", text="Extra"),
            _make_table_shape("Tbl1", [["X"]]),
        ]
        slide = _make_slide(shapes, has_notes=True, notes_text="Sample text here")
        al = _standard_allowlist(approved={1})

        report = sanitize_shell(slide, "proposal_cover", al)
        assert "placeholder" in report.cleared_by_type
        assert "text_box" in report.cleared_by_type
        assert "table" in report.cleared_by_type
        assert "speaker_notes" in report.cleared_by_type

    def test_multiple_shapes_mixed(self):
        shapes = [
            _make_placeholder_shape(1, text="Approved PH"),
            _make_placeholder_shape(99, text="Non-approved PH"),
            _make_text_box_shape("Preserved", text="Keep"),
            _make_text_box_shape("NotPreserved", text="Clear"),
            _make_image_shape("Logo"),
        ]
        slide = _make_slide(shapes)
        al = _standard_allowlist(
            approved={1},
            preserved={"Preserved"},
        )

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 3
        assert report.preserved_count == 2


# ── Fail-closed: unknown text-bearing elements ─────────────────────────


class TestFailClosed:
    def test_unknown_shape_raises_sanitization_error(self):
        """Unknown shapes that cannot be classified must trigger fail-closed."""
        shape = _make_unknown_shape("Mystery Shape")
        slide = _make_slide([shape])
        al = _standard_allowlist()

        with pytest.raises(SanitizationError, match="unknown shape type"):
            sanitize_shell(slide, "proposal_cover", al)

    def test_unknown_shape_error_includes_shell_id(self):
        shape = _make_unknown_shape("Mystery")
        slide = _make_slide([shape])
        al = _standard_allowlist()

        with pytest.raises(SanitizationError, match="proposal_cover"):
            sanitize_shell(slide, "proposal_cover", al)

    def test_unknown_shape_error_includes_shape_name(self):
        shape = _make_unknown_shape("MyWeirdShape")
        slide = _make_slide([shape])
        al = _standard_allowlist()

        with pytest.raises(SanitizationError, match="MyWeirdShape"):
            sanitize_shell(slide, "proposal_cover", al)

    def test_known_non_text_shapes_do_not_raise(self):
        """Pictures, connectors, etc. are known non-text types — no error."""
        shapes = [
            _make_image_shape("Logo"),
            _make_connector_shape("Line"),
        ]
        slide = _make_slide(shapes)
        al = _standard_allowlist()

        # Should NOT raise
        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.preserved_count == 2

    def test_missing_allowlist_raises(self):
        with pytest.raises(SanitizationError, match="unknown_shell"):
            sanitize_all_shells(
                {"unknown_shell": _make_slide([])},
                {},
            )


# ── Comments / hidden metadata sanitization ─────────────────────────────


class TestCommentsSanitization:
    def test_sanitize_comments_with_forbidden_content(self):
        """Comments with template-example content should be cleared."""
        slide = _make_slide([])

        # Mock a comment relationship
        rel = MagicMock()
        rel.reltype = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
        target_part = MagicMock()
        target_part.blob = b"Lorem ipsum sample comment"
        rel.target_part = target_part
        slide.part.rels.values = MagicMock(return_value=[rel])

        cleared = _sanitize_comments(slide, "proposal_cover")
        assert len(cleared) == 1
        assert cleared[0].element_type == "comment"
        assert cleared[0].had_content is True

    def test_sanitize_comments_with_normal_content(self):
        """Comments with normal content should not be cleared."""
        slide = _make_slide([])

        rel = MagicMock()
        rel.reltype = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
        target_part = MagicMock()
        target_part.blob = b"Review this section before submission"
        rel.target_part = target_part
        slide.part.rels.values = MagicMock(return_value=[rel])

        cleared = _sanitize_comments(slide, "proposal_cover")
        assert len(cleared) == 0

    def test_sanitize_comments_no_rels(self):
        """Slides without comment rels produce no cleared elements."""
        slide = _make_slide([])
        cleared = _sanitize_comments(slide, "proposal_cover")
        assert len(cleared) == 0

    def test_comments_integrated_in_sanitize_shell(self):
        """Comments clearing is invoked as part of full sanitize_shell."""
        slide = _make_slide([])
        rel = MagicMock()
        rel.reltype = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
        target_part = MagicMock()
        target_part.blob = b"Click to edit this example: comment"
        rel.target_part = target_part
        slide.part.rels.values = MagicMock(return_value=[rel])

        report = sanitize_shell(slide, "proposal_cover", _standard_allowlist())
        assert report.cleared_by_type.get("comment", 0) == 1


class TestHiddenMetadataSanitization:
    def test_sanitize_hidden_metadata_no_metadata(self):
        """Slides without hidden metadata produce no cleared elements."""
        slide = _make_slide([])
        cleared = _sanitize_hidden_metadata(slide, "proposal_cover")
        assert len(cleared) == 0

    def test_hidden_metadata_integrated_in_sanitize_shell(self):
        """Hidden metadata clearing is invoked as part of full sanitize_shell."""
        slide = _make_slide([])
        # No metadata to clear, just verify it doesn't crash
        report = sanitize_shell(slide, "proposal_cover", _standard_allowlist())
        assert report.cleared_by_type.get("hidden_metadata", 0) == 0


# ── Section divider sanitization ────────────────────────────────────────


class TestSectionDividerSanitization:
    def test_divider_01_sanitization(self):
        """section_divider_01 can be sanitized with its allowlist."""
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        al = allowlists["section_divider_01"]

        shape_title = _make_placeholder_shape(0, text="Understanding")
        shape_body = _make_placeholder_shape(10, text="Client's key challenges")
        slide = _make_slide([shape_title, shape_body])

        report = sanitize_shell(slide, "section_divider_01", al)
        assert report.total_cleared == 2  # both placeholders cleared for injection

    def test_divider_06_sanitization(self):
        """section_divider_06 can be sanitized with its allowlist."""
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        al = allowlists["section_divider_06"]

        shape_title = _make_placeholder_shape(0, text="Governance")
        slide = _make_slide([shape_title])

        report = sanitize_shell(slide, "section_divider_06", al)
        assert report.total_cleared == 1

    def test_all_dividers_have_title_and_body_approved(self):
        """All 6 section dividers should approve idx 0 (TITLE) and 10 (BODY)."""
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        for i in range(1, 7):
            al = allowlists[f"section_divider_{i:02d}"]
            assert 0 in al.approved_placeholder_indices, f"Divider {i:02d} missing TITLE"
            assert 10 in al.approved_placeholder_indices, f"Divider {i:02d} missing BODY"

    def test_divider_non_approved_placeholder_cleared(self):
        """Non-approved placeholders on dividers are cleared."""
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        al = allowlists["section_divider_03"]

        shape_ok = _make_placeholder_shape(0, text="Methodology")
        shape_bad = _make_placeholder_shape(99, text="Rogue text")
        slide = _make_slide([shape_ok, shape_bad])

        report = sanitize_shell(slide, "section_divider_03", al)
        non_approved = [
            ce for ce in report.cleared_elements
            if "non-approved" in ce.reason
        ]
        assert len(non_approved) == 1


# ── sanitize_all_shells: batch ──────────────────────────────────────────


class TestSanitizeAllShells:
    def test_sanitizes_all_9(self):
        """Can batch-sanitize all 9 A2 assets."""
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        slides = {}
        for shell_id in allowlists:
            slides[shell_id] = _make_slide([
                _make_placeholder_shape(0, text="Title"),
            ])

        reports = sanitize_all_shells(slides, allowlists)
        assert len(reports) == 9

    def test_missing_allowlist_raises(self):
        slides = {"unknown_shell": _make_slide([])}
        allowlists = {}
        with pytest.raises(SanitizationError, match="unknown_shell"):
            sanitize_all_shells(slides, allowlists)


# ── validate_sanitization ──────────────────────────────────────────────


class TestValidateSanitization:
    def test_clean_reports(self):
        reports = {
            "pc": SanitizationReport(
                shell_id="pc", total_cleared=2,
                cleared_by_type={"placeholder": 2},
                cleared_elements=(), preserved_count=1,
            ),
        }
        errors = validate_sanitization(reports)
        assert errors == []

    def test_reports_with_errors(self):
        reports = {
            "pc": SanitizationReport(
                shell_id="pc", total_cleared=0,
                cleared_by_type={}, cleared_elements=(),
                preserved_count=0, errors=["shape corruption detected"],
            ),
        }
        errors = validate_sanitization(reports)
        assert len(errors) == 1
        assert "shape corruption" in errors[0]


# ── Zero-shape-creation guardrail ───────────────────────────────────────


class TestZeroShapeCreation:
    def test_source_has_no_shape_creation_calls(self):
        """shell_sanitizer.py must never call shape creation methods."""
        source_path = Path(__file__).resolve().parent.parent.parent / "src" / "services" / "shell_sanitizer.py"
        source = source_path.read_text(encoding="utf-8")
        # Check function calls (with open paren) to avoid matching comments
        assert ".add_shape(" not in source
        assert ".add_textbox(" not in source
        assert ".add_table(" not in source
        assert ".add_picture(" not in source
