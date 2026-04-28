"""Proposal-option gating in conformance + orchestrator — Slice 4.3.

Pass 6 of validate_conformance scans rendered SourceBook sections for
two failure classes:
  * unresolved numeric commitments (numeric ranges/units in
    client-facing text that match neither an RFP fact nor an approved
    proposal option),
  * unapproved proposal_option text appearing in any client-facing
    section.

Both produce critical ConformanceFailure entries that drive
conformance_status="fail" → final_acceptance_decision="reject" through
the orchestrator gate path established in Slice 3.6.
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
    RFPInterpretation,
    SlideBlueprintEntry,
    SourceBook,
    SourceBookReview,
)


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


# ── Pass 6: unresolved numeric commitments produce critical failures ──


@pytest.mark.asyncio
async def test_unresolved_numeric_commitment_in_client_body_flagged() -> None:
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview="Phased rollout across 5-8 countries.",
        ),
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
    unresolved = [
        f for f in report.forbidden_claims
        if f.requirement_id == "UNRESOLVED_COMMITMENT"
    ]
    assert len(unresolved) >= 1
    assert any("5-8" in f.failure_reason for f in unresolved)
    # Critical → drives conformance fail + reject
    assert report.conformance_status == "fail"
    assert report.final_acceptance_decision == "reject"


@pytest.mark.asyncio
async def test_unresolved_commitment_in_slide_body_flagged() -> None:
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        slide_blueprints=[
            SlideBlueprintEntry(
                slide_number=3,
                title="Scope",
                key_message="Coverage spans 5-8 countries.",
            ),
        ],
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
    assert any(
        f.requirement_id == "UNRESOLVED_COMMITMENT"
        for f in report.forbidden_claims
    )
    assert report.conformance_status == "fail"


# ── Resolved commitments do not flag ──────────────────────────────────


@pytest.mark.asyncio
async def test_commitment_resolved_to_rfp_fact_passes() -> None:
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="RFP-FACT-DUR",
        text="Contract duration: 12 months",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview="Engagement runs 12 months end to end.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=reg,
            proposal_options=ProposalOptionRegistry(),
        )
    assert not any(
        f.requirement_id == "UNRESOLVED_COMMITMENT"
        for f in report.forbidden_claims
    )


@pytest.mark.asyncio
async def test_commitment_resolved_to_approved_option_passes() -> None:
    claim_reg = ClaimRegistry()
    claim_reg.register(ClaimProvenance(
        claim_id="OPT-RANGE-1",
        text="Pilot scope: 5-8 countries",
        claim_kind="proposal_option",
        source_kind="model_generated",
        verification_status="proposal_option",
    ))
    opt_reg = ProposalOptionRegistry()
    opt_reg.register(ProposalOption(
        option_id="OPT-RANGE-1",
        text="Pilot scope: 5-8 countries",
        claim_provenance_id="OPT-RANGE-1",
        category="numeric_range",
        approved_for_external_use=True,
        priced=True,
        approved_by="bid_director",
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview="Pilot scope: 5-8 countries.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=claim_reg,
            proposal_options=opt_reg,
        )
    assert not any(
        f.requirement_id == "UNRESOLVED_COMMITMENT"
        for f in report.forbidden_claims
    )


# ── Unapproved option text in client-facing — separate flag ───────────


@pytest.mark.asyncio
async def test_unapproved_option_text_in_client_facing_flagged() -> None:
    claim_reg = ClaimRegistry()
    claim_reg.register(ClaimProvenance(
        claim_id="OPT-NUM-1",
        text="propose dual-track methodology",
        claim_kind="proposal_option",
        source_kind="model_generated",
        verification_status="proposal_option",
    ))
    opt_reg = ProposalOptionRegistry()
    opt_reg.register(ProposalOption(
        option_id="OPT-NUM-1",
        text="propose dual-track methodology",
        claim_provenance_id="OPT-NUM-1",
        category="methodology_choice",
        approved_for_external_use=False,
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview=(
                "We propose dual-track methodology to deliver value."
            ),
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=claim_reg,
            proposal_options=opt_reg,
        )
    flagged = [
        f for f in report.forbidden_claims
        if f.requirement_id == "UNAPPROVED_OPTION"
    ]
    assert len(flagged) >= 1
    assert report.conformance_status == "fail"


@pytest.mark.asyncio
async def test_approved_option_text_in_client_facing_passes() -> None:
    claim_reg = ClaimRegistry()
    claim_reg.register(ClaimProvenance(
        claim_id="OPT-APPROVED",
        text="dual-track methodology",
        claim_kind="proposal_option",
        source_kind="model_generated",
        verification_status="proposal_option",
    ))
    opt_reg = ProposalOptionRegistry()
    opt_reg.register(ProposalOption(
        option_id="OPT-APPROVED",
        text="dual-track methodology",
        claim_provenance_id="OPT-APPROVED",
        category="methodology_choice",
        approved_for_external_use=True,
        priced=True,
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview="We propose dual-track methodology.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=claim_reg,
            proposal_options=opt_reg,
        )
    assert not any(
        f.requirement_id == "UNAPPROVED_OPTION"
        for f in report.forbidden_claims
    )


# ── Acceptance #7: internal-only sections don't trigger commitment scan ─


@pytest.mark.asyncio
async def test_internal_only_section_not_scanned_for_commitments() -> None:
    """Numeric commitments in evidence_ledger / internal_gap_appendix
    sections do not trigger the gate — they belong to internal
    notebooks, not client-facing artifacts."""
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="Clean text.",
        ),
    )
    # Force an evidence_ledger entry that has a numeric range.
    from src.models.source_book import EvidenceLedger, EvidenceLedgerEntry
    sb.evidence_ledger = EvidenceLedger(entries=[
        EvidenceLedgerEntry(
            claim_id="CLM-1",
            claim_text="Internal note: option for 5-8 countries pending approval",
            source_type="internal",
        ),
    ])
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
        f.requirement_id == "UNRESOLVED_COMMITMENT"
        for f in report.forbidden_claims
    )


# ── Final-gate path: orchestrator rejects on commitment failure ───────


@pytest.mark.asyncio
async def test_orchestrator_rejects_when_commitment_failure_present() -> None:
    """The orchestrator's should_accept_source_book sees the conformance
    fail and rejects, regardless of the coverage report status. This
    proves the Slice-4 failure flows through the actual gate path
    established in Slice 3.6."""
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview="Pilot 5-8 countries.",
        ),
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
    assert report.conformance_status == "fail"
    accepted = should_accept_source_book(_passing_review(), report)
    assert accepted is False
