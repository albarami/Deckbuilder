"""Regression — Slice 4 acceptance demonstration end-to-end.

Walks the full Slice-4 acceptance set against a synthesized "5-8
countries" commitment scenario. The frozen UNESCO source_book.docx
does not literally contain the canonical "5-8 countries" phrase under
the current pipeline output, so this regression uses focused synthetic
SourceBooks to exercise:

  * acceptance #1: proposal_option claims live in claim_registry
    under claim_kind="proposal_option";
  * acceptance #2: proposal_option claims fail can_use_as_proof_point;
  * acceptance #3: client-facing numeric commitments must resolve to
    an RFP fact OR an externally publishable proposal_option;
  * acceptance #4: unresolved client-facing numeric commitments cause
    the actual orchestrator gate to reject;
  * acceptance #5: approved_for_external_use=False blocks client-
    facing publication;
  * acceptance #6: pricing-relevant categories also require priced=True
    OR a non-empty pricing_impact_note;
  * acceptance #7: internal_bid_notes / proposal_option_ledger remain
    safe homes for unapproved options;
  * acceptance #8: the orchestrator gate path is the chokepoint —
    validate_conformance + should_accept_source_book.
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
    SlideBlueprintEntry,
    SourceBook,
    SourceBookReview,
)
from src.services.artifact_gates import ArtifactSection, can_use_as_proof_point
from src.services.numeric_commitment_detector import detect_numeric_commitments


# ── Helpers ────────────────────────────────────────────────────────────


def _patch_pass3():
    return patch(
        "src.agents.source_book.conformance_validator._pass3_semantic_checks",
        AsyncMock(return_value=[]),
    )


def _minimal_rfp() -> RFPContext:
    return RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )


def _passing_review() -> SourceBookReview:
    return SourceBookReview(
        overall_score=4,
        pass_threshold_met=True,
        competitive_viability="adequate",
    )


def _option_claim(claim_id: str = "OPT-5-8") -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text="Pilot scope: 5-8 countries",
        claim_kind="proposal_option",
        source_kind="model_generated",
        verification_status="proposal_option",
    )


def _sourcebook_with_5_8_in_body() -> SourceBook:
    return SourceBook(
        rfp_name="UNESCO",
        client_name="UNESCO",
        proposed_solution=ProposedSolution(
            methodology_overview="Pilot scope: 5-8 countries.",
        ),
    )


def _sourcebook_with_5_8_in_slide() -> SourceBook:
    return SourceBook(
        rfp_name="UNESCO",
        client_name="UNESCO",
        slide_blueprints=[
            SlideBlueprintEntry(
                slide_number=4,
                title="Coverage",
                key_message="We will cover 5-8 countries.",
            ),
        ],
    )


# ── Acceptance #1 — registration as proposal_option ────────────────────


def test_proposal_option_lives_in_claim_registry() -> None:
    reg = ClaimRegistry()
    reg.register(_option_claim())
    options = reg.proposal_options
    assert len(options) == 1
    assert options[0].claim_kind == "proposal_option"


# ── Acceptance #2 — never proof point ─────────────────────────────────


def test_proposal_option_never_passes_proof_point_gate() -> None:
    assert can_use_as_proof_point(_option_claim()) is False


# ── Acceptance #3 — must resolve to RFP fact or approved option ───────


def test_unresolved_5_8_countries_in_body() -> None:
    sections = [ArtifactSection(
        section_path="proposed_solution/methodology_overview",
        section_type="client_facing_body",
        text="Pilot scope: 5-8 countries.",
    )]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert any(
        nc.canonical == "5-8" and nc.resolution == "unresolved"
        for nc in found
    )


def test_5_8_countries_resolves_to_externally_publishable_option() -> None:
    claim_reg = ClaimRegistry()
    claim_reg.register(_option_claim())
    opt_reg = ProposalOptionRegistry()
    opt_reg.register(ProposalOption(
        option_id="OPT-5-8",
        text="Pilot scope: 5-8 countries",
        claim_provenance_id="OPT-5-8",
        category="numeric_range",
        approved_for_external_use=True,
        priced=True,
        approved_by="bid_director",
    ))
    sections = [ArtifactSection(
        section_path="proposed_solution/methodology_overview",
        section_type="client_facing_body",
        text="Pilot scope: 5-8 countries.",
    )]
    found = detect_numeric_commitments(sections, claim_reg, opt_reg)
    approved = [nc for nc in found if nc.resolution == "approved_option"]
    assert approved
    assert approved[0].resolved_option_id == "OPT-5-8"


# ── Acceptance #4 — unresolved commitments reject the artifact ────────


@pytest.mark.asyncio
async def test_unresolved_5_8_in_body_forces_orchestrator_reject() -> None:
    sb = _sourcebook_with_5_8_in_body()
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=ClaimRegistry(),
            proposal_options=ProposalOptionRegistry(),
        )
    assert report.conformance_status == "fail"
    assert should_accept_source_book(_passing_review(), report) is False


@pytest.mark.asyncio
async def test_unresolved_5_8_in_slide_forces_reject() -> None:
    sb = _sourcebook_with_5_8_in_slide()
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=ClaimRegistry(),
            proposal_options=ProposalOptionRegistry(),
        )
    assert report.conformance_status == "fail"


# ── Acceptance #5 — unapproved option blocked from client-facing ──────


@pytest.mark.asyncio
async def test_unapproved_option_in_body_blocks_acceptance() -> None:
    claim_reg = ClaimRegistry()
    claim_reg.register(_option_claim())
    opt_reg = ProposalOptionRegistry()
    opt_reg.register(ProposalOption(
        option_id="OPT-5-8",
        text="Pilot scope: 5-8 countries",
        claim_provenance_id="OPT-5-8",
        category="numeric_range",
        approved_for_external_use=False,  # not approved
    ))
    sb = _sourcebook_with_5_8_in_body()
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=claim_reg,
            proposal_options=opt_reg,
        )
    # Either UNRESOLVED_COMMITMENT or UNAPPROVED_OPTION fires; both reject.
    flagged = {f.requirement_id for f in report.forbidden_claims}
    assert flagged & {"UNRESOLVED_COMMITMENT", "UNAPPROVED_OPTION"}
    assert report.conformance_status == "fail"


# ── Acceptance #6 — priced=True OR pricing_impact_note required ───────


def test_pricing_category_approved_but_unpriced_no_note_blocked() -> None:
    """Approved + priced=False + no pricing_impact_note → not externally
    publishable for pricing-relevant categories (numeric_range here)."""
    opt = ProposalOption(
        option_id="OPT-NPN",
        text="5-8 countries",
        claim_provenance_id="OPT-NPN",
        category="numeric_range",
        approved_for_external_use=True,
        priced=False,
        pricing_impact_note="",
    )
    assert opt.is_externally_publishable is False


def test_pricing_category_with_pricing_impact_note_publishable() -> None:
    opt = ProposalOption(
        option_id="OPT-N",
        text="5-8 countries",
        claim_provenance_id="OPT-N",
        category="numeric_range",
        approved_for_external_use=True,
        priced=False,
        pricing_impact_note="±5% absorbed in management fee",
    )
    assert opt.is_externally_publishable is True


def test_pricing_category_priced_publishable() -> None:
    opt = ProposalOption(
        option_id="OPT-P",
        text="5-8 countries",
        claim_provenance_id="OPT-P",
        category="numeric_range",
        approved_for_external_use=True,
        priced=True,
    )
    assert opt.is_externally_publishable is True


def test_non_pricing_category_does_not_require_pricing_signals() -> None:
    """methodology_choice and scope_boundary are not pricing-relevant —
    approval alone makes them publishable."""
    for cat in ("methodology_choice", "scope_boundary"):
        opt = ProposalOption(
            option_id=f"OPT-{cat}",
            text="x",
            claim_provenance_id=f"OPT-{cat}",
            category=cat,  # type: ignore[arg-type]
            approved_for_external_use=True,
            priced=False,
            pricing_impact_note="",
        )
        assert opt.is_externally_publishable is True


@pytest.mark.asyncio
async def test_pricing_category_approved_no_pricing_signal_still_blocks_acceptance() -> None:
    """Even with approved_for_external_use=True, a numeric_range option
    that is unpriced and lacks a pricing_impact_note cannot resolve a
    client-facing commitment. The orchestrator gate rejects."""
    claim_reg = ClaimRegistry()
    claim_reg.register(_option_claim())
    opt_reg = ProposalOptionRegistry()
    opt_reg.register(ProposalOption(
        option_id="OPT-5-8",
        text="Pilot scope: 5-8 countries",
        claim_provenance_id="OPT-5-8",
        category="numeric_range",
        approved_for_external_use=True,  # but…
        priced=False,
        pricing_impact_note="",  # no pricing signal
    ))
    sb = _sourcebook_with_5_8_in_body()
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=claim_reg,
            proposal_options=opt_reg,
        )
    assert report.conformance_status == "fail"
    assert should_accept_source_book(_passing_review(), report) is False


# ── Acceptance #7 — internal-only is safe ─────────────────────────────


@pytest.mark.asyncio
async def test_internal_bid_notes_text_does_not_block_acceptance() -> None:
    """A 5-8 commitment in the evidence ledger / internal notes does
    not trigger Pass 6 because those sections are internal-only."""
    from src.models.source_book import EvidenceLedger, EvidenceLedgerEntry
    sb = SourceBook(
        rfp_name="UNESCO",
        client_name="UNESCO",
        evidence_ledger=EvidenceLedger(entries=[
            EvidenceLedgerEntry(
                claim_id="CLM-INTERNAL",
                claim_text="Internal note: option for 5-8 countries pending approval",
                source_type="internal",
            ),
        ]),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=ClaimRegistry(),
            proposal_options=ProposalOptionRegistry(),
        )
    assert not any(
        f.requirement_id in {"UNRESOLVED_COMMITMENT", "UNAPPROVED_OPTION"}
        for f in report.forbidden_claims
    )


# ── Acceptance #8 — final gate rejects through the actual orchestrator ─


@pytest.mark.asyncio
async def test_orchestrator_gate_is_chokepoint_for_unresolved_commitments() -> None:
    """The end-to-end Slice-4 acceptance: validate_conformance produces
    a critical Pass-6 failure for an unresolved 5-8 commitment, and
    should_accept_source_book — the actual gate function called from
    graph.py — rejects."""
    sb = _sourcebook_with_5_8_in_body()
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=ClaimRegistry(),
            proposal_options=ProposalOptionRegistry(),
        )
    # Pass 6 fired
    assert any(
        f.requirement_id == "UNRESOLVED_COMMITMENT"
        for f in report.forbidden_claims
    )
    # Status is fail
    assert report.conformance_status == "fail"
    # Orchestrator gate rejects
    assert should_accept_source_book(_passing_review(), report) is False
