"""Slide blueprint proof-point gating — Slice 2.3.

Every proof_point on every slide blueprint must resolve to a
ClaimProvenance in the ClaimRegistry AND pass can_use_as_proof_point().
Anything else is dropped from the blueprint and reported as a
ProofPointGatingViolation. PRJ-/CLI-/CLM- identifiers must be
resolvable to verified+permissioned claims to survive this gate.
"""
from __future__ import annotations

from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.source_book import SlideBlueprintEntry
from src.services.artifact_gates import (
    ProofPointGatingViolation,
    gate_slide_proof_points,
)


def _verified_internal(claim_id: str, text: str) -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_verified",
        evidence_role="bidder_capability_proof",
        requires_client_naming_permission=True,
        client_naming_permission=True,
        scope_summary_allowed_for_proposal=True,
    )


def _verified_external(claim_id: str, text: str) -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="direct_topic",
        evidence_role="methodology_support",
    )


def _unverified_internal(claim_id: str, text: str) -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_unverified",
    )


# ── Drop-and-report ────────────────────────────────────────────────────


def test_unresolved_proof_point_dropped() -> None:
    bp = SlideBlueprintEntry(
        slide_number=5,
        title="Capability proof",
        proof_points=["PRJ-001"],
    )
    registry = ClaimRegistry()
    gated, violations = gate_slide_proof_points([bp], registry)
    assert gated[0].proof_points == []
    assert len(violations) == 1
    assert violations[0].slide_number == 5
    assert violations[0].proof_point == "PRJ-001"
    assert violations[0].reason == "unresolved_in_registry"


def test_unverified_internal_proof_point_dropped() -> None:
    bp = SlideBlueprintEntry(
        slide_number=8,
        title="SDAIA experience",
        proof_points=["BIDDER-001"],
    )
    registry = ClaimRegistry()
    registry.register(_unverified_internal("BIDDER-001", "SG SDAIA project"))
    gated, violations = gate_slide_proof_points([bp], registry)
    assert gated[0].proof_points == []
    assert len(violations) == 1
    assert violations[0].claim_id == "BIDDER-001"
    assert violations[0].reason == "not_a_proof_point"
    assert violations[0].verification_status == "internal_unverified"


# ── Keep-when-verified ─────────────────────────────────────────────────


def test_verified_external_methodology_kept() -> None:
    bp = SlideBlueprintEntry(
        slide_number=3,
        title="UNESCO methodology",
        proof_points=["EXT-007"],
    )
    registry = ClaimRegistry()
    registry.register(_verified_external("EXT-007", "UNESCO RAM framework"))
    gated, violations = gate_slide_proof_points([bp], registry)
    assert gated[0].proof_points == ["EXT-007"]
    assert violations == []


def test_verified_internal_with_permissions_kept() -> None:
    bp = SlideBlueprintEntry(
        slide_number=10,
        title="Prior client engagement",
        proof_points=["BIDDER-123"],
    )
    registry = ClaimRegistry()
    registry.register(_verified_internal("BIDDER-123", "SDAIA AI program 2024"))
    gated, violations = gate_slide_proof_points([bp], registry)
    assert gated[0].proof_points == ["BIDDER-123"]
    assert violations == []


def test_text_resolution_kept_when_verified() -> None:
    """proof_point can be a text snippet, resolved via registry text match."""
    bp = SlideBlueprintEntry(
        slide_number=12,
        title="Methodology",
        proof_points=["UNESCO RAM framework"],
    )
    registry = ClaimRegistry()
    registry.register(_verified_external("EXT-007", "UNESCO RAM framework"))
    gated, violations = gate_slide_proof_points([bp], registry)
    assert gated[0].proof_points == ["UNESCO RAM framework"]
    assert violations == []


# ── must_have_evidence is gated alongside proof_points ─────────────────


def test_must_have_evidence_unverified_dropped() -> None:
    bp = SlideBlueprintEntry(
        slide_number=7,
        title="Required proof",
        must_have_evidence=["PRJ-002"],
        proof_points=["PRJ-002"],
    )
    registry = ClaimRegistry()
    registry.register(_unverified_internal("PRJ-002", "Some unverified project"))
    gated, violations = gate_slide_proof_points([bp], registry)
    assert gated[0].proof_points == []
    assert gated[0].must_have_evidence == []
    # Reported once for proof_points and once for must_have_evidence
    assert len(violations) == 2


def test_must_have_evidence_verified_kept() -> None:
    bp = SlideBlueprintEntry(
        slide_number=4,
        title="Required proof",
        must_have_evidence=["EXT-007"],
        proof_points=["EXT-007"],
    )
    registry = ClaimRegistry()
    registry.register(_verified_external("EXT-007", "UNESCO RAM"))
    gated, violations = gate_slide_proof_points([bp], registry)
    assert gated[0].proof_points == ["EXT-007"]
    assert gated[0].must_have_evidence == ["EXT-007"]
    assert violations == []


# ── Mixed: kept and dropped on the same slide ──────────────────────────


def test_mixed_proof_points_partial_kept() -> None:
    bp = SlideBlueprintEntry(
        slide_number=9,
        title="Mixed",
        proof_points=["EXT-007", "PRJ-001", "BIDDER-VERIFIED"],
    )
    registry = ClaimRegistry()
    registry.register(_verified_external("EXT-007", "Verified external"))
    registry.register(_verified_internal("BIDDER-VERIFIED", "Verified bidder"))
    # PRJ-001 unresolved
    gated, violations = gate_slide_proof_points([bp], registry)
    assert sorted(gated[0].proof_points) == sorted(["EXT-007", "BIDDER-VERIFIED"])
    assert len(violations) == 1
    assert violations[0].proof_point == "PRJ-001"


# ── Empty registry / empty blueprint behavior ──────────────────────────


def test_blueprint_without_proof_points_unaffected() -> None:
    bp = SlideBlueprintEntry(slide_number=1, title="Title slide")
    registry = ClaimRegistry()
    gated, violations = gate_slide_proof_points([bp], registry)
    assert gated[0].proof_points == []
    assert violations == []


def test_violation_carries_full_context() -> None:
    bp = SlideBlueprintEntry(
        slide_number=11,
        title="Capability proof",
        proof_points=["BIDDER-X"],
    )
    registry = ClaimRegistry()
    registry.register(_unverified_internal("BIDDER-X", "Unverified internal"))
    gated, violations = gate_slide_proof_points([bp], registry)
    v = violations[0]
    assert isinstance(v, ProofPointGatingViolation)
    assert v.slide_number == 11
    assert v.proof_point == "BIDDER-X"
    assert v.claim_id == "BIDDER-X"
    assert v.reason == "not_a_proof_point"
    assert v.verification_status == "internal_unverified"
