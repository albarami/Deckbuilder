"""Tests for ClaimRegistry, typed ledgers, and ClaimLedgerBundle."""
import pytest

from src.models.claim_provenance import (
    BidderEvidenceLedger,
    ClaimLedgerBundle,
    ClaimProvenance,
    ClaimRegistry,
    ExternalMethodologyLedger,
    ProposalOptionLedger,
    RFPFactLedger,
)


# ── ClaimRegistry ────────────────────────────────────────────────


def test_registry_register_and_get():
    reg = ClaimRegistry()
    c = ClaimProvenance(
        claim_id="RFP-FACT-001", text="test",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    )
    reg.register(c)
    assert reg.get("RFP-FACT-001") is not None
    assert reg.get("NONEXISTENT") is None


def test_registry_views():
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="RFP-001", text="t", claim_kind="rfp_fact",
        source_kind="rfp_document", verification_status="verified_from_rfp",
    ))
    reg.register(ClaimProvenance(
        claim_id="BIDDER-001", text="t", claim_kind="internal_company_claim",
        source_kind="internal_backend", verification_status="internal_unverified",
    ))
    reg.register(ClaimProvenance(
        claim_id="EXT-001", text="t", claim_kind="external_methodology",
        source_kind="external_source", verification_status="externally_verified",
    ))
    reg.register(ClaimProvenance(
        claim_id="OPT-001", text="t", claim_kind="proposal_option",
        source_kind="model_generated", verification_status="proposal_option",
    ))
    reg.register(ClaimProvenance(
        claim_id="INF-001", text="t", claim_kind="generated_inference",
        source_kind="model_generated", verification_status="generated_inference",
    ))
    assert len(reg.rfp_facts) == 1
    assert len(reg.bidder_claims) == 1
    assert len(reg.external_methodology) == 1
    assert len(reg.proposal_options) == 1
    assert len(reg.generated_inferences) == 1


def test_resolve_proof_point_by_id():
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="EXT-007", text="UNESCO RAM",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
    ))
    assert reg.resolve_proof_point("EXT-007") is not None
    assert reg.resolve_proof_point("EXT-007").claim_id == "EXT-007"


def test_resolve_proof_point_by_text():
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="RFP-002", text="مدة العقد 12 شهراً",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    resolved = reg.resolve_proof_point("مدة العقد 12 شهراً")
    assert resolved is not None
    assert resolved.claim_id == "RFP-002"


def test_resolve_proof_point_returns_none_for_unknown():
    reg = ClaimRegistry()
    assert reg.resolve_proof_point("totally unknown text") is None


# ── Typed Ledgers ────────────────────────────────────────────────


def test_rfp_fact_ledger_rejects_wrong_kind():
    with pytest.raises((AssertionError, Exception)):
        RFPFactLedger(entries=[ClaimProvenance(
            claim_id="BAD", text="t", claim_kind="internal_company_claim",
            source_kind="internal_backend", verification_status="internal_unverified",
        )])


def test_rfp_fact_ledger_accepts_correct_kind():
    ledger = RFPFactLedger(entries=[ClaimProvenance(
        claim_id="RFP-001", text="t", claim_kind="rfp_fact",
        source_kind="rfp_document", verification_status="verified_from_rfp",
    )])
    assert len(ledger.entries) == 1


def test_bidder_ledger_rejects_rfp_fact():
    with pytest.raises((AssertionError, Exception)):
        BidderEvidenceLedger(entries=[ClaimProvenance(
            claim_id="RFP-001", text="t", claim_kind="rfp_fact",
            source_kind="rfp_document", verification_status="verified_from_rfp",
        )])


def test_bidder_ledger_accepts_internal():
    ledger = BidderEvidenceLedger(entries=[ClaimProvenance(
        claim_id="BIDDER-001", text="t", claim_kind="internal_company_claim",
        source_kind="internal_backend", verification_status="internal_unverified",
    )])
    assert len(ledger.entries) == 1


def test_external_ledger_rejects_internal():
    with pytest.raises((AssertionError, Exception)):
        ExternalMethodologyLedger(entries=[ClaimProvenance(
            claim_id="BIDDER-001", text="t", claim_kind="internal_company_claim",
            source_kind="internal_backend", verification_status="internal_unverified",
        )])


def test_proposal_option_ledger_accepts_options():
    ledger = ProposalOptionLedger(entries=[ClaimProvenance(
        claim_id="OPT-001", text="5-8 countries", claim_kind="proposal_option",
        source_kind="model_generated", verification_status="proposal_option",
    )])
    assert len(ledger.entries) == 1


# ── ClaimLedgerBundle ────────────────────────────────────────────


def test_bundle_creation():
    bundle = ClaimLedgerBundle(
        registry=ClaimRegistry(),
        rfp_fact_ledger=RFPFactLedger(),
        bidder_evidence_ledger=BidderEvidenceLedger(),
        external_methodology_ledger=ExternalMethodologyLedger(),
        proposal_option_ledger=ProposalOptionLedger(),
    )
    assert bundle.compliance_index is None
