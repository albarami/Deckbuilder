"""Source hierarchy conflict resolver — Slice 5.3.

Acceptance #8: source hierarchy conflicts are resolved field-
specifically and unresolved conflicts require clarification or block
external use.

The resolver is fed two competing values for a single field, each
attributed to a source. It consults ``FIELD_SOURCE_HIERARCHY`` for
that field and picks the higher-priority source. When both sources
sit at equal priority or neither is in the hierarchy, the resolution
is "unresolved" and the conflict requires clarification.
"""
from __future__ import annotations

from src.services.source_hierarchy_conflict import (
    FIELD_SOURCE_HIERARCHY,
    SourceConflict,
    resolve_source_conflict,
)


# ── Hierarchy data is well-formed ──────────────────────────────────────


def test_hierarchy_includes_award_mechanism() -> None:
    h = FIELD_SOURCE_HIERARCHY["award_mechanism"]
    assert "evaluation_criteria_sheet" in h
    assert "rfp_booklet" in h
    assert h.index("evaluation_criteria_sheet") < h.index("rfp_booklet")


def test_hierarchy_includes_scope() -> None:
    h = FIELD_SOURCE_HIERARCHY["scope"]
    assert h[0] == "rfp_booklet"
    assert "scope_annex" in h


def test_hierarchy_includes_pricing_line_items() -> None:
    h = FIELD_SOURCE_HIERARCHY["pricing_line_items"]
    assert h[0] == "boq_pricing_table"


def test_hierarchy_includes_legal_terms() -> None:
    h = FIELD_SOURCE_HIERARCHY["legal_terms"]
    assert h[0] == "special_conditions"


# ── Resolution: known field, both sources in hierarchy ────────────────


def test_award_mechanism_eval_criteria_beats_rfp_booklet() -> None:
    conflict = resolve_source_conflict(
        field="award_mechanism",
        value_a="pass_fail_then_lowest_price",
        source_a="evaluation_criteria_sheet",
        value_b="weighted_70_30",
        source_b="rfp_booklet",
    )
    assert conflict.resolution == "evaluation_criteria_sheet_wins"
    assert conflict.resolved_value == "pass_fail_then_lowest_price"
    assert "evaluation_criteria_sheet" in conflict.conflict_note


def test_scope_rfp_booklet_beats_special_conditions() -> None:
    conflict = resolve_source_conflict(
        field="scope",
        value_a="A",
        source_a="rfp_booklet",
        value_b="B",
        source_b="special_conditions",
    )
    assert conflict.resolution == "rfp_booklet_wins"
    assert conflict.resolved_value == "A"


def test_pricing_boq_beats_financial_offer_template() -> None:
    conflict = resolve_source_conflict(
        field="pricing_line_items",
        value_a="500,000 SAR",
        source_a="boq_pricing_table",
        value_b="450,000 SAR",
        source_b="financial_offer_template",
    )
    assert conflict.resolution == "boq_pricing_table_wins"
    assert conflict.resolved_value == "500,000 SAR"


# ── Resolution: argument order does not matter ───────────────────────


def test_argument_order_irrelevant_lower_first() -> None:
    """value_a/source_a as the lower-priority side: resolver still
    picks the higher-priority value, regardless of argument order."""
    conflict = resolve_source_conflict(
        field="award_mechanism",
        value_a="weighted_70_30",
        source_a="rfp_booklet",
        value_b="pass_fail_then_lowest_price",
        source_b="evaluation_criteria_sheet",
    )
    assert conflict.resolved_value == "pass_fail_then_lowest_price"
    assert conflict.resolution == "evaluation_criteria_sheet_wins"


# ── Equal priority → unresolved ──────────────────────────────────────


def test_same_source_returns_unresolved() -> None:
    conflict = resolve_source_conflict(
        field="award_mechanism",
        value_a="A",
        source_a="evaluation_criteria_sheet",
        value_b="B",
        source_b="evaluation_criteria_sheet",
    )
    assert conflict.resolution == "unresolved"
    assert conflict.requires_clarification is True


# ── Unknown field → unresolved ───────────────────────────────────────


def test_unknown_field_yields_unresolved() -> None:
    conflict = resolve_source_conflict(
        field="not_a_real_field",
        value_a="A",
        source_a="rfp_booklet",
        value_b="B",
        source_b="contract_model",
    )
    assert conflict.resolution == "unresolved"
    assert conflict.requires_clarification is True


# ── Unknown source on either side → unresolved ───────────────────────


def test_source_a_not_in_hierarchy_falls_back_to_b() -> None:
    """When only one source is in the hierarchy for the field, that
    source wins by default (the unknown side has no priority)."""
    conflict = resolve_source_conflict(
        field="award_mechanism",
        value_a="A",
        source_a="random_email_thread",
        value_b="B",
        source_b="evaluation_criteria_sheet",
    )
    assert conflict.resolved_value == "B"
    assert conflict.resolution == "evaluation_criteria_sheet_wins"


def test_neither_source_in_hierarchy_unresolved() -> None:
    conflict = resolve_source_conflict(
        field="award_mechanism",
        value_a="A",
        source_a="random_email_thread",
        value_b="B",
        source_b="phone_call_notes",
    )
    assert conflict.resolution == "unresolved"
    assert conflict.requires_clarification is True


# ── Same value, different sources → no conflict ──────────────────────


def test_same_value_different_sources_marks_no_conflict() -> None:
    conflict = resolve_source_conflict(
        field="scope",
        value_a="strategic_plan",
        source_a="rfp_booklet",
        value_b="strategic_plan",
        source_b="scope_annex",
    )
    assert conflict.resolution == "no_conflict"
    assert conflict.resolved_value == "strategic_plan"
    assert conflict.requires_clarification is False


# ── SourceConflict shape ─────────────────────────────────────────────


def test_unresolved_carries_both_values_and_sources() -> None:
    conflict = resolve_source_conflict(
        field="award_mechanism",
        value_a="A",
        source_a="random_email_thread",
        value_b="B",
        source_b="phone_call_notes",
    )
    assert conflict.value_a == "A"
    assert conflict.source_a == "random_email_thread"
    assert conflict.value_b == "B"
    assert conflict.source_b == "phone_call_notes"
    assert conflict.field == "award_mechanism"
    assert conflict.resolved_value == ""


def test_source_conflict_default_construction() -> None:
    sc = SourceConflict(
        field="award_mechanism",
        value_a="A",
        source_a="x",
        value_b="B",
        source_b="y",
    )
    assert sc.resolution == "unresolved"
    assert sc.requires_clarification is True
    assert sc.resolved_value == ""
