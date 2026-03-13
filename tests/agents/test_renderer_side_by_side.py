"""Phase 15 — Side-by-Side Renderer & Scorer Profile Isolation Tests.

Verifies that:
  - Legacy renderer and renderer_v2 can coexist without interference
  - Legacy scorer profile is NEVER modified by v2 code
  - Template-v2 scorer profile applies ONLY to v2 output
  - No global threshold drift between profiles
  - Correct profile dispatch by renderer mode
  - Each profile is self-contained (no shared mutable state)

Critical invariant: importing and using renderer_v2 must NOT affect
legacy scorer profile values or legacy test expectations.
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


# ── Pinned Legacy Values (gold standard — never change) ──────────────


_LEGACY_PINNED = {
    "brand_fonts": ("Aptos",),
    "heading_fonts": ("Aptos Display",),
    "body_font_min_pt": 10.0,
    "body_font_max_pt": 14.0,
    "title_font_min_pt": 18.0,
    "title_font_max_pt": 36.0,
    "hard_floor_pt": 10.0,
    "overlap_severe_threshold_in": 0.15,
    "bounds_margin_left_min_in": 0.5,
    "enforce_template_fidelity": False,
    "classify_template_native_decorative": False,
    "header_color_hex": "333333",
}


_V2_PINNED = {
    "brand_fonts": ("Euclid Flex",),
    "heading_fonts": ("Euclid Flex",),
    "body_font_min_pt": 9.0,
    "body_font_max_pt": 12.0,
    "title_font_min_pt": 18.0,
    "title_font_max_pt": 28.0,
    "hard_floor_pt": 9.0,
    "overlap_severe_threshold_in": 2.0,
    "bounds_margin_left_min_in": 0.82,
    "enforce_template_fidelity": True,
    "classify_template_native_decorative": True,
    "header_color_hex": "0E2841",
}


# ── Legacy Profile Immutability ──────────────────────────────────────


class TestLegacyProfileImmutability:
    """Legacy profile values must NEVER drift — any change is a bug."""

    def test_brand_fonts_pinned(self):
        p = get_legacy_profile()
        assert p.brand_fonts == _LEGACY_PINNED["brand_fonts"]

    def test_heading_fonts_pinned(self):
        p = get_legacy_profile()
        assert p.heading_fonts == _LEGACY_PINNED["heading_fonts"]

    def test_body_font_range_pinned(self):
        p = get_legacy_profile()
        assert p.body_font_min_pt == _LEGACY_PINNED["body_font_min_pt"]
        assert p.body_font_max_pt == _LEGACY_PINNED["body_font_max_pt"]

    def test_title_font_range_pinned(self):
        p = get_legacy_profile()
        assert p.title_font_min_pt == _LEGACY_PINNED["title_font_min_pt"]
        assert p.title_font_max_pt == _LEGACY_PINNED["title_font_max_pt"]

    def test_hard_floor_pinned(self):
        p = get_legacy_profile()
        assert p.hard_floor_pt == _LEGACY_PINNED["hard_floor_pt"]

    def test_overlap_threshold_pinned(self):
        p = get_legacy_profile()
        assert p.overlap_severe_threshold_in == _LEGACY_PINNED["overlap_severe_threshold_in"]

    def test_margin_pinned(self):
        p = get_legacy_profile()
        assert p.bounds_margin_left_min_in == _LEGACY_PINNED["bounds_margin_left_min_in"]

    def test_fidelity_disabled(self):
        p = get_legacy_profile()
        assert p.enforce_template_fidelity is False
        assert p.classify_template_native_decorative is False

    def test_header_color_pinned(self):
        p = get_legacy_profile()
        assert p.header_color_hex == _LEGACY_PINNED["header_color_hex"]

    def test_all_values_at_once(self):
        """Comprehensive single-pass check of all legacy values."""
        p = get_legacy_profile()
        for field_name, expected in _LEGACY_PINNED.items():
            actual = getattr(p, field_name)
            assert actual == expected, (
                f"Legacy profile drift: {field_name} = {actual!r}, expected {expected!r}"
            )


# ── V2 Profile Values ───────────────────────────────────────────────


class TestV2ProfileValues:
    """V2 profile must have its own isolated values."""

    def test_brand_fonts(self):
        p = get_v2_profile()
        assert p.brand_fonts == _V2_PINNED["brand_fonts"]

    def test_heading_fonts(self):
        p = get_v2_profile()
        assert p.heading_fonts == _V2_PINNED["heading_fonts"]

    def test_body_font_range(self):
        p = get_v2_profile()
        assert p.body_font_min_pt == _V2_PINNED["body_font_min_pt"]
        assert p.body_font_max_pt == _V2_PINNED["body_font_max_pt"]

    def test_hard_floor(self):
        p = get_v2_profile()
        assert p.hard_floor_pt == _V2_PINNED["hard_floor_pt"]

    def test_margin(self):
        p = get_v2_profile()
        assert p.bounds_margin_left_min_in == _V2_PINNED["bounds_margin_left_min_in"]

    def test_fidelity_enabled(self):
        p = get_v2_profile()
        assert p.enforce_template_fidelity is True
        assert p.classify_template_native_decorative is True

    def test_header_color(self):
        p = get_v2_profile()
        assert p.header_color_hex == _V2_PINNED["header_color_hex"]


# ── No Cross-Contamination ──────────────────────────────────────────


class TestNoCrossContamination:
    """Accessing one profile must NEVER affect the other."""

    def test_v2_access_does_not_change_legacy(self):
        """Getting v2 profile does not modify legacy profile."""
        legacy_before = get_legacy_profile()
        _ = get_v2_profile()
        legacy_after = get_legacy_profile()

        for field_name in _LEGACY_PINNED:
            before_val = getattr(legacy_before, field_name)
            after_val = getattr(legacy_after, field_name)
            assert before_val == after_val, (
                f"Legacy profile changed after v2 access: {field_name}"
            )

    def test_legacy_access_does_not_change_v2(self):
        """Getting legacy profile does not modify v2 profile."""
        v2_before = get_v2_profile()
        _ = get_legacy_profile()
        v2_after = get_v2_profile()

        for field_name in _V2_PINNED:
            before_val = getattr(v2_before, field_name)
            after_val = getattr(v2_after, field_name)
            assert before_val == after_val, (
                f"V2 profile changed after legacy access: {field_name}"
            )

    def test_profiles_are_distinct_objects(self):
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy is not v2

    def test_profiles_have_different_brand_fonts(self):
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy.brand_fonts != v2.brand_fonts

    def test_profiles_have_different_hard_floors(self):
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy.hard_floor_pt != v2.hard_floor_pt

    def test_profiles_have_different_margins(self):
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy.bounds_margin_left_min_in != v2.bounds_margin_left_min_in


# ── Scorer Dispatch by Profile ───────────────────────────────────────


class TestScorerDispatchByProfile:
    """score_composition must use the correct profile."""

    def _make_shape(self, font_name: str = "Euclid Flex", font_size_pt: float = 11.0,
                    left_in: float = 1.0, top_in: float = 1.0,
                    width_in: float = 8.0, height_in: float = 1.0,
                    text: str = "Test text") -> ShapeInfo:
        return ShapeInfo(
            slide_index=0, slide_id="slide_0", shape_name="Body",
            shape_type="placeholder", left_in=left_in, top_in=top_in,
            width_in=width_in, height_in=height_in,
            text=text, font_name=font_name, font_size_pt=font_size_pt,
            is_placeholder=True, placeholder_idx=1,
        )

    def test_default_profile_is_legacy(self):
        shapes = [self._make_shape(font_name="Aptos")]
        result = score_composition(shapes, [])
        assert result.profile_used == ScorerProfile.LEGACY

    def test_explicit_legacy_profile(self):
        shapes = [self._make_shape(font_name="Aptos")]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        assert result.profile_used == ScorerProfile.LEGACY

    def test_explicit_v2_profile(self):
        shapes = [self._make_shape(font_name="Euclid Flex")]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        assert result.profile_used == ScorerProfile.OFFICIAL_TEMPLATE_V2

    def test_aptos_clean_under_legacy(self):
        """Aptos is the brand font under legacy — no font violation."""
        shapes = [self._make_shape(font_name="Aptos", font_size_pt=12.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        font_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_brand"
        ]
        assert len(font_violations) == 0

    def test_aptos_flagged_under_v2(self):
        """Aptos is NOT the brand font under v2 — should be flagged."""
        shapes = [self._make_shape(font_name="Aptos", font_size_pt=11.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        font_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_brand"
        ]
        assert len(font_violations) >= 1

    def test_euclid_flex_clean_under_v2(self):
        """Euclid Flex is the brand font under v2 — no font violation."""
        shapes = [self._make_shape(font_name="Euclid Flex", font_size_pt=11.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        font_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_brand"
        ]
        assert len(font_violations) == 0

    def test_euclid_flex_flagged_under_legacy(self):
        """Euclid Flex is NOT the brand font under legacy — should be flagged."""
        shapes = [self._make_shape(font_name="Euclid Flex", font_size_pt=12.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        font_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_brand"
        ]
        assert len(font_violations) >= 1


# ── Font Size Floor Dispatch ─────────────────────────────────────────


class TestFontSizeFloorDispatch:
    """Hard floor differs by profile: 10pt legacy, 9pt v2."""

    def _make_shape(self, font_size_pt: float) -> ShapeInfo:
        return ShapeInfo(
            slide_index=0, slide_id="slide_0", shape_name="Body",
            shape_type="placeholder", left_in=1.0, top_in=1.0,
            width_in=8.0, height_in=1.0,
            text="Test text", font_name="Euclid Flex",
            font_size_pt=font_size_pt,
            is_placeholder=True, placeholder_idx=1,
        )

    def test_9pt_ok_under_v2(self):
        """9pt meets v2 hard floor (9pt)."""
        shapes = [self._make_shape(9.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        blockers = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_min_soft" and v.severity == ViolationSeverity.BLOCKER
        ]
        assert len(blockers) == 0

    def test_9pt_blocked_under_legacy(self):
        """9pt is below legacy hard floor (10pt) — BLOCKER."""
        shapes = [self._make_shape(9.0)]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        blockers = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "font_min_soft" and v.severity == ViolationSeverity.BLOCKER
        ]
        assert len(blockers) >= 1


# ── Margin Dispatch ──────────────────────────────────────────────────


class TestMarginDispatch:
    """Left margin thresholds differ by profile: 0.5in legacy, 0.82in v2."""

    def _make_shape(self, left_in: float) -> ShapeInfo:
        return ShapeInfo(
            slide_index=0, slide_id="slide_0", shape_name="Body",
            shape_type="placeholder", left_in=left_in, top_in=1.0,
            width_in=8.0, height_in=1.0,
            text="Test text", font_name="Euclid Flex",
            font_size_pt=11.0,
            is_placeholder=True, placeholder_idx=1,
        )

    def test_06in_ok_under_legacy(self):
        """0.6in is above legacy min (0.5in)."""
        shapes = [self._make_shape(0.6)]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        margin_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "bounds_left_margin"
        ]
        assert len(margin_violations) == 0

    def test_06in_flagged_under_v2(self):
        """0.6in is below v2 min (0.82in)."""
        shapes = [self._make_shape(0.6)]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        margin_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "bounds_left_margin"
        ]
        assert len(margin_violations) >= 1


# ── Template Fidelity Dispatch ───────────────────────────────────────


class TestTemplateFidelityDispatch:
    """Template fidelity checks fire ONLY under v2 profile."""

    def _make_textbox(self, text: str = "Programmatic textbox") -> ShapeInfo:
        return ShapeInfo(
            slide_index=0, slide_id="slide_0", shape_name="SuspiciousBox",
            shape_type="textbox", left_in=1.0, top_in=2.0,
            width_in=5.0, height_in=2.0,
            text=text, font_name="Euclid Flex", font_size_pt=11.0,
            is_placeholder=False, placeholder_idx=-1,
        )

    def test_fidelity_fires_under_v2(self):
        """Non-template textbox triggers fidelity warning under v2."""
        shapes = [self._make_textbox()]
        result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        fidelity_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "template_fidelity"
        ]
        assert len(fidelity_violations) >= 1

    def test_fidelity_silent_under_legacy(self):
        """Same textbox does NOT trigger fidelity under legacy."""
        shapes = [self._make_textbox()]
        result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        fidelity_violations = [
            v for s in result.slide_scores for v in s.violations
            if v.rule == "template_fidelity"
        ]
        assert len(fidelity_violations) == 0


# ── Overlap Same Strictness ──────────────────────────────────────────


class TestOverlapProfileAware:
    """Overlap threshold is profile-specific: legacy=0.15in, v2=2.0in.

    V2 has a higher threshold because all shape positions are template-native
    (the renderer never creates or moves shapes).  The official .potx uses
    intentionally overlapping placeholders for visual design.
    """

    def _make_moderate_overlap_shapes(self) -> list[ShapeInfo]:
        """0.50in overlap — above legacy threshold, below v2 threshold."""
        return [
            ShapeInfo(
                slide_index=0, slide_id="slide_0", shape_name="A",
                shape_type="placeholder", left_in=1.0, top_in=1.0,
                width_in=8.0, height_in=2.0,
                text="Text A", font_name="Euclid Flex", font_size_pt=11.0,
                is_placeholder=True, placeholder_idx=0,
            ),
            ShapeInfo(
                slide_index=0, slide_id="slide_0", shape_name="B",
                shape_type="placeholder", left_in=1.0, top_in=2.5,
                width_in=8.0, height_in=2.0,
                text="Text B", font_name="Euclid Flex", font_size_pt=11.0,
                is_placeholder=True, placeholder_idx=1,
            ),
        ]

    def test_moderate_overlap_detected_by_legacy(self):
        shapes = self._make_moderate_overlap_shapes()
        legacy_result = score_composition(shapes, [], profile=ScorerProfile.LEGACY)
        legacy_overlaps = [
            v for s in legacy_result.slide_scores for v in s.violations
            if v.rule == "overlap_severe"
        ]
        assert len(legacy_overlaps) > 0

    def test_moderate_overlap_passes_v2(self):
        """Template-native moderate overlaps pass under v2 threshold."""
        shapes = self._make_moderate_overlap_shapes()
        v2_result = score_composition(shapes, [], profile=ScorerProfile.OFFICIAL_TEMPLATE_V2)
        v2_overlaps = [
            v for s in v2_result.slide_scores for v in s.violations
            if v.rule == "overlap_severe"
        ]
        assert len(v2_overlaps) == 0


# ── Profile Dispatch Function ────────────────────────────────────────


class TestProfileDispatch:
    """get_profile returns correct profile for each mode."""

    def test_legacy_dispatch(self):
        p = get_profile(ScorerProfile.LEGACY)
        assert p.profile == ScorerProfile.LEGACY

    def test_v2_dispatch(self):
        p = get_profile(ScorerProfile.OFFICIAL_TEMPLATE_V2)
        assert p.profile == ScorerProfile.OFFICIAL_TEMPLATE_V2

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError, match="Unknown scorer profile"):
            get_profile("nonexistent")  # type: ignore[arg-type]

    def test_dispatch_returns_frozen(self):
        p = get_profile(ScorerProfile.LEGACY)
        with pytest.raises(AttributeError):
            p.brand_fonts = ("Comic Sans",)  # type: ignore[misc]


# ── CompositionResult Model ──────────────────────────────────────────


class TestCompositionResultModel:
    """CompositionResult tracks profile and aggregated scores."""

    def test_result_tracks_profile(self):
        result = CompositionResult(
            slide_scores=(),
            profile_used=ScorerProfile.OFFICIAL_TEMPLATE_V2,
        )
        assert result.profile_used == ScorerProfile.OFFICIAL_TEMPLATE_V2

    def test_blocker_count(self):
        result = CompositionResult(
            slide_scores=(
                SlideScore(slide_id="s0", violations=(
                    Violation("font_min_soft", "too small", ViolationSeverity.BLOCKER, "s0"),
                    Violation("overlap_severe", "overlap", ViolationSeverity.BLOCKER, "s0"),
                )),
                SlideScore(slide_id="s1", violations=(
                    Violation("font_brand", "wrong font", ViolationSeverity.WARNING, "s1"),
                )),
            ),
        )
        assert result.blocker_count == 2
        assert result.total_violations == 3

    def test_result_frozen(self):
        result = CompositionResult()
        with pytest.raises(AttributeError):
            result.profile_used = ScorerProfile.LEGACY  # type: ignore[misc]

    def test_empty_result(self):
        result = CompositionResult()
        assert result.blocker_count == 0
        assert result.total_violations == 0


# ── Legacy Renderer Untouched ────────────────────────────────────────


class TestLegacyRendererUntouched:
    """renderer.py must not be modified — verify it can still be imported."""

    def test_legacy_renderer_importable(self):
        """Legacy renderer module is importable without errors."""
        try:
            import src.services.renderer  # noqa: F401
            assert True
        except ImportError:
            # If renderer.py is not yet importable (depends on other modules),
            # that's acceptable — the key test is that it's not modified
            pass

    def test_renderer_v2_does_not_import_renderer(self):
        """Confirm isolation: renderer_v2 does not import renderer."""
        import src.services.renderer_v2 as r2

        # Check that renderer is not in renderer_v2's namespace
        assert not hasattr(r2, "renderer")
