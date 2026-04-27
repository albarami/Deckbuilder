"""Artifact gates — context-specific usage rules for claims in the pipeline.

Every claim must pass the appropriate gate before appearing in an artifact.
The gates form a hierarchy from most permissive (internal_gap_appendix)
to most restrictive (client_proposal / proof_point).

Architecture invariant:
    absence of Engine 2 verification defaults to internal_unverified = blocked.
"""

from __future__ import annotations

from typing import Literal

from src.models.claim_provenance import ClaimProvenance


# ── Context-specific gates ───────────────────────────────────────


def can_use_as_proof_point(claim: ClaimProvenance) -> bool:
    """Strictest gate: proof columns, capability evidence, slide proof_points.

    Only verified + permissioned claims pass.
    """
    if claim.verification_status == "forbidden":
        return False

    if claim.claim_kind == "rfp_fact":
        return claim.verification_status == "verified_from_rfp"

    if claim.claim_kind == "external_methodology":
        return (
            claim.verification_status == "externally_verified"
            and claim.relevance_class in ("direct_topic", "adjacent_domain")
            and claim.evidence_role == "methodology_support"
        )

    if claim.claim_kind == "internal_company_claim":
        if claim.verification_status != "internal_verified":
            return False
        if (
            claim.requires_client_naming_permission
            and claim.client_naming_permission is not True
        ):
            return False
        if (
            claim.requires_partner_naming_permission
            and claim.partner_naming_permission is not True
        ):
            return False
        if claim.scope_summary_allowed_for_proposal is False:
            return False
        return True

    # proposal_option, generated_inference: never proof points
    return False


def can_use_in_source_book_analysis(
    claim: ClaimProvenance,
    section_type: Literal[
        "client_facing_body",
        "internal_bid_notes",
        "internal_gap_appendix",
        "evidence_gap_register",
    ],
) -> bool:
    """Source book body: analysis, problem framing, methodology design.

    Internal sections allow everything. Client-facing body is selective:
    - rfp_facts: always
    - external_methodology: verified or partially_verified (with restrictions)
    - internal_company_claim: only if internal_verified
    - generated_inference: only if labelled + context-approved
    - proposal_option: never in client-facing body
    """
    if claim.verification_status == "forbidden":
        return False

    if section_type in ("internal_gap_appendix", "evidence_gap_register"):
        return True

    if section_type == "internal_bid_notes":
        return True  # everything except forbidden

    # client_facing_body rules:
    if claim.claim_kind == "rfp_fact":
        return True

    if claim.claim_kind == "external_methodology":
        if claim.verification_status == "externally_verified":
            return claim.relevance_class in (
                "direct_topic",
                "adjacent_domain",
                "analogical",
            )
        if claim.verification_status == "partially_verified":
            return (
                claim.relevance_class != "analogical"
                and claim.evidence_role
                in ("methodology_support", "risk_or_assumption_support")
            )
        return False

    if claim.claim_kind == "internal_company_claim":
        return claim.verification_status == "internal_verified"

    if claim.claim_kind == "generated_inference":
        return (
            claim.verification_status == "generated_inference"
            and claim.inference_label_present is True
            and "source_book_analysis" in claim.inference_allowed_context
        )

    if claim.claim_kind == "proposal_option":
        return False  # options go to internal bid strategy only

    return False


def can_use_in_slide_blueprint(claim: ClaimProvenance) -> bool:
    """Slide blueprints: more restrictive than source book.

    No unverified internal claims. No proposal options.
    Generated inferences blocked from slides entirely.
    """
    if claim.verification_status == "forbidden":
        return False
    if claim.claim_kind in (
        "rfp_fact",
        "external_methodology",
        "internal_company_claim",
    ):
        return can_use_as_proof_point(claim)
    return False  # generated_inference and proposal_option blocked


def can_use_in_speaker_notes(claim: ClaimProvenance) -> bool:
    """Speaker notes: allows labelled generated inferences."""
    return (
        claim.claim_kind == "generated_inference"
        and claim.inference_label_present is True
        and "speaker_notes" in claim.inference_allowed_context
    )


def can_use_in_client_proposal(claim: ClaimProvenance) -> bool:
    """Final proposal: strictest external-facing gate."""
    return can_use_as_proof_point(claim)


def can_use_in_internal_gap_appendix(claim: ClaimProvenance) -> bool:
    """Internal appendix: everything visible for review."""
    return True


# ── Usage normalization ──────────────────────────────────────────


def normalize_usage_allowed(claim: ClaimProvenance) -> list[str]:
    """Compute actual allowed usage from verification status.

    usage_allowed is subordinate to verification_status — this function
    overrides manually-set usage when the claim is unverified or forbidden.
    Does NOT touch requested_external_contexts.
    """
    if claim.verification_status in ("internal_unverified", "forbidden"):
        return ["internal_gap_appendix"]
    if can_use_as_proof_point(claim):
        return claim.usage_allowed
    return ["internal_gap_appendix"]
