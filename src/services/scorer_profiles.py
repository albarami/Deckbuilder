"""Phase 14 — Renderer-Mode-Aware Scorer Profiles.

Isolates composition-scorer configuration behind renderer mode so that
legacy scoring behavior is **completely unchanged** while template-v2
output uses its own font, size, and fidelity expectations.

Each profile is a frozen dataclass with all thresholds and brand rules.
The legacy profile's values are pinned — any drift is a test failure.

Profile dispatch:
  - ``get_profile(ScorerProfile.LEGACY)`` → legacy thresholds
  - ``get_profile(ScorerProfile.OFFICIAL_TEMPLATE_V2)`` → v2 thresholds
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


# ── Profile selector ───────────────────────────────────────────────────


class ScorerProfile(StrEnum):
    """Renderer mode that determines which scorer thresholds to use."""

    LEGACY = "legacy"
    OFFICIAL_TEMPLATE_V2 = "official_template_v2"


# ── Profile configuration ─────────────────────────────────────────────


@dataclass(frozen=True)
class ProfileConfig:
    """Immutable scorer configuration for one renderer mode.

    All thresholds, brand expectations, and rule toggles live here.
    No global state — each profile is self-contained.
    """

    profile: ScorerProfile

    # Brand fonts
    brand_fonts: tuple[str, ...]
    heading_fonts: tuple[str, ...]

    # Font size expectations (points)
    body_font_min_pt: float
    body_font_max_pt: float
    title_font_min_pt: float
    title_font_max_pt: float
    hard_floor_pt: float

    # Overlap / bounds thresholds (inches)
    overlap_severe_threshold_in: float
    bounds_margin_left_min_in: float

    # Template-fidelity rule (v2 only)
    enforce_template_fidelity: bool
    classify_template_native_decorative: bool

    # Header color expectation
    header_color_hex: str


# ── Pinned legacy profile ─────────────────────────────────────────────

# These values are frozen.  Any change to legacy defaults is a
# cross-contamination bug and must fail the explicit drift test.

_LEGACY_PROFILE = ProfileConfig(
    profile=ScorerProfile.LEGACY,
    brand_fonts=("Aptos",),
    heading_fonts=("Aptos Display",),
    body_font_min_pt=10.0,
    body_font_max_pt=14.0,
    title_font_min_pt=18.0,
    title_font_max_pt=36.0,
    hard_floor_pt=10.0,
    overlap_severe_threshold_in=0.15,
    bounds_margin_left_min_in=0.5,
    enforce_template_fidelity=False,
    classify_template_native_decorative=False,
    header_color_hex="333333",
)


# ── Template-v2 profile (new, isolated) ────────────────────────────────

_TEMPLATE_V2_PROFILE = ProfileConfig(
    profile=ScorerProfile.OFFICIAL_TEMPLATE_V2,
    brand_fonts=("Euclid Flex",),
    heading_fonts=("Euclid Flex",),
    body_font_min_pt=9.0,
    body_font_max_pt=12.0,
    title_font_min_pt=18.0,
    title_font_max_pt=28.0,
    hard_floor_pt=9.0,
    # Template-v2 uses a higher overlap threshold because all shape
    # positions are template-native — the renderer never creates or
    # moves shapes.  The official .potx uses intentionally overlapping
    # placeholders for visual design (e.g., case-study and team-bio
    # layouts with stacked text fields).  Threshold accommodates the
    # template's own max overlap (~1.0in) with headroom.
    overlap_severe_threshold_in=2.0,
    bounds_margin_left_min_in=0.82,
    enforce_template_fidelity=True,
    classify_template_native_decorative=True,
    header_color_hex="0E2841",
)


# ── Profile dispatch ──────────────────────────────────────────────────


def get_profile(mode: ScorerProfile) -> ProfileConfig:
    """Return the scorer profile configuration for *mode*.

    Fail-closed: unknown modes raise ValueError.
    """
    if mode == ScorerProfile.LEGACY:
        return _LEGACY_PROFILE
    if mode == ScorerProfile.OFFICIAL_TEMPLATE_V2:
        return _TEMPLATE_V2_PROFILE
    raise ValueError(f"Unknown scorer profile: '{mode}'")


def get_legacy_profile() -> ProfileConfig:
    """Convenience: return the legacy profile (never modified)."""
    return _LEGACY_PROFILE


def get_v2_profile() -> ProfileConfig:
    """Convenience: return the template-v2 profile."""
    return _TEMPLATE_V2_PROFILE
