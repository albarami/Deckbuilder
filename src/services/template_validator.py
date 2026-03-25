"""Template alignment validator for section-ordered blueprints."""

from __future__ import annotations

import logging

from src.models.slide_blueprint import SlideBlueprintEntry
from src.models.template_contract import TemplateSectionSpec

logger = logging.getLogger(__name__)


_CASE_POOL_SECTIONS = {"S18", "S20", "S22", "S24", "S26", "S28"}
_TEAM_POOL_SECTION = "S30"
_METHODOLOGY_SECTION = "S09"
_INTRO_SECTION = "S02"
_TOC_SECTION = "S03"


def _is_generated_content(entry: SlideBlueprintEntry) -> bool:
    return any(
        (
            entry.slide_title,
            entry.key_message,
            entry.bullet_points,
            entry.evidence_ids,
            entry.visual_guidance,
        )
    )


def _emit_warnings(blueprint: list[SlideBlueprintEntry]) -> None:
    case_pool_count = sum(
        1
        for e in blueprint
        if e.section_id in _CASE_POOL_SECTIONS
        and e.house_action == "select_from_pool"
    )
    if case_pool_count < 3:
        logger.warning(
            "Template alignment warning: case study pool selections below "
            "minimum (found %s, need >= 3).",
            case_pool_count,
        )

    team_pool_count = sum(
        1
        for e in blueprint
        if e.section_id == _TEAM_POOL_SECTION and e.house_action == "select_from_pool"
    )
    if team_pool_count < 2:
        logger.warning(
            "Template alignment warning: team bio pool selections below "
            "minimum (found %s, need >= 2).",
            team_pool_count,
        )

    methodology_count = sum(1 for e in blueprint if e.section_id == _METHODOLOGY_SECTION)
    if methodology_count < 3:
        logger.warning("Template alignment warning: methodology has fewer than 3 slides (found %s).", methodology_count)


def validate_blueprint_against_template(
    blueprint: list[SlideBlueprintEntry],
    template: list[TemplateSectionSpec],
) -> list[str]:
    """Validate blueprint entries against the canonical template contract."""
    violations: list[str] = []
    _emit_warnings(blueprint)

    template_map = {spec.section_id: spec for spec in template}
    template_index = {spec.section_id: idx for idx, spec in enumerate(template)}
    required_sections = [spec.section_id for spec in template if spec.required]

    seen_sections: set[str] = set()
    section_counts: dict[str, int] = {}
    last_idx = -1

    for entry in blueprint:
        if entry.section_id not in template_map:
            violations.append(
                f"Unknown section_id '{entry.section_id}' not present in template contract."
            )
            continue

        spec = template_map[entry.section_id]
        idx = template_index[entry.section_id]

        if idx < last_idx:
            violations.append(
                f"Section order violation: '{entry.section_id}' appears after a later template section."
            )
        last_idx = max(last_idx, idx)

        if spec.ownership == "house":
            if _is_generated_content(entry):
                violations.append(
                    f"House-owned section '{entry.section_id}' contains generated content fields."
                )
            if entry.house_action is None:
                violations.append(
                    f"House-owned section '{entry.section_id}' must set house_action."
                )

        section_counts[entry.section_id] = section_counts.get(entry.section_id, 0) + 1
        seen_sections.add(entry.section_id)

    for required_section in required_sections:
        if required_section not in seen_sections:
            violations.append(f"Missing required section '{required_section}'.")

    for section_id, count in section_counts.items():
        spec = template_map.get(section_id)
        if spec is None:
            continue
        if (
            not spec.repeatable
            and spec.max_dynamic_slides in (None, 1)
            and count > 1
        ):
            violations.append(
                f"Section '{section_id}' is fixed but appears {count} times."
            )
        if spec.max_dynamic_slides is not None and count > spec.max_dynamic_slides:
            violations.append(
                f"Section '{section_id}' exceeds max dynamic slides "
                f"({count} > {spec.max_dynamic_slides})."
            )

    intro_positions = [i for i, entry in enumerate(blueprint) if entry.section_id == _INTRO_SECTION]
    toc_positions = [i for i, entry in enumerate(blueprint) if entry.section_id == _TOC_SECTION]
    if not intro_positions:
        violations.append("Missing Introduction Message section 'S02' before ToC.")
    if intro_positions and toc_positions and intro_positions[0] > toc_positions[0]:
        violations.append("Introduction Message 'S02' must appear before Table of Contents 'S03'.")

    has_house_reference = any(
        entry.ownership in {"house", "hybrid"} and entry.house_action is not None
        for entry in blueprint
    )
    if not has_house_reference:
        violations.append("Blueprint must include house/hybrid reference entries, not dynamic-only sections.")

    return violations

