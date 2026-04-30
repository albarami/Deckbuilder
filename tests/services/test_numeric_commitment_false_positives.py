"""Tests for numeric commitment detector false-positive exclusions.

The detector must NOT flag:
- HR requirement IDs (HR-L1-009 → 1-009 → false range)
- Hijri dates (1447-11-08 → 1447-11 → false range)
- DEL/COMP/SCOPE/CLM reference IDs
- CR compliance IDs

It MUST still flag:
- Real numeric ranges in prose (5-8 دول, 20-25 KPIs)
- Single-number commitments with scope units (40 workshops)
"""

from __future__ import annotations

import pytest

from src.models.claim_provenance import ClaimRegistry, ClaimProvenance
from src.services.artifact_gates import ArtifactSection
from src.services.numeric_commitment_detector import (
    detect_numeric_commitments,
)

try:
    from src.models.claim_provenance import ProposalOptionRegistry
except ImportError:
    # Fallback if not yet defined
    ProposalOptionRegistry = type("ProposalOptionRegistry", (), {
        "get": lambda self, x: None,
    })


def _empty_registries():
    return ClaimRegistry(), ProposalOptionRegistry()


def _section(text: str, section_type: str = "client_facing_body") -> list[ArtifactSection]:
    return [ArtifactSection(
        section_path="test/body",
        section_type=section_type,
        text=text,
    )]


# ── False positive exclusions ────────────────────────────────────


def test_hr_id_not_flagged_as_commitment():
    """HR-L1-009 should not be flagged — 1-009 is an ID, not a range."""
    reg, opts = _empty_registries()
    sections = _section("متطلب HR-L1-009 يشترط السرية")
    results = detect_numeric_commitments(sections, reg, opts)
    flagged = [r for r in results if "1-9" in r.canonical or "1-009" in r.canonical]
    assert flagged == [], f"HR-L1-009 falsely flagged: {[r.canonical for r in flagged]}"


def test_hr_id_014_not_flagged():
    """HR-L1-014 should not be flagged."""
    reg, opts = _empty_registries()
    sections = _section("سريان العرض 90 يوماً (HR-L1-014)")
    results = detect_numeric_commitments(sections, reg, opts)
    flagged = [r for r in results if "1-14" in r.canonical or "1-014" in r.canonical]
    assert flagged == [], f"HR-L1-014 falsely flagged: {[r.canonical for r in flagged]}"


def test_hijri_date_not_flagged():
    """Hijri date 1447-11-08 should not be flagged as numeric range."""
    reg, opts = _empty_registries()
    sections = _section("آخر موعد للاستفسارات 1447-11-08 هـ")
    results = detect_numeric_commitments(sections, reg, opts)
    flagged = [r for r in results if "1447" in r.canonical or "11-1447" in r.canonical]
    assert flagged == [], f"Hijri date falsely flagged: {[r.canonical for r in flagged]}"


def test_hijri_date_1448_not_flagged():
    """Hijri date 1448-01 should not be flagged."""
    reg, opts = _empty_registries()
    sections = _section("بدء الخدمة المتوقع 1448-01-15")
    results = detect_numeric_commitments(sections, reg, opts)
    flagged = [r for r in results if "1448" in r.canonical or "1-1448" in r.canonical]
    assert flagged == [], f"Hijri date 1448 falsely flagged: {[r.canonical for r in flagged]}"


def test_del_id_not_flagged():
    """DEL-005 should not be flagged."""
    reg, opts = _empty_registries()
    sections = _section("المخرج DEL-005 يتضمن تصميم المبادرات")
    results = detect_numeric_commitments(sections, reg, opts)
    flagged = [r for r in results if "5" in r.canonical and "del" in r.text.lower()]
    # DEL-005 is an ID reference, not a numeric commitment
    assert not any("DEL" in r.text for r in results)


def test_comp_id_not_flagged():
    """COMP-001 should not be flagged."""
    reg, opts = _empty_registries()
    sections = _section("بند COMP-001 (HR-L1-001)")
    results = detect_numeric_commitments(sections, reg, opts)
    flagged = [r for r in results if "1-1" in r.canonical]
    assert flagged == [], f"COMP-001 falsely flagged: {[r.canonical for r in flagged]}"


def test_clm_id_not_flagged():
    """CLM-PRJ-001 should not be flagged."""
    reg, opts = _empty_registries()
    sections = _section("مرجع CLM-PRJ-001 يثبت الخبرة")
    results = detect_numeric_commitments(sections, reg, opts)
    # CLM-PRJ-001 contains PRJ-001 which has 1 as a number, but it's an ID
    assert not any("CLM" in r.text for r in results)


# ── True positives still flagged ─────────────────────────────────


def test_real_range_still_flagged():
    """5-8 دول should still be flagged as a numeric commitment."""
    reg, opts = _empty_registries()
    sections = _section("دراسة مقارنة في 5-8 دول")
    results = detect_numeric_commitments(sections, reg, opts)
    flagged = [r for r in results if r.canonical == "5-8"]
    assert len(flagged) >= 1, "Real range 5-8 should be flagged"


def test_real_single_number_still_flagged():
    """40 workshops should still be flagged."""
    reg, opts = _empty_registries()
    sections = _section("تنفيذ 40 ورشة عمل خلال المشروع")
    results = detect_numeric_commitments(sections, reg, opts)
    flagged = [r for r in results if "40" in r.canonical]
    assert len(flagged) >= 1, "Single number 40 workshops should be flagged"


def test_real_range_20_25_flagged():
    """20-25 KPIs should still be flagged."""
    reg, opts = _empty_registries()
    sections = _section("تحديد 20-25 مؤشر أداء رئيسي")
    results = detect_numeric_commitments(sections, reg, opts)
    flagged = [r for r in results if r.canonical == "20-25"]
    assert len(flagged) >= 1, "Real range 20-25 should be flagged"


# ── Internal sections not scanned ────────────────────────────────


def test_internal_section_not_scanned():
    """Internal sections should not be scanned for commitments."""
    reg, opts = _empty_registries()
    sections = _section("نلتزم بتنفيذ 5-8 دول", section_type="internal_gap_appendix")
    results = detect_numeric_commitments(sections, reg, opts)
    assert results == []
