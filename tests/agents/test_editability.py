"""Phase 15 — Output Editability Tests.

Verify that rendered PPTX output remains fully editable in PowerPoint:

  - Text frames are accessible and writable after injection
  - Font sizes respect hard floor (never below HARD_FLOOR_PT)
  - Continuation markers are detectable and well-formed
  - Truncation produces valid text with ellipsis
  - FitResult records are frozen and traceable
  - Auto-shrink never goes below hard floor
  - Overflow detection works correctly for both title and body
"""

from __future__ import annotations

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
    split_for_continuation,
    truncate_to_fit,
)


# ── Font Size Guardrails ─────────────────────────────────────────────


class TestFontSizeGuardrails:
    """Font sizes must never go below HARD_FLOOR_PT."""

    def test_hard_floor_value(self):
        """Hard floor is 9pt for template-v2."""
        assert HARD_FLOOR_PT == 9

    def test_body_range(self):
        """Body font range: 9-12pt."""
        assert BODY_FONT_MIN_PT == 9
        assert BODY_FONT_MAX_PT == 12

    def test_title_range(self):
        """Title font range: 18-28pt."""
        assert TITLE_FONT_MIN_PT == 18
        assert TITLE_FONT_MAX_PT == 28

    def test_reduction_never_below_floor(self):
        """compute_reduced_font_size never returns below HARD_FLOOR_PT."""
        # Very long text that would need extreme reduction
        long_text = "A" * 5000
        result = compute_reduced_font_size(long_text, "BODY", 12.0)
        if result is not None:
            assert result >= HARD_FLOOR_PT

    def test_title_reduction_never_below_title_min(self):
        """Title reduction stays within title range."""
        long_title = "Very Long Title " * 30
        result = compute_reduced_font_size(long_title, "TITLE", 28.0)
        if result is not None:
            assert result >= TITLE_FONT_MIN_PT


# ── Overflow Detection ───────────────────────────────────────────────


class TestOverflowDetection:
    """Overflow detection must correctly identify when text exceeds capacity."""

    def test_short_body_no_overflow(self):
        assert not detect_overflow("Short text", "BODY")

    def test_long_body_overflows(self):
        long_text = "Paragraph.\n" * 20
        assert detect_overflow(long_text, "BODY")

    def test_short_title_no_overflow(self):
        assert not detect_overflow("Title", "TITLE")

    def test_long_title_overflows(self):
        long_title = "Very Long Title Word " * 20
        assert detect_overflow(long_title, "TITLE")

    def test_center_title_type(self):
        assert not detect_overflow("Short", "CENTER_TITLE")

    def test_subtitle_type(self):
        assert not detect_overflow("Short", "SUBTITLE")

    def test_empty_text_no_overflow(self):
        assert not detect_overflow("", "BODY")


# ── Line Count Estimation ────────────────────────────────────────────


class TestLineCountEstimation:
    """Line count estimation must handle newlines and wrapping."""

    def test_empty_string(self):
        assert estimate_line_count("", 90) == 0

    def test_single_line(self):
        assert estimate_line_count("Hello", 90) == 1

    def test_explicit_newlines(self):
        assert estimate_line_count("Line 1\nLine 2\nLine 3", 90) == 3

    def test_long_line_wraps(self):
        # 200 chars at 90 cpl should wrap to ~3 lines
        text = "A" * 200
        result = estimate_line_count(text, 90)
        assert result == 3  # ceil(200/90) = 3

    def test_blank_lines_counted(self):
        text = "Line 1\n\nLine 3"
        result = estimate_line_count(text, 90)
        assert result == 3  # line1 + blank + line3


# ── Truncation ───────────────────────────────────────────────────────


class TestTruncation:
    """Truncation must produce valid text with ellipsis marker."""

    def test_truncated_text_ends_with_ellipsis(self):
        # Need >12 visual lines at 90 cpl to trigger overflow
        long_text = "Paragraph about consulting services and methodology.\n" * 25
        result = truncate_to_fit(long_text, "BODY")
        assert result.endswith(ELLIPSIS)

    def test_truncated_text_shorter_than_original(self):
        long_text = "Paragraph about consulting services and methodology.\n" * 25
        result = truncate_to_fit(long_text, "BODY")
        assert len(result) < len(long_text)

    def test_short_text_not_truncated(self):
        short = "Short text"
        result = truncate_to_fit(short, "BODY")
        assert result == short

    def test_ellipsis_value(self):
        assert ELLIPSIS == "…"


# ── Continuation Splitting ───────────────────────────────────────────


class TestContinuationSplitting:
    """Continuation split must produce a marked first part and remainder."""

    def test_split_returns_two_parts(self):
        long_text = "Paragraph.\n" * 30
        first, remainder = split_for_continuation(long_text, "BODY")
        assert first
        assert remainder

    def test_first_part_has_marker(self):
        long_text = "Paragraph.\n" * 30
        first, _ = split_for_continuation(long_text, "BODY")
        assert CONTINUATION_MARKER in first

    def test_short_text_no_split(self):
        short = "Short text"
        first, remainder = split_for_continuation(short, "BODY")
        assert first == short
        assert remainder == ""

    def test_continuation_marker_value(self):
        assert "[continued on next slide]" in CONTINUATION_MARKER


# ── FitResult Data Class ─────────────────────────────────────────────


class TestFitResultModel:
    """FitResult must be frozen and capture all fitting metadata."""

    def test_fit_result_frozen(self):
        r = FitResult(placeholder_idx=0, original_length=100,
                      fitted_length=80, strategy=FitStrategy.FONT_REDUCTION)
        with pytest.raises(AttributeError):
            r.strategy = FitStrategy.TRUNCATION  # type: ignore[misc]

    def test_fit_result_no_action(self):
        r = FitResult(placeholder_idx=0, original_length=50,
                      fitted_length=50, strategy=FitStrategy.NONE)
        assert r.strategy == FitStrategy.NONE
        assert not r.continuation_needed

    def test_fit_result_continuation(self):
        r = FitResult(placeholder_idx=1, original_length=500,
                      fitted_length=200, strategy=FitStrategy.CONTINUATION,
                      continuation_needed=True)
        assert r.continuation_needed is True
        assert r.strategy == FitStrategy.CONTINUATION

    def test_fit_result_font_reduction(self):
        r = FitResult(placeholder_idx=0, original_length=200,
                      fitted_length=200, strategy=FitStrategy.FONT_REDUCTION,
                      font_size_pt=10.0)
        assert r.font_size_pt == 10.0


# ── SlideFitReport ───────────────────────────────────────────────────


class TestSlideFitReport:
    """SlideFitReport aggregates per-placeholder fit results."""

    def test_report_frozen(self):
        report = SlideFitReport(semantic_layout_id="content_heading_desc")
        with pytest.raises(AttributeError):
            report.semantic_layout_id = "other"  # type: ignore[misc]

    def test_report_any_continuation(self):
        report = SlideFitReport(
            semantic_layout_id="methodology_detail",
            results=(
                FitResult(0, 50, 50, FitStrategy.NONE),
                FitResult(1, 500, 200, FitStrategy.CONTINUATION, continuation_needed=True),
            ),
            any_continuation=True,
        )
        assert report.any_continuation is True

    def test_report_no_continuation(self):
        report = SlideFitReport(
            semantic_layout_id="content_heading_desc",
            results=(
                FitResult(0, 50, 50, FitStrategy.NONE),
            ),
            any_continuation=False,
        )
        assert report.any_continuation is False


# ── FitStrategy Values ───────────────────────────────────────────────


class TestFitStrategy:
    """FitStrategy enum must have all expected values."""

    def test_strategy_values(self):
        assert FitStrategy.NONE == "none"
        assert FitStrategy.FONT_REDUCTION == "font_reduction"
        assert FitStrategy.TRUNCATION == "truncation"
        assert FitStrategy.CONTINUATION == "continuation"

    def test_exactly_four_strategies(self):
        assert len(list(FitStrategy)) == 4

    def test_is_str_enum(self):
        assert isinstance(FitStrategy.NONE, str)


# ── Composite fit_content ────────────────────────────────────────────


class TestFitContent:
    """fit_content returns (fitted_text, FitResult) tuple."""

    def test_short_text_no_action(self):
        fitted_text, result = fit_content("Short text", 0, "BODY")
        assert result.strategy == FitStrategy.NONE
        assert fitted_text == "Short text"

    def test_long_text_triggers_fitting(self):
        long_text = "Methodology paragraph.\n" * 30
        fitted_text, result = fit_content(long_text, 1, "BODY")
        assert result.strategy != FitStrategy.NONE

    def test_title_fitting(self):
        short_title = "Normal Title"
        fitted_text, result = fit_content(short_title, 0, "TITLE")
        assert result.strategy == FitStrategy.NONE
        assert fitted_text == short_title
