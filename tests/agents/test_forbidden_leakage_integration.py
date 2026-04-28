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
