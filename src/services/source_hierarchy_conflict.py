"""Source hierarchy conflict resolver — Slice 5.3.

When two RFP-side sources disagree about the same field (e.g. the
evaluation criteria sheet says pass/fail but the RFP booklet describes
a 70/30 weighted model), the writer must NOT silently pick one. This
module encodes the field-specific authority order from the design
doc's Section 4 and produces a structured ``SourceConflict`` record:
when one source is higher in the hierarchy, that value wins; when
neither has priority, the conflict is "unresolved" and requires
human clarification before any external use.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.models.common import DeckForgeBaseModel


# Field-specific source-of-truth order. Earlier entries outrank later.
FIELD_SOURCE_HIERARCHY: dict[str, list[str]] = {
    "award_mechanism": [
        "evaluation_criteria_sheet",
        "rfp_booklet",
        "special_conditions",
        "contract_model",
        "general_terms",
        "model_inference",
    ],
    "scope": [
        "rfp_booklet",
        "scope_annex",
        "boq_pricing_table",
        "special_conditions",
        "contract_model",
    ],
    "pricing_line_items": [
        "boq_pricing_table",
        "rfp_booklet",
        "financial_offer_template",
    ],
    "legal_terms": [
        "special_conditions",
        "contract_model",
        "general_terms",
    ],
}


class SourceConflict(DeckForgeBaseModel):
    """A structured record of a value disagreement between two sources."""

    field: str
    value_a: str
    source_a: str
    value_b: str
    source_b: str
    resolution: Literal[
        "no_conflict",
        "unresolved",
    ] | str = "unresolved"
    resolved_value: str = ""
    conflict_note: str = ""
    requires_clarification: bool = True


def _priority(field: str, source: str) -> int | None:
    """Return the position of ``source`` in the field's hierarchy
    (lower index = higher priority). ``None`` if the source isn't
    listed."""
    hierarchy = FIELD_SOURCE_HIERARCHY.get(field)
    if hierarchy is None:
        return None
    try:
        return hierarchy.index(source)
    except ValueError:
        return None


def resolve_source_conflict(
    *,
    field: str,
    value_a: str,
    source_a: str,
    value_b: str,
    source_b: str,
) -> SourceConflict:
    """Resolve a two-source disagreement using ``FIELD_SOURCE_HIERARCHY``.

    Outcomes:
      * ``no_conflict`` when both sources report the same value;
      * ``<winner>_wins`` when the field is known and exactly one
        source has higher priority;
      * ``unresolved`` (with ``requires_clarification=True``) when the
        field is unknown, both sources are tied, or neither source
        appears in the hierarchy.
    """
    if value_a == value_b:
        return SourceConflict(
            field=field,
            value_a=value_a,
            source_a=source_a,
            value_b=value_b,
            source_b=source_b,
            resolution="no_conflict",
            resolved_value=value_a,
            conflict_note="Both sources report the same value.",
            requires_clarification=False,
        )

    p_a = _priority(field, source_a)
    p_b = _priority(field, source_b)

    if p_a is None and p_b is None:
        return SourceConflict(
            field=field,
            value_a=value_a,
            source_a=source_a,
            value_b=value_b,
            source_b=source_b,
            resolution="unresolved",
            resolved_value="",
            conflict_note=(
                f"Neither {source_a!r} nor {source_b!r} is registered in "
                f"FIELD_SOURCE_HIERARCHY[{field!r}]; clarification required."
            ),
            requires_clarification=True,
        )

    if p_a is None:
        return SourceConflict(
            field=field,
            value_a=value_a,
            source_a=source_a,
            value_b=value_b,
            source_b=source_b,
            resolution=f"{source_b}_wins",
            resolved_value=value_b,
            conflict_note=(
                f"{source_a!r} is not in the hierarchy for {field!r}; "
                f"{source_b!r} wins by default."
            ),
            requires_clarification=False,
        )
    if p_b is None:
        return SourceConflict(
            field=field,
            value_a=value_a,
            source_a=source_a,
            value_b=value_b,
            source_b=source_b,
            resolution=f"{source_a}_wins",
            resolved_value=value_a,
            conflict_note=(
                f"{source_b!r} is not in the hierarchy for {field!r}; "
                f"{source_a!r} wins by default."
            ),
            requires_clarification=False,
        )

    if p_a == p_b:
        # Same source on both sides (callers sometimes do this when
        # the values disagree across two passes of the same source).
        return SourceConflict(
            field=field,
            value_a=value_a,
            source_a=source_a,
            value_b=value_b,
            source_b=source_b,
            resolution="unresolved",
            resolved_value="",
            conflict_note=(
                f"Both sources have equal priority in "
                f"FIELD_SOURCE_HIERARCHY[{field!r}]; clarification required."
            ),
            requires_clarification=True,
        )

    if p_a < p_b:
        return SourceConflict(
            field=field,
            value_a=value_a,
            source_a=source_a,
            value_b=value_b,
            source_b=source_b,
            resolution=f"{source_a}_wins",
            resolved_value=value_a,
            conflict_note=(
                f"{source_a!r} outranks {source_b!r} in "
                f"FIELD_SOURCE_HIERARCHY[{field!r}]."
            ),
            requires_clarification=False,
        )
    return SourceConflict(
        field=field,
        value_a=value_a,
        source_a=source_a,
        value_b=value_b,
        source_b=source_b,
        resolution=f"{source_b}_wins",
        resolved_value=value_b,
        conflict_note=(
            f"{source_b!r} outranks {source_a!r} in "
            f"FIELD_SOURCE_HIERARCHY[{field!r}]."
        ),
        requires_clarification=False,
    )
