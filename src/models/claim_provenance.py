"""Claim Provenance — strict provenance model for every claim in the pipeline.

Every claim carries a ClaimProvenance record that tracks its origin,
verification status, allowed usage, and disclosure permissions. This
replaces EvidenceLedgerEntry, ClassifiedClaim, AssertionLabel, and
the inline classification logic in evidence_extractor.py.

Architecture invariant:
    A claim cannot appear as a proof point, client-facing factual
    assertion, capability evidence, or slide proof unless
    can_use_as_proof_point() or the appropriate context-specific gate
    allows it. Absence of Engine 2 verification defaults to
    internal_unverified = blocked.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from src.models.common import DeckForgeBaseModel


# ── Source Reference ─────────────────────────────────────────────


class SourceReference(DeckForgeBaseModel):
    """A single source location — file, page, clause, evidence ID."""

    file: str = ""
    page: str = ""
    clause: str = ""
    evidence_id: str = ""


# ── Claim Provenance ─────────────────────────────────────────────


class ClaimProvenance(DeckForgeBaseModel):
    """Core provenance record for every claim in the pipeline."""

    claim_id: str
    text: str

    claim_kind: Literal[
        "rfp_fact",
        "internal_company_claim",
        "external_methodology",
        "generated_inference",
        "proposal_option",
    ]

    source_kind: Literal[
        "rfp_document",
        "internal_backend",
        "external_source",
        "model_generated",
    ]

    verification_status: Literal[
        "verified_from_rfp",
        "internal_verified",
        "internal_unverified",
        "externally_verified",
        "partially_verified",
        "proposal_option",
        "generated_inference",
        "forbidden",
    ]

    evidence_role: Literal[
        "requirement_source",
        "methodology_support",
        "bidder_capability_proof",
        "compliance_attachment",
        "proposal_design_option",
        "risk_or_assumption_support",
        "not_applicable",
    ] = "not_applicable"

    usage_allowed: list[
        Literal[
            "source_book",
            "slide_blueprint",
            "proposal",
            "internal_gap_appendix",
            "internal_bid_notes",
            "proposal_option_ledger",
            "evidence_gap_register",
            "drafting_notes",
        ]
    ] = Field(default_factory=lambda: ["internal_gap_appendix"])

    # Engine 2 intended use — preserved before normalize_usage_allowed()
    requested_external_contexts: list[
        Literal["source_book", "slide_blueprint", "proposal", "attachment_pack"]
    ] = Field(default_factory=list)

    # Source references (list-based, supports multi-source claims)
    source_refs: list[SourceReference] = Field(default_factory=list)
    primary_source_ref: SourceReference | None = None

    # Bidder attachment / disclosure permissions
    requires_bidder_attachment: bool = False
    requires_client_naming_permission: bool = False
    client_naming_permission: bool | None = None
    requires_partner_naming_permission: bool = False
    partner_naming_permission: bool | None = None
    scope_summary_allowed_for_proposal: bool | None = None

    confidence: float = 0.0

    # Formal deliverable classification (derived, not manually trusted)
    deliverable_origin: Literal[
        "boq_line",
        "deliverables_annex",
        "scope_clause",
        "special_condition",
        "generated_supporting_artifact",
        "not_applicable",
    ] = "not_applicable"
    formal_deliverable: bool = False
    pricing_line_item: bool = False
    cross_cutting_workstream: bool = False

    # Evidence quality (for external_methodology)
    relevance_class: Literal[
        "direct_topic",
        "adjacent_domain",
        "analogical",
        "not_classified",
    ] = "not_classified"

    # Inference controls (for generated_inference)
    inference_label_present: bool = False
    inference_allowed_context: list[str] = Field(default_factory=list)

    # Blocking / clarification metadata
    blocked_reason: str | None = None
    requires_clarification: bool = False
    clarification_question_id: str | None = None
    owner: str | None = None

    @model_validator(mode="after")
    def derive_deliverable_flags(self) -> "ClaimProvenance":
        """Derive formal_deliverable, pricing_line_item, cross_cutting_workstream
        from deliverable_origin. These flags are never manually trusted.

        Uses object.__setattr__ to bypass validate_assignment=True on
        DeckForgeBaseModel, which would otherwise cause infinite recursion.
        """
        is_formal = self.deliverable_origin in ("boq_line", "deliverables_annex")
        object.__setattr__(self, "formal_deliverable", is_formal)
        object.__setattr__(self, "pricing_line_item", self.deliverable_origin == "boq_line")
        object.__setattr__(
            self,
            "cross_cutting_workstream",
            self.deliverable_origin in ("special_condition", "scope_clause")
            and not is_formal,
        )
        return self
