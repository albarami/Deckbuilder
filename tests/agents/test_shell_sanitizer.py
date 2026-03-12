"""Tests for Phase 10 — shell_sanitizer.py.

Tests A2 shell sanitization with allowlist model:
- Allowlist loading from catalog lock
- Approved placeholder clearing for injection
- Non-approved placeholder clearing
- Non-placeholder text box clearing
- Table clearing
- Speaker notes clearing
- Alt-text clearing
- Preserved region handling
- Fail-closed on missing allowlist
- SanitizationReport categorized by type
- Zero-shape-creation guardrail (no add_shape/add_textbox)
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock

import pytest

from src.services.shell_sanitizer import (
    ClearedElement,
    SanitizationError,
    SanitizationReport,
    ShellAllowlist,
    get_allowlist,
    load_a2_allowlists,
    sanitize_all_shells,
    sanitize_shell,
    validate_sanitization,
    _is_forbidden_notes_content,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "data"
CATALOG_LOCK_EN = DATA_DIR / "catalog_lock_en.json"


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
    """Create a mock pptx table."""
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
    return shape


def _make_image_shape(name: str = "Picture 1"):
    shape = MagicMock()
    shape.name = name
    shape.is_placeholder = False
    shape.has_text_frame = False
    shape.has_table = False
    shape._element = MagicMock()
    shape._element.find = MagicMock(return_value=None)
    return shape


def _make_slide(shapes: list, has_notes: bool = False, notes_text: str = ""):
    slide = MagicMock()
    slide.shapes = shapes
    slide.has_notes_slide = has_notes
    if has_notes:
        notes_frame = _make_text_frame(notes_text)
        slide.notes_slide = MagicMock()
        slide.notes_slide.notes_text_frame = notes_frame
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


# ── load_a2_allowlists ─────────────────────────────────────────────────


class TestLoadAllowlists:
    @pytest.mark.skipif(not CATALOG_LOCK_EN.exists(), reason="No catalog lock")
    def test_loads_from_catalog_lock(self):
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        assert len(allowlists) == 3
        assert "proposal_cover" in allowlists
        assert "intro_message" in allowlists
        assert "toc_agenda" in allowlists

    @pytest.mark.skipif(not CATALOG_LOCK_EN.exists(), reason="No catalog lock")
    def test_proposal_cover_allowlist(self):
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        al = allowlists["proposal_cover"]
        assert al.approved_placeholder_indices == {1, 10, 11, 12}

    @pytest.mark.skipif(not CATALOG_LOCK_EN.exists(), reason="No catalog lock")
    def test_intro_message_has_preserved_regions(self):
        allowlists = load_a2_allowlists(CATALOG_LOCK_EN)
        al = allowlists["intro_message"]
        assert "Slide Number Placeholder 8" in al.preserved_shape_names

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(SanitizationError, match="not found"):
            load_a2_allowlists(tmp_path / "nonexistent.json")

    def test_empty_a2_raises(self, tmp_path):
        p = tmp_path / "lock.json"
        p.write_text(json.dumps({"a2_shells": {}}))
        with pytest.raises(SanitizationError, match="no 'a2_shells'"):
            load_a2_allowlists(p)

    def test_no_a2_key_raises(self, tmp_path):
        p = tmp_path / "lock.json"
        p.write_text(json.dumps({"layouts": {}}))
        with pytest.raises(SanitizationError, match="no 'a2_shells'"):
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


# ── _is_forbidden_notes_content ─────────────────────────────────────────


class TestForbiddenContent:
    def test_empty_not_forbidden(self):
        assert _is_forbidden_notes_content("") is False
        assert _is_forbidden_notes_content("   ") is False

    def test_lorem_ipsum_forbidden(self):
        assert _is_forbidden_notes_content("Lorem ipsum dolor sit amet") is True

    def test_click_to_edit_forbidden(self):
        assert _is_forbidden_notes_content("Click to edit master text") is True

    def test_sample_text_forbidden(self):
        assert _is_forbidden_notes_content("This is sample text for the slide") is True

    def test_normal_content_not_forbidden(self):
        assert _is_forbidden_notes_content("Discuss market analysis with client") is False

    def test_insert_text_here_forbidden(self):
        assert _is_forbidden_notes_content("Insert text here") is True


# ── sanitize_shell ──────────────────────────────────────────────────────


class TestSanitizeShell:
    def test_approved_placeholder_cleared_for_injection(self):
        """Approved placeholders have their template text cleared."""
        shape = _make_placeholder_shape(1, text="Template Title Here")
        slide = _make_slide([shape])
        al = _standard_allowlist(approved={1})

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("placeholder", 0) == 1
        # The text was cleared
        assert shape.text_frame.paragraphs[0].runs[0].text == ""

    def test_non_approved_placeholder_cleared(self):
        """Placeholders not on the allowlist have text cleared."""
        shape = _make_placeholder_shape(99, text="Secret Text")
        slide = _make_slide([shape])
        al = _standard_allowlist(approved={1, 10})

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 1
        cleared = report.cleared_elements[0]
        assert cleared.element_type == "placeholder"
        assert "non-approved" in cleared.reason

    def test_text_box_outside_allowlist_cleared(self):
        """Non-placeholder text boxes not on preserved list are cleared."""
        shape = _make_text_box_shape("Random TextBox", text="Leftover text")
        slide = _make_slide([shape])
        al = _standard_allowlist(preserved=set())

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("text_box", 0) == 1

    def test_preserved_text_region_kept(self):
        """Shapes on the preserved allowlist are not cleared."""
        shape = _make_text_box_shape("Slide Number Placeholder 8", text="‹#›")
        slide = _make_slide([shape])
        al = _standard_allowlist(preserved={"Slide Number Placeholder 8"})

        report = sanitize_shell(slide, "intro_message", al)
        assert report.total_cleared == 0
        assert report.preserved_count == 1
        # Text was NOT cleared
        assert shape.text_frame.paragraphs[0].runs[0].text == "‹#›"

    def test_table_outside_allowlist_cleared(self):
        """Tables not on preserved tables list are cleared."""
        shape = _make_table_shape("Random Table", [["A", "B"], ["C", "D"]])
        slide = _make_slide([shape])
        al = _standard_allowlist(preserved_tables=set())

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("table", 0) == 1

    def test_preserved_table_kept(self):
        """Tables on the preserved tables list are not cleared."""
        shape = _make_table_shape("Approved Table", [["Data"]])
        slide = _make_slide([shape])
        al = _standard_allowlist(preserved_tables={"Approved Table"})

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 0
        assert report.preserved_count == 1

    def test_image_shape_preserved(self):
        """Non-text shapes (images) are always preserved."""
        shape = _make_image_shape("Logo")
        slide = _make_slide([shape])
        al = _standard_allowlist()

        report = sanitize_shell(slide, "proposal_cover", al)
        assert report.total_cleared == 0
        assert report.preserved_count == 1

    def test_speaker_notes_with_forbidden_content_cleared(self):
        """Speaker notes with template-example text are cleared."""
        slide = _make_slide([], has_notes=True, notes_text="Lorem ipsum dolor sit amet")

        report = sanitize_shell(slide, "proposal_cover", _standard_allowlist())
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("speaker_notes", 0) == 1

    def test_speaker_notes_with_normal_content_kept(self):
        """Speaker notes with real content are not cleared."""
        slide = _make_slide([], has_notes=True, notes_text="Discuss quarterly results")

        report = sanitize_shell(slide, "proposal_cover", _standard_allowlist())
        notes_cleared = report.cleared_by_type.get("speaker_notes", 0)
        assert notes_cleared == 0

    def test_no_notes_slide_ok(self):
        """Slides without notes don't cause errors."""
        slide = _make_slide([])
        report = sanitize_shell(slide, "proposal_cover", _standard_allowlist())
        assert report.total_cleared == 0

    def test_approved_table_placeholder_cleared_for_injection(self):
        """Table placeholders on the allowlist are cleared for injection."""
        shape = _make_placeholder_shape(10, has_table=True,
                                        table_data=[["Old", "Data"]])
        slide = _make_slide([shape])
        al = _standard_allowlist(approved={10})

        report = sanitize_shell(slide, "toc_agenda", al)
        assert report.total_cleared == 1
        assert report.cleared_by_type.get("table", 0) == 1

    def test_had_content_flag(self):
        """ClearedElement tracks whether content existed before clearing."""
        shape_with = _make_placeholder_shape(1, text="Has text")
        shape_without = _make_placeholder_shape(10, text="")
        slide = _make_slide([shape_with, shape_without])
        al = _standard_allowlist(approved={1, 10})

        report = sanitize_shell(slide, "proposal_cover", al)
        elements = {ce.shape_name: ce for ce in report.cleared_elements}
        assert elements["Placeholder 1"].had_content is True
        assert elements["Placeholder 10"].had_content is False

    def test_report_categorized_by_type(self):
        """Report correctly categorizes by element_type."""
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
        """Complex slide with mixed shapes."""
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
        # 1 approved cleared, 1 non-approved cleared, 1 text_box cleared
        assert report.total_cleared == 3
        # Preserved text box + image = 2 preserved
        assert report.preserved_count == 2


# ── sanitize_all_shells ─────────────────────────────────────────────────


class TestSanitizeAllShells:
    def test_sanitizes_all(self):
        shapes1 = [_make_placeholder_shape(1, text="Title")]
        shapes2 = [_make_placeholder_shape(0, text="ToC Title")]
        slides = {
            "proposal_cover": _make_slide(shapes1),
            "toc_agenda": _make_slide(shapes2),
        }
        allowlists = {
            "proposal_cover": _standard_allowlist("proposal_cover", approved={1}),
            "toc_agenda": _standard_allowlist("toc_agenda", approved={0}),
        }

        reports = sanitize_all_shells(slides, allowlists)
        assert "proposal_cover" in reports
        assert "toc_agenda" in reports
        assert reports["proposal_cover"].total_cleared == 1
        assert reports["toc_agenda"].total_cleared == 1

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
    def test_source_has_no_add_shape(self):
        """shell_sanitizer.py must never call add_shape/add_textbox/add_table."""
        source_path = Path(__file__).resolve().parent.parent.parent / "src" / "services" / "shell_sanitizer.py"
        source = source_path.read_text(encoding="utf-8")
        assert "add_shape" not in source
        assert "add_textbox" not in source
        assert "add_table" not in source
        assert "add_picture" not in source
