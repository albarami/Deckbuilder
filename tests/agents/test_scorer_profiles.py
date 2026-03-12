"""Tests for Phase 14 — scorer_profiles.py.

Tests renderer-mode-aware scorer profile dispatch, legacy profile
immutability, template-v2 profile isolation, and no cross-contamination.

Critical invariant: legacy profile values are **pinned** — any change
is a cross-contamination bug.
"""

from __future__ import annotations

import pytest

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

    def test_overlap_thresholds_same_strictness(self):
        """v2 uses same overlap strictness as legacy — no leniency."""
        legacy = get_legacy_profile()
        v2 = get_v2_profile()
        assert legacy.overlap_severe_threshold_in == v2.overlap_severe_threshold_in

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
