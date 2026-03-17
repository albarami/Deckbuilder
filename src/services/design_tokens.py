"""Centralized design tokens for the DeckForge PPTX rendering engine.

This module is the SINGLE SOURCE OF TRUTH for all layout geometry,
typography, colors, margins, and thresholds used by formatting.py,
renderer.py, and components.py.

No new hardcoded layout numbers should be introduced outside this file.
All dimensions are in inches (converted to EMU at call site via Inches()).
All font sizes are in points (converted to EMU at call site via Pt()).
"""

from __future__ import annotations

from dataclasses import dataclass

from pptx.dml.color import RGBColor

from src.models.enums import DensityBudget, LayoutType

# ---------------------------------------------------------------------------
# Slide canvas
# ---------------------------------------------------------------------------
SLIDE_WIDTH_IN: float = 13.33
SLIDE_HEIGHT_IN: float = 7.5


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Palette:
    """Brand colors from Presentation6.pptx theme. Immutable."""

    # Primary brand
    NAVY: RGBColor = RGBColor(14, 40, 65)
    TEAL: RGBColor = RGBColor(21, 96, 130)
    ORANGE: RGBColor = RGBColor(233, 113, 50)
    GREEN: RGBColor = RGBColor(25, 107, 36)
    BLUE: RGBColor = RGBColor(15, 158, 213)
    DARK_TEAL: RGBColor = RGBColor(70, 120, 134)

    # Neutrals
    WHITE: RGBColor = RGBColor(255, 255, 255)
    LIGHT_GRAY: RGBColor = RGBColor(242, 242, 242)
    MID_GRAY: RGBColor = RGBColor(217, 217, 217)
    DARK_TEXT: RGBColor = RGBColor(51, 51, 51)

    # Status
    STATUS_GREEN: RGBColor = RGBColor(25, 107, 36)
    STATUS_AMBER: RGBColor = RGBColor(233, 113, 50)
    STATUS_RED: RGBColor = RGBColor(192, 57, 43)

    # Status backgrounds (pastel)
    STATUS_GREEN_BG: RGBColor = RGBColor(232, 245, 233)
    STATUS_AMBER_BG: RGBColor = RGBColor(255, 243, 224)
    STATUS_RED_BG: RGBColor = RGBColor(255, 235, 238)


COLORS = _Palette()


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Typography:
    """Font families and size constants in points. Immutable."""

    # Font families
    HEADING_FONT: str = "Aptos Display"
    BODY_FONT: str = "Aptos"

    # Title / heading sizes
    TITLE_BAR_PT: int = 22

    # Body / content sizes
    KEY_MESSAGE_PT: int = 14
    BODY_PT: int = 12
    BODY_SUB_PT: int = 11

    # Stat callout sizes
    STAT_BIG_PT: int = 54
    STAT_SUPPORT_PT: int = 16

    # Agenda sizes
    AGENDA_NUM_PT: int = 18
    AGENDA_TEXT_PT: int = 16

    # Table sizes
    TABLE_HEADER_PT: int = 12
    TABLE_BODY_PT: int = 11

    # Step / flow sizes
    STEP_NUM_PT: int = 20
    STEP_NAME_PT: int = 10
    STEP_DETAIL_PT: int = 13


TYPO = _Typography()


# ---------------------------------------------------------------------------
# Region helper
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Region:
    """A rectangular region on a slide, in inches."""

    left: float
    top: float
    width: float
    height: float


# ---------------------------------------------------------------------------
# Content layout
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _ContentLayout:
    """Standard content area dimensions from the template."""

    margin_left: float = 0.92
    margin_right: float = 0.92
    title_top: float = 0.4
    title_height: float = 1.45
    content_width: float = 11.5
    body_top: float = 2.0
    body_height: float = 4.76
    footer_top: float = 6.95
    footer_height: float = 0.4


CONTENT = _ContentLayout()

# Named regions
TITLE_BAR = Region(
    left=0.0,
    top=0.0,
    width=SLIDE_WIDTH_IN,
    height=0.85,
)

KEY_MESSAGE = Region(
    left=CONTENT.margin_left,
    top=1.55,
    width=CONTENT.content_width,
    height=0.4,
)

BODY_WITH_BAR = Region(
    left=CONTENT.margin_left,
    top=2.1,
    width=CONTENT.content_width,
    height=4.6,
)

STAT_CALLOUT = Region(
    left=1.5,
    top=2.2,
    width=10.0,
    height=4.5,
)

CHART = Region(
    left=1.5,
    top=2.0,
    width=8.0,
    height=4.5,
)

AGENDA = Region(
    left=0.92,
    top=2.0,
    width=8.0,
    height=4.5,
)

FRAMEWORK_FALLBACK = Region(
    left=0.92,
    top=2.2,
    width=11.5,
    height=4.5,
)

BODY_FALLBACK = Region(
    left=CONTENT.margin_left,
    top=CONTENT.body_top,
    width=CONTENT.content_width,
    height=CONTENT.body_height,
)


# ---------------------------------------------------------------------------
# Table tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _TableTokens:
    """Table rendering dimensions and proportions."""

    default_left: float = 0.92
    default_top: float = 2.0
    default_width: float = 11.5

    pipe_row_height: float = 0.38
    styled_row_height: float = 0.4

    # Cell margins in EMU
    cell_margin_top: int = 54000
    cell_margin_bottom: int = 54000
    cell_margin_left: int = 91440
    cell_margin_right: int = 91440

    # Column proportions
    min_col_proportion: float = 0.08
    max_col_proportion: float = 0.5
    label_col_proportion: float = 0.3

    # Border
    border_width: int = 6350


TABLE = _TableTokens()


# ---------------------------------------------------------------------------
# Flow tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _FlowTokens:
    """Process flow step-box rendering dimensions."""

    available_width: float = 11.0
    arrow_gap: float = 0.35
    box_height: float = 0.75
    max_box_width: float = 2.5
    max_steps: int = 6
    start_x_offset: float = 0.92
    top_y: float = 2.2
    detail_gap: float = 0.4
    detail_height: float = 3.5
    min_key_detail_pairs: int = 3

    # Tier layout
    min_tier_count: int = 3
    tier_box_height: float = 1.2
    tier_gap_y: float = 0.2
    tier_top: float = 2.2
    tier_left: float = 0.92
    tier_available_width: float = 11.5
    tier_name_pt: int = 12
    tier_detail_pt: int = 10


FLOW = _FlowTokens()


# ---------------------------------------------------------------------------
# Spacing
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Spacing:
    """Paragraph and element spacing in points."""

    stat_after_big_pt: int = 24
    stat_after_support_pt: int = 6
    agenda_after_pt: int = 8
    body_after_pt: int = 4
    detail_after_pt: int = 4


SPACING = _Spacing()


# ---------------------------------------------------------------------------
# Overflow thresholds
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _OverflowThresholds:
    """Content limits for overflow detection. Used by overflow.py."""

    max_chars_per_slide: int = 1200
    max_chars_per_bullet: int = 250
    max_bullets_per_slide: int = 8
    max_table_rows: int = 10
    font_reduction_step_pt: int = 2
    min_body_font_pt: int = 10
    min_table_font_pt: int = 9


OVERFLOW = _OverflowThresholds()


# ---------------------------------------------------------------------------
# Stat chip tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _StatChipTokens:
    """Stat chip rendering dimensions for STAT_CALLOUT visual layout."""

    # Chip row
    chip_top: float = 2.2
    chip_height: float = 1.1
    chip_gap: float = 0.3
    chip_left: float = 0.92
    chip_available_width: float = 11.5

    # Font sizes
    chip_number_pt: int = 40
    chip_label_pt: int = 13

    # Narrative row
    narrative_top: float = 3.5
    narrative_height: float = 0.6
    narrative_pt: int = 13

    # Support row
    support_top: float = 4.3
    support_height: float = 2.5
    support_pt: int = 13

    # Limits
    max_chips: int = 5
    min_pipe_stats: int = 2


STAT_CHIPS = _StatChipTokens()


# ---------------------------------------------------------------------------
# Team card tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _TeamCardTokens:
    """Team card grid rendering dimensions for TEAM visual layout."""

    # Grid positioning
    grid_top: float = 2.2
    grid_left: float = 0.92
    grid_available_width: float = 11.5
    card_gap_x: float = 0.25
    card_gap_y: float = 0.25
    card_height: float = 2.2
    header_bar_height: float = 0.45
    card_corner_radius: float = 0.08
    card_border_width: int = 6350

    # Font sizes
    role_pt: int = 12
    name_pt: int = 11
    quals_pt: int = 10

    # Limits
    max_cols: int = 3
    max_cards: int = 6
    min_cards_for_grid: int = 3

    # Internal padding
    body_pad_x: float = 0.1
    body_pad_top: float = 0.05
    role_text_pad: float = 0.02

    # Accent line
    accent_line_height: float = 0.05


TEAM_CARDS = _TeamCardTokens()


# ---------------------------------------------------------------------------
# Timeline tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _TimelineTokens:
    """Horizontal timeline bar rendering dimensions for TIMELINE visual layout."""

    # Bar
    bar_top: float = 2.5
    bar_height: float = 0.65
    bar_left: float = 0.92
    bar_available_width: float = 11.5

    # Font sizes
    phase_name_pt: int = 11
    duration_pt: int = 10
    detail_pt: int = 10
    detail_key_pt: int = 11

    # Duration labels
    duration_label_top: float = 2.15
    duration_label_height: float = 0.3

    # Detail cards
    detail_top: float = 3.4
    detail_card_height: float = 3.0

    # Support row
    support_top: float = 6.5
    support_height: float = 0.4
    support_pt: int = 10

    # Fallback
    table_fallback_top: float = 3.4

    # Limits
    max_phases: int = 6
    min_phases_for_visual: int = 3


TIMELINE_VIS = _TimelineTokens()


# ---------------------------------------------------------------------------
# Comparison tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _ComparisonTokens:
    """Comparison layout visual chrome dimensions (additive, non-obscuring)."""

    # Divider
    divider_x: float = 6.665
    divider_top: float = 2.1
    divider_height: float = 4.5
    divider_width: float = 0.02

    # Accent bars
    accent_bar_top: float = 2.0
    accent_bar_height: float = 0.04
    left_accent_left: float = 0.92
    left_accent_width: float = 5.5
    right_accent_left: float = 6.92
    right_accent_width: float = 5.5


COMPARISON_VIS = _ComparisonTokens()


# ---------------------------------------------------------------------------
# Closing layout tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _ClosingLayoutTokens:
    """Closing slide branded treatment tokens."""

    band_top_in: float = 0.0
    band_height_in: float = 2.8
    band_width_in: float = 13.33

    # Title
    title_top_in: float = 0.5
    title_left_in: float = 0.92
    title_width_in: float = 11.5
    title_height_in: float = 1.2
    title_pt: int = 28

    # Accent line
    accent_top_in: float = 2.8
    accent_height_in: float = 0.06
    accent_left_in: float = 0.92
    accent_width_in: float = 11.5

    # Message
    message_top_in: float = 3.1
    message_left_in: float = 0.92
    message_width_in: float = 11.5
    message_height_in: float = 0.6
    message_pt: int = 14

    # Body
    body_top_in: float = 3.9
    body_left_in: float = 0.92
    body_width_in: float = 11.5
    body_height_in: float = 2.8
    body_pt: int = 12

    # Subtitle
    subtitle_top_in: float = 4.0
    subtitle_height_in: float = 2.5


CLOSING_LAYOUT = _ClosingLayoutTokens()


# ---------------------------------------------------------------------------
# Cover layout tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _CoverLayoutTokens:
    """Title/cover slide metadata constraint tokens."""

    metadata_max_height_in: float = 0.6
    metadata_max_bottom_in: float = 6.8


COVER_LAYOUT = _CoverLayoutTokens()


# ---------------------------------------------------------------------------
# Two-column tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _TwoColTokens:
    """Two-column layout equalization tokens."""

    gutter_in: float = 0.3


TWO_COL = _TwoColTokens()


# ---------------------------------------------------------------------------
# Table enhancement tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _TableEnhancementTokens:
    """Enhanced table visual treatment tokens."""

    enhanced_row_height: float = 0.42
    header_row_height: float = 0.45


TABLE_ENHANCED = _TableEnhancementTokens()


# ---------------------------------------------------------------------------
# Archetype budgets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ArchetypeBudget:
    """Per-layout content budget. Immutable."""

    max_bullets: int
    max_chars_per_bullet: int
    max_chars_per_slide: int
    max_table_rows: int


_STANDARD_BUDGETS: dict[LayoutType, _ArchetypeBudget] = {
    LayoutType.TITLE: _ArchetypeBudget(5, 120, 400, 8),
    LayoutType.AGENDA: _ArchetypeBudget(10, 80, 800, 8),
    LayoutType.SECTION: _ArchetypeBudget(2, 120, 300, 8),
    LayoutType.CONTENT_1COL: _ArchetypeBudget(6, 200, 1000, 8),
    LayoutType.CONTENT_2COL: _ArchetypeBudget(8, 160, 1000, 8),
    LayoutType.DATA_CHART: _ArchetypeBudget(4, 180, 600, 8),
    LayoutType.FRAMEWORK: _ArchetypeBudget(6, 200, 900, 8),
    LayoutType.COMPARISON: _ArchetypeBudget(8, 160, 1000, 8),
    LayoutType.STAT_CALLOUT: _ArchetypeBudget(5, 120, 500, 8),
    LayoutType.TEAM: _ArchetypeBudget(6, 150, 800, 10),
    LayoutType.TIMELINE: _ArchetypeBudget(6, 180, 900, 10),
    LayoutType.COMPLIANCE_MATRIX: _ArchetypeBudget(4, 250, 1400, 10),
    LayoutType.CLOSING: _ArchetypeBudget(5, 120, 500, 8),
}

_DENSITY_MULTIPLIERS: dict[DensityBudget, float] = {
    DensityBudget.LIGHT: 0.6,
    DensityBudget.STANDARD: 1.0,
    DensityBudget.DENSE: 1.35,
}

_DEFAULT_BUDGET = _STANDARD_BUDGETS[LayoutType.CONTENT_1COL]


def get_archetype_budget(
    layout_type: LayoutType,
    density_budget: DensityBudget | None = None,
) -> _ArchetypeBudget:
    """Look up content budget for a layout + density tier.

    Falls back to STANDARD when density_budget is None.
    Falls back to CONTENT_1COL when layout_type is unknown.
    """
    base = _STANDARD_BUDGETS.get(layout_type, _DEFAULT_BUDGET)
    tier = density_budget or DensityBudget.STANDARD
    mult = _DENSITY_MULTIPLIERS[tier]

    if mult == 1.0:
        return base

    return _ArchetypeBudget(
        max_bullets=int(base.max_bullets * mult),
        max_chars_per_bullet=base.max_chars_per_bullet,
        max_chars_per_slide=int(base.max_chars_per_slide * mult),
        max_table_rows=base.max_table_rows,
    )


# ---------------------------------------------------------------------------
# Title-bar layout set
# ---------------------------------------------------------------------------
TITLE_BAR_LAYOUTS: frozenset[LayoutType] = frozenset({
    LayoutType.CONTENT_1COL,
    LayoutType.CONTENT_2COL,
    LayoutType.DATA_CHART,
    LayoutType.FRAMEWORK,
    LayoutType.COMPARISON,
    LayoutType.STAT_CALLOUT,
    LayoutType.TEAM,
    LayoutType.TIMELINE,
    LayoutType.COMPLIANCE_MATRIX,
})


# ---------------------------------------------------------------------------
# Composition thresholds
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _CompositionThresholds:
    """Thresholds for render-aware composition scoring."""

    # Overlap
    overlap_warning_pct: float = 5.0
    overlap_blocker_pct: float = 25.0
    min_shape_area_sq_in: float = 0.01

    # Decorative
    decorative_max_area_sq_in: float = 0.1
    footer_region_top_in: float = 6.95
    logo_region_top_max_in: float = 1.0
    logo_region_bottom_min_in: float = 7.0

    # Canvas
    slide_width_in: float = 13.33
    slide_height_in: float = 7.5

    # Font
    font_min_blocker_pt: int = 9
    font_min_warning_pt: int = 10
    max_body_font_sizes: int = 3
    brand_fonts: tuple[str, ...] = ("Aptos Display", "Aptos")

    # Margins
    margin_left_min_in: float = 0.7
    margin_right_max_in: float = 12.6

    # Content body
    content_body_top_min_in: float = 1.8

    # Framework
    framework_height_tolerance_in: float = 0.15
    framework_gap_tolerance_in: float = 0.15

    # Team card
    team_card_top_tolerance_in: float = 0.05
    team_card_width_tolerance_in: float = 0.3
    team_card_height_tolerance_in: float = 0.2

    # Stat chip
    stat_chip_gap_tolerance_in: float = 0.3

    # Timeline
    timeline_bar_top_tolerance_in: float = 0.3

    # Compliance
    compliance_table_top_min_in: float = 1.5
    compliance_table_top_max_in: float = 3.0
    compliance_table_min_width_in: float = 10.0


COMPOSITION = _CompositionThresholds()

ACCENT1_RGB = (21, 96, 130)
ACCENT2_RGB = (233, 113, 50)
