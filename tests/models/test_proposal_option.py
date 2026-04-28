"""ProposalOption model + register/lookup helpers — Slice 4.1.

A ProposalOption is the option metadata sidecar for a ClaimProvenance
whose claim_kind is "proposal_option". It carries gating fields that
ClaimProvenance does not own (and should not own, since they're
specific to the proposal_option kind):

  * approved_for_external_use — whether this option can appear in
    client-facing sections
  * priced — whether the option has been costed
  * approved_by — actor accountable for approval
  * pricing_impact_note — explicit text describing pricing impact when
    `priced=False`

Tests cover the model invariants and the registry helpers that wire
options into a DeckForgeState.
"""
from __future__ import annotations

import pytest

from src.models.claim_provenance import (
    ClaimProvenance,
    ClaimRegistry,
    ProposalOption,
    ProposalOptionRegistry,
)


def _option_claim(claim_id: str = "OPT-001", text: str = "5-8 countries") -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="proposal_option",
        source_kind="model_generated",
        verification_status="proposal_option",
    )


# ── Model defaults ────────────────────────────────────────────────────


def test_default_option_is_unapproved_unpriced() -> None:
    opt = ProposalOption(
        option_id="OPT-001",
        text="5-8 countries",
        claim_provenance_id="OPT-001",
        category="numeric_range",
    )
    assert opt.approved_for_external_use is False
    assert opt.priced is False
    assert opt.approved_by is None
    assert opt.pricing_impact_note == ""


def test_option_can_be_marked_approved_and_priced() -> None:
    opt = ProposalOption(
        option_id="OPT-001",
        text="5-8 countries",
        claim_provenance_id="OPT-001",
        category="numeric_range",
        approved_for_external_use=True,
        priced=True,
        approved_by="bid_director",
        pricing_impact_note="±5% pricing flex absorbed in management fee",
    )
    assert opt.approved_for_external_use is True
    assert opt.priced is True
    assert opt.approved_by == "bid_director"
    assert "±5%" in opt.pricing_impact_note


def test_option_category_is_validated() -> None:
    """Only the design-doc categories are accepted."""
    with pytest.raises(Exception):
        ProposalOption(
            option_id="OPT-001",
            text="x",
            claim_provenance_id="OPT-001",
            category="not_a_category",  # type: ignore[arg-type]
        )


def test_option_id_required() -> None:
    with pytest.raises(Exception):
        ProposalOption(
            option_id="",
            text="x",
            claim_provenance_id="OPT-001",
            category="numeric_range",
        )


# ── Registry register / get / list ────────────────────────────────────


def test_registry_register_and_get() -> None:
    reg = ProposalOptionRegistry()
    opt = ProposalOption(
        option_id="OPT-001",
        text="5-8 countries",
        claim_provenance_id="OPT-001",
        category="numeric_range",
    )
    reg.register(opt)
    assert reg.get("OPT-001") is opt
    assert reg.get("nope") is None


def test_registry_register_overwrites_same_id() -> None:
    reg = ProposalOptionRegistry()
    reg.register(ProposalOption(
        option_id="OPT-1",
        text="A",
        claim_provenance_id="OPT-1",
        category="numeric_range",
    ))
    reg.register(ProposalOption(
        option_id="OPT-1",
        text="B",
        claim_provenance_id="OPT-1",
        category="numeric_range",
    ))
    assert reg.get("OPT-1").text == "B"


def test_registry_list_options() -> None:
    reg = ProposalOptionRegistry()
    reg.register(ProposalOption(
        option_id="OPT-1", text="A", claim_provenance_id="OPT-1",
        category="numeric_range",
    ))
    reg.register(ProposalOption(
        option_id="OPT-2", text="B", claim_provenance_id="OPT-2",
        category="methodology_choice",
    ))
    assert {o.option_id for o in reg.options} == {"OPT-1", "OPT-2"}


# ── Linkage to ClaimRegistry ──────────────────────────────────────────


def test_resolve_option_via_claim_registry_and_option_registry() -> None:
    """Both registries are queryable: claim_registry holds the
    ClaimProvenance, proposal_options holds the option metadata."""
    claim_reg = ClaimRegistry()
    opt_reg = ProposalOptionRegistry()

    claim_reg.register(_option_claim("OPT-001", "5-8 countries"))
    opt_reg.register(ProposalOption(
        option_id="OPT-001",
        text="5-8 countries",
        claim_provenance_id="OPT-001",
        category="numeric_range",
        approved_for_external_use=True,
        priced=True,
    ))
    claim = claim_reg.get("OPT-001")
    option = opt_reg.get("OPT-001")
    assert claim is not None
    assert option is not None
    assert claim.claim_id == option.claim_provenance_id


def test_state_has_proposal_options_field() -> None:
    """DeckForgeState holds a ProposalOptionRegistry alongside
    claim_registry so the option metadata travels with the pipeline."""
    from src.models.state import DeckForgeState
    s = DeckForgeState()
    assert isinstance(s.proposal_options, ProposalOptionRegistry)
    assert s.proposal_options.options == []


# ── ClaimProvenance + option gate sanity ──────────────────────────────


def test_proposal_option_claim_never_proof_point() -> None:
    """Acceptance #2: proposal_option claims fail can_use_as_proof_point."""
    from src.services.artifact_gates import can_use_as_proof_point
    claim = _option_claim()
    assert can_use_as_proof_point(claim) is False
