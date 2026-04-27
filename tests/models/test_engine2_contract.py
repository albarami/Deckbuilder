"""Tests for Engine 2 contract models."""
from src.models.engine2_contract import (
    Engine2ProofRequest,
    Engine2ProofResponse,
    default_engine2_response,
)


def test_default_response_is_unverified():
    req = Engine2ProofRequest(
        claim_id="BIDDER-001",
        claim_text="SDAIA project",
        requested_proof_type="prior_project",
    )
    resp = default_engine2_response(req)
    assert resp.verified is False
    assert resp.verification_status == "internal_unverified"
    assert resp.client_name_disclosure_allowed is False
    assert resp.partner_name_disclosure_allowed is False
    assert resp.scope_summary_allowed_for_proposal is False


def test_request_carries_permission_requirements():
    req = Engine2ProofRequest(
        claim_id="BIDDER-002",
        claim_text="UNESCO partnership",
        requested_proof_type="partner_permission",
        requires_partner_naming_permission=True,
        anonymized_allowed=True,
    )
    assert req.requires_partner_naming_permission is True
    assert req.anonymized_allowed is True


def test_request_carries_external_contexts():
    req = Engine2ProofRequest(
        claim_id="BIDDER-003",
        claim_text="Prior project",
        requested_proof_type="prior_project",
        requested_external_contexts=["source_book", "slide_blueprint"],
    )
    assert req.requested_external_contexts == ["source_book", "slide_blueprint"]


def test_response_with_approved_wording():
    resp = Engine2ProofResponse(
        claim_id="BIDDER-004",
        verified=True,
        verification_status="internal_verified",
        client_name_disclosure_allowed=True,
        approved_public_wording="Previous work with a Saudi government AI authority",
        anonymized_wording="a Saudi government authority",
    )
    assert resp.verified is True
    assert resp.approved_public_wording is not None
