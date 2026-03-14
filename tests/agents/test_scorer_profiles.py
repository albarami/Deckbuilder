"""Tests for Phase 14 — scorer_profiles.py + composition_scorer.py integration.

Tests renderer-mode-aware scorer profile dispatch, legacy profile
immutability, template-v2 profile isolation, no cross-contamination,
AND that composition_scorer.py actually dispatches scoring behavior
based on the active profile.

Critical invariant: legacy profile values are **pinned** — any change
is a cross-contamination bug.
"""

from __future__ import annotations

import pytest

from src.services.composition_scorer import (
    CompositionResult,
    ShapeInfo,
    SlideScore,
    Violation,
    ViolationSeverity,
    score_composition,
)
from src.services.scorer_profiles import (
    ProfileConfig,
    ScorerProfile,
    get_legacy_profile,
    get_profile,
    get_v2_profile,
)


# ── ScorerProfile enum ────────────────────────────────────────────────


class TestScorerProfile:
    def test_values(self):
        assert ScorerProfile.LEGACY == "legacy"
        assert ScorerProfile.OFFICIAL_TEMPLATE_V2 == "official_template_v2"

    def test_is_str_enum(self):
        assert isinstance(ScorerProfile.LEGACY, str)
        assert isinstance(ScorerProfile.OFFICIAL_TEMPLATE_V2, str)

    def test_exactly_two_members(self):
        members = list(ScorerProfile)
        assert len(members) == 2


# ── ProfileConfig ──────────────────────────────────────────────────────


class TestProfileConfig:
    def test_frozen(self):
        p = get_legacy_profile()
        with pytest.raises(AttributeError):
            p.brand_fonts = ("Comic Sans",)  # type: ignore[misc]

    def test_fields_present(self):
        p = get_legacy_profile()
        assert hasattr(p, "profile")
        assert hasattr(p, "brand_fonts")
        assert hasattr(p, "heading_fonts")
        assert hasattr(p, "body_font_min_pt")
        assert hasattr(p, "body_font_max_pt")
        assert hasattr(p, "title_font_min_pt")
        assert hasattr(p, "title_font_max_pt")
        assert hasattr(p, "hard_floor_pt")
        assert hasattr(p, "overlap_severe_threshold_in")
        assert hasattr(p, "bounds_margin_left_min_in")
        assert hasattr(p, "enforce_template_fidelity")
        assert hasattr(p, "classify_template_native_decorative")
        assert hasattr(p, "header_color_hex")


# ── Profile dispatch ──────────────────────────────────────────────────


class TestGetProfile:
    def test_dispatch_legacy(self):
        p = get_profile(ScorerProfile.LEGACY)
        assert p.profile == ScorerProfile.LEGACY

    def test_dispatch_v2(self):
        p = get_profile(ScorerProfile.OFFICIAL_TEMPLATE_V2)
        assert p.profile == ScorerProfile.OFFICIAL_TEMPLATE_V2

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError, match="Unknown scorer profile"):
            get_profile("nonexistent")  # type: ignore[arg-type]

    def test_convenience_legacy(self):
        p = get_legacy_profile()
        assert p is get_profile(ScorerProfile.LEGACY)

    def test_convenience_v2(self):
        p = get_v2_profile()
        assert p is get_profile(ScorerProfile.OFFICIAL_TEMPLATE_V2)


# ── Legacy profile pinned values (CRITICAL: no drift allowed) ─────────


class TestLegacyProfilePinned:
    """Every value in the legacy profile is pinned.

    If ANY assertion here fails, it means a global threshold change
    leaked into the legacy profile — a cross-contamination bug.
    """

    def setup_method(self):
        self.p = get_legacy_profile()

    def test_brand_fonts(self):
        assert self.p.brand_fonts == ("Aptos",)

    def test_heading_fonts(self):
        assert self.p.heading_fonts == ("Aptos Display",)

    def test_body_font_min_pt(self):
        assert self.p.body_font_min_pt == 10.0

    def test_body_font_max_pt(self):
        assert self.p.body_font_max_pt == 14.0

    def test_title_font_min_pt(self):
        assert self.p.title_font_min_pt == 18.0

    def test_title_font_max_pt(self):
        assert self.p.title_font_max_pt == 36.0

    def test_hard_floor_pt(self):
        assert self.p.hard_floor_pt == 10.0

    def test_overlap_severe_threshold(self):
        assert self.p.overlap_severe_threshold_in == 0.15

    def test_bounds_margin_left_min(self):
        assert self.p.bounds_margin_left_min_in == 0.5

    def test_no_template_fidelity(self):
        assert self.p.enforce_template_fidelity is False

    def test_no_decorative_classification(self):
        assert self.p.classify_template_native_decorative is False

    def test_header_color(self):
        assert self.p.header_color_hex == "333333"


# ── Template-v2 profile values ─────────────────────────────────────────


class TestV2Profile:
    def setup_method(self):
        self.p = get_v2_profile()

    def test_brand_fonts_euclid(self):
        assert self.p.brand_fonts == ("Euclid Flex",)

    def test_heading_fonts_euclid(self):
        assert self.p.heading_fonts == ("Euclid Flex",)

    def test_body_font_range_9_to_12(self):
        assert self.p.body_font_min_pt == 9.0
        assert self.p.body_font_max_pt == 12.0

    def test_title_font_range_18_to_28(self):
        assert self.p.title_font_min_pt == 18.0
        assert self.p.title_font_max_pt == 28.0

    def test_hard_floor_9pt(self):
        assert self.p.hard_floor_pt == 9.0

    def test_left_margin_0_82(self):
        assert self.p.bounds_margin_left_min_in == 0.82

    def test_template_fidelity_enabled(self):
        assert self.p.enforce_template_fidelity is True

    def test_decorative_classification_enabled(self):
        assert self.p.classify_template_native_decorative is True

    def test_header_color_navy(self):
        assert self.p.header_color_hex == "0E2841"


# ── No cross-contamination ────────────────────────────────────────────


class TestNoCrossContamination:
    """Verify that v2 profile values differ from legacy where expected,
    and that legacy values are never affected by v2 changes."""

    def test_brand_fonts_differ(self):
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy.brand_fonts != v2.brand_fonts

    def test_body_font_ranges_differ(self):
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy.body_font_min_pt != v2.body_font_min_pt
        assert legacy.body_font_max_pt != v2.body_font_max_pt

    def test_hard_floors_differ(self):
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy.hard_floor_pt != v2.hard_floor_pt

    def test_header_colors_differ(self):
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy.header_color_hex != v2.header_color_hex

    def test_fidelity_rules_differ(self):
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy.enforce_template_fidelity != v2.enforce_template_fidelity

    def test_overlap_thresholds_v2_accommodates_template_design(self):
        """v2 uses a higher overlap threshold to accommodate template-native
        overlapping placeholders (the official .potx uses intentional overlap
        for visual design in case-study, team-bio, and other layouts)."""
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        # v2 must be >= legacy (never stricter than legacy for overlap)
        assert v2.overlap_severe_threshold_in >= legacy.overlap_severe_threshold_in
        # v2 threshold accommodates template design (~1.0in max overlap)
        assert v2.overlap_severe_threshold_in == 2.0

    def test_dispatch_returns_different_objects(self):
        legacy = get_profile(ScorerProfile.LEGACY)
        v2 = get_profile(ScorerProfile.OFFICIAL_TEMPLATE_V2)
        assert legacy is not v2

    def test_legacy_identity_stable(self):
        """Calling get_legacy_profile() twice returns the same object."""
        a = get_legacy_profile()
        b = get_legacy_profile()
        assert a is b

    def test_v2_identity_stable(self):
        """Calling get_v2_profile() twice returns the same object."""
        a = get_v2_profile()
        b = get_v2_profile()
        assert a is b

    def test_legacy_unaffected_after_v2_access(self):
        """Accessing v2 profile does not mutate legacy profile."""
        legacy_before = get_legacy_profile()
        _ = get_v2_profile()
        legacy_after = get_legacy_profile()
        assert legacy_before is legacy_after
        assert legacy_before.brand_fonts == ("Aptos",)
        assert legacy_before.body_font_min_pt == 10.0


# ══════════════════════════════════════════════════════════════════════
# INTEGRATION: composition_scorer actually dispatches by profile
# ══════════════════════════════════════════════════════════════════════


def _shape(
    font_name: str = "Aptos",
    font_size_pt: float = 11.0,
    left_in: float = 1.0,
    text: str = "Sample text content",
    **kwargs,
) -> ShapeInfo:
    """Convenience helper to build a ShapeInfo for testing."""
    defaults = dict(
        slide_index=0, slide_id="slide_0", shape_name="TestShape",
        shape_type="placeholder", top_in=2.0, width_in=8.0, height_in=1.0,
        is_placeholder=True, placeholder_idx=0,
    )
    defaults.update(kwargs)
    return ShapeInfo(
        font_name=font_name, font_size_pt=font_size_pt,
        left_in=left_in, text=text, **defaults,
    )


# ── score_composition dispatches by profile ───────────────────────────


class TestScorerDispatchesByProfile:
    """Prove that score_composition() actually uses the profile parameter."""

    def test_default_profile_is_legacy(self):
        shapes = [_shape(font_name="Aptos", font_size_pt=11.0)]
        result = score_composition(shapes, [])
        assert result.profile_used == ScorerProfile.LEGACY

    def test_explicit_v2_profile_stored(self):
        shapes = [_shape(font_name="Euclid Flex", font_size_pt=10.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        assert result.profile_used == ScorerProfile.OFFICIAL_TEMPLATE_V2


# ── Brand font enforcement differs by profile ─────────────────────────


class TestBrandFontDispatch:
    """Prove that brand font checking uses profile-specific font lists."""

    def test_aptos_clean_under_legacy(self):
        """Aptos is the legacy brand font — no font_brand violation."""
        shapes = [_shape(font_name="Aptos", font_size_pt=11.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        font_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_brand"
        ]
        assert len(font_violations) == 0

    def test_aptos_flagged_under_v2(self):
        """Aptos is NOT the v2 brand font — should flag font_brand."""
        shapes = [_shape(font_name="Aptos", font_size_pt=10.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        font_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_brand"
        ]
        assert len(font_violations) > 0

    def test_euclid_clean_under_v2(self):
        """Euclid Flex is the v2 brand font — no font_brand violation."""
        shapes = [_shape(font_name="Euclid Flex", font_size_pt=10.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        font_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_brand"
        ]
        assert len(font_violations) == 0

    def test_euclid_flagged_under_legacy(self):
        """Euclid Flex is NOT the legacy brand font — should flag."""
        shapes = [_shape(font_name="Euclid Flex", font_size_pt=11.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        font_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_brand"
        ]
        assert len(font_violations) > 0


# ── Font size floor differs by profile ─────────────────────────────────


class TestFontSizeFloorDispatch:
    """Prove that hard_floor_pt differs between profiles."""

    def test_9pt_ok_under_v2(self):
        """9pt is valid under v2 (hard floor = 9pt)."""
        shapes = [_shape(font_name="Euclid Flex", font_size_pt=9.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        size_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_min_soft"
        ]
        assert len(size_violations) == 0

    def test_9pt_blocker_under_legacy(self):
        """9pt is below legacy hard floor (10pt) — should be a blocker."""
        shapes = [_shape(font_name="Aptos", font_size_pt=9.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        size_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_min_soft"
        ]
        assert len(size_violations) > 0
        assert size_violations[0].severity == ViolationSeverity.BLOCKER

    def test_10pt_ok_under_legacy(self):
        """10pt is at the legacy hard floor — no violation."""
        shapes = [_shape(font_name="Aptos", font_size_pt=10.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        size_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_min_soft"
        ]
        assert len(size_violations) == 0

    def test_8pt_blocker_under_both(self):
        """8pt is below both profiles' floors."""
        for profile in (ScorerProfile.LEGACY, ScorerProfile.OFFICIAL_TEMPLATE_V2):
            font = "Aptos" if profile == ScorerProfile.LEGACY else "Euclid Flex"
            shapes = [_shape(font_name=font, font_size_pt=8.0)]
            result = score_composition(shapes, [], profile=profile)
            size_violations = [
                v for s in result.slide_scores for v in s.violations
                if v.rule == "font_min_soft"
            ]
            assert len(size_violations) > 0, f"8pt should be blocker under {profile}"


# ── Left margin differs by profile ────────────────────────────────────


class TestLeftMarginDispatch:
    """Prove bounds_margin_left_min_in is profile-specific."""

    def test_0_6in_ok_under_legacy(self):
        """0.6in left is above legacy minimum (0.5in)."""
        shapes = [_shape(left_in=0.6)]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        margin_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "bounds_left_margin"
        ]
        assert len(margin_violations) == 0

    def test_0_6in_flagged_under_v2(self):
        """0.6in left is below v2 minimum (0.82in)."""
        shapes = [_shape(font_name="Euclid Flex", left_in=0.6)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        margin_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "bounds_left_margin"
        ]
        assert len(margin_violations) > 0

    def test_0_85in_ok_under_v2(self):
        """0.85in left is above v2 minimum (0.82in)."""
        shapes = [_shape(font_name="Euclid Flex", left_in=0.85)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        margin_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "bounds_left_margin"
        ]
        assert len(margin_violations) == 0


# ── Template fidelity only under v2 ───────────────────────────────────


class TestTemplateFidelityDispatch:
    """Prove template_fidelity rule only fires under v2 profile."""

    def _non_template_textbox(self) -> ShapeInfo:
        return _shape(
            shape_type="textbox", is_placeholder=False,
            shape_name="ProgrammaticBox", text="Some injected content here",
            top_in=3.0, left_in=1.0, width_in=5.0, height_in=1.0,
            font_name="Euclid Flex", font_size_pt=10.0,
        )

    def test_no_fidelity_check_under_legacy(self):
        """Legacy profile does not enforce template fidelity."""
        shapes = [self._non_template_textbox()]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        fidelity_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "template_fidelity"
        ]
        assert len(fidelity_violations) == 0

    def test_fidelity_check_fires_under_v2(self):
        """V2 profile detects non-template textboxes."""
        shapes = [self._non_template_textbox()]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        fidelity_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "template_fidelity"
        ]
        assert len(fidelity_violations) > 0

    def test_decorative_shapes_excluded_under_v2(self):
        """Template-native decorative elements don't trigger fidelity."""
        # Shape at very top = template chrome
        decorative = _shape(
            shape_type="textbox", is_placeholder=False,
            shape_name="HeaderBar", text="SG",
            top_in=0.1, left_in=0.0, width_in=13.0, height_in=0.2,
            font_name="Euclid Flex", font_size_pt=8.0,
        )
        shapes = [decorative]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        fidelity_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "template_fidelity"
        ]
        assert len(fidelity_violations) == 0


# ── Overlap strictness same for both profiles ─────────────────────────


class TestOverlapStrictness:
    """Overlap detection uses profile-specific thresholds.

    Legacy threshold: 0.15in (strict — shapes are code-generated).
    V2 threshold: 2.0in (lenient — all shapes are template-native,
    official .potx uses intentionally overlapping placeholders).
    """

    def _moderate_overlap_shapes(self) -> list[ShapeInfo]:
        """Shapes with 0.50in overlap — above legacy, below v2 threshold."""
        a = _shape(
            shape_name="ShapeA", top_in=2.0, height_in=1.5,
            left_in=1.0, width_in=5.0,
        )
        b = _shape(
            shape_name="ShapeB", top_in=3.0, height_in=1.5,
            left_in=1.0, width_in=5.0,
        )
        return [a, b]

    def _extreme_overlap_shapes(self) -> list[ShapeInfo]:
        """Shapes with 2.5in overlap — above both thresholds."""
        a = _shape(
            shape_name="ShapeA", top_in=1.0, height_in=3.0,
            left_in=1.0, width_in=5.0,
        )
        b = _shape(
            shape_name="ShapeB", top_in=1.5, height_in=3.0,
            left_in=1.0, width_in=5.0,
        )
        return [a, b]

    def test_moderate_overlap_detected_under_legacy(self):
        shapes = self._moderate_overlap_shapes()
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        overlap = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "overlap_severe"
        ]
        assert len(overlap) > 0

    def test_moderate_overlap_not_detected_under_v2(self):
        """Template-native moderate overlaps pass under v2 threshold."""
        shapes = self._moderate_overlap_shapes()
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        overlap = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "overlap_severe"
        ]
        assert len(overlap) == 0

    def test_extreme_overlap_detected_under_v2(self):
        """Extreme overlaps (> 2.0in) still caught under v2."""
        shapes = self._extreme_overlap_shapes()
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        overlap = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "overlap_severe"
        ]
        assert len(overlap) > 0

    def test_v2_threshold_higher_than_legacy(self):
        """V2 threshold is intentionally higher to accommodate template design."""
        legacy_cfg = get_profile(ScorerProfile.LEGACY)
        v2_cfg = get_profile(ScorerProfile.OFFICIAL_TEMPLATE_V2)
        assert v2_cfg.overlap_severe_threshold_in > legacy_cfg.overlap_severe_threshold_in


# ── CompositionResult data model ──────────────────────────────────────


class TestCompositionResultModel:
    def test_blocker_count(self):
        v = Violation(rule="font_min_soft", message="too small",
                      severity=ViolationSeverity.BLOCKER, slide_id="s0")
        ss = SlideScore(slide_id="s0", violations=(v,))
        r = CompositionResult(slide_scores=(ss,))
        assert r.blocker_count == 1

    def test_total_violations(self):
        v1 = Violation(rule="r1", message="m1", severity=ViolationSeverity.WARNING)
        v2 = Violation(rule="r2", message="m2", severity=ViolationSeverity.BLOCKER)
        ss = SlideScore(slide_id="s0", violations=(v1, v2))
        r = CompositionResult(slide_scores=(ss,))
        assert r.total_violations == 2

    def test_empty_result(self):
        r = CompositionResult()
        assert r.blocker_count == 0
        assert r.total_violations == 0

    def test_frozen_shape_info(self):
        s = _shape()
        with pytest.raises(AttributeError):
            s.font_name = "X"  # type: ignore[misc]

    def test_frozen_violation(self):
        v = Violation(rule="r", message="m", severity=ViolationSeverity.INFO)
        with pytest.raises(AttributeError):
            v.rule = "x"  # type: ignore[misc]
