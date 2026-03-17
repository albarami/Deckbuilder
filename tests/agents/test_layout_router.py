"""Tests for Phase 8 — layout_router.py.

Tests SlideObject -> semantic layout ID mapping, methodology phase
routing, pool asset routing, batch routing, error handling, and
verification that no raw display names appear in routing results.
"""

from __future__ import annotations

import pytest

from src.models.enums import LayoutType
from src.models.methodology_blueprint import (
    PhaseBlueprint,
    build_methodology_blueprint,
)
from src.services.layout_router import (
    CASE_STUDY_LAYOUTS,
    TEAM_BIO_LAYOUT,
    LayoutRoutingError,
    LayoutRoutingResult,
    RoutedLayout,
    route_layout_type,
    route_methodology_phase,
    route_pool_asset,
    route_variable_slides,
)
from src.services.slide_budgeter import SlideBudget

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_phases(count: int, *, activity_count: int = 2) -> list[dict]:
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


def _empty_budget() -> SlideBudget:
    """Minimal budget for routing tests."""
    return SlideBudget(total_slides=0, section_budgets={})


# ── RoutedLayout ─────────────────────────────────────────────────────────


class TestRoutedLayout:
    def test_frozen(self):
        rl = RoutedLayout(semantic_layout_id="content_heading_desc")
        with pytest.raises(AttributeError):
            rl.semantic_layout_id = "hacked"  # type: ignore[misc]

    def test_fields(self):
        rl = RoutedLayout(
            semantic_layout_id="content_heading_desc",
            layout_type=LayoutType.CONTENT_1COL,
            section_id="section_01",
            routing_reason="test",
        )
        assert rl.semantic_layout_id == "content_heading_desc"
        assert rl.layout_type == LayoutType.CONTENT_1COL
        assert rl.section_id == "section_01"
        assert rl.routing_reason == "test"


# ── route_layout_type ───────────────────────────────────────────────────


class TestRouteLayoutType:
    def test_content_1col(self):
        result = route_layout_type(LayoutType.CONTENT_1COL)
        assert result.semantic_layout_id == "content_heading_desc"

    def test_content_2col(self):
        result = route_layout_type(LayoutType.CONTENT_2COL)
        assert result.semantic_layout_id == "content_heading_desc_box"

    def test_framework(self):
        result = route_layout_type(LayoutType.FRAMEWORK)
        assert result.semantic_layout_id == "content_heading_4boxes"

    def test_team_layout(self):
        result = route_layout_type(LayoutType.TEAM)
        assert result.semantic_layout_id == "team_two_members"

    def test_all_layout_types_have_mapping(self):
        """Every LayoutType must have a default semantic layout ID."""
        for lt in LayoutType:
            result = route_layout_type(lt)
            assert result.semantic_layout_id
            assert result.semantic_layout_id.islower() or "_" in result.semantic_layout_id

    def test_section_id_propagated(self):
        result = route_layout_type(LayoutType.CONTENT_1COL, section_id="section_01")
        assert result.section_id == "section_01"

    def test_routing_reason_present(self):
        result = route_layout_type(LayoutType.CONTENT_1COL)
        assert "CONTENT_1COL" in result.routing_reason

    def test_no_raw_display_names(self):
        """No routing result should contain raw display names."""
        raw_names = {
            "Methodology -4- Overview of Phases",
            "Methdology -4- Focused Phase",
            "two team members",
            "Services - Cases",
        }
        for lt in LayoutType:
            result = route_layout_type(lt)
            assert result.semantic_layout_id not in raw_names


# ── route_methodology_phase ─────────────────────────────────────────────


class TestRouteMethodologyPhase:
    @pytest.fixture
    def phase_4(self) -> PhaseBlueprint:
        bp = build_methodology_blueprint(4, _make_phases(4, activity_count=5))
        return bp.phases[0]

    @pytest.fixture
    def phase_3_no_detail(self) -> PhaseBlueprint:
        bp = build_methodology_blueprint(3, _make_phases(3, activity_count=2))
        return bp.phases[0]

    def test_overview_routing(self, phase_4):
        result = route_methodology_phase(phase_4, slide_role="overview")
        assert result.semantic_layout_id == "methodology_overview_4"
        assert result.section_id == "section_03"

    def test_focused_routing(self, phase_4):
        result = route_methodology_phase(phase_4, slide_role="focused")
        assert result.semantic_layout_id == "methodology_focused_4"

    def test_detail_routing(self, phase_4):
        result = route_methodology_phase(phase_4, slide_role="detail")
        assert result.semantic_layout_id == "methodology_detail"

    def test_3_phase_overview(self, phase_3_no_detail):
        result = route_methodology_phase(phase_3_no_detail, slide_role="overview")
        assert result.semantic_layout_id == "methodology_overview_3"

    def test_detail_missing_raises(self, phase_3_no_detail):
        with pytest.raises(LayoutRoutingError, match="no detail layouts"):
            route_methodology_phase(phase_3_no_detail, slide_role="detail")

    def test_invalid_role_raises(self, phase_4):
        with pytest.raises(LayoutRoutingError, match="Invalid slide_role"):
            route_methodology_phase(phase_4, slide_role="summary")

    def test_routing_reason_auditable(self, phase_4):
        result = route_methodology_phase(phase_4, slide_role="focused")
        assert "methodology" in result.routing_reason
        assert "focused" in result.routing_reason
        assert "phase_01" in result.routing_reason

    def test_all_methodology_ids_are_semantic(self, phase_4):
        for role in ("overview", "focused", "detail"):
            result = route_methodology_phase(phase_4, slide_role=role)
            assert result.semantic_layout_id.startswith("methodology_")


# ── route_pool_asset ────────────────────────────────────────────────────


class TestRoutePoolAsset:
    def test_case_study_detailed(self):
        result = route_pool_asset("case_study", section_id="section_02")
        assert result.semantic_layout_id == "case_study_detailed"
        assert result.section_id == "section_02"

    def test_case_study_cases(self):
        result = route_pool_asset(
            "case_study", section_id="section_02", layout_variant="cases",
        )
        assert result.semantic_layout_id == "case_study_cases"

    def test_case_study_invalid_variant_raises(self):
        with pytest.raises(LayoutRoutingError, match="Unknown case study variant"):
            route_pool_asset("case_study", layout_variant="summary")

    def test_team_bio(self):
        result = route_pool_asset("team_bio", section_id="section_05")
        assert result.semantic_layout_id == "team_two_members"
        assert result.section_id == "section_05"

    def test_unknown_type_raises(self):
        with pytest.raises(LayoutRoutingError, match="Unknown pool asset type"):
            route_pool_asset("certificate")

    def test_case_study_layouts_constant(self):
        assert "case_study_cases" in CASE_STUDY_LAYOUTS
        assert "case_study_detailed" in CASE_STUDY_LAYOUTS

    def test_team_bio_layout_constant(self):
        assert TEAM_BIO_LAYOUT == "team_two_members"

    def test_routing_reason_auditable(self):
        result = route_pool_asset("case_study", layout_variant="detailed")
        assert "case study" in result.routing_reason
        assert "detailed" in result.routing_reason


# ── route_variable_slides (batch routing) ───────────────────────────────


class TestRouteVariableSlides:
    def test_layout_type_batch(self):
        specs = [
            {"layout_type": LayoutType.CONTENT_1COL, "section_id": "section_01"},
            {"layout_type": LayoutType.FRAMEWORK, "section_id": "section_01"},
        ]
        result = route_variable_slides(specs, _empty_budget())
        assert isinstance(result, LayoutRoutingResult)
        assert len(result.routed) == 2
        assert result.errors == []
        assert result.routed[0].semantic_layout_id == "content_heading_desc"
        assert result.routed[1].semantic_layout_id == "content_heading_4boxes"

    def test_pool_asset_batch(self):
        specs = [
            {"asset_type": "case_study", "section_id": "section_02"},
            {"asset_type": "team_bio", "section_id": "section_05"},
        ]
        result = route_variable_slides(specs, _empty_budget())
        assert len(result.routed) == 2
        assert result.routed[0].semantic_layout_id == "case_study_detailed"
        assert result.routed[1].semantic_layout_id == "team_two_members"

    def test_methodology_batch(self):
        meth = build_methodology_blueprint(3, _make_phases(3))
        specs = [
            {"methodology_phase": "phase_01", "slide_role": "overview"},
            {"methodology_phase": "phase_01", "slide_role": "focused"},
            {"methodology_phase": "phase_02", "slide_role": "focused"},
        ]
        result = route_variable_slides(specs, _empty_budget(), meth)
        assert len(result.routed) == 3
        assert result.routed[0].semantic_layout_id == "methodology_overview_3"
        assert result.routed[1].semantic_layout_id == "methodology_focused_3"

    def test_mixed_batch(self):
        meth = build_methodology_blueprint(3, _make_phases(3))
        specs = [
            {"layout_type": LayoutType.CONTENT_1COL, "section_id": "section_01"},
            {"methodology_phase": "phase_01", "slide_role": "focused"},
            {"asset_type": "case_study", "section_id": "section_02"},
        ]
        result = route_variable_slides(specs, _empty_budget(), meth)
        assert len(result.routed) == 3
        assert result.errors == []

    def test_missing_spec_keys_error(self):
        specs = [{"section_id": "section_01"}]  # no type key
        result = route_variable_slides(specs, _empty_budget())
        assert len(result.routed) == 0
        assert len(result.errors) == 1
        assert "missing" in result.errors[0]

    def test_invalid_methodology_phase_error(self):
        meth = build_methodology_blueprint(3, _make_phases(3))
        specs = [
            {"methodology_phase": "phase_99", "slide_role": "focused"},
        ]
        result = route_variable_slides(specs, _empty_budget(), meth)
        assert len(result.routed) == 0
        assert len(result.errors) == 1
        assert "phase_99" in result.errors[0]

    def test_string_layout_type_coercion(self):
        specs = [
            {"layout_type": "CONTENT_1COL", "section_id": "section_01"},
        ]
        result = route_variable_slides(specs, _empty_budget())
        assert len(result.routed) == 1
        assert result.routed[0].semantic_layout_id == "content_heading_desc"

    def test_empty_specs(self):
        result = route_variable_slides([], _empty_budget())
        assert len(result.routed) == 0
        assert result.errors == []

    def test_result_routed_is_tuple(self):
        specs = [
            {"layout_type": LayoutType.CONTENT_1COL, "section_id": "section_01"},
        ]
        result = route_variable_slides(specs, _empty_budget())
        assert isinstance(result.routed, tuple)

    def test_partial_errors_dont_block_valid(self):
        """Valid specs succeed even if others fail."""
        specs = [
            {"layout_type": LayoutType.CONTENT_1COL, "section_id": "section_01"},
            {"section_id": "section_01"},  # invalid — no type key
            {"asset_type": "team_bio", "section_id": "section_05"},
        ]
        result = route_variable_slides(specs, _empty_budget())
        assert len(result.routed) == 2
        assert len(result.errors) == 1


# ── No raw display names ───────────────────────────────────────────────


class TestNoRawDisplayNames:
    def test_all_default_mappings_are_semantic(self):
        """Every default mapping must be a semantic layout ID."""
        raw_names = {
            "Methodology -4- Overview of Phases",
            "Methdology -4- Focused Phase",
            "Methodolgy - Detailed Phase",
            "two team members",
            "Services - Cases",
            "Services - Detailed Case",
            "Section Divider",
        }
        for lt in LayoutType:
            result = route_layout_type(lt)
            assert result.semantic_layout_id not in raw_names
            # Must be lowercase/underscore style
            assert result.semantic_layout_id == result.semantic_layout_id.lower() or \
                   "_" in result.semantic_layout_id

    def test_pool_layouts_are_semantic(self):
        for layout_id in CASE_STUDY_LAYOUTS:
            assert layout_id.startswith("case_study_")
        assert TEAM_BIO_LAYOUT.startswith("team_")
