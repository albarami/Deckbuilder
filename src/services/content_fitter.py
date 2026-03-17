"""Phase 12 — Content Fitter.

Overflow handling for placeholder text.  Detects when injected content
exceeds the available space in a placeholder, then applies progressive
fitting strategies:

  1. Auto-shrink: reduce font size within an allowed range
  2. Truncation: trim excess text with an ellipsis marker
  3. Continuation: signal that content overflows and needs a follow-on slide

No shape creation.  All fitting operates on existing placeholders only.
This module is in the renderer_v2 code path — zero ``add_shape`` /
``add_textbox`` calls permitted.

Font-size guardrails (Euclid Flex, template-v2):
  - Title placeholders: 18–28 pt  (min–max)
  - Body placeholders:   9–12 pt  (min–max)
  - Minimum readable:    9 pt (hard floor — never shrink below)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────


class FitStrategy(StrEnum):
    """Strategy applied to fit content into a placeholder."""

    NONE = "none"                    # content fits as-is
    FONT_REDUCTION = "font_reduction"
    TRUNCATION = "truncation"
    CONTINUATION = "continuation"    # overflow → needs follow-on slide


# Font-size guardrails (points).  Defined per placeholder role.
TITLE_FONT_MAX_PT = 28
TITLE_FONT_MIN_PT = 18
BODY_FONT_MAX_PT = 12
BODY_FONT_MIN_PT = 9
HARD_FLOOR_PT = 9

# Characters-per-line estimates (Euclid Flex at body size on 8.5" content).
# Used for heuristic overflow detection when actual extents are unavailable.
_CHARS_PER_LINE_BODY = 90
_CHARS_PER_LINE_TITLE = 55

# Maximum lines per placeholder type before overflow is flagged.
_MAX_LINES_TITLE = 3
_MAX_LINES_BODY = 12

# Truncation suffix
ELLIPSIS = "…"

# Continuation marker appended when content overflows to a follow-on slide.
CONTINUATION_MARKER = " [continued on next slide]"


# ── Data classes ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class FitResult:
    """Result of fitting content into a single placeholder."""

    placeholder_idx: int
    original_length: int
    fitted_length: int
    strategy: FitStrategy
    font_size_pt: float | None = None   # final font size after reduction
    continuation_needed: bool = False    # True if content overflows
    detail: str = ""


@dataclass(frozen=True)
class SlideFitReport:
    """Aggregated fit results for one slide."""

    semantic_layout_id: str
    results: tuple[FitResult, ...] = ()
    any_continuation: bool = False


# ── Overflow detection ─────────────────────────────────────────────────


def estimate_line_count(text: str, chars_per_line: int) -> int:
    """Estimate how many visual lines *text* will occupy.

    Counts explicit newlines and wraps long logical lines.
    """
    if not text:
        return 0

    total = 0
    for line in text.split("\n"):
        line_len = len(line)
        if line_len == 0:
            total += 1  # blank line
        else:
            total += max(1, -(-line_len // chars_per_line))  # ceil division
    return total


def detect_overflow(
    text: str,
    placeholder_type: str,
    *,
    max_lines: int | None = None,
    chars_per_line: int | None = None,
) -> bool:
    """Return True if *text* is estimated to overflow the placeholder."""
    if not text:
        return False

    is_title = placeholder_type in ("TITLE", "CENTER_TITLE", "SUBTITLE")
    cpl = chars_per_line or (_CHARS_PER_LINE_TITLE if is_title else _CHARS_PER_LINE_BODY)
    ml = max_lines or (_MAX_LINES_TITLE if is_title else _MAX_LINES_BODY)

    return estimate_line_count(text, cpl) > ml


# ── Font reduction ─────────────────────────────────────────────────────


def compute_reduced_font_size(
    text: str,
    placeholder_type: str,
    current_size_pt: float | None = None,
    *,
    max_lines: int | None = None,
    chars_per_line: int | None = None,
) -> float | None:
    """Compute the smallest acceptable font size that fits *text*.

    Returns the reduced size in points, or ``None`` if the content fits
    at the current size (no reduction needed).  Never returns below
    ``HARD_FLOOR_PT``.

    The heuristic: each 1-pt reduction adds ~8 chars/line capacity
    (approximation for Euclid Flex proportional widths).
    """
    is_title = placeholder_type in ("TITLE", "CENTER_TITLE", "SUBTITLE")
    cpl = chars_per_line or (_CHARS_PER_LINE_TITLE if is_title else _CHARS_PER_LINE_BODY)
    ml = max_lines or (_MAX_LINES_TITLE if is_title else _MAX_LINES_BODY)
    max_pt = current_size_pt or (TITLE_FONT_MAX_PT if is_title else BODY_FONT_MAX_PT)
    min_pt = TITLE_FONT_MIN_PT if is_title else BODY_FONT_MIN_PT

    lines = estimate_line_count(text, cpl)
    if lines <= ml:
        return None  # fits already

    # Progressively increase chars_per_line by shrinking font
    candidate_pt = max_pt
    chars_per_pt_gain = 8  # approx extra chars per line per pt reduction
    while candidate_pt > min_pt:
        candidate_pt -= 0.5
        adjusted_cpl = cpl + int((max_pt - candidate_pt) * chars_per_pt_gain)
        lines = estimate_line_count(text, adjusted_cpl)
        if lines <= ml:
            return max(candidate_pt, HARD_FLOOR_PT)

    return max(min_pt, HARD_FLOOR_PT)


# ── Truncation ─────────────────────────────────────────────────────────


def truncate_to_fit(
    text: str,
    placeholder_type: str,
    *,
    max_lines: int | None = None,
    chars_per_line: int | None = None,
) -> str:
    """Truncate *text* to approximately fit within the placeholder.

    Adds an ellipsis at the truncation point.  Uses line-aware splitting
    to handle text with many newlines correctly.
    """
    if not text:
        return text

    is_title = placeholder_type in ("TITLE", "CENTER_TITLE", "SUBTITLE")
    cpl = chars_per_line or (_CHARS_PER_LINE_TITLE if is_title else _CHARS_PER_LINE_BODY)
    ml = max_lines or (_MAX_LINES_TITLE if is_title else _MAX_LINES_BODY)

    if not detect_overflow(text, placeholder_type, max_lines=ml, chars_per_line=cpl):
        return text

    # Line-aware truncation: keep logical lines until visual line count
    # reaches the limit.
    logical_lines = text.split("\n")
    kept: list[str] = []
    visual_count = 0

    for line in logical_lines:
        line_visual = max(1, -(-len(line) // cpl)) if line else 1
        if visual_count + line_visual > ml:
            # Partial keep of this line if it wraps
            remaining_visual = ml - visual_count
            if remaining_visual > 0 and len(line) > 0:
                keep_chars = remaining_visual * cpl
                partial = line[:keep_chars]
                last_space = partial.rfind(" ")
                if last_space > keep_chars // 2:
                    partial = partial[:last_space]
                kept.append(partial)
            break
        kept.append(line)
        visual_count += line_visual

    result = "\n".join(kept).rstrip()
    if len(result) < len(text):
        result += ELLIPSIS
    return result


# ── Continuation signaling ─────────────────────────────────────────────


def split_for_continuation(
    text: str,
    placeholder_type: str,
    *,
    max_lines: int | None = None,
    chars_per_line: int | None = None,
) -> tuple[str, str]:
    """Split *text* into a first-slide portion and a continuation portion.

    The first portion fits the placeholder and ends with a continuation
    marker.  The second portion is the overflow text for a follow-on slide.

    Returns (first_part, overflow_part).  If no split is needed, returns
    (text, "").
    """
    if not text:
        return (text, "")

    is_title = placeholder_type in ("TITLE", "CENTER_TITLE", "SUBTITLE")
    cpl = chars_per_line or (_CHARS_PER_LINE_TITLE if is_title else _CHARS_PER_LINE_BODY)
    ml = max_lines or (_MAX_LINES_TITLE if is_title else _MAX_LINES_BODY)

    if not detect_overflow(text, placeholder_type, max_lines=ml, chars_per_line=cpl):
        return (text, "")

    # Line-aware split: keep logical lines until we've used (ml - 1)
    # visual lines, reserving the last line for the continuation marker.
    reserve_lines = max(1, ml - 1)
    logical_lines = text.split("\n")
    kept: list[str] = []
    visual_count = 0

    for i, line in enumerate(logical_lines):
        line_visual = max(1, -(-len(line) // cpl)) if line else 1
        if visual_count + line_visual > reserve_lines:
            # Partial keep if this line is long
            remaining_visual = reserve_lines - visual_count
            if remaining_visual > 0 and len(line) > 0:
                keep_chars = remaining_visual * cpl
                partial = line[:keep_chars]
                last_space = partial.rfind(" ")
                if last_space > keep_chars // 2:
                    partial = partial[:last_space]
                kept.append(partial)
            break
        kept.append(line)
        visual_count += line_visual

    first_part = "\n".join(kept).rstrip() + CONTINUATION_MARKER

    # Everything after the kept portion is overflow
    kept_text_len = len("\n".join(kept))
    overflow = text[kept_text_len:].lstrip("\n").lstrip()

    return (first_part, overflow)


# ── Composite fitter ──────────────────────────────────────────────────


def fit_content(
    text: str,
    placeholder_idx: int,
    placeholder_type: str,
    *,
    current_font_pt: float | None = None,
    allow_font_reduction: bool = True,
    allow_truncation: bool = True,
    allow_continuation: bool = True,
    max_lines: int | None = None,
    chars_per_line: int | None = None,
) -> tuple[str, FitResult]:
    """Apply the best fitting strategy to *text* for a placeholder.

    Strategy priority:
      1. No action needed (content fits).
      2. Font reduction (if allowed and sufficient).
      3. Truncation (if allowed).
      4. Continuation signaling (if allowed) — returns first portion only,
         caller must handle the overflow via a follow-on slide.

    Returns (fitted_text, FitResult).
    """
    original_len = len(text) if text else 0

    # 1. Check if it fits already
    if not detect_overflow(text, placeholder_type, max_lines=max_lines,
                           chars_per_line=chars_per_line):
        return (text, FitResult(
            placeholder_idx=placeholder_idx,
            original_length=original_len,
            fitted_length=original_len,
            strategy=FitStrategy.NONE,
            detail="content fits without adjustment",
        ))

    # 2. Try font reduction
    if allow_font_reduction:
        reduced_pt = compute_reduced_font_size(
            text, placeholder_type, current_font_pt,
            max_lines=max_lines, chars_per_line=chars_per_line,
        )
        if reduced_pt is not None:
            # Re-check overflow at reduced font size
            is_title = placeholder_type in ("TITLE", "CENTER_TITLE", "SUBTITLE")
            base_cpl = chars_per_line or (
                _CHARS_PER_LINE_TITLE if is_title else _CHARS_PER_LINE_BODY
            )
            max_pt = current_font_pt or (
                TITLE_FONT_MAX_PT if is_title else BODY_FONT_MAX_PT
            )
            adjusted_cpl = base_cpl + int((max_pt - reduced_pt) * 8)
            ml = max_lines or (_MAX_LINES_TITLE if is_title else _MAX_LINES_BODY)
            if estimate_line_count(text, adjusted_cpl) <= ml:
                return (text, FitResult(
                    placeholder_idx=placeholder_idx,
                    original_length=original_len,
                    fitted_length=original_len,
                    strategy=FitStrategy.FONT_REDUCTION,
                    font_size_pt=reduced_pt,
                    detail=f"font reduced to {reduced_pt}pt",
                ))

    # 3. Try truncation
    if allow_truncation:
        truncated = truncate_to_fit(
            text, placeholder_type,
            max_lines=max_lines, chars_per_line=chars_per_line,
        )
        return (truncated, FitResult(
            placeholder_idx=placeholder_idx,
            original_length=original_len,
            fitted_length=len(truncated),
            strategy=FitStrategy.TRUNCATION,
            detail=f"truncated from {original_len} to {len(truncated)} chars",
        ))

    # 4. Continuation
    if allow_continuation:
        first_part, overflow = split_for_continuation(
            text, placeholder_type,
            max_lines=max_lines, chars_per_line=chars_per_line,
        )
        return (first_part, FitResult(
            placeholder_idx=placeholder_idx,
            original_length=original_len,
            fitted_length=len(first_part),
            strategy=FitStrategy.CONTINUATION,
            continuation_needed=True,
            detail=f"split: {len(first_part)} chars on slide, {len(overflow)} overflow",
        ))

    # 5. Fallback: return as-is (overflow accepted)
    return (text, FitResult(
        placeholder_idx=placeholder_idx,
        original_length=original_len,
        fitted_length=original_len,
        strategy=FitStrategy.NONE,
        detail="overflow accepted (no fitting strategy allowed)",
    ))


def fit_slide_content(
    contents: dict[int, tuple[str, str]],
    semantic_layout_id: str,
    *,
    allow_font_reduction: bool = True,
    allow_truncation: bool = True,
    allow_continuation: bool = True,
) -> tuple[dict[int, str], SlideFitReport]:
    """Fit all placeholder contents for a single slide.

    Parameters
    ----------
    contents : dict[int, tuple[str, str]]
        Mapping of placeholder_idx -> (text, placeholder_type).
    semantic_layout_id : str
        Semantic layout ID for reporting.

    Returns
    -------
    (fitted_contents, report)
        fitted_contents maps idx -> fitted text string.
    """
    fitted: dict[int, str] = {}
    results: list[FitResult] = []
    any_cont = False

    for idx, (text, ph_type) in contents.items():
        fitted_text, result = fit_content(
            text, idx, ph_type,
            allow_font_reduction=allow_font_reduction,
            allow_truncation=allow_truncation,
            allow_continuation=allow_continuation,
        )
        fitted[idx] = fitted_text
        results.append(result)
        if result.continuation_needed:
            any_cont = True

    return (fitted, SlideFitReport(
        semantic_layout_id=semantic_layout_id,
        results=tuple(results),
        any_continuation=any_cont,
    ))
