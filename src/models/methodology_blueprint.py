"""Phase 3b — Methodology Blueprint.

Strict structure for the methodology section (~50% of the proposal deck).
Each MethodologyBlueprint defines phase count, per-phase layouts (by
semantic layout ID), deliverable linkage, and governance touchpoints.

The blueprint is consumed by the SlideBudgeter and layout_router —
it is NOT optional.  Every methodology section must have an explicit
blueprint before slides are created.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Exceptions ────────────────────────────────────────────────────────────


class MethodologyBlueprintError(RuntimeError):
    """Raised on invalid methodology blueprint configuration."""


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PhaseBlueprint:
    """Blueprint for one methodology phase."""

    phase_id: str
    phase_number: int                       # 1-based
    phase_name_en: str
    phase_name_ar: str
    overview_layout: str                    # semantic layout ID
    focused_layouts: list[str] = field(default_factory=list)   # semantic layout IDs
    detail_layouts: list[str] = field(default_factory=list)    # semantic layout IDs
    activities: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    governance_tier: str = ""               # e.g. "Steering Committee"
    slide_count_min: int = 2                # overview + at least 1 focused


@dataclass(frozen=True)
class MethodologyBlueprint:
    """Complete methodology section blueprint."""

    phase_count: int                        # 3-5 phases
    phases: list[PhaseBlueprint]
    deliverables_linkage: dict[str, list[str]] = field(default_factory=dict)
    governance_touchpoints: dict[str, str] = field(default_factory=dict)
    evidence_anchors: list[str] = field(default_factory=list)
    timeline_span: str = ""                 # e.g. "12 weeks"

    @property
    def total_min_slides(self) -> int:
        """Minimum total slides across all phases (overview + focused + details)."""
        # 1 overview slide + sum of per-phase minimums
        return 1 + sum(p.slide_count_min for p in self.phases)

    @property
    def all_semantic_layout_ids(self) -> list[str]:
        """All semantic layout IDs referenced by this blueprint."""
        ids: list[str] = []
        for phase in self.phases:
            ids.append(phase.overview_layout)
            ids.extend(phase.focused_layouts)
            ids.extend(phase.detail_layouts)
        return ids


# ── Semantic layout ID sets for methodology ───────────────────────────────
# These are the ONLY layout IDs methodology slides may use.

METHODOLOGY_LAYOUTS_4_PHASE: dict[str, str] = {
    "overview": "methodology_overview_4",
    "focused": "methodology_focused_4",
    "detail": "methodology_detail",
}

METHODOLOGY_LAYOUTS_3_PHASE: dict[str, str] = {
    "overview": "methodology_overview_3",
    "focused": "methodology_focused_3",
    "detail": "methodology_detail",
}


# ── Builder ───────────────────────────────────────────────────────────────


def build_methodology_blueprint(
    phase_count: int,
    phases: list[dict[str, Any]],
    *,
    deliverables_linkage: dict[str, list[str]] | None = None,
    governance_touchpoints: dict[str, str] | None = None,
    evidence_anchors: list[str] | None = None,
    timeline_span: str = "",
    grammar_dir: Path | None = None,
) -> MethodologyBlueprint:
    """Build a MethodologyBlueprint from phase definitions.

    Parameters
    ----------
    phase_count : int
        Number of methodology phases (must be 3-5).
    phases : list[dict]
        Per-phase definitions.  Each dict must have:
        - phase_name_en: str
        - phase_name_ar: str (optional, defaults to "")
        - activities: list[str]
        - deliverables: list[str]
        - governance_tier: str (optional)
    deliverables_linkage : dict, optional
        Phase ID -> list of deliverable IDs linked to timeline.
    governance_touchpoints : dict, optional
        Phase ID -> governance tier name.
    evidence_anchors : list, optional
        Evidence references for methodology justification.
    timeline_span : str
        Overall timeline (e.g. "16 weeks").
    grammar_dir : Path, optional
        Path to template_grammar directory for framing language enrichment.

    Returns
    -------
    MethodologyBlueprint

    Raises
    ------
    MethodologyBlueprintError
        If phase_count is out of range or phase definitions are invalid.
    """
    if not 3 <= phase_count <= 5:
        raise MethodologyBlueprintError(
            f"Phase count must be 3-5, got {phase_count}"
        )
    if len(phases) != phase_count:
        raise MethodologyBlueprintError(
            f"Expected {phase_count} phase definitions, got {len(phases)}"
        )

    # Select layout family based on phase count
    if phase_count <= 3:
        layout_family = METHODOLOGY_LAYOUTS_3_PHASE
    else:
        layout_family = METHODOLOGY_LAYOUTS_4_PHASE

    phase_blueprints: list[PhaseBlueprint] = []
    for i, pdef in enumerate(phases):
        phase_num = i + 1
        phase_id = f"phase_{phase_num:02d}"

        name_en = pdef.get("phase_name_en", "")
        if not name_en:
            raise MethodologyBlueprintError(
                f"Phase {phase_num} missing phase_name_en"
            )

        activities = pdef.get("activities", [])
        deliverables_list = pdef.get("deliverables", [])
        governance_tier = pdef.get("governance_tier", "")

        # Determine detail layouts: phases with >3 activities get detail slides
        detail_layouts: list[str] = []
        if len(activities) > 3:
            detail_layouts = [layout_family["detail"]]

        # Minimum slides: 1 focused + details
        slide_min = 1 + len(detail_layouts)

        phase_blueprints.append(PhaseBlueprint(
            phase_id=phase_id,
            phase_number=phase_num,
            phase_name_en=name_en,
            phase_name_ar=pdef.get("phase_name_ar", ""),
            overview_layout=layout_family["overview"],
            focused_layouts=[layout_family["focused"]],
            detail_layouts=detail_layouts,
            activities=activities,
            deliverables=deliverables_list,
            governance_tier=governance_tier,
            slide_count_min=slide_min,
        ))

    return MethodologyBlueprint(
        phase_count=phase_count,
        phases=phase_blueprints,
        deliverables_linkage=deliverables_linkage or {},
        governance_touchpoints=governance_touchpoints or {},
        evidence_anchors=evidence_anchors or [],
        timeline_span=timeline_span,
    )


def validate_methodology_layouts(
    blueprint: MethodologyBlueprint,
    available_layout_ids: set[str],
) -> list[str]:
    """Validate all layout IDs in blueprint exist in the catalog lock.

    Returns a list of error messages (empty if valid).
    Fail-closed: any missing layout ID is a hard error.
    """
    errors: list[str] = []
    for layout_id in blueprint.all_semantic_layout_ids:
        if layout_id not in available_layout_ids:
            errors.append(
                f"Methodology layout '{layout_id}' not found in catalog lock"
            )
    return errors
