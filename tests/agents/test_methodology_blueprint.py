"""Tests for Phase 3b — methodology_blueprint.py.

Tests methodology blueprint construction, phase ordering, layout ID
resolution (semantic only), deliverable linkage, and fail-closed
validation against catalog lock layout sets.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.methodology_blueprint import (
    METHODOLOGY_LAYOUTS_3_PHASE,
    METHODOLOGY_LAYOUTS_4_PHASE,
    MethodologyBlueprint,
    MethodologyBlueprintError,
    PhaseBlueprint,
    build_methodology_blueprint,
    validate_methodology_layouts,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "data"
CATALOG_LOCK_EN = DATA_DIR / "catalog_lock_en.json"


def _load_layout_ids() -> set[str]:
    """Load all semantic layout IDs from EN catalog lock."""
    with open(CATALOG_LOCK_EN, encoding="utf-8") as f:
        lock = json.load(f)
    return set(lock.get("layouts", {}).keys())


def _make_phases(count: int, *, activity_count: int = 2) -> list[dict]:
    """Create minimal phase definitions."""
    return [
        {
            "phase_name_en": f"Phase {i + 1}",
            "phase_name_ar": f"المرحلة {i + 1}",
            "activities": [f"activity_{j}" for j in range(activity_count)],
            "deliverables": [f"deliverable_{j}" for j in range(2)],
            "governance_tier": "Steering Committee",
        }
        for i in range(count)
    ]


# ── Layout family constants ──────────────────────────────────────────────


class TestLayoutFamilies:
    def test_4_phase_family_has_all_keys(self):
        assert "overview" in METHODOLOGY_LAYOUTS_4_PHASE
        assert "focused" in METHODOLOGY_LAYOUTS_4_PHASE
        assert "detail" in METHODOLOGY_LAYOUTS_4_PHASE

    def test_3_phase_family_has_all_keys(self):
        assert "overview" in METHODOLOGY_LAYOUTS_3_PHASE
        assert "focused" in METHODOLOGY_LAYOUTS_3_PHASE
        assert "detail" in METHODOLOGY_LAYOUTS_3_PHASE

    def test_4_phase_uses_semantic_ids(self):
        for layout_id in METHODOLOGY_LAYOUTS_4_PHASE.values():
            assert layout_id.startswith("methodology_")

    def test_3_phase_uses_semantic_ids(self):
        for layout_id in METHODOLOGY_LAYOUTS_3_PHASE.values():
            assert layout_id.startswith("methodology_")

    def test_families_share_detail_layout(self):
        assert (
            METHODOLOGY_LAYOUTS_3_PHASE["detail"]
            == METHODOLOGY_LAYOUTS_4_PHASE["detail"]
        )

    def test_families_differ_on_overview(self):
        assert (
            METHODOLOGY_LAYOUTS_3_PHASE["overview"]
            != METHODOLOGY_LAYOUTS_4_PHASE["overview"]
        )


# ── Blueprint construction ───────────────────────────────────────────────


class TestBuildMethodologyBlueprint:
    def test_3_phase_blueprint(self):
        bp = build_methodology_blueprint(3, _make_phases(3))
        assert bp.phase_count == 3
        assert len(bp.phases) == 3

    def test_4_phase_blueprint(self):
        bp = build_methodology_blueprint(4, _make_phases(4))
        assert bp.phase_count == 4
        assert len(bp.phases) == 4

    def test_5_phase_blueprint(self):
        bp = build_methodology_blueprint(5, _make_phases(5))
        assert bp.phase_count == 5
        assert len(bp.phases) == 5

    def test_2_phases_raises(self):
        with pytest.raises(MethodologyBlueprintError, match="3-5"):
            build_methodology_blueprint(2, _make_phases(2))

    def test_6_phases_raises(self):
        with pytest.raises(MethodologyBlueprintError, match="3-5"):
            build_methodology_blueprint(6, _make_phases(6))

    def test_phase_count_mismatch_raises(self):
        with pytest.raises(MethodologyBlueprintError, match="Expected 4"):
            build_methodology_blueprint(4, _make_phases(3))

    def test_missing_phase_name_raises(self):
        phases = [{"activities": [], "deliverables": []}]
        with pytest.raises(MethodologyBlueprintError, match="phase_name_en"):
            build_methodology_blueprint(3, phases * 3)


# ── Phase blueprint properties ───────────────────────────────────────────


class TestPhaseBlueprint:
    def test_phase_numbers_sequential(self):
        bp = build_methodology_blueprint(4, _make_phases(4))
        for i, phase in enumerate(bp.phases):
            assert phase.phase_number == i + 1

    def test_phase_ids_formatted(self):
        bp = build_methodology_blueprint(3, _make_phases(3))
        assert bp.phases[0].phase_id == "phase_01"
        assert bp.phases[2].phase_id == "phase_03"

    def test_frozen_phase(self):
        bp = build_methodology_blueprint(3, _make_phases(3))
        with pytest.raises(AttributeError):
            bp.phases[0].phase_name_en = "hacked"  # type: ignore[misc]

    def test_activities_preserved(self):
        phases = _make_phases(3, activity_count=5)
        bp = build_methodology_blueprint(3, phases)
        assert len(bp.phases[0].activities) == 5

    def test_deliverables_preserved(self):
        bp = build_methodology_blueprint(3, _make_phases(3))
        assert len(bp.phases[0].deliverables) == 2

    def test_governance_tier_preserved(self):
        bp = build_methodology_blueprint(3, _make_phases(3))
        assert bp.phases[0].governance_tier == "Steering Committee"


# ── Layout selection logic ───────────────────────────────────────────────


class TestLayoutSelection:
    def test_3_phase_uses_3_phase_layouts(self):
        bp = build_methodology_blueprint(3, _make_phases(3))
        assert bp.phases[0].overview_layout == METHODOLOGY_LAYOUTS_3_PHASE["overview"]
        assert bp.phases[0].focused_layouts == [METHODOLOGY_LAYOUTS_3_PHASE["focused"]]

    def test_4_phase_uses_4_phase_layouts(self):
        bp = build_methodology_blueprint(4, _make_phases(4))
        assert bp.phases[0].overview_layout == METHODOLOGY_LAYOUTS_4_PHASE["overview"]

    def test_5_phase_uses_4_phase_layouts(self):
        """5-phase methodology also uses the 4-phase layout family."""
        bp = build_methodology_blueprint(5, _make_phases(5))
        assert bp.phases[0].overview_layout == METHODOLOGY_LAYOUTS_4_PHASE["overview"]

    def test_detail_layout_when_many_activities(self):
        """Phases with >3 activities get detail slides."""
        phases = _make_phases(3, activity_count=5)
        bp = build_methodology_blueprint(3, phases)
        assert len(bp.phases[0].detail_layouts) == 1
        assert bp.phases[0].detail_layouts[0].startswith("methodology_")

    def test_no_detail_layout_when_few_activities(self):
        """Phases with <=3 activities get no detail slides."""
        phases = _make_phases(3, activity_count=2)
        bp = build_methodology_blueprint(3, phases)
        assert bp.phases[0].detail_layouts == []

    def test_no_raw_display_names_in_layouts(self):
        """All layout references must be semantic IDs."""
        raw_names = {
            "Methodology -4- Overview of Phases",
            "Methdology -4- Focused Phase",
            "Methodolgy - Detailed Phase",
        }
        bp = build_methodology_blueprint(4, _make_phases(4, activity_count=5))
        for layout_id in bp.all_semantic_layout_ids:
            assert layout_id not in raw_names


# ── Computed properties ──────────────────────────────────────────────────


class TestComputedProperties:
    def test_total_min_slides_3_phase_simple(self):
        """3 phases x 1 focused each + 1 overview = 4 minimum."""
        bp = build_methodology_blueprint(3, _make_phases(3, activity_count=2))
        assert bp.total_min_slides == 4  # 1 overview + 3 × (1 focused)

    def test_total_min_slides_with_details(self):
        """Phases with details have higher minimums."""
        bp = build_methodology_blueprint(3, _make_phases(3, activity_count=5))
        # Each phase: 1 focused + 1 detail = 2 min; plus 1 overview = 7
        assert bp.total_min_slides == 7

    def test_all_semantic_layout_ids_complete(self):
        bp = build_methodology_blueprint(3, _make_phases(3, activity_count=5))
        ids = bp.all_semantic_layout_ids
        # 3 phases × (1 overview + 1 focused + 1 detail) = 9
        assert len(ids) == 9

    def test_all_semantic_layout_ids_no_duplicates_check(self):
        """Layout IDs may repeat (each phase uses same family)."""
        bp = build_methodology_blueprint(3, _make_phases(3))
        ids = bp.all_semantic_layout_ids
        # All should be valid methodology layout IDs
        for lid in ids:
            assert lid.startswith("methodology_")


# ── Deliverables and governance ──────────────────────────────────────────


class TestDeliverablesAndGovernance:
    def test_deliverables_linkage(self):
        bp = build_methodology_blueprint(
            3,
            _make_phases(3),
            deliverables_linkage={"phase_01": ["report_1", "dashboard"]},
        )
        assert bp.deliverables_linkage["phase_01"] == ["report_1", "dashboard"]

    def test_governance_touchpoints(self):
        bp = build_methodology_blueprint(
            3,
            _make_phases(3),
            governance_touchpoints={"phase_01": "Steering Committee"},
        )
        assert bp.governance_touchpoints["phase_01"] == "Steering Committee"

    def test_evidence_anchors(self):
        bp = build_methodology_blueprint(
            3,
            _make_phases(3),
            evidence_anchors=["case_study_banking", "framework_digital"],
        )
        assert len(bp.evidence_anchors) == 2

    def test_timeline_span(self):
        bp = build_methodology_blueprint(
            3,
            _make_phases(3),
            timeline_span="16 weeks",
        )
        assert bp.timeline_span == "16 weeks"


# ── Catalog lock validation ──────────────────────────────────────────────


class TestValidateMethodologyLayouts:
    @pytest.mark.skipif(
        not CATALOG_LOCK_EN.exists(),
        reason="Catalog lock not available",
    )
    def test_all_methodology_layouts_in_catalog_lock(self):
        """All methodology layout IDs must exist in the catalog lock."""
        layout_ids = _load_layout_ids()
        bp = build_methodology_blueprint(4, _make_phases(4, activity_count=5))
        errors = validate_methodology_layouts(bp, layout_ids)
        assert errors == [], f"Missing layouts: {errors}"

    @pytest.mark.skipif(
        not CATALOG_LOCK_EN.exists(),
        reason="Catalog lock not available",
    )
    def test_3_phase_layouts_in_catalog_lock(self):
        layout_ids = _load_layout_ids()
        bp = build_methodology_blueprint(3, _make_phases(3, activity_count=5))
        errors = validate_methodology_layouts(bp, layout_ids)
        assert errors == [], f"Missing layouts: {errors}"

    def test_missing_layout_detected(self):
        """Fail-closed: missing layout ID produces error."""
        bp = build_methodology_blueprint(3, _make_phases(3))
        errors = validate_methodology_layouts(bp, set())  # empty catalog
        assert len(errors) > 0
        assert all("not found" in e for e in errors)

    def test_partial_catalog_detects_gaps(self):
        """Only overview present, focused missing."""
        bp = build_methodology_blueprint(3, _make_phases(3))
        partial = {"methodology_overview_3"}
        errors = validate_methodology_layouts(bp, partial)
        assert any("methodology_focused_3" in e for e in errors)
