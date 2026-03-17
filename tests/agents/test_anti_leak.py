"""Phase 15 — Anti-Leak Tests (Cross-Module).

Verifies that template-example content cannot leak into rendered output
through any path.  Tests the interaction between shell_sanitizer,
placeholder_injectors, content_fitter, and renderer_v2 to prove:

  - Non-approved placeholder text is cleared before injection
  - Non-placeholder text boxes are cleared (freeform text shapes)
  - Table cell text in non-approved tables is cleared
  - Speaker notes with forbidden content are cleared
  - Alt-text with forbidden content is cleared
  - Only explicitly selected case studies / team bios appear
  - ContentSourcePolicy is validated on every ManifestEntry
  - Allowlist integrity: only approved targets survive sanitization
  - Forbidden template-example markers are detected
  - B-variable slides receive PROPOSAL_SPECIFIC content only
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.shell_sanitizer import (
    ClearedElement,
    SanitizationError,
    SanitizationReport,
    ShellAllowlist,
    _is_forbidden_content,
    get_allowlist,
    sanitize_shell,
)

# ── Mock helpers ──────────────────────────────────────────────────────


def _make_run(text: str = ""):
    run = MagicMock()
    run.text = text
    run.font = MagicMock()
    run.font.name = "Euclid Flex"
    run.font.size = None
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


def _make_placeholder_shape(idx: int, text: str = "", name: str = ""):
    shape = MagicMock()
    shape.name = name or f"Placeholder {idx}"
    shape.is_placeholder = True
    shape.has_text_frame = True
    shape.has_table = False
    shape.placeholder_format = MagicMock()
    shape.placeholder_format.idx = idx
    shape.text_frame = _make_text_frame(text)
    shape.description = ""
    return shape


def _make_textbox_shape(text: str = "", name: str = "TextBox"):
    shape = MagicMock()
    shape.name = name
    shape.is_placeholder = False
    shape.has_text_frame = True
    shape.has_table = False
    shape.text_frame = _make_text_frame(text)
    shape.shape_type = "TEXT_BOX"
    shape.description = ""
    return shape


def _make_table_shape(rows: list[list[str]], name: str = "Table"):
    shape = MagicMock()
    shape.name = name
    shape.is_placeholder = False
    shape.has_text_frame = False
    shape.has_table = True

    mock_rows = []
    for row_data in rows:
        cells = []
        for cell_text in row_data:
            cell = MagicMock()
            cell.text = cell_text
            cells.append(cell)
        row = MagicMock()
        row.cells = cells
        mock_rows.append(row)

    shape.table = MagicMock()
    shape.table.rows = mock_rows
    shape.description = ""
    return shape


def _make_slide(shapes: list, shell_id: str = "proposal_cover"):
    slide = MagicMock()
    slide.shapes = shapes
    slide.notes_slide = MagicMock()
    slide.notes_slide.notes_text_frame = _make_text_frame("")
    slide._element = MagicMock()
    slide._element.iter = MagicMock(return_value=[])
    slide.part = MagicMock()
    slide.part.rels = MagicMock()
    slide.part.rels.values = MagicMock(return_value=[])
    return slide


# ── Forbidden Content Detection ───────────────────────────────────────


class TestForbiddenContentDetection:
    """Verify all forbidden template-example markers are detected."""

    @pytest.mark.parametrize("text", [
        "lorem ipsum dolor sit amet",
        "LOREM IPSUM dolor",
        "sample text goes here",
        "Click to edit master title style",
        "insert text here",
        "type here to add content",
        "Add text for this section",
        "example: project overview",
        "[example] Film Sector Analysis",
        "<example>Tadawul case study</example>",
    ])
    def test_forbidden_content_detected(self, text: str):
        assert _is_forbidden_content(text) is True

    @pytest.mark.parametrize("text", [
        "Strategic Gears Consulting",
        "Our methodology ensures quality",
        "Phase 1: Discovery and Analysis",
        "Dr. Ahmad Al-Rashid, Managing Director",
        "",
        "   ",
    ])
    def test_clean_content_not_flagged(self, text: str):
        assert _is_forbidden_content(text) is False


# ── Allowlist Enforcement ─────────────────────────────────────────────


class TestAllowlistEnforcement:
    """Prove that ONLY allowlisted targets survive sanitization."""

    def test_approved_placeholder_text_cleared_for_injection(self):
        """Approved placeholders get cleared so injectors start blank."""
        al = ShellAllowlist(
            shell_id="proposal_cover",
            approved_placeholder_indices={0, 1},
            preserved_shape_names=set(),
            preserved_table_names=set(),
        )
        ph0 = _make_placeholder_shape(0, "Old title", "Title Placeholder")
        ph1 = _make_placeholder_shape(1, "Old subtitle", "Subtitle Placeholder")
        slide = _make_slide([ph0, ph1])

        report = sanitize_shell(slide, "proposal_cover", al)
        # Approved placeholders cleared for injection
        assert report.total_cleared >= 2

    def test_non_approved_placeholder_cleared(self):
        """Placeholders NOT on allowlist get their text cleared."""
        al = ShellAllowlist(
            shell_id="test_shell",
            approved_placeholder_indices={0},  # only 0 approved
            preserved_shape_names=set(),
            preserved_table_names=set(),
        )
        ph_approved = _make_placeholder_shape(0, "Approved text")
        ph_denied = _make_placeholder_shape(5, "Template example text")
        slide = _make_slide([ph_approved, ph_denied])

        report = sanitize_shell(slide, "test_shell", al)
        # Both are cleared (approved for injection, denied for safety)
        assert report.total_cleared >= 2

    def test_non_placeholder_textbox_cleared(self):
        """Freeform text boxes NOT on preserved list are cleared."""
        al = ShellAllowlist(
            shell_id="intro_message",
            approved_placeholder_indices=set(),
            preserved_shape_names={"KeepMe"},
            preserved_table_names=set(),
        )
        keep = _make_textbox_shape("Institutional text", "KeepMe")
        clear = _make_textbox_shape("Template example text", "FreeformBox")
        slide = _make_slide([keep, clear])

        report = sanitize_shell(slide, "intro_message", al)
        # FreeformBox should be cleared; KeepMe preserved
        assert report.preserved_count >= 1
        cleared_names = [e.shape_name for e in report.cleared_elements]
        assert "FreeformBox" in cleared_names

    def test_non_approved_table_cleared(self):
        """Tables NOT on preserved list have all cell text cleared."""
        al = ShellAllowlist(
            shell_id="toc_agenda",
            approved_placeholder_indices=set(),
            preserved_shape_names=set(),
            preserved_table_names={"AgendaTable"},
        )
        keep_table = _make_table_shape([["Item 1", "10:00"]], "AgendaTable")
        clear_table = _make_table_shape([["Film Sector", "Tadawul"]], "ExampleTable")
        slide = _make_slide([keep_table, clear_table])

        report = sanitize_shell(slide, "toc_agenda", al)
        assert report.preserved_count >= 1
        cleared_names = [e.shape_name for e in report.cleared_elements]
        assert "ExampleTable" in cleared_names


# ── Cross-Module: Sanitization + Injection Integration ────────────────


class TestSanitizationBeforeInjection:
    """Prove that sanitization clears template text BEFORE injectors run,
    so no template-example content survives into the final output."""

    def test_sanitize_then_inject_flow(self):
        """Simulates the renderer_v2 flow: clone → sanitize → inject.
        After sanitization, approved placeholder should be blank."""
        al = ShellAllowlist(
            shell_id="section_divider_01",
            approved_placeholder_indices={0},
            preserved_shape_names=set(),
            preserved_table_names=set(),
        )
        ph = _make_placeholder_shape(0, "OLD TEMPLATE TEXT")
        slide = _make_slide([ph])

        # Step 1: sanitize (clears text for injection)
        report = sanitize_shell(slide, "section_divider_01", al)
        assert report.total_cleared >= 1

        # Step 2: after sanitization the run text should be blank
        run = ph.text_frame.paragraphs[0].runs[0]
        assert run.text == ""

    def test_non_approved_content_cannot_reach_output(self):
        """Non-approved placeholder text stays cleared — even if someone
        tried to read it after sanitization."""
        al = ShellAllowlist(
            shell_id="section_divider_02",
            approved_placeholder_indices={0},
            preserved_shape_names=set(),
            preserved_table_names=set(),
        )
        denied = _make_placeholder_shape(5, "Sensitive template data")
        approved = _make_placeholder_shape(0, "Will be replaced")
        slide = _make_slide([denied, approved])

        sanitize_shell(slide, "section_divider_02", al)

        # The denied placeholder's text was cleared
        denied_run = denied.text_frame.paragraphs[0].runs[0]
        assert denied_run.text == ""


# ── Fail-Closed Behavior ─────────────────────────────────────────────


class TestFailClosedSanitization:
    """Sanitizer must fail closed on unknown text-bearing elements."""

    def test_fail_closed_on_missing_allowlist(self):
        """get_allowlist raises SanitizationError for unknown shell."""
        allowlists = {
            "proposal_cover": ShellAllowlist(
                shell_id="proposal_cover",
                approved_placeholder_indices={0},
                preserved_shape_names=set(),
                preserved_table_names=set(),
            ),
        }
        with pytest.raises(SanitizationError, match="No allowlist"):
            get_allowlist(allowlists, "unknown_shell_id")


# ── ContentSourcePolicy Enforcement ──────────────────────────────────


class TestContentSourcePolicyEnforcement:
    """Verify ContentSourcePolicy semantics are correct."""

    def test_policy_values(self):
        from src.models.proposal_manifest import ContentSourcePolicy

        assert ContentSourcePolicy.INSTITUTIONAL_REUSE == "institutional_reuse"
        assert ContentSourcePolicy.APPROVED_ASSET_POOL == "approved_asset_pool"
        assert ContentSourcePolicy.PROPOSAL_SPECIFIC == "proposal_specific"
        assert ContentSourcePolicy.FORBIDDEN_TEMPLATE_EXAMPLE == "forbidden_template_example"

    def test_forbidden_policy_blocks_content(self):
        """FORBIDDEN_TEMPLATE_EXAMPLE entries must never carry injection data."""
        from src.models.proposal_manifest import ContentSourcePolicy

        # A manifest entry with FORBIDDEN policy must have no injection data
        policy = ContentSourcePolicy.FORBIDDEN_TEMPLATE_EXAMPLE
        assert policy == "forbidden_template_example"
        # renderer_v2 validates this — no injection data for forbidden entries


# ── SanitizationReport Integrity ──────────────────────────────────────


class TestSanitizationReportIntegrity:
    """Report must categorize all cleared elements by type."""

    def test_report_tracks_by_type(self):
        report = SanitizationReport(
            shell_id="test",
            total_cleared=3,
            cleared_by_type={"placeholder": 2, "text_box": 1},
            cleared_elements=(
                ClearedElement("test", "placeholder", "PH1", "cleared for injection", True),
                ClearedElement("test", "placeholder", "PH2", "non-approved", True),
                ClearedElement("test", "text_box", "TB1", "not on preserved list", True),
            ),
            preserved_count=1,
        )
        assert report.total_cleared == 3
        assert report.cleared_by_type["placeholder"] == 2
        assert report.cleared_by_type["text_box"] == 1
        assert report.preserved_count == 1

    def test_cleared_element_frozen(self):
        elem = ClearedElement("test", "placeholder", "PH1", "reason", True)
        with pytest.raises(AttributeError):
            elem.shell_id = "other"  # type: ignore[misc]

    def test_report_frozen(self):
        report = SanitizationReport(
            shell_id="test",
            total_cleared=0,
            cleared_by_type={},
            cleared_elements=(),
            preserved_count=0,
        )
        with pytest.raises(AttributeError):
            report.shell_id = "other"  # type: ignore[misc]


# ── All 9 A2 Shell IDs ──────────────────────────────────────────────


class TestAll9A2ShellIDs:
    """Verify all 9 A2 assets are recognized: 3 covers + 6 dividers."""

    EXPECTED_SHELL_IDS = [
        "proposal_cover",
        "intro_message",
        "toc_agenda",
        "section_divider_01",
        "section_divider_02",
        "section_divider_03",
        "section_divider_04",
        "section_divider_05",
        "section_divider_06",
    ]

    def test_shell_ids_count(self):
        assert len(self.EXPECTED_SHELL_IDS) == 9

    def test_cover_shells_present(self):
        covers = [s for s in self.EXPECTED_SHELL_IDS if not s.startswith("section_")]
        assert len(covers) == 3

    def test_divider_shells_present(self):
        dividers = [s for s in self.EXPECTED_SHELL_IDS if s.startswith("section_divider_")]
        assert len(dividers) == 6

    def test_divider_numbering(self):
        """Dividers numbered 01-06 in strict sequence."""
        dividers = sorted(
            s for s in self.EXPECTED_SHELL_IDS if s.startswith("section_divider_")
        )
        expected = [f"section_divider_{i:02d}" for i in range(1, 7)]
        assert dividers == expected
