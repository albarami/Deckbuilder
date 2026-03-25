"""Tests for template-locked blueprint validation."""

from __future__ import annotations

from src.models.slide_blueprint import SlideBlueprintEntry
from src.models.template_contract import TEMPLATE_SECTION_ORDER
from src.services.template_validator import validate_blueprint_against_template


def _dynamic_entry(section_id: str, section_name: str) -> SlideBlueprintEntry:
    return SlideBlueprintEntry(
        section_id=section_id,
        section_name=section_name,
        ownership="dynamic",
        slide_title=f"{section_name} title",
        key_message=f"{section_name} key message",
        bullet_points=[f"{section_name} bullet"],
        evidence_ids=["CLM-0001"],
        visual_guidance="Use a clean business visual.",
    )


def _hybrid_entry(section_id: str, section_name: str) -> SlideBlueprintEntry:
    return SlideBlueprintEntry(
        section_id=section_id,
        section_name=section_name,
        ownership="hybrid",
        slide_title=section_name,
        key_message=f"{section_name} shell guidance",
        house_action="include_as_is",
    )


def _house_entry(section_id: str, section_name: str, action: str = "include_as_is") -> SlideBlueprintEntry:
    return SlideBlueprintEntry(
        section_id=section_id,
        section_name=section_name,
        ownership="house",
        house_action=action,  # type: ignore[arg-type]
        pool_selection_criteria=(
            "Select most relevant assets to the RFP."
            if action == "select_from_pool"
            else None
        ),
    )


def _valid_blueprint() -> list[SlideBlueprintEntry]:
    # Full contract coverage: explicit entry for every S01..S31 section.
    entries: list[SlideBlueprintEntry] = []
    for spec in TEMPLATE_SECTION_ORDER:
        section_id = spec.section_id
        section_name = spec.section_name

        if section_id == "S09":
            # Exactly 3 methodology entries in canonical order.
            entries.extend(
                [
                    _dynamic_entry("S09", "Methodology (Overview)"),
                    _dynamic_entry("S09", "Methodology (Focused Phase)"),
                    _dynamic_entry("S09", "Methodology (Detailed Phase)"),
                ]
            )
            continue

        if spec.ownership == "dynamic":
            entries.append(_dynamic_entry(section_id, section_name))
            continue

        if spec.ownership == "hybrid":
            entries.append(_hybrid_entry(section_id, section_name))
            continue

        # House ownership — explicit include/skip references.
        if section_id in {"S18", "S20", "S22"}:
            entries.append(_house_entry(section_id, section_name, action="select_from_pool"))
            continue
        if section_id == "S30":
            entries.append(_house_entry(section_id, section_name, action="select_from_pool"))
            entries.append(_house_entry(section_id, section_name, action="select_from_pool"))
            continue
        if section_id == "S31":
            entries.append(_house_entry(section_id, section_name, action="include_as_is"))
            continue
        entries.append(_house_entry(section_id, section_name, action="skip"))

    return entries


def test_valid_blueprint_passes_validation() -> None:
    violations = validate_blueprint_against_template(_valid_blueprint(), TEMPLATE_SECTION_ORDER)
    assert violations == []


def test_wrong_section_order_fails() -> None:
    blueprint = _valid_blueprint()
    blueprint[1], blueprint[2] = blueprint[2], blueprint[1]  # S03 before S02

    violations = validate_blueprint_against_template(blueprint, TEMPLATE_SECTION_ORDER)

    assert any("Section order violation" in v for v in violations)


def test_missing_required_section_fails() -> None:
    blueprint = [entry for entry in _valid_blueprint() if entry.section_id != "S31"]

    violations = validate_blueprint_against_template(blueprint, TEMPLATE_SECTION_ORDER)

    assert any("Missing required section 'S31'" in v for v in violations)


def test_house_section_with_generated_content_fails() -> None:
    blueprint = _valid_blueprint()
    # Build an intentionally invalid entry bypassing model validator
    # to exercise service-level validation behavior.
    blueprint.append(
        SlideBlueprintEntry.model_construct(
            section_id="S14",
            section_name="Corporate Main Shell Sequence",
            ownership="house",
            house_action="include_as_is",
            slide_title="Generated house title should fail",
            key_message=None,
            bullet_points=None,
            evidence_ids=None,
            visual_guidance=None,
            pool_selection_criteria=None,
        )
    )

    violations = validate_blueprint_against_template(blueprint, TEMPLATE_SECTION_ORDER)

    assert any("House-owned section 'S14' contains generated content fields." in v for v in violations)


def test_unknown_section_id_fails() -> None:
    blueprint = _valid_blueprint()
    blueprint.append(_dynamic_entry("S99", "Unknown Section"))

    violations = validate_blueprint_against_template(blueprint, TEMPLATE_SECTION_ORDER)

    assert any("Unknown section_id 'S99'" in v for v in violations)


def test_methodology_exceeds_capacity_fails() -> None:
    blueprint = _valid_blueprint()
    blueprint.extend(
        [
            _dynamic_entry("S09", "Methodology extra 1"),
            _dynamic_entry("S09", "Methodology extra 2"),
            _dynamic_entry("S09", "Methodology extra 3"),
            _dynamic_entry("S09", "Methodology extra 4"),
        ]
    )  # total S09 = 7

    violations = validate_blueprint_against_template(blueprint, TEMPLATE_SECTION_ORDER)

    assert any("Section 'S09' exceeds max dynamic slides (7 > 3)." in v for v in violations)


def test_missing_introduction_message_fails() -> None:
    blueprint = [entry for entry in _valid_blueprint() if entry.section_id != "S02"]

    violations = validate_blueprint_against_template(blueprint, TEMPLATE_SECTION_ORDER)

    assert any("Missing Introduction Message section 'S02' before ToC." in v for v in violations)


def test_dynamic_only_blueprint_fails() -> None:
    blueprint = [
        _dynamic_entry("S02", "Introduction Message"),
        _dynamic_entry("S05", "Understanding of Project"),
        _dynamic_entry("S07", "Why Strategic Gears"),
        _dynamic_entry("S09", "Methodology"),
        _dynamic_entry("S11", "Timeline"),
    ]

    violations = validate_blueprint_against_template(blueprint, TEMPLATE_SECTION_ORDER)

    assert any("Blueprint must include house/hybrid reference entries" in v for v in violations)

