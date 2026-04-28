"""Forbidden-leakage scanner integrated into conformance validator (Pass 5).

Slice 2.2: when validate_conformance receives a SourceBook with PRJ-/CLI-/CLM-
identifiers in client-facing sections, the scanner produces ConformanceFailure
entries on `forbidden_claims`. Internal-only sections (evidence_ledger,
internal_gap_appendix) are exempt. When a ClaimRegistry is supplied and a
matching verified+permissioned claim exists, the semantic phrase is allowed.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.source_book.conformance_validator import validate_conformance
from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.common import BilingualText
from src.models.conformance import HardRequirement
from src.models.rfp import RFPContext
from src.models.source_book import (
    ClientProblemFraming,
    EvidenceLedger,
    EvidenceLedgerEntry,
    RFPInterpretation,
    SlideBlueprintEntry,
    SourceBook,
    WhyStrategicGears,
)


def _minimal_rfp() -> RFPContext:
    return RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )


def _patch_pass3():
    return patch(
        "src.agents.source_book.conformance_validator._pass3_semantic_checks",
        AsyncMock(return_value=[]),
    )


@pytest.mark.asyncio
async def test_prj_id_in_client_facing_section_flagged() -> None:
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="Bidder has prior project [PRJ-001] with SDAIA.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )

    leakage_failures = [
        f for f in report.forbidden_claims
        if "PRJ-001" in f.failure_reason or "PRJ-001" in f.requirement_text
    ]
    assert len(leakage_failures) >= 1, (
        f"PRJ-001 must be flagged by Pass 5; got forbidden_claims="
        f"{[f.failure_reason for f in report.forbidden_claims]}"
    )


@pytest.mark.asyncio
async def test_cli_id_in_slide_blueprint_proof_points_flagged() -> None:
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        slide_blueprints=[
            SlideBlueprintEntry(
                slide_number=8,
                title="Capability proof",
                proof_points=["CLI-002", "EXT-007"],
                must_have_evidence=["CLI-002", "EXT-007"],
            ),
        ],
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )

    assert any(
        "CLI-002" in f.failure_reason for f in report.forbidden_claims
    ), f"CLI-002 must be flagged in slide proof points; got {[f.failure_reason for f in report.forbidden_claims]}"


@pytest.mark.asyncio
async def test_clm_id_in_proof_column_flagged() -> None:
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        why_strategic_gears=WhyStrategicGears(
            certifications_and_compliance=["CLM-099 internal proof"],
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )

    assert any(
        "CLM-099" in f.failure_reason for f in report.forbidden_claims
    )


@pytest.mark.asyncio
async def test_evidence_ledger_section_is_internal_and_exempt() -> None:
    """PRJ/CLI/CLM in evidence_ledger is fine — that section is internal-only."""
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        evidence_ledger=EvidenceLedger(
            entries=[
                EvidenceLedgerEntry(
                    claim_id="CLM-099",
                    claim_text="internal note: PRJ-001 needs Engine 2",
                    source_type="internal",
                ),
            ],
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )

    # No leakage failure should be produced from the evidence_ledger section.
    leakage_failures = [
        f for f in report.forbidden_claims
        if f.requirement_id == "FORBIDDEN-LEAKAGE"
    ]
    assert leakage_failures == []


@pytest.mark.asyncio
async def test_semantic_phrase_in_client_body_flagged_without_registry() -> None:
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        client_problem_framing=ClientProblemFraming(
            current_state_challenge=(
                "خبرة موثقة في العمل مع سدايا تتيح لنا تنفيذ المشروع."
            ),
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )

    assert any(
        "خبرة موثقة" in f.failure_reason or "سدايا" in f.failure_reason
        for f in report.forbidden_claims
    )


@pytest.mark.asyncio
async def test_semantic_phrase_allowed_when_registry_has_verified_claim() -> None:
    """If a verified+permissioned bidder claim covers the semantic phrase,
    the scanner does not flag it."""
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        client_problem_framing=ClientProblemFraming(
            current_state_challenge=(
                "خبرة موثقة في العمل مع سدايا تتيح لنا تنفيذ المشروع."
            ),
        ),
    )
    registry = ClaimRegistry()
    registry.register(ClaimProvenance(
        claim_id="BIDDER-VERIFIED-001",
        text="خبرة موثقة في العمل مع سدايا",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_verified",
        requires_client_naming_permission=True,
        client_naming_permission=True,
        scope_summary_allowed_for_proposal=True,
    ))

    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=registry,
        )

    semantic_failures = [
        f for f in report.forbidden_claims
        if "خبرة موثقة" in f.failure_reason
    ]
    assert semantic_failures == [], (
        f"Verified+permissioned claim should suppress semantic flag, "
        f"got {[f.failure_reason for f in semantic_failures]}"
    )


@pytest.mark.asyncio
async def test_clean_source_book_produces_no_leakage_flags() -> None:
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="Clean text without identifiers.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )
    leakage_failures = [
        f for f in report.forbidden_claims
        if f.requirement_id == "FORBIDDEN-LEAKAGE"
    ]
    assert leakage_failures == []


@pytest.mark.asyncio
async def test_leakage_failures_are_critical() -> None:
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="PRJ-001 leaked into body.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )
    leakage_failures = [
        f for f in report.forbidden_claims
        if f.requirement_id == "FORBIDDEN-LEAKAGE"
    ]
    assert len(leakage_failures) >= 1
    for f in leakage_failures:
        assert f.severity == "critical"


# ── Slice 2.5: leakage must force conformance fail + reject ───────────


@pytest.mark.asyncio
async def test_leakage_blocks_acceptance_with_no_hrs() -> None:
    """Even when there are zero hard requirements, a forbidden-leakage
    failure in client-facing body forces conformance_status=fail and
    final_acceptance_decision=reject. Prevents the 'no HRs → auto-pass'
    bypass that existed before Slice 2.2."""
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="PRJ-001 leaked into client body.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )
    assert report.conformance_status == "fail"
    assert report.final_acceptance_decision == "reject"


@pytest.mark.asyncio
async def test_leakage_blocks_acceptance_alongside_passing_hrs() -> None:
    """Even when every hard requirement passes, a single PRJ leak in
    client-facing content must still produce conformance fail + reject."""
    hr = HardRequirement(
        requirement_id="HR-DUMMY-001",
        category="contract_duration",
        subject="Contract duration",
        value_text="6",
        value_number=6.0,
        validation_scope="source_book",
        severity="major",
    )
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="Contract is 6 months. Bidder has PRJ-001.",
        ),
    )
    rfp = _minimal_rfp()
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[hr],
            rfp_context=rfp,
            uploaded_documents=[],
        )
    leakage_failures = [
        f for f in report.forbidden_claims
        if f.requirement_id == "FORBIDDEN-LEAKAGE"
    ]
    assert len(leakage_failures) >= 1
    assert report.conformance_status == "fail"
    assert report.final_acceptance_decision == "reject"


@pytest.mark.asyncio
async def test_clean_source_book_with_zero_hrs_passes() -> None:
    """Counterfactual: with no leakage AND no HRs, the validator returns
    pass/accept. This isolates the leakage signal as the rejection cause."""
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="Clean text without internal identifiers.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )
    assert report.conformance_status == "pass"
    assert report.final_acceptance_decision == "accept"


@pytest.mark.asyncio
async def test_final_artifact_gate_rejects_on_leakage() -> None:
    """final_artifact_gate must produce decision=reject when the
    conformance report carries any forbidden-leakage failure."""
    from src.models.source_book import SourceBookReview
    from src.services.artifact_gates import (
        EvidenceCoverageReport,
        EvidenceCoverageRequirement,
        final_artifact_gate,
    )

    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="PRJ-001 leaked into client body.",
        ),
    )
    with _patch_pass3():
        conf = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )

    review = SourceBookReview(
        overall_score=4, pass_threshold_met=True,
        competitive_viability="adequate",
    )
    coverage = EvidenceCoverageReport(
        requirements=[EvidenceCoverageRequirement(
            topic="dummy", minimum_direct_sources=1, found_direct=1, status="met",
        )],
        status="pass",
    )

    decision = final_artifact_gate(
        conf, review, coverage, [], ClaimRegistry(), [],
    )
    assert decision.decision == "reject"
    assert decision.proposal_ready is False
    assert "DRAFT" in decision.artifact_label
