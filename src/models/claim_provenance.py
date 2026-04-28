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


# ── Claim Registry ───────────────────────────────────────────────


class ClaimRegistry(DeckForgeBaseModel):
    """One canonical claim store. Typed ledgers are views over this registry."""

    claims: dict[str, ClaimProvenance] = Field(default_factory=dict)

    def register(self, claim: ClaimProvenance) -> None:
        self.claims[claim.claim_id] = claim

    def get(self, claim_id: str) -> ClaimProvenance | None:
        return self.claims.get(claim_id)

    def resolve_proof_point(self, proof: str) -> ClaimProvenance | None:
        """Resolve a proof point (ID or text snippet) to a claim."""
        if proof in self.claims:
            return self.claims[proof]
        for claim in self.claims.values():
            if proof in claim.text or claim.text in proof:
                return claim
        return None

    @property
    def rfp_facts(self) -> list[ClaimProvenance]:
        return [c for c in self.claims.values() if c.claim_kind == "rfp_fact"]

    @property
    def bidder_claims(self) -> list[ClaimProvenance]:
        return [
            c for c in self.claims.values()
            if c.claim_kind == "internal_company_claim"
        ]

    @property
    def external_methodology(self) -> list[ClaimProvenance]:
        return [
            c for c in self.claims.values()
            if c.claim_kind == "external_methodology"
        ]

    @property
    def proposal_options(self) -> list[ClaimProvenance]:
        return [c for c in self.claims.values() if c.claim_kind == "proposal_option"]

    @property
    def generated_inferences(self) -> list[ClaimProvenance]:
        return [
            c for c in self.claims.values()
            if c.claim_kind == "generated_inference"
        ]


# ── Typed Ledgers (validated views) ──────────────────────────────


class RFPFactLedger(DeckForgeBaseModel):
    """Facts extracted directly from the RFP booklet. Never sent to Engine 2."""

    entries: list[ClaimProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kinds(self) -> "RFPFactLedger":
        for claim in self.entries:
            assert claim.claim_kind == "rfp_fact", (
                f"RFPFactLedger entry {claim.claim_id} has wrong kind: {claim.claim_kind}"
            )
            assert claim.source_kind == "rfp_document", (
                f"RFPFactLedger entry {claim.claim_id} has wrong source: {claim.source_kind}"
            )
            assert claim.verification_status == "verified_from_rfp", (
                f"RFPFactLedger entry {claim.claim_id} has wrong status: {claim.verification_status}"
            )
        return self


class BidderEvidenceLedger(DeckForgeBaseModel):
    """Company-side proof claims. Default internal_unverified until Engine 2."""

    entries: list[ClaimProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kinds(self) -> "BidderEvidenceLedger":
        for claim in self.entries:
            assert claim.claim_kind == "internal_company_claim", (
                f"BidderEvidenceLedger entry {claim.claim_id} has wrong kind: {claim.claim_kind}"
            )
            assert claim.source_kind == "internal_backend", (
                f"BidderEvidenceLedger entry {claim.claim_id} has wrong source: {claim.source_kind}"
            )
        return self


class ExternalMethodologyLedger(DeckForgeBaseModel):
    """External academic/industry sources with relevance classification."""

    entries: list[ClaimProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kinds(self) -> "ExternalMethodologyLedger":
        for claim in self.entries:
            assert claim.claim_kind == "external_methodology", (
                f"ExternalMethodologyLedger entry {claim.claim_id} has wrong kind: {claim.claim_kind}"
            )
            assert claim.source_kind == "external_source", (
                f"ExternalMethodologyLedger entry {claim.claim_id} has wrong source: {claim.source_kind}"
            )
        return self


class ProposalOptionLedger(DeckForgeBaseModel):
    """Design choices and numeric commitments. Not facts, not proof."""

    entries: list[ClaimProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kinds(self) -> "ProposalOptionLedger":
        for claim in self.entries:
            assert claim.claim_kind == "proposal_option", (
                f"ProposalOptionLedger entry {claim.claim_id} has wrong kind: {claim.claim_kind}"
            )
        return self


# ── Proposal Option (Slice 4.1) ──────────────────────────────────


class ProposalOption(DeckForgeBaseModel):
    """Option metadata sidecar for a ClaimProvenance whose claim_kind
    is ``proposal_option``.

    The ClaimProvenance carries the option's text, kind, and
    verification status; this model carries the gating fields the
    proposal_option kind needs:

    * approved_for_external_use — gate for client-facing sections
    * priced — whether the option is costed in the bid
    * approved_by — accountable approver
    * pricing_impact_note — required when priced=False
    """

    option_id: str
    text: str
    claim_provenance_id: str  # → ClaimRegistry.get(...)

    category: Literal[
        "numeric_range",
        "methodology_choice",
        "resource_allocation",
        "scope_boundary",
        "timeline_assumption",
    ]

    approved_for_external_use: bool = False
    priced: bool = False
    approved_by: str | None = None
    pricing_impact_note: str = ""

    @model_validator(mode="after")
    def _option_id_required(self) -> "ProposalOption":
        if not self.option_id:
            raise ValueError("option_id must be a non-empty string")
        if not self.claim_provenance_id:
            raise ValueError("claim_provenance_id must be a non-empty string")
        return self

    @property
    def is_externally_publishable(self) -> bool:
        """Acceptance gate combining approval + pricing discipline.

        Pricing-relevant categories (numeric_range, resource_allocation,
        timeline_assumption) require the option to be either priced
        OR carry an explicit pricing_impact_note. Without one of those
        signals an approved option still cannot land in client-facing
        text, because the bid team has not declared how the commitment
        feeds the financial offer.
        """
        if not self.approved_for_external_use:
            return False
        if self.category in {
            "numeric_range",
            "resource_allocation",
            "timeline_assumption",
        }:
            if not self.priced and not (self.pricing_impact_note or "").strip():
                return False
        return True


class ProposalOptionRegistry(DeckForgeBaseModel):
    """Sidecar registry for ProposalOption metadata.

    Indexed by option_id (which equals claim_provenance_id by
    convention so the option and its ClaimProvenance share the same
    addressing namespace). Use alongside ClaimRegistry: the claim
    registry holds the proposal_option ClaimProvenance, this registry
    holds the option's gating metadata.
    """

    by_id: dict[str, ProposalOption] = Field(default_factory=dict)

    def register(self, option: ProposalOption) -> None:
        self.by_id[option.option_id] = option

    def get(self, option_id: str) -> "ProposalOption | None":
        return self.by_id.get(option_id)

    @property
    def options(self) -> list[ProposalOption]:
        return list(self.by_id.values())


# ── Compliance Index ─────────────────────────────────────────────


class ComplianceIndexEntry(DeckForgeBaseModel):
    """Structured compliance check for one hard requirement."""

    requirement_id: str
    requirement_text: str

    response_status: Literal[
        "covered_pending_attachment",
        "covered_by_declaration",
        "covered_by_response_text",
        "missing",
        "not_applicable",
    ]

    content_conformance_pass: bool = False
    submission_pack_ready: bool = False

    response_section: str = ""
    attachment_required: bool = False
    attachment_name: str = ""
    attachment_verified: bool = False

    not_applicable_rationale: str = ""

    owner: str = ""
    arabic_aliases: list[str] = Field(default_factory=list)

    rfp_requirement_claim_id: str = ""
    bidder_response_claim_id: str | None = None
    attachment_claim_id: str | None = None

    @model_validator(mode="after")
    def derive_gates(self) -> "ComplianceIndexEntry":
        """Derive content_conformance_pass and submission_pack_ready."""
        content_pass = False
        submission_ready = False

        if self.response_status in (
            "covered_by_declaration",
            "covered_by_response_text",
        ):
            content_pass = True
        elif self.response_status == "covered_pending_attachment":
            content_pass = True
            submission_ready = self.attachment_verified
        elif self.response_status == "not_applicable":
            content_pass = bool(self.not_applicable_rationale)

        object.__setattr__(self, "content_conformance_pass", content_pass)
        object.__setattr__(self, "submission_pack_ready", submission_ready)
        return self


class ComplianceIndex(DeckForgeBaseModel):
    """Structured compliance index — consumed by validator before text scanning."""

    entries: list[ComplianceIndexEntry] = Field(default_factory=list)


# ── Claim Ledger Bundle ──────────────────────────────────────────


class ClaimLedgerBundle(DeckForgeBaseModel):
    """Single canonical claim package passed through the pipeline."""

    registry: ClaimRegistry
    rfp_fact_ledger: RFPFactLedger
    bidder_evidence_ledger: BidderEvidenceLedger
    external_methodology_ledger: ExternalMethodologyLedger
    proposal_option_ledger: ProposalOptionLedger
    compliance_index: ComplianceIndex | None = None
