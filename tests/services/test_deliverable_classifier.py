"""Formal deliverable classifier — Slice 5.2.

Acceptance #6: ``formal_deliverable=True`` is permitted only when the
origin is ``boq_line`` or ``deliverables_annex``.

Acceptance #7: scope clauses and special conditions become cross-
cutting workstreams. When the LLM proposes a ``D-N`` id for a non-
formal deliverable, ``normalize_to_workstream_id`` rewrites it to a
workstream prefix (KT-N / GOV-N / MGMT-N / TRAIN-N / …) so the source
book never carries fake D- formal deliverable ids.
"""
from __future__ import annotations

import pytest

from src.services.deliverable_classifier import (
    DeliverableClassification,
    classify_deliverable,
    normalize_to_workstream_id,
)


# ── Acceptance #6 — formal flag is True only for BOQ / annex origins ──


def test_boq_line_origin_is_formal_and_priced() -> None:
    d = DeliverableClassification(
        id="D-1",
        name="Investment Promotion Strategy Report",
        origin="boq_line",
    )
    assert d.formal_deliverable is True
    assert d.pricing_line_item is True
    assert d.cross_cutting_workstream is False


def test_deliverables_annex_origin_is_formal_not_priced() -> None:
    d = DeliverableClassification(
        id="D-2",
        name="Annex C — Final Report",
        origin="deliverables_annex",
    )
    assert d.formal_deliverable is True
    assert d.pricing_line_item is False
    assert d.cross_cutting_workstream is False


def test_scope_clause_origin_is_workstream_not_formal() -> None:
    d = DeliverableClassification(
        id="KT-1",
        name="Knowledge transfer plan",
        origin="scope_clause",
    )
    assert d.formal_deliverable is False
    assert d.pricing_line_item is False
    assert d.cross_cutting_workstream is True


def test_special_condition_is_workstream_not_formal() -> None:
    d = DeliverableClassification(
        id="TRAIN-1",
        name="Training program",
        origin="special_condition",
    )
    assert d.formal_deliverable is False
    assert d.cross_cutting_workstream is True


def test_generated_supporting_artifact_is_neither_formal_nor_workstream() -> None:
    d = DeliverableClassification(
        id="GEN-1",
        name="Internal stakeholder map",
        origin="generated_supporting_artifact",
    )
    assert d.formal_deliverable is False
    assert d.cross_cutting_workstream is False


# ── Acceptance #7 — D-N normalization to workstream id ────────────────


def test_normalize_d_id_with_scope_clause_origin_to_workstream() -> None:
    """LLM said D-3 but origin is scope_clause. The id must be
    rewritten to a workstream prefix that reflects the deliverable's
    name (training → TRAIN-N; knowledge transfer → KT-N; etc.)."""
    new_id = normalize_to_workstream_id(
        original_id="D-3",
        name="Training and knowledge transfer",
        origin="scope_clause",
    )
    assert not new_id.startswith("D-")
    assert new_id.startswith(("TRAIN-", "KT-"))


def test_normalize_d_id_for_governance_special_condition() -> None:
    new_id = normalize_to_workstream_id(
        original_id="D-9",
        name="Governance committee charter",
        origin="special_condition",
    )
    assert not new_id.startswith("D-")
    assert new_id.startswith("GOV-")


def test_normalize_d_id_for_management_workstream() -> None:
    new_id = normalize_to_workstream_id(
        original_id="D-2",
        name="Project management methodology",
        origin="scope_clause",
    )
    assert new_id.startswith("MGMT-") or new_id.startswith("PM-")


def test_normalize_keeps_d_id_for_boq_line() -> None:
    """A genuinely-BOQ-origin item keeps its D-id."""
    new_id = normalize_to_workstream_id(
        original_id="D-1",
        name="Investment Promotion Strategy Report",
        origin="boq_line",
    )
    assert new_id == "D-1"


def test_normalize_keeps_d_id_for_deliverables_annex() -> None:
    new_id = normalize_to_workstream_id(
        original_id="D-2",
        name="Annex C — Final Report",
        origin="deliverables_annex",
    )
    assert new_id == "D-2"


def test_normalize_falls_back_to_workstream_when_unmatched_name() -> None:
    """When the name doesn't match a known category, normalize to a
    generic workstream prefix (WS-N)."""
    new_id = normalize_to_workstream_id(
        original_id="D-5",
        name="Bespoke custom thing",
        origin="scope_clause",
    )
    assert not new_id.startswith("D-")
    assert new_id.startswith("WS-")


# ── classify_deliverable convenience helper ──────────────────────────


def test_classify_deliverable_normalizes_when_non_formal() -> None:
    d = classify_deliverable(
        id_hint="D-3",
        name="Training and knowledge transfer",
        origin="scope_clause",
    )
    # Auto-normalized id, derived flags
    assert not d.id.startswith("D-")
    assert d.formal_deliverable is False
    assert d.cross_cutting_workstream is True


def test_classify_deliverable_keeps_d_id_when_formal() -> None:
    d = classify_deliverable(
        id_hint="D-1",
        name="Investment Promotion Strategy Report",
        origin="boq_line",
    )
    assert d.id == "D-1"
    assert d.formal_deliverable is True
    assert d.pricing_line_item is True


# ── DeliverableClassification rejects mismatched manual flags ────────


def test_cannot_force_formal_flag_when_origin_is_scope_clause() -> None:
    """Even if a caller passes formal_deliverable=True, the model
    validator overwrites the derived flags from origin so the boolean
    cannot be tampered with."""
    d = DeliverableClassification(
        id="D-99",
        name="Tampered",
        origin="scope_clause",
        formal_deliverable=True,  # request — overridden
        pricing_line_item=True,
    )
    assert d.formal_deliverable is False
    assert d.pricing_line_item is False
    assert d.cross_cutting_workstream is True


def test_classification_preserves_registered_claim_link() -> None:
    d = DeliverableClassification(
        id="D-1",
        name="X",
        origin="boq_line",
        registered_as_claim="RFP-FACT-DELIV-D-1",
    )
    assert d.registered_as_claim == "RFP-FACT-DELIV-D-1"


def test_unknown_origin_rejected() -> None:
    with pytest.raises(Exception):
        DeliverableClassification(
            id="D-1",
            name="X",
            origin="not_a_valid_origin",  # type: ignore[arg-type]
        )
