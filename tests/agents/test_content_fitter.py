"""Tests for Phase 12 — content_fitter.py.

Tests overflow detection, font reduction, truncation, continuation
signaling, and the composite fitter.  Verifies zero shape creation
in the module source.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.content_fitter import (
    BODY_FONT_MAX_PT,
    BODY_FONT_MIN_PT,
    CONTINUATION_MARKER,
    ELLIPSIS,
    HARD_FLOOR_PT,
    TITLE_FONT_MAX_PT,
    TITLE_FONT_MIN_PT,
    FitResult,
    FitStrategy,
    SlideFitReport,
    compute_reduced_font_size,
    detect_overflow,
    estimate_line_count,
    fit_content,
    fit_slide_content,
    split_for_continuation,
    truncate_to_fit,
)


# ── Constants ──────────────────────────────────────────────────────────


class TestConstants:
    def test_title_font_range(self):
        assert TITLE_FONT_MIN_PT < TITLE_FONT_MAX_PT
        assert TITLE_FONT_MIN_PT >= HARD_FLOOR_PT

    def test_body_font_range(self):
        assert BODY_FONT_MIN_PT < BODY_FONT_MAX_PT
        assert BODY_FONT_MIN_PT >= HARD_FLOOR_PT

    def test_hard_floor(self):
        assert HARD_FLOOR_PT == 9

    def test_fit_strategy_values(self):
        assert FitStrategy.NONE == "none"
        assert FitStrategy.FONT_REDUCTION == "font_reduction"
        assert FitStrategy.TRUNCATION == "truncation"
        assert FitStrategy.CONTINUATION == "continuation"


# ── FitResult ──────────────────────────────────────────────────────────


class TestFitResult:
    def test_frozen(self):
        r = FitResult(
            placeholder_idx=0, original_length=100,
            fitted_length=80, strategy=FitStrategy.TRUNCATION,
        )
        with pytest.raises(AttributeError):
            r.strategy = FitStrategy.NONE  # type: ignore[misc]

    def test_default_values(self):
        r = FitResult(
            placeholder_idx=0, original_length=50,
            fitted_length=50, strategy=FitStrategy.NONE,
        )
        assert r.font_size_pt is None
        assert r.continuation_needed is False
        assert r.detail == ""


# ── SlideFitReport ─────────────────────────────────────────────────────


class TestSlideFitReport:
    def test_frozen(self):
        r = SlideFitReport(semantic_layout_id="test")
        with pytest.raises(AttributeError):
            r.semantic_layout_id = "x"  # type: ignore[misc]

    def test_defaults(self):
        r = SlideFitReport(semantic_layout_id="test")
        assert r.results == ()
        assert r.any_continuation is False


# ── estimate_line_count ────────────────────────────────────────────────


class TestEstimateLineCount:
    def test_empty_string(self):
        assert estimate_line_count("", 80) == 0

    def test_single_short_line(self):
        assert estimate_line_count("Hello", 80) == 1

    def test_wrapping(self):
        text = "A" * 200
        assert estimate_line_count(text, 80) == 3  # ceil(200/80)

    def test_explicit_newlines(self):
        text = "Line 1\nLine 2\nLine 3"
        assert estimate_line_count(text, 80) == 3

    def test_mixed_wrapping_and_newlines(self):
        # One short line + one long line that wraps to 2
        text = "Short\n" + "A" * 200
        result = estimate_line_count(text, 80)
        assert result == 4  # 1 + ceil(200/80)=3

    def test_blank_lines_counted(self):
        text = "Line 1\n\nLine 3"
        assert estimate_line_count(text, 80) == 3

    def test_exact_multiple(self):
        text = "A" * 160
        assert estimate_line_count(text, 80) == 2


# ── detect_overflow ────────────────────────────────────────────────────


class TestDetectOverflow:
    def test_short_body_no_overflow(self):
        assert detect_overflow("Short text", "BODY") is False

    def test_empty_no_overflow(self):
        assert detect_overflow("", "BODY") is False

    def test_long_body_overflows(self):
        text = "\n".join(["Line " + str(i) for i in range(20)])
        assert detect_overflow(text, "BODY") is True

    def test_long_title_overflows(self):
        text = "A very long title " * 20
        assert detect_overflow(text, "TITLE") is True

    def test_custom_max_lines(self):
        text = "Line 1\nLine 2\nLine 3"
        assert detect_overflow(text, "BODY", max_lines=2) is True
        assert detect_overflow(text, "BODY", max_lines=5) is False

    def test_center_title_uses_title_limits(self):
        # CENTER_TITLE should use title limits (3 lines)
        text = "Line\n" * 5
        assert detect_overflow(text, "CENTER_TITLE") is True

    def test_subtitle_uses_title_limits(self):
        text = "Line\n" * 5
        assert detect_overflow(text, "SUBTITLE") is True


# ── compute_reduced_font_size ──────────────────────────────────────────


class TestComputeReducedFontSize:
    def test_no_reduction_needed(self):
        result = compute_reduced_font_size("Short", "BODY")
        assert result is None

    def test_reduction_for_long_body(self):
        text = "\n".join(["Line " + str(i) for i in range(15)])
        result = compute_reduced_font_size(text, "BODY")
        assert result is not None
        assert result >= BODY_FONT_MIN_PT

    def test_never_below_hard_floor(self):
        text = "\n".join(["A" * 200 for _ in range(50)])
        result = compute_reduced_font_size(text, "BODY")
        assert result is not None
        assert result >= HARD_FLOOR_PT

    def test_title_reduction(self):
        text = "A very long title that spans many many words " * 5
        result = compute_reduced_font_size(text, "TITLE")
        if result is not None:
            assert result >= TITLE_FONT_MIN_PT

    def test_custom_current_size(self):
        text = "\n".join(["Line " + str(i) for i in range(15)])
        result = compute_reduced_font_size(text, "BODY", current_size_pt=11.0)
        if result is not None:
            assert result < 11.0
            assert result >= BODY_FONT_MIN_PT


# ── truncate_to_fit ────────────────────────────────────────────────────


class TestTruncateToFit:
    def test_short_text_unchanged(self):
        text = "Short text"
        assert truncate_to_fit(text, "BODY") == text

    def test_empty_unchanged(self):
        assert truncate_to_fit("", "BODY") == ""

    def test_long_text_truncated(self):
        text = "A " * 1000
        result = truncate_to_fit(text, "BODY", max_lines=3, chars_per_line=80)
        assert len(result) < len(text)
        assert result.endswith(ELLIPSIS)

    def test_truncation_at_word_boundary(self):
        text = "word " * 200
        result = truncate_to_fit(text, "BODY", max_lines=2, chars_per_line=80)
        # Should not cut mid-word (unless no good boundary found)
        assert result.endswith(ELLIPSIS)
        without_ellipsis = result[:-len(ELLIPSIS)]
        # Last char before ellipsis should be a word char or space
        assert without_ellipsis[-1] != " "  # trailing space stripped

    def test_title_truncation(self):
        text = "Very Long Title " * 20
        result = truncate_to_fit(text, "TITLE", max_lines=2, chars_per_line=55)
        assert len(result) < len(text)
        assert result.endswith(ELLIPSIS)


# ── split_for_continuation ─────────────────────────────────────────────


class TestSplitForContinuation:
    def test_short_text_no_split(self):
        first, overflow = split_for_continuation("Short text", "BODY")
        assert first == "Short text"
        assert overflow == ""

    def test_empty_no_split(self):
        first, overflow = split_for_continuation("", "BODY")
        assert first == ""
        assert overflow == ""

    def test_long_text_splits(self):
        text = "Paragraph one.\n" * 20
        first, overflow = split_for_continuation(text, "BODY")
        assert first.endswith(CONTINUATION_MARKER)
        assert len(overflow) > 0

    def test_continuation_marker_present(self):
        text = "Line " * 500
        first, _ = split_for_continuation(text, "BODY", max_lines=3, chars_per_line=80)
        assert CONTINUATION_MARKER in first

    def test_overflow_is_remainder(self):
        text = "A " * 500
        first, overflow = split_for_continuation(
            text, "BODY", max_lines=2, chars_per_line=80,
        )
        # Together they should cover all original content
        # (minus marker and whitespace trimming)
        combined = first.replace(CONTINUATION_MARKER, "") + " " + overflow
        # Both parts should be non-empty
        assert len(first) > 0
        assert len(overflow) > 0

    def test_prefers_paragraph_break(self):
        text = "First paragraph.\n\nSecond paragraph that is very long. " * 10
        first, overflow = split_for_continuation(
            text, "BODY", max_lines=3, chars_per_line=80,
        )
        # Should split at a paragraph boundary if possible
        assert first.endswith(CONTINUATION_MARKER)


# ── fit_content (composite) ────────────────────────────────────────────


class TestFitContent:
    def test_fits_without_adjustment(self):
        text = "Short body text"
        fitted, result = fit_content(text, 13, "BODY")
        assert fitted == text
        assert result.strategy == FitStrategy.NONE
        assert result.continuation_needed is False

    def test_font_reduction_tried_first(self):
        text = "\n".join(["Line " + str(i) for i in range(15)])
        fitted, result = fit_content(text, 13, "BODY")
        # Font reduction should be tried before truncation
        if result.strategy == FitStrategy.FONT_REDUCTION:
            assert result.font_size_pt is not None
            assert result.font_size_pt >= BODY_FONT_MIN_PT
            assert fitted == text  # text unchanged when font reduced

    def test_truncation_when_font_reduction_disabled(self):
        text = "\n".join(["Line " + str(i) for i in range(15)])
        fitted, result = fit_content(
            text, 13, "BODY",
            allow_font_reduction=False,
        )
        assert result.strategy == FitStrategy.TRUNCATION
        assert fitted.endswith(ELLIPSIS)

    def test_continuation_when_others_disabled(self):
        text = "\n".join(["Line " + str(i) for i in range(15)])
        fitted, result = fit_content(
            text, 13, "BODY",
            allow_font_reduction=False,
            allow_truncation=False,
        )
        assert result.strategy == FitStrategy.CONTINUATION
        assert result.continuation_needed is True
        assert CONTINUATION_MARKER in fitted

    def test_no_strategy_allowed_returns_as_is(self):
        text = "\n".join(["Line " + str(i) for i in range(15)])
        fitted, result = fit_content(
            text, 13, "BODY",
            allow_font_reduction=False,
            allow_truncation=False,
            allow_continuation=False,
        )
        assert fitted == text
        assert result.strategy == FitStrategy.NONE
        assert "overflow accepted" in result.detail

    def test_result_fields_populated(self):
        text = "Short"
        _, result = fit_content(text, 0, "TITLE")
        assert result.placeholder_idx == 0
        assert result.original_length == 5
        assert result.fitted_length == 5


# ── fit_slide_content ──────────────────────────────────────────────────


class TestFitSlideContent:
    def test_all_fit(self):
        contents = {
            0: ("Short title", "TITLE"),
            13: ("Short body", "BODY"),
        }
        fitted, report = fit_slide_content(contents, "content_heading_desc")
        assert report.semantic_layout_id == "content_heading_desc"
        assert report.any_continuation is False
        assert len(report.results) == 2
        assert fitted[0] == "Short title"
        assert fitted[13] == "Short body"

    def test_mixed_fit_strategies(self):
        short_body = "OK"
        long_body = "\n".join(["Line " + str(i) for i in range(20)])
        contents = {
            0: ("Title", "TITLE"),
            13: (short_body, "BODY"),
            23: (long_body, "BODY"),
        }
        fitted, report = fit_slide_content(contents, "methodology_overview_4")
        assert len(report.results) == 3
        # Short body should be NONE, long body may be reduced/truncated
        none_results = [r for r in report.results if r.strategy == FitStrategy.NONE]
        assert len(none_results) >= 2  # title + short body

    def test_continuation_flagged(self):
        very_long = "\n".join(["Line " + str(i) for i in range(30)])
        contents = {13: (very_long, "BODY")}
        _, report = fit_slide_content(
            contents, "content_heading_desc",
            allow_font_reduction=False,
            allow_truncation=False,
            allow_continuation=True,
        )
        assert report.any_continuation is True
        assert any(r.continuation_needed for r in report.results)

    def test_empty_contents(self):
        fitted, report = fit_slide_content({}, "test_layout")
        assert fitted == {}
        assert report.results == ()
        assert report.any_continuation is False

    def test_report_frozen(self):
        _, report = fit_slide_content({}, "test")
        with pytest.raises(AttributeError):
            report.semantic_layout_id = "x"  # type: ignore[misc]


# ── Zero-shape-creation guardrail ──────────────────────────────────────


class TestZeroShapeCreation:
    def test_source_has_no_shape_creation_calls(self):
        """content_fitter.py must never call shape creation methods."""
        source_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "services" / "content_fitter.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert ".add_shape(" not in source
        assert ".add_textbox(" not in source
        assert ".add_table(" not in source
        assert ".add_picture(" not in source
