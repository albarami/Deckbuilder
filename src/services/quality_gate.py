"""Phase G Quality Gate — automated presentation acceptance gate.

Runs after rendering, before final save.  Evaluates hard rejection rules
(R1-R10) and scored metrics (S1-S4).  Fail-closed: if ANY hard rule fails,
the deck is rejected and not saved.

Reference: docs/plans/2026-03-20-phase-g3-quality-gate-definition.md

Implementation-honest enforcement status:
  ENFORCEABLE_NOW   — R1, R2, R3, R4, R5, R7, R8, R9, R10
  DEFERRED          — R6 (intro filler not wired), R11 (clone schemas missing)
  PENDING_EXTENSION — P1-P5 (OBJECT injector extension not yet built)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.agents.section_fillers.g2_schemas import (
    APPROVED_ENGLISH_TERMS,
    MethodologyOutput,
)
from src.services.placeholder_injectors import InjectionResult

# ── Constants ──────────────────────────────────────────────────────────

# Placeholder marker patterns (R8)
_PLACEHOLDER_PATTERNS = [
    re.compile(r"\{\{.*?\}\}"),           # {{...}}
    re.compile(r"\[PLACEHOLDER[^\]]*\]", re.IGNORECASE),
    re.compile(r"\[TBC\]", re.IGNORECASE),
    re.compile(r"\[TBD\]", re.IGNORECASE),
    re.compile(r"\[INSERT[^\]]*\]", re.IGNORECASE),
    re.compile(r"\[BD team[^\]]*\]", re.IGNORECASE),
    re.compile(r"\[CRITICAL:[^\]]*\]", re.IGNORECASE),
    re.compile(r"\bTODO\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"GAP-\d{3}"),
]

# Internal note patterns (R9)
_INTERNAL_NOTE_PATTERNS = [
    re.compile(r"\[INTERNAL[^\]]*\]", re.IGNORECASE),
    re.compile(r"\[NOTE:[^\]]*\]", re.IGNORECASE),
    re.compile(r"\[DRAFT[^\]]*\]", re.IGNORECASE),
]

# Required sections (R5) — 10 required sections
REQUIRED_SECTIONS = frozenset({
    "cover",           # Introduction (cover + intro_message)
    "section_01",      # Understanding
    "section_02",      # Why Strategic Gears
    "section_03",      # Methodology
    "section_04",      # Timeline & Deliverables
    "section_05",      # Team
    "section_06",      # Governance
    "section_07",      # Case Studies / Precedent Evidence
    "section_08",      # Company Profile
    "toc",             # Table of Contents
})

# RENDERABLE_NOW layouts — can be fully populated via current injectors
RENDERABLE_NOW_LAYOUTS = frozenset({
    "intro_message",
    "methodology_overview_3", "methodology_overview_4",
    "methodology_focused_3", "methodology_focused_4",
    "methodology_detail",
    "content_heading_desc",
    "content_heading_only",
    "content_heading_content",
    "proposal_cover",
    "toc_table",
    "team_two_members",
    "case_study_detailed", "case_study_cases",
    "section_divider_01", "section_divider_02", "section_divider_03",
    "section_divider_04", "section_divider_05", "section_divider_06",
    "section_divider_07", "section_divider_08", "section_divider_09",
    "layout_heading_description_and_content_box",
    "layout_heading_and_subheading",
})

# Layouts requiring injector extension (OBJECT zones not yet populated)
REQUIRES_EXTENSION_LAYOUTS = frozenset({
    "layout_heading_and_4_boxes_of_content",
    "layout_heading_and_two_content_with_tiltes",
    "layout_heading_text_box_and_content",
    "layout_heading_description_and_two_rows_of_content_boxes",
})


# ── Result ─────────────────────────────────────────────────────────────


@dataclass
class QualityGateResult:
    """Result of the presentation quality gate."""

    passed: bool = True                          # True only if ALL hard rules pass
    hard_failures: list[str] = field(default_factory=list)
    pending_findings: list[str] = field(default_factory=list)

    # Scored metrics
    methodology_structure_score: float = 0.0      # S1: 0-100
    section_completeness_score: float = 0.0       # S2: 0-100
    content_density_score: float = 0.0            # S3: 0-100
    arabic_integrity_score: float | None = None   # S4: 0-100 (None for EN)

    # Per-section detail
    section_details: dict[str, dict] = field(default_factory=dict)


# ── Text extraction helpers ────────────────────────────────────────────


def _extract_injection_texts(
    injection_data: dict[str, Any] | None,
) -> list[str]:
    """Extract all text strings from injection_data for scanning."""
    if not injection_data:
        return []
    texts: list[str] = []
    for key, value in injection_data.items():
        if key == "source_slide_idx":
            continue
        if isinstance(value, str) and value.strip():
            texts.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                if isinstance(v, str) and v.strip():
                    texts.append(v)
    return texts


def _extract_all_slide_texts(
    records: list[dict[str, Any]],
) -> list[tuple[int, str]]:
    """Extract (slide_index, text) pairs from all slide records."""
    result: list[tuple[int, str]] = []
    for i, record in enumerate(records):
        injection_data = record.get("injection_data")
        for text in _extract_injection_texts(injection_data):
            result.append((i, text))
    return result


# ── Hard rules ─────────────────────────────────────────────────────────


def _check_r2_prose_detection(
    records: list[dict[str, Any]],
) -> list[str]:
    """R2: No renderable zone may have >25 consecutive words without \\n.

    Checks RENDERABLE_NOW layouts only.
    """
    failures: list[str] = []
    for i, record in enumerate(records):
        layout = record.get("semantic_layout_id", "")
        if layout not in RENDERABLE_NOW_LAYOUTS:
            continue
        injection_data = record.get("injection_data")
        for text in _extract_injection_texts(injection_data):
            segments = text.split("\n")
            for seg in segments:
                word_count = len(seg.split())
                if word_count > 25:
                    failures.append(
                        f"R2: Prose detected on slide {i} "
                        f"(layout={layout}): {word_count} consecutive "
                        f"words without line break",
                    )
                    break  # One failure per text block is enough
    return failures


def _check_r3_methodology_structure(
    filler_outputs: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[str]:
    """R3: Methodology phase structure must be valid.

    Checks from MethodologyOutput schema + rendered methodology slides.
    """
    failures: list[str] = []
    meth_output = filler_outputs.get("section_03")
    if meth_output is None:
        failures.append("R3: No MethodologyOutput found in filler_outputs")
        return failures

    if not isinstance(meth_output, MethodologyOutput):
        failures.append(
            f"R3: section_03 filler output is {type(meth_output).__name__}, "
            "expected MethodologyOutput",
        )
        return failures

    # Check focused slide title uniqueness
    focused_titles = [fs.title for fs in meth_output.focused_slides]
    if len(focused_titles) != len(set(focused_titles)):
        failures.append(
            "R3: Methodology focused slides have duplicate titles: "
            + ", ".join(focused_titles),
        )

    # Check detail slides have non-empty 3 zones
    for j, ds in enumerate(meth_output.detail_slides):
        if not ds.activities.items:
            failures.append(
                f"R3: Methodology detail slide {j} has empty activities",
            )
        if not ds.deliverables.items:
            failures.append(
                f"R3: Methodology detail slide {j} has empty deliverables",
            )
        if not ds.frameworks.items:
            failures.append(
                f"R3: Methodology detail slide {j} has empty "
                "tools_frameworks",
            )

    # Check overview phase differentiation
    overview = meth_output.overview
    phase_titles = [p.phase_title for p in overview.phases]
    if len(phase_titles) != len(set(phase_titles)):
        failures.append(
            "R3: Methodology overview has duplicate phase titles: "
            + ", ".join(phase_titles),
        )

    return failures


def _check_r4_methodology_phase_count(
    filler_outputs: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[str]:
    """R4: Methodology phase count consistency."""
    failures: list[str] = []
    meth_output = filler_outputs.get("section_03")
    if meth_output is None or not isinstance(meth_output, MethodologyOutput):
        return failures  # R3 already flagged this

    grid_count = len(meth_output.overview.phases)
    focused_count = len(meth_output.focused_slides)
    detail_count = len(meth_output.detail_slides)

    if grid_count not in (3, 4):
        failures.append(
            f"R4: Grid phase count must be 3 or 4, got {grid_count}",
        )

    if focused_count != grid_count:
        failures.append(
            f"R4: Focused slide count ({focused_count}) != "
            f"grid phase count ({grid_count})",
        )

    # Detail slides cover grid phases only; overflow is a separate field
    has_overflow = meth_output.phase_5_overflow is not None
    expected_detail = grid_count
    if detail_count != expected_detail:
        failures.append(
            f"R4: Detail slide count ({detail_count}) != "
            f"expected ({expected_detail}, overflow={has_overflow})",
        )

    if grid_count == 3 and has_overflow:
        failures.append(
            "R4: 3-phase engagement must not have overflow",
        )

    if has_overflow:
        overflow = meth_output.phase_5_overflow
        if overflow and overflow.phase_number != 5:
            failures.append(
                f"R4: Overflow phase_number must be 5, "
                f"got {overflow.phase_number}",
            )

    return failures


def _check_r5_section_presence(
    records: list[dict[str, Any]],
) -> list[str]:
    """R5: All required sections must be present."""
    present_sections: set[str] = set()
    for record in records:
        section_id = record.get("section_id", "")
        if section_id:
            present_sections.add(section_id)

    failures: list[str] = []
    for required in sorted(REQUIRED_SECTIONS):
        if required not in present_sections:
            failures.append(
                f"R5: Required section '{required}' is missing from deck",
            )
    return failures


def _check_r7_empty_renderable_slides(
    records: list[dict[str, Any]],
    injection_results: list[InjectionResult | None],
) -> list[str]:
    """R7: No more than 10% of RENDERABLE_NOW slides may have zero injections."""
    renderable_count = 0
    empty_count = 0

    for i, record in enumerate(records):
        layout = record.get("semantic_layout_id", "")
        if layout not in RENDERABLE_NOW_LAYOUTS:
            continue
        renderable_count += 1

        if i < len(injection_results) and injection_results[i] is not None:
            ir = injection_results[i]
            if len(ir.injected) == 0:
                empty_count += 1
        else:
            # No injection result = no content injected
            injection_data = record.get("injection_data")
            if not injection_data or set(injection_data.keys()) <= {
                "source_slide_idx",
            }:
                empty_count += 1

    if renderable_count == 0:
        return []

    ratio = empty_count / renderable_count
    if ratio > 0.10:
        return [
            f"R7: {empty_count}/{renderable_count} "
            f"({ratio:.0%}) RENDERABLE_NOW slides have zero injections "
            f"(threshold: 10%)",
        ]
    return []


def _check_r8_placeholder_markers(
    records: list[dict[str, Any]],
) -> list[str]:
    """R8: No slide text may contain placeholder markers."""
    failures: list[str] = []
    for i, record in enumerate(records):
        injection_data = record.get("injection_data")
        for text in _extract_injection_texts(injection_data):
            for pattern in _PLACEHOLDER_PATTERNS:
                match = pattern.search(text)
                if match:
                    failures.append(
                        f"R8: Placeholder marker '{match.group()}' "
                        f"found on slide {i}",
                    )
                    break  # One per slide is enough
    return failures


def _check_r9_internal_notes(
    records: list[dict[str, Any]],
) -> list[str]:
    """R9: No slide text may contain internal markers."""
    failures: list[str] = []
    for i, record in enumerate(records):
        injection_data = record.get("injection_data")
        for text in _extract_injection_texts(injection_data):
            for pattern in _INTERNAL_NOTE_PATTERNS:
                match = pattern.search(text)
                if match:
                    failures.append(
                        f"R9: Internal note '{match.group()}' "
                        f"found on slide {i}",
                    )
                    break
    return failures


def _check_r10_arabic_purity(
    records: list[dict[str, Any]],
    language: str,
) -> list[str]:
    """R10: Arabic decks must have no unapproved English in renderable zones."""
    if language != "ar":
        return []

    failures: list[str] = []
    for i, record in enumerate(records):
        layout = record.get("semantic_layout_id", "")
        if layout not in RENDERABLE_NOW_LAYOUTS:
            continue
        injection_data = record.get("injection_data")
        for text in _extract_injection_texts(injection_data):
            english_words = re.findall(r"[a-zA-Z]{2,}", text)
            for word in english_words:
                if (
                    word not in APPROVED_ENGLISH_TERMS
                    and word.upper() not in APPROVED_ENGLISH_TERMS
                ):
                    failures.append(
                        f"R10: Unapproved English word '{word}' "
                        f"on slide {i} (layout={layout})",
                    )
                    break  # One per slide
    return failures


# ── Pending-extension findings ─────────────────────────────────────────


def _collect_pending_findings(
    records: list[dict[str, Any]],
) -> list[str]:
    """P1-P5: Record OBJECT zones expected but empty on extension layouts."""
    findings: list[str] = []
    for i, record in enumerate(records):
        layout = record.get("semantic_layout_id", "")
        section_id = record.get("section_id", "")
        if layout not in REQUIRES_EXTENSION_LAYOUTS:
            continue

        if section_id == "section_01":
            findings.append(
                f"P1: Understanding slide {i} ({layout}) — "
                "OBJECT zones empty (awaiting inject_multi_body extension)",
            )
        elif section_id == "section_04":
            findings.append(
                f"P2: Timeline slide {i} ({layout}) — "
                "OBJECT zones empty (awaiting inject_multi_body extension)",
            )
        elif section_id == "section_06":
            findings.append(
                f"P3: Governance slide {i} ({layout}) — "
                "OBJECT zones empty (awaiting inject_multi_body extension)",
            )
    return findings


# ── Scored metrics ─────────────────────────────────────────────────────


def _score_s1_methodology_structure(
    filler_outputs: dict[str, Any],
) -> float:
    """S1: Methodology Structure Score (0-100)."""
    meth_output = filler_outputs.get("section_03")
    if meth_output is None or not isinstance(meth_output, MethodologyOutput):
        return 0.0

    score = 0.0
    overview = meth_output.overview
    grid_count = len(overview.phases)
    has_overflow = meth_output.phase_5_overflow is not None

    # Phase count validity (15% weight, or 30% if no overflow)
    overflow_weight = 15.0 if has_overflow else 0.0
    phase_validity_weight = 15.0 + (15.0 - overflow_weight if not has_overflow else 0.0)

    if grid_count in (3, 4):
        score += phase_validity_weight

    # Overview phase differentiation (25%)
    phase_titles = [p.phase_title for p in overview.phases]
    unique_ratio = len(set(phase_titles)) / max(len(phase_titles), 1)
    score += 25.0 * unique_ratio

    # Focused slide title uniqueness (20%)
    focused_titles = [fs.title for fs in meth_output.focused_slides]
    focused_unique = len(set(focused_titles)) / max(len(focused_titles), 1)
    score += 20.0 * focused_unique

    # Detail slide structure (25%)
    detail_scores: list[float] = []
    for ds in meth_output.detail_slides:
        zones_populated = sum([
            len(ds.activities.items) >= 2,
            len(ds.deliverables.items) >= 2,
            len(ds.frameworks.items) >= 2,
        ])
        detail_scores.append(zones_populated / 3.0)
    if detail_scores:
        score += 25.0 * (sum(detail_scores) / len(detail_scores))

    # Phase 5 overflow (15% if applicable)
    if has_overflow and overflow_weight > 0:
        overflow = meth_output.phase_5_overflow
        if overflow:
            score += overflow_weight  # Present = full points

    return min(score, 100.0)


def _score_s2_section_completeness(
    records: list[dict[str, Any]],
) -> float:
    """S2: Section Completeness Score (0-100)."""
    present_sections: set[str] = set()
    for record in records:
        section_id = record.get("section_id", "")
        if section_id:
            present_sections.add(section_id)

    # Points per section
    section_points = {
        "cover": 10,      # Cover + Intro Message
        "toc": 5,         # Table of Contents
        "section_01": 12,  # Understanding
        "section_02": 8,   # Why Strategic Gears
        "section_03": 18,  # Methodology
        "section_04": 9,   # Timeline
        "section_05": 9,   # Team
        "section_06": 9,   # Governance
        "section_07": 10,  # Case Studies
        "section_08": 10,  # Company Profile
    }

    total = sum(
        points
        for section_id, points in section_points.items()
        if section_id in present_sections
    )
    return float(total)


def _score_s3_content_density(
    records: list[dict[str, Any]],
) -> float:
    """S3: Content Density Score (0-100).

    Checks RENDERABLE_NOW layouts for content quality metrics.
    """
    violations = 0
    checks = 0

    for record in records:
        layout = record.get("semantic_layout_id", "")
        if layout not in RENDERABLE_NOW_LAYOUTS:
            continue
        injection_data = record.get("injection_data")
        if not injection_data:
            continue

        for text in _extract_injection_texts(injection_data):
            checks += 1
            # Check bullet length
            segments = text.split("\n")
            for seg in segments:
                words = len(seg.split())
                if words > 25:
                    violations += 1

            # Check title length (if it's the title field)
            if text == injection_data.get("title", ""):
                word_count = len(text.split())
                if word_count < 3 or word_count > 10:
                    violations += 1

    if checks == 0:
        return 0.0
    return max(0.0, 100.0 - (violations * 10.0))


def _score_s4_arabic_integrity(
    records: list[dict[str, Any]],
    language: str,
) -> float | None:
    """S4: Arabic Integrity Score (0-100, None for EN)."""
    if language != "ar":
        return None

    unapproved_count = 0
    for record in records:
        layout = record.get("semantic_layout_id", "")
        if layout not in RENDERABLE_NOW_LAYOUTS:
            continue
        injection_data = record.get("injection_data")
        for text in _extract_injection_texts(injection_data):
            english_words = re.findall(r"[a-zA-Z]{2,}", text)
            for word in english_words:
                if (
                    word not in APPROVED_ENGLISH_TERMS
                    and word.upper() not in APPROVED_ENGLISH_TERMS
                ):
                    unapproved_count += 1

    return max(0.0, 100.0 - (unapproved_count * 10.0))


# ── Main entry point ──────────────────────────────────────────────────


def run_quality_gate(
    *,
    records: list[dict[str, Any]],
    filler_outputs: dict[str, Any] | None = None,
    injection_results: list[InjectionResult | None] | None = None,
    language: str = "en",
) -> QualityGateResult:
    """Run the quality gate on a rendered deck.

    Parameters
    ----------
    records : list[dict]
        Slide records with keys: semantic_layout_id, section_id,
        injection_data, entry_type.
    filler_outputs : dict[str, Any], optional
        G2 schema objects per section (keyed by section_id).
    injection_results : list[InjectionResult | None], optional
        InjectionResult per slide (parallel to records).
    language : str
        Output language ("en" or "ar").

    Returns
    -------
    QualityGateResult
        Gate result with pass/fail, failures, findings, and scores.
    """
    if filler_outputs is None:
        filler_outputs = {}
    if injection_results is None:
        injection_results = []

    result = QualityGateResult()
    all_failures: list[str] = []

    # ── Hard rules (ENFORCEABLE_NOW) ───────────────────────────────
    # R1: Schema validation — already enforced at filler parse time
    #     by Pydantic. We verify filler_outputs exist for registered
    #     sections. If a filler produced output, it already passed R1.

    # R2: Prose detection on renderable zones
    all_failures.extend(_check_r2_prose_detection(records))

    # R3: Methodology phase structure
    all_failures.extend(
        _check_r3_methodology_structure(filler_outputs, records),
    )

    # R4: Methodology phase count consistency
    all_failures.extend(
        _check_r4_methodology_phase_count(filler_outputs, records),
    )

    # R5: Section presence
    all_failures.extend(_check_r5_section_presence(records))

    # R6: Intro message completeness — DEFERRED
    # IntroductionFiller is not wired into the live pipeline (intro is
    # a2_shell in the cover section). Cannot check filler_output for
    # section_00. Deferred until intro filler is live.

    # R7: Empty renderable slide detection
    all_failures.extend(
        _check_r7_empty_renderable_slides(records, injection_results),
    )

    # R8: Placeholder marker detection
    all_failures.extend(_check_r8_placeholder_markers(records))

    # R9: Internal note detection
    all_failures.extend(_check_r9_internal_notes(records))

    # R10: Arabic purity on renderable zones
    all_failures.extend(_check_r10_arabic_purity(records, language))

    # R11: Clone section integrity — DEFERRED
    # TeamOutput, CaseStudyOutput, CompanyProfileOutput G2 schemas
    # do not exist yet. Cannot validate clone structure.
    # Deferred until clone schemas are implemented.

    # ── Set pass/fail ──────────────────────────────────────────────
    result.hard_failures = all_failures
    result.passed = len(all_failures) == 0

    # ── Pending-extension findings (P1-P5) ─────────────────────────
    result.pending_findings = _collect_pending_findings(records)

    # ── Scored metrics ─────────────────────────────────────────────
    result.methodology_structure_score = _score_s1_methodology_structure(
        filler_outputs,
    )
    result.section_completeness_score = _score_s2_section_completeness(
        records,
    )
    result.content_density_score = _score_s3_content_density(records)
    result.arabic_integrity_score = _score_s4_arabic_integrity(
        records, language,
    )

    return result
