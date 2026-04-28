"""Slice 4.5 — pipeline wiring for proposal_option registration.

The strategy / claim-ledger stage must reflect every ProposalOption
that lands in ``state.proposal_options`` (from the bid team, a config,
or a future option-generating agent) into ``state.claim_registry`` as
a canonical ``ClaimProvenance(claim_kind="proposal_option")`` entry.

Tested invariants:
  * helper ``register_proposal_options(state)`` is idempotent and only
    touches the proposal_option bucket;
  * the actual pipeline node (``proposal_strategy_node``) calls the
    helper, so options are reflected on every strategy run;
  * Pass 6 of validate_conformance, fed by the post-wiring state,
    accepts approved/publishable options and rejects unapproved ones —
    closing acceptance #6 of the user's Slice-4 spec;
  * proposal_option claims still fail can_use_as_proof_point;
  * no rfp_fact / internal_company_claim / external_methodology claim
    is mutated.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.source_book.conformance_validator import validate_conformance
from src.agents.source_book.orchestrator import should_accept_source_book
from src.models.claim_provenance import (
    ClaimProvenance,
    ClaimRegistry,
    ProposalOption,
    ProposalOptionRegistry,
)
from src.models.common import BilingualText
from src.models.rfp import RFPContext
from src.models.source_book import (
    ProposedSolution,
    SourceBook,
    SourceBookReview,
)
from src.models.state import DeckForgeState
from src.services.artifact_gates import can_use_as_proof_point
from src.services.proposal_option_registrar import register_proposal_options


def _patch_pass3():
    return patch(
        "src.agents.source_book.conformance_validator._pass3_semantic_checks",
        AsyncMock(return_value=[]),
    )


def _approved_option(
    option_id: str = "OPT-5-8",
    *,
    text: str = "Pilot scope: 5-8 countries",
    category: str = "numeric_range",
    priced: bool = True,
    pricing_impact_note: str = "",
) -> ProposalOption:
    return ProposalOption(
        option_id=option_id,
        text=text,
        claim_provenance_id=option_id,
        category=category,  # type: ignore[arg-type]
        approved_for_external_use=True,
        priced=priced,
        pricing_impact_note=pricing_impact_note,
        approved_by="bid_director" if priced or pricing_impact_note else None,
    )


def _unapproved_option(
    option_id: str = "OPT-5-8-UNAPPROVED",
    *,
    text: str = "Pilot scope: 5-8 countries",
) -> ProposalOption:
    return ProposalOption(
        option_id=option_id,
        text=text,
        claim_provenance_id=option_id,
        category="numeric_range",
        approved_for_external_use=False,
    )


# ── Helper-level wiring ───────────────────────────────────────────────


def test_helper_reflects_options_into_claim_registry() -> None:
    state = DeckForgeState()
    state.proposal_options.register(_approved_option("OPT-A", text="5-8 countries"))
    state.proposal_options.register(_unapproved_option("OPT-B", text="dual-track"))

    register_proposal_options(state)

    registered = state.claim_registry.proposal_options
    by_id = {c.claim_id: c for c in registered}
    assert "OPT-A" in by_id and "OPT-B" in by_id
    for c in registered:
        assert c.claim_kind == "proposal_option"
        assert c.source_kind == "model_generated"
        assert c.verification_status == "proposal_option"


def test_helper_is_idempotent() -> None:
    state = DeckForgeState()
    state.proposal_options.register(_approved_option("OPT-A", text="5-8 countries"))
    register_proposal_options(state)
    register_proposal_options(state)
    register_proposal_options(state)
    # Still just one OPT-A claim in the registry
    assert sum(
        1 for c in state.claim_registry.proposal_options if c.claim_id == "OPT-A"
    ) == 1


def test_helper_does_not_mutate_other_claim_kinds() -> None:
    state = DeckForgeState()
    state.claim_registry.register(ClaimProvenance(
        claim_id="RFP-FACT-001",
        text="x",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    state.claim_registry.register(ClaimProvenance(
        claim_id="BIDDER-001",
        text="x",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_unverified",
    ))
    state.claim_registry.register(ClaimProvenance(
        claim_id="EXT-001",
        text="x",
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status="externally_verified",
    ))
    state.proposal_options.register(_approved_option("OPT-A", text="5-8 countries"))
    register_proposal_options(state)

    rfp_ids = {c.claim_id for c in state.claim_registry.rfp_facts}
    bidder_ids = {c.claim_id for c in state.claim_registry.bidder_claims}
    ext_ids = {c.claim_id for c in state.claim_registry.external_methodology}
    assert rfp_ids == {"RFP-FACT-001"}
    assert bidder_ids == {"BIDDER-001"}
    assert ext_ids == {"EXT-001"}


def test_helper_handles_empty_options_registry() -> None:
    state = DeckForgeState()
    register_proposal_options(state)
    assert state.claim_registry.proposal_options == []


# ── Pipeline node integration ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_proposal_strategy_node_registers_options() -> None:
    """The actual proposal_strategy_node, after the agent runs, must
    call register_proposal_options. We patch the agent to return a
    no-op update and seed state.proposal_options in advance."""
    from src.agents.proposal_strategy import agent as strategy_agent
    from src.pipeline import graph as pipeline_graph

    state = DeckForgeState()
    state.proposal_options.register(_approved_option("OPT-A", text="5-8 countries"))

    async def _fake_strategy_run(_state):
        return {"proposal_strategy": None, "session": _state.session}

    with patch.object(strategy_agent, "run", _fake_strategy_run):
        updates = await pipeline_graph.proposal_strategy_node(state)

    # The update payload must carry the augmented claim_registry
    assert "claim_registry" in updates
    registered = updates["claim_registry"].proposal_options
    assert any(c.claim_id == "OPT-A" for c in registered)


# ── Pass 6 against pipeline-populated state ───────────────────────────


@pytest.mark.asyncio
async def test_pass6_resolves_against_pipeline_populated_approved_option() -> None:
    """Approved 5-8 countries option seeded into state, run through the
    wiring helper, then fed into validate_conformance — Pass 6 must
    find the option via the post-wiring state.claim_registry and NOT
    flag the commitment."""
    state = DeckForgeState()
    state.proposal_options.register(_approved_option(
        "OPT-5-8", text="Pilot scope: 5-8 countries", priced=True,
    ))
    register_proposal_options(state)

    sb = SourceBook(
        rfp_name="X", client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview="Pilot scope: 5-8 countries.",
        ),
    )
    rfp = RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=rfp,
            uploaded_documents=[],
            claim_registry=state.claim_registry,
            proposal_options=state.proposal_options,
        )
    assert not any(
        f.requirement_id in {"UNRESOLVED_COMMITMENT", "UNAPPROVED_OPTION"}
        for f in report.forbidden_claims
    )


@pytest.mark.asyncio
async def test_pass6_rejects_when_pipeline_populated_option_is_unapproved() -> None:
    state = DeckForgeState()
    state.proposal_options.register(_unapproved_option(
        "OPT-5-8-UNAPPROVED", text="Pilot scope: 5-8 countries",
    ))
    register_proposal_options(state)

    sb = SourceBook(
        rfp_name="X", client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview="Pilot scope: 5-8 countries.",
        ),
    )
    rfp = RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=rfp,
            uploaded_documents=[],
            claim_registry=state.claim_registry,
            proposal_options=state.proposal_options,
        )
    flagged = {f.requirement_id for f in report.forbidden_claims}
    assert flagged & {"UNRESOLVED_COMMITMENT", "UNAPPROVED_OPTION"}
    assert report.conformance_status == "fail"
    assert should_accept_source_book(
        SourceBookReview(
            overall_score=4,
            pass_threshold_met=True,
            competitive_viability="adequate",
        ),
        report,
    ) is False


@pytest.mark.asyncio
async def test_pass6_rejects_when_pipeline_option_is_pricing_unsignalled() -> None:
    """Approved+priced=False+no pricing_impact_note in pricing category
    → not externally publishable → resolution fails → reject."""
    state = DeckForgeState()
    state.proposal_options.register(ProposalOption(
        option_id="OPT-5-8-NPN",
        text="Pilot scope: 5-8 countries",
        claim_provenance_id="OPT-5-8-NPN",
        category="numeric_range",
        approved_for_external_use=True,
        priced=False,
        pricing_impact_note="",
    ))
    register_proposal_options(state)

    sb = SourceBook(
        rfp_name="X", client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview="Pilot scope: 5-8 countries.",
        ),
    )
    rfp = RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=rfp,
            uploaded_documents=[],
            claim_registry=state.claim_registry,
            proposal_options=state.proposal_options,
        )
    assert report.conformance_status == "fail"


# ── Acceptance: proposal_option claims still never proof points ───────


def test_pipeline_registered_option_is_never_proof_point() -> None:
    state = DeckForgeState()
    state.proposal_options.register(_approved_option("OPT-A", text="5-8 countries"))
    register_proposal_options(state)
    for c in state.claim_registry.proposal_options:
        assert can_use_as_proof_point(c) is False


# ── Acceptance #7 fail-closed when nothing is registered ──────────────


@pytest.mark.asyncio
async def test_no_options_plus_client_facing_commitment_fails_closed() -> None:
    """When state.proposal_options is empty (no options registered) and
    the SourceBook contains a client-facing numeric commitment, Pass 6
    fires UNRESOLVED_COMMITMENT and the gate rejects."""
    state = DeckForgeState()
    register_proposal_options(state)  # no-op, registry stays empty
    assert state.proposal_options.options == []

    sb = SourceBook(
        rfp_name="X", client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview="Pilot scope: 5-8 countries.",
        ),
    )
    rfp = RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=rfp,
            uploaded_documents=[],
            claim_registry=state.claim_registry,
            proposal_options=state.proposal_options,
        )
    assert any(
        f.requirement_id == "UNRESOLVED_COMMITMENT"
        for f in report.forbidden_claims
    )
    assert report.conformance_status == "fail"
