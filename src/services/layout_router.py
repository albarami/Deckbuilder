"""Phase 8 — Layout Router.

Maps SlideObject content types to semantic layout IDs from the catalog
lock.  Receives the SlideBudget as input context.  Never references raw
layout display names — all routing is by semantic layout ID only.

The router resolves:
- LayoutType enum values -> semantic layout IDs
- Section context -> appropriate layout variant
- Methodology phases -> blueprint-driven layout IDs
- Pool assets (case studies, team bios) -> their fixed semantic IDs

The router does NOT create slides.  It only determines WHICH semantic
layout ID each slide should use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.models.enums import LayoutType
from src.models.methodology_blueprint import MethodologyBlueprint, PhaseBlueprint
from src.services.slide_budgeter import SlideBudget


# ── Exceptions ──────────────────────────────────────────────────────────


class LayoutRoutingError(RuntimeError):
    """Raised when layout routing fails."""


# ── Routing result ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class RoutedLayout:
    """Result of routing a single slide to a semantic layout ID."""

    semantic_layout_id: str
    layout_type: LayoutType | None = None
    section_id: str = ""
    routing_reason: str = ""  # auditable reason for this choice


@dataclass(frozen=True)
class LayoutRoutingResult:
    """Complete routing result for all variable slides."""

    routed: tuple[RoutedLayout, ...] = ()
    errors: list[str] = field(default_factory=list)


# ── Layout type -> semantic layout ID mapping ───────────────────────────

# Default semantic layout IDs for each LayoutType.
# These are the general-purpose content layouts from the catalog lock.
_LAYOUT_TYPE_DEFAULTS: dict[LayoutType, str] = {
    LayoutType.TITLE: "content_heading_only",
    LayoutType.AGENDA: "toc_table",
    LayoutType.SECTION: "content_heading_only",
    LayoutType.CONTENT_1COL: "content_heading_desc",
    LayoutType.CONTENT_2COL: "content_heading_desc_box",
    LayoutType.DATA_CHART: "content_heading_content",
    LayoutType.FRAMEWORK: "content_heading_4boxes",
    LayoutType.COMPARISON: "content_heading_desc_box",
    LayoutType.STAT_CALLOUT: "content_heading_content",
    LayoutType.TEAM: "team_two_members",
    LayoutType.TIMELINE: "content_heading_content",
    LayoutType.COMPLIANCE_MATRIX: "content_heading_content",
    LayoutType.CLOSING: "contact",
}

# Pool asset semantic layout IDs (fixed by catalog lock)
CASE_STUDY_LAYOUTS: tuple[str, ...] = (
    "case_study_cases",
    "case_study_detailed",
)
TEAM_BIO_LAYOUT: str = "team_two_members"


# ── Routing functions ───────────────────────────────────────────────────


def route_layout_type(
    layout_type: LayoutType,
    *,
    section_id: str = "",
) -> RoutedLayout:
    """Route a LayoutType to its default semantic layout ID.

    Parameters
    ----------
    layout_type : LayoutType
        The slide's layout type from the legacy pipeline.
    section_id : str
        The proposal section this slide belongs to.

    Returns
    -------
    RoutedLayout
        Routing result with semantic layout ID and reason.

    Raises
    ------
    LayoutRoutingError
        If the layout type has no known mapping.
    """
    if layout_type not in _LAYOUT_TYPE_DEFAULTS:
        raise LayoutRoutingError(
            f"No default layout mapping for LayoutType '{layout_type}'"
        )

    semantic_id = _LAYOUT_TYPE_DEFAULTS[layout_type]
    return RoutedLayout(
        semantic_layout_id=semantic_id,
        layout_type=layout_type,
        section_id=section_id,
        routing_reason=f"default mapping for {layout_type}",
    )


def route_methodology_phase(
    phase: PhaseBlueprint,
    *,
    slide_role: str = "focused",
) -> RoutedLayout:
    """Route a methodology phase to its semantic layout ID.

    Parameters
    ----------
    phase : PhaseBlueprint
        The methodology phase blueprint.
    slide_role : str
        Which role: "overview", "focused", or "detail".

    Returns
    -------
    RoutedLayout

    Raises
    ------
    LayoutRoutingError
        If the slide_role is invalid or no layout available.
    """
    if slide_role == "overview":
        layout_id = phase.overview_layout
    elif slide_role == "focused":
        if not phase.focused_layouts:
            raise LayoutRoutingError(
                f"Phase {phase.phase_id} has no focused layouts"
            )
        layout_id = phase.focused_layouts[0]
    elif slide_role == "detail":
        if not phase.detail_layouts:
            raise LayoutRoutingError(
                f"Phase {phase.phase_id} has no detail layouts"
            )
        layout_id = phase.detail_layouts[0]
    else:
        raise LayoutRoutingError(
            f"Invalid slide_role '{slide_role}'; must be 'overview', "
            f"'focused', or 'detail'"
        )

    return RoutedLayout(
        semantic_layout_id=layout_id,
        section_id="section_03",
        routing_reason=f"methodology {slide_role} for {phase.phase_id}",
    )


def route_pool_asset(
    asset_type: str,
    *,
    section_id: str = "",
    layout_variant: str = "",
) -> RoutedLayout:
    """Route a pool asset (case study or team bio) to its layout.

    Parameters
    ----------
    asset_type : str
        "case_study" or "team_bio".
    section_id : str
        The proposal section.
    layout_variant : str
        For case studies: "cases" or "detailed" (default: "detailed").

    Returns
    -------
    RoutedLayout

    Raises
    ------
    LayoutRoutingError
        If the asset_type is unknown.
    """
    if asset_type == "case_study":
        variant = layout_variant or "detailed"
        if variant == "cases":
            layout_id = "case_study_cases"
        elif variant == "detailed":
            layout_id = "case_study_detailed"
        else:
            raise LayoutRoutingError(
                f"Unknown case study variant '{variant}'; "
                f"must be 'cases' or 'detailed'"
            )
        return RoutedLayout(
            semantic_layout_id=layout_id,
            section_id=section_id,
            routing_reason=f"case study pool asset ({variant})",
        )
    elif asset_type == "team_bio":
        return RoutedLayout(
            semantic_layout_id=TEAM_BIO_LAYOUT,
            section_id=section_id,
            routing_reason="team bio pool asset",
        )
    else:
        raise LayoutRoutingError(
            f"Unknown pool asset type '{asset_type}'; "
            f"must be 'case_study' or 'team_bio'"
        )


def route_variable_slides(
    slide_specs: list[dict[str, Any]],
    budget: SlideBudget,
    methodology_blueprint: MethodologyBlueprint | None = None,
) -> LayoutRoutingResult:
    """Route a batch of variable slide specifications to semantic layout IDs.

    Each spec dict should have:
    - ``layout_type``: LayoutType enum value (for B variable slides)
    - ``section_id``: which section the slide belongs to
    - ``asset_type``: "case_study" or "team_bio" (for pool assets)
    - ``methodology_phase``: phase_id (for methodology slides)
    - ``slide_role``: "overview"/"focused"/"detail" (for methodology)

    Parameters
    ----------
    slide_specs : list[dict]
        Slide specifications to route.
    budget : SlideBudget
        The computed slide budget (used for validation context).
    methodology_blueprint : MethodologyBlueprint, optional
        Required if any specs reference methodology phases.

    Returns
    -------
    LayoutRoutingResult
        Tuple of routed layouts and any errors.
    """
    routed: list[RoutedLayout] = []
    errors: list[str] = []

    # Index methodology phases by phase_id for lookup
    phase_map: dict[str, PhaseBlueprint] = {}
    if methodology_blueprint:
        for phase in methodology_blueprint.phases:
            phase_map[phase.phase_id] = phase

    for i, spec in enumerate(slide_specs):
        try:
            section_id = spec.get("section_id", "")

            if "asset_type" in spec:
                # Pool asset routing
                result = route_pool_asset(
                    spec["asset_type"],
                    section_id=section_id,
                    layout_variant=spec.get("layout_variant", ""),
                )
                routed.append(result)

            elif "methodology_phase" in spec:
                # Methodology routing
                phase_id = spec["methodology_phase"]
                if phase_id not in phase_map:
                    errors.append(
                        f"Spec {i}: methodology phase '{phase_id}' "
                        f"not in blueprint"
                    )
                    continue
                result = route_methodology_phase(
                    phase_map[phase_id],
                    slide_role=spec.get("slide_role", "focused"),
                )
                routed.append(result)

            elif "layout_type" in spec:
                # Standard layout type routing
                layout_type = spec["layout_type"]
                if isinstance(layout_type, str):
                    layout_type = LayoutType(layout_type)
                result = route_layout_type(
                    layout_type,
                    section_id=section_id,
                )
                routed.append(result)

            else:
                errors.append(
                    f"Spec {i}: missing 'layout_type', 'asset_type', "
                    f"or 'methodology_phase'"
                )

        except (LayoutRoutingError, ValueError) as exc:
            errors.append(f"Spec {i}: {exc}")

    return LayoutRoutingResult(
        routed=tuple(routed),
        errors=errors,
    )
