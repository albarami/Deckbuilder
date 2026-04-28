"""Engine 2 contract interface — request/response models and default resolver.

Engine 2 does not exist yet. This module defines the contract boundary
so Engine 1 can enforce gating rules regardless. The default resolver
returns internal_unverified for everything, which blocks proposal-facing use.

When Engine 2 is later implemented, it only changes verification_status
and disclosure permissions — it does not change the pipeline rules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from src.models.common import DeckForgeBaseModel

if TYPE_CHECKING:
    from src.models.claim_provenance import ClaimProvenance, ClaimRegistry


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


def _infer_proof_type(claim: "ClaimProvenance") -> str:
    """Infer the requested_proof_type for a bidder evidence claim."""
    text = claim.text.lower()
    if "cv" in text or "consultant" in text or "team" in text:
        return "consultant_cv"
    if "certificate" in text or "شهادة" in claim.text:
        return "company_certificate"
    if "case study" in text or "case_study" in text:
        return "case_study"
    if "permission" in text or "naming" in text:
        return (
            "partner_permission"
            if claim.requires_partner_naming_permission
            else "client_permission"
        )
    if "client reference" in text or "reference" in text:
        return "client_reference"
    if "legal" in text or "registration" in text or "license" in text:
        return "legal_document"
    return "prior_project"


def build_engine2_shopping_list(
    registry: "ClaimRegistry",
) -> list[Engine2ProofRequest]:
    """Build the Engine 2 proof-shopping list from the ClaimRegistry.

    Filters on claim properties (not ID prefixes). Only emits requests for
    bidder evidence claims that are still ``internal_unverified``. RFP
    facts, external methodology, proposal options, and generated
    inferences are NEVER added — that is the core invariant of Slice 1.
    """
    requests: list[Engine2ProofRequest] = []
    for claim in registry.claims.values():
        if claim.claim_kind != "internal_company_claim":
            continue
        if claim.source_kind != "internal_backend":
            continue
        if claim.verification_status != "internal_unverified":
            continue

        internal_ref = (
            claim.source_refs[0].evidence_id
            if claim.source_refs
            else None
        )
        requests.append(
            Engine2ProofRequest(
                claim_id=claim.claim_id,
                claim_text=claim.text,
                requested_proof_type=_infer_proof_type(claim),
                internal_ref=internal_ref,
                requested_external_contexts=(
                    list(claim.requested_external_contexts)
                    if claim.requested_external_contexts
                    else ["source_book"]
                ),
                requires_client_naming_permission=(
                    claim.requires_client_naming_permission
                ),
                requires_partner_naming_permission=(
                    claim.requires_partner_naming_permission
                ),
                requires_scope_summary_permission=(
                    claim.scope_summary_allowed_for_proposal is not None
                ),
            )
        )

    # Defensive invariant: no non-bidder claim may ever appear here.
    for r in requests:
        c = registry.get(r.claim_id)
        assert c is not None and c.claim_kind == "internal_company_claim", (
            f"build_engine2_shopping_list invariant violated for {r.claim_id}"
        )
    return requests
