"""Generated-inference gating in conformance — Slice 5.4 / Pass 7.

Acceptance #9: the final gate rejects unlabelled generated assumptions
in client-facing sections or slide proof points. Labelled inferences
are allowed only in approved contexts:
  * source-book analysis bodies when ``"source_book_analysis" in
    inference_allowed_context``;
  * speaker notes when ``"speaker_notes" in inference_allowed_context``.

Pass 7 walks every rendered ArtifactSection and, for each registered
generated_inference claim whose text appears in the section, applies
the correct context gate. Failed gates produce critical
``UNLABELLED_INFERENCE`` ConformanceFailure entries that drive
conformance_status="fail" → orchestrator reject.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.source_book.conformance_validator import validate_conformance
from src.agents.source_book.orchestrator import should_accept_source_book
from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.common import BilingualText
from src.models.rfp import RFPContext
from src.models.source_book import (
    ProposedSolution,
    RFPInterpretation,
    SlideBlueprintEntry,
    SourceBook,
    SourceBookReview,
    WhyStrategicGears,
)
from src.services.artifact_gates import can_use_as_proof_point


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


def _inference(
    claim_id: str,
    text: str,
    *,
    labelled: bool = False,
    contexts: list[str] | None = None,
) -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="generated_inference",
        source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=labelled,
        inference_allowed_context=contexts or [],
    )


# ── Acceptance #2 — generated_inference never proof point ─────────────


def test_unlabelled_inference_never_proof_point() -> None:
    assert can_use_as_proof_point(_inference("INF-1", "Award is pass/fail")) is False


def test_labelled_inference_with_speaker_notes_still_not_proof() -> None:
    """Even fully-labelled inferences cannot be proof points — proof
    requires verified evidence, not authored guesses."""
    claim = _inference(
        "INF-2",
        "Award is pass/fail",
        labelled=True,
        contexts=["speaker_notes", "source_book_analysis"],
    )
    assert can_use_as_proof_point(claim) is False


# ── Pass 7: unlabelled inference in client-facing body → fail ─────────


@pytest.mark.asyncio
async def test_unlabelled_inference_in_client_body_flagged() -> None:
    reg = ClaimRegistry()
    reg.register(_inference(
        "INF-AWARD",
        "Award mechanism likely pass/fail",
        labelled=False,
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope=(
                "Award mechanism likely pass/fail per evaluator pattern."
            ),
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=reg,
        )
    flagged = [
        f for f in report.forbidden_claims
        if f.requirement_id == "UNLABELLED_INFERENCE"
    ]
    assert len(flagged) >= 1
    assert any("INF-AWARD" in f.failure_reason for f in flagged)
    assert report.conformance_status == "fail"
    assert should_accept_source_book(_passing_review(), report) is False


# ── Acceptance #3: labelled + source_book_analysis context → allowed ──


@pytest.mark.asyncio
async def test_labelled_inference_with_source_book_analysis_context_allowed() -> None:
    reg = ClaimRegistry()
    reg.register(_inference(
        "INF-AWARD-2",
        "Award mechanism likely pass/fail",
        labelled=True,
        contexts=["source_book_analysis"],
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="Award mechanism likely pass/fail per evaluator pattern.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=reg,
        )
    assert not any(
        f.requirement_id == "UNLABELLED_INFERENCE"
        for f in report.forbidden_claims
    )


@pytest.mark.asyncio
async def test_labelled_inference_without_required_context_blocked() -> None:
    """Acceptance #3: labelled + ``source_book_analysis`` must be in
    inference_allowed_context. Just labelled is not enough."""
    reg = ClaimRegistry()
    reg.register(_inference(
        "INF-X",
        "Award mechanism likely pass/fail",
        labelled=True,
        contexts=["speaker_notes"],  # no source_book_analysis
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="Award mechanism likely pass/fail per evaluator pattern.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=reg,
        )
    assert any(
        f.requirement_id == "UNLABELLED_INFERENCE"
        for f in report.forbidden_claims
    )


# ── Slide proof points NEVER carry inferences ────────────────────────


@pytest.mark.asyncio
async def test_inference_in_slide_proof_points_always_blocked() -> None:
    """Even labelled inferences cannot survive in slide_proof_points
    — proof_points must pass can_use_as_proof_point."""
    reg = ClaimRegistry()
    reg.register(_inference(
        "INF-PROOF",
        "competitor likely Big Four firm",
        labelled=True,
        contexts=["source_book_analysis", "slide_blueprint"],
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        slide_blueprints=[
            SlideBlueprintEntry(
                slide_number=8,
                title="Competitive landscape",
                proof_points=["competitor likely Big Four firm"],
                must_have_evidence=["competitor likely Big Four firm"],
            ),
        ],
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=reg,
        )
    assert any(
        f.requirement_id == "UNLABELLED_INFERENCE"
        for f in report.forbidden_claims
    )
    assert report.conformance_status == "fail"


@pytest.mark.asyncio
async def test_inference_in_slide_body_blocked() -> None:
    reg = ClaimRegistry()
    reg.register(_inference(
        "INF-BODY",
        "client priority likely cost reduction",
        labelled=False,
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        slide_blueprints=[
            SlideBlueprintEntry(
                slide_number=2,
                title="Why now",
                key_message="client priority likely cost reduction.",
            ),
        ],
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=reg,
        )
    assert any(
        f.requirement_id == "UNLABELLED_INFERENCE"
        for f in report.forbidden_claims
    )


# ── Internal-only sections always allowed ────────────────────────────


@pytest.mark.asyncio
async def test_inference_in_evidence_ledger_allowed() -> None:
    """evidence_ledger / internal_gap_appendix sections allow any
    inference: those sections are internal notebooks."""
    from src.models.source_book import EvidenceLedger, EvidenceLedgerEntry

    reg = ClaimRegistry()
    reg.register(_inference(
        "INF-NOTE",
        "internal hypothesis: award is likely pass/fail",
        labelled=False,
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        evidence_ledger=EvidenceLedger(entries=[
            EvidenceLedgerEntry(
                claim_id="CLM-1",
                claim_text="internal hypothesis: award is likely pass/fail",
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
            claim_registry=reg,
        )
    assert not any(
        f.requirement_id == "UNLABELLED_INFERENCE"
        for f in report.forbidden_claims
    )


# ── Proof-column also blocked when inference unlabelled ──────────────


@pytest.mark.asyncio
async def test_inference_in_proof_column_blocked() -> None:
    reg = ClaimRegistry()
    reg.register(_inference(
        "INF-PROOF-COL",
        "team likely has SDAIA experience",
        labelled=False,
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        why_strategic_gears=WhyStrategicGears(
            certifications_and_compliance=[
                "team likely has SDAIA experience",
            ],
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=reg,
        )
    assert any(
        f.requirement_id == "UNLABELLED_INFERENCE"
        for f in report.forbidden_claims
    )


# ── Clean SourceBook produces no Pass-7 flags ────────────────────────


@pytest.mark.asyncio
async def test_clean_source_book_no_inference_failures() -> None:
    reg = ClaimRegistry()
    reg.register(_inference(
        "INF-IDLE",
        "internal speculation about competitor pricing",
        labelled=False,
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope="Clean text without any inference.",
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=reg,
        )
    assert not any(
        f.requirement_id == "UNLABELLED_INFERENCE"
        for f in report.forbidden_claims
    )
    # Conformance can still pass — no inferences leaked.
    assert report.conformance_status == "pass"


# ── Final-gate orchestrator path ─────────────────────────────────────


@pytest.mark.asyncio
async def test_orchestrator_rejects_when_inference_failure_present() -> None:
    """The orchestrator gate (the chokepoint Slice-3.6 wired) rejects
    on any critical Pass-7 UNLABELLED_INFERENCE."""
    reg = ClaimRegistry()
    reg.register(_inference(
        "INF-LEAK",
        "client likely values rapid mobilization",
    ))
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        proposed_solution=ProposedSolution(
            methodology_overview=(
                "client likely values rapid mobilization above all else."
            ),
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
            claim_registry=reg,
        )
    assert report.conformance_status == "fail"
    assert should_accept_source_book(_passing_review(), report) is False
