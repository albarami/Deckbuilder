"""Density Scorer — deterministic, no LLM.

Evaluates every slide against archetype-specific content budgets.
Produces advisory split/compression suggestions.
Never mutates SlideObjects — validate-only.

Visible-text only: title + body text counted.
Speaker notes are EXCLUDED from all char/bullet counts.
"""

from __future__ import annotations

import re

from src.models.enums import DensityBudget, DensityViolationSeverity, LayoutType
from src.models.slides import SlideObject
from src.models.submission import (
    CompressionSuggestion,
    DensityResult,
    DensityViolation,
    SlideBrief,
    SlideDensityScore,
    SplitSuggestion,
)
from src.services.design_tokens import _ArchetypeBudget, get_archetype_budget
from src.services.formatting import is_pipe_table

_NO_SPLIT_LAYOUTS: frozenset[LayoutType] = frozenset({
    LayoutType.TITLE,
    LayoutType.AGENDA,
    LayoutType.SECTION,
    LayoutType.CLOSING,
    LayoutType.STAT_CALLOUT,
    LayoutType.DATA_CHART,
})

_NUMERIC_TOKEN_RE = re.compile(r"\d[\d,.%]*")
_ALL_CAPS_RE = re.compile(r"\b[A-Z]{2,}\b")
_REF_TAG_RE = re.compile(r"\[Ref:[^\]]*\]")
_QUOTED_STRING_RE = re.compile(r'"[^"]*"|\'[^\']*\'')
_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")
_TRAILING_EMDASH_RE = re.compile(r"\s+\u2014\s+.*$")


def _compress_bullet(text: str, max_chars: int) -> str | None:
    """Attempt deterministic compression of a single bullet.

    Returns compressed text, or None if no safe compression is possible.
    Only called when bullet is between 100-125% of limit.
    """
    if "|" in text:
        return None

    original_refs = set(_REF_TAG_RE.findall(text))

    def _refs_preserved(candidate: str) -> bool:
        return original_refs <= set(_REF_TAG_RE.findall(candidate))

    # Try removing trailing parenthetical
    m = _TRAILING_PAREN_RE.search(text)
    if m and not _REF_TAG_RE.search(m.group()):
        candidate = text[:m.start()].rstrip()
        if len(candidate) <= max_chars and _refs_preserved(candidate):
            return candidate

    # Try removing trailing em-dash clause
    m = _TRAILING_EMDASH_RE.search(text)
    if m and not _REF_TAG_RE.search(m.group()):
        candidate = text[:m.start()].rstrip()
        if len(candidate) <= max_chars and _refs_preserved(candidate):
            return candidate

    # Try truncation with ellipsis
    if len(text) > max_chars:
        candidate = text[:max_chars - 3] + "..."
        if _refs_preserved(candidate):
            # Check quoted strings are preserved
            quotes_in_original = _QUOTED_STRING_RE.findall(text)
            quotes_in_candidate = _QUOTED_STRING_RE.findall(candidate)
            if len(quotes_in_candidate) == len(quotes_in_original):
                # Check numeric tokens preserved
                orig_nums = _NUMERIC_TOKEN_RE.findall(text)
                cand_nums = _NUMERIC_TOKEN_RE.findall(candidate)
                if len(orig_nums) != 1 or orig_nums[0] in cand_nums:
                    # Check all-caps terms preserved
                    orig_caps = set(_ALL_CAPS_RE.findall(text))
                    cand_caps = set(_ALL_CAPS_RE.findall(candidate))
                    if orig_caps <= cand_caps:
                        return candidate

    return None


def _suggest_split(
    slide: SlideObject,
    budget: _ArchetypeBudget,
    total_chars: int,
    elements: list[str],
) -> SplitSuggestion | None:
    """Generate a split suggestion if slide is >130% of char budget.

    Returns None for no-split layouts or when only pipe rows exist.
    """
    if slide.layout_type in _NO_SPLIT_LAYOUTS:
        return None

    if total_chars <= int(budget.max_chars_per_slide * 1.3):
        return None

    # Filter to regular (non-pipe) bullets
    if is_pipe_table(elements):
        regular_bullets = [e for e in elements if "|" not in e]
    else:
        regular_bullets = list(elements)

    if not regular_bullets:
        return None

    # Find split point at ~50% of total regular chars
    cumulative = 0
    total_regular_chars = sum(len(b) for b in regular_bullets)
    half = total_regular_chars / 2
    split_idx = 0

    for i, bullet in enumerate(regular_bullets):
        cumulative += len(bullet)
        if cumulative >= half:
            split_idx = i
            break

    chars_a = sum(len(b) for b in regular_bullets[:split_idx + 1])
    chars_b = sum(len(b) for b in regular_bullets[split_idx + 1:])

    return SplitSuggestion(
        source_slide_id=slide.slide_id,
        reason=f"Slide at {total_chars} chars exceeds 130% of {budget.max_chars_per_slide} budget",
        suggested_split_point=split_idx,
        estimated_slide_a_chars=chars_a,
        estimated_slide_b_chars=chars_b,
    )


def score_slide(
    slide: SlideObject,
    density_budget: DensityBudget | None = None,
) -> SlideDensityScore:
    """Score a single slide against its archetype budget.

    Visible-text only: title + body text_elements.
    Speaker notes are EXCLUDED.
    """
    budget = get_archetype_budget(slide.layout_type, density_budget)

    elements = slide.body_content.text_elements if slide.body_content else []

    # Count characters
    title_chars = len(slide.title) if slide.title else 0
    element_chars = sum(len(e) for e in elements)
    total_chars = title_chars + element_chars

    # Utilization percentage
    utilization = (total_chars / budget.max_chars_per_slide * 100) if budget.max_chars_per_slide else 0.0

    # Determine table mode
    table_mode = is_pipe_table(elements) if elements else False

    if table_mode:
        pipe_rows = [e for e in elements if "|" in e]
        regular_bullets = [e for e in elements if "|" not in e]
    else:
        pipe_rows = []
        regular_bullets = list(elements)

    # Counts
    bullet_count = len(regular_bullets)
    max_bullet_chars = max((len(b) for b in regular_bullets), default=0)
    table_row_count = len(pipe_rows)

    violations: list[DensityViolation] = []

    # Check bullet count
    if regular_bullets and bullet_count > budget.max_bullets:
        ratio = bullet_count / budget.max_bullets
        if ratio > 1.5:
            severity = DensityViolationSeverity.BLOCKER
        else:
            severity = DensityViolationSeverity.WARNING
        violations.append(DensityViolation(
            field="bullet_count",
            actual=bullet_count,
            limit=budget.max_bullets,
            severity=severity,
            message=f"{bullet_count} bullets exceed limit of {budget.max_bullets}",
        ))

    # Check per-bullet char limits
    for i, bullet in enumerate(regular_bullets):
        blen = len(bullet)
        if blen > budget.max_chars_per_bullet:
            ratio = blen / budget.max_chars_per_bullet
            if ratio > 1.25:
                severity = DensityViolationSeverity.BLOCKER
            else:
                severity = DensityViolationSeverity.WARNING
            violations.append(DensityViolation(
                field=f"chars_per_bullet:{i}",
                actual=blen,
                limit=budget.max_chars_per_bullet,
                severity=severity,
                message=f"Bullet {i} has {blen} chars, limit {budget.max_chars_per_bullet}",
            ))

    # Check total chars per slide
    if total_chars > budget.max_chars_per_slide:
        ratio = total_chars / budget.max_chars_per_slide
        if ratio > 1.3:
            severity = DensityViolationSeverity.BLOCKER
        else:
            severity = DensityViolationSeverity.WARNING
        violations.append(DensityViolation(
            field="chars_per_slide",
            actual=total_chars,
            limit=budget.max_chars_per_slide,
            severity=severity,
            message=f"{total_chars} chars exceed slide limit of {budget.max_chars_per_slide}",
        ))

    # Check table rows
    if table_mode and table_row_count > budget.max_table_rows:
        violations.append(DensityViolation(
            field="table_rows",
            actual=table_row_count,
            limit=budget.max_table_rows,
            severity=DensityViolationSeverity.BLOCKER,
            message=f"{table_row_count} table rows exceed limit of {budget.max_table_rows}",
        ))

    # Try deterministic compression for bullets between 100-125% of limit
    compression_suggestions: list[CompressionSuggestion] = []
    for i, bullet in enumerate(regular_bullets):
        blen = len(bullet)
        if not (budget.max_chars_per_bullet < blen <= int(budget.max_chars_per_bullet * 1.25)):
            continue
        compressed = _compress_bullet(bullet, budget.max_chars_per_bullet)
        if compressed is None:
            continue
        compression_suggestions.append(CompressionSuggestion(
            slide_id=slide.slide_id,
            bullet_index=i,
            original_text=bullet,
            compressed_text=compressed,
            chars_saved=blen - len(compressed),
            rule_applied="deterministic_compression",
        ))

    # Generate split suggestion if needed
    split_suggestion = _suggest_split(slide, budget, total_chars, elements)

    # Determine if slide passes
    has_blocker = any(
        v.severity == DensityViolationSeverity.BLOCKER for v in violations
    )

    return SlideDensityScore(
        slide_id=slide.slide_id,
        layout_type=slide.layout_type,
        density_budget=density_budget or DensityBudget.STANDARD,
        bullet_count=bullet_count,
        total_chars=total_chars,
        max_bullet_chars=max_bullet_chars,
        budget_utilization_pct=round(utilization, 1),
        violations=violations,
        split_suggestion=split_suggestion,
        compression_suggestions=compression_suggestions,
        passes=not has_blocker,
    )


def score_deck(
    slides: list[SlideObject],
    briefs: list[SlideBrief] | None = None,
) -> DensityResult:
    """Score all slides in a deck against their archetype budgets.

    When briefs are provided, each slide's density_budget comes from its
    matching brief. When no brief matches, defaults to STANDARD.
    """
    if not slides:
        return DensityResult(summary="No slides to score")

    # Build brief lookup map
    brief_map: dict = {}
    if briefs:
        for b in briefs:
            brief_map[b.slide_id] = b

    slide_scores: list[SlideDensityScore] = []
    total_violations = 0
    blocker_count = 0
    warning_count = 0
    slides_over_budget = 0
    split_count = 0

    for slide in slides:
        brief = brief_map.get(slide.slide_id)
        density = brief.density_budget if brief else None

        sc = score_slide(slide, density_budget=density)
        slide_scores.append(sc)

        total_violations += len(sc.violations)
        blocker_count += sum(
            1 for v in sc.violations
            if v.severity == DensityViolationSeverity.BLOCKER
        )
        warning_count += sum(
            1 for v in sc.violations
            if v.severity == DensityViolationSeverity.WARNING
        )

        if not sc.passes:
            slides_over_budget += 1
        if sc.split_suggestion:
            split_count += 1

    is_within = blocker_count == 0

    summary = (
        f"{len(slides)} slides scored: "
        f"{blocker_count} blockers, {warning_count} warnings, "
        f"{slides_over_budget} over budget, "
        f"{split_count} split suggestions"
    )

    return DensityResult(
        slide_scores=slide_scores,
        total_violations=total_violations,
        blocker_count=blocker_count,
        warning_count=warning_count,
        slides_over_budget=slides_over_budget,
        split_suggestions_count=split_count,
        is_within_budget=is_within,
        summary=summary,
    )
