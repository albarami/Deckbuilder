"""Engine 2 contract interface — request/response models and default resolver.

Engine 2 does not exist yet. This module defines the contract boundary
so Engine 1 can enforce gating rules regardless. The default resolver
returns internal_unverified for everything, which blocks proposal-facing use.

When Engine 2 is later implemented, it only changes verification_status
and disclosure permissions — it does not change the pipeline rules.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.models.common import DeckForgeBaseModel


class Engine2ProofRequest(DeckForgeBaseModel):
    """What Engine 1 asks Engine 2 to verify."""

    claim_id: str
    claim_text: str
    requested_proof_type: Literal[
        "prior_project",
        "client_reference",
        "consultant_cv",
        "company_certificate",
        "legal_document",
        "case_study",
        "client_permission",
        "partner_permission",
    ]
    internal_ref: str | None = None
    requested_external_contexts: list[
        Literal["source_book", "slide_blueprint", "proposal", "attachment_pack"]
    ] = Field(default_factory=list)
    requires_client_naming_permission: bool = False
    requires_partner_naming_permission: bool = False
    requires_scope_summary_permission: bool = False
    desired_external_wording: str | None = None
    anonymized_allowed: bool = True


class Engine2ProofResponse(DeckForgeBaseModel):
    """What Engine 2 returns after verification."""

    claim_id: str
    verified: bool = False
    verification_status: Literal[
        "internal_verified",
        "internal_unverified",
        "not_found",
        "permission_denied",
        "insufficient_evidence",
    ] = "internal_unverified"

    client_name_disclosure_allowed: bool = False
    partner_name_disclosure_allowed: bool = False
    scope_summary_allowed_for_proposal: bool = False
    public_case_study_available: bool = False

    evidence_refs: list[str] = Field(default_factory=list)
    approved_public_wording: str | None = None
    anonymized_wording: str | None = None
    reviewer_notes: str | None = None


def default_engine2_response(
    request: Engine2ProofRequest,
) -> Engine2ProofResponse:
    """Default: everything unverified, everything blocked."""
    return Engine2ProofResponse(
        claim_id=request.claim_id,
        verified=False,
        verification_status="internal_unverified",
        reviewer_notes=(
            "Engine 2 not implemented. "
            "Claim blocked from proposal-facing use."
        ),
    )
