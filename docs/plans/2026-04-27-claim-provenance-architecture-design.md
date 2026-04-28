# Source Book Pipeline: Claim Provenance, Evidence Fidelity, and Artifact Gate Architecture

> **Prior tactical validator/content-fidelity plan retained for regression fixtures and acceptance reporting only. Implementation superseded by claim-provenance architecture.**

## Problem Statement

The Source Book pipeline produces artifacts where unverified internal claims appear as proof points, direct RFP facts are sent to Engine 2 as proof gaps, formal deliverables are misclassified, routing selects weak generic packs, and the conformance validator produces false negatives from brittle text scanning. Two failed runs (`sb-ar-1776112115`, `sb-ar-1777280086`) demonstrate that these are systemic failures across `extract_rfp → route_rfp → build_evidence_pack → build_claim_ledger → draft_source_book → draft_slide_blueprint → validate_conformance → gate_artifacts`, not fixable by prompt wording or validator-only patches.

## Architecture Invariant

> A claim cannot appear as a proof point, client-facing factual assertion, capability evidence, or slide proof unless `can_use_as_proof_point()` or the appropriate context-specific gate allows it. Absence of Engine 2 verification defaults to `internal_unverified` = blocked.

## Implementation Strategy

**Approach C: Vertical Slice per Claim Kind.** Each slice implements one `claim_kind` end-to-end through the full pipeline, proves it against frozen regression fixtures, and keeps the pipeline runnable after each checkpoint.

- **Slice 1** — `rfp_fact`: RFP fact ledger, verified_from_rfp status, structured compliance index, validator rewrite.
- **Slice 2** — `internal_company_claim`: bidder evidence ledger, Engine 2 contract, can_use_as_proof_point(), forbidden-leakage validator, PRJ/CLI blocking.
- **Slice 3** — `external_methodology`: evidence quality classification, coverage gates, analogical-source restrictions.
- **Slice 4** — `proposal_option`: option ledger, numeric commitment gating, approved_for_external_use enforcement.
- **Slice 5** — `generated_inference`: portal inference guard, deliverable classifier, source hierarchy conflict resolver.
- **Cross-cutting** (woven into each slice): multi-label routing, skeleton packs, structured conformance index, slide blueprint proof gating, artifact final gate, checkpoint reporting.

## Decisions Log

| Question | Decision | Rationale |
|---|---|---|
| Old plan relationship | **(B) Partially supersede** | Keep fixtures, acceptance gates, ID-level reporting. Replace implementation approach. |
| Engine 2 boundary | **(C) Contract as defaults** | ClaimProvenance with `internal_unverified` IS the stub. No separate service. |
| Domain packs | **(B) Skeleton packs** | Strong keywords + forbidden assumptions now. Full enrichment later. |
| Implementation order | **(C) Vertical slices** | Each slice fixes one failure class end-to-end with regression proof. |

---

## Section 1: ClaimProvenance — The Core Model

Every claim in the pipeline carries a `ClaimProvenance` record. This replaces `EvidenceLedgerEntry`, `ClassifiedClaim`, `AssertionLabel`, and the inline classification logic in `evidence_extractor.py`.

```python
class SourceReference(DeckForgeBaseModel):
    file: str = ""
    page: str = ""
    clause: str = ""
    evidence_id: str = ""


class ClaimProvenance(DeckForgeBaseModel):
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

    usage_allowed: list[Literal[
        "source_book", "slide_blueprint", "proposal",
        "internal_gap_appendix", "internal_bid_notes",
        "proposal_option_ledger", "evidence_gap_register",
        "drafting_notes",
    ]] = Field(default_factory=lambda: ["internal_gap_appendix"])

    # Engine 2 intended use — preserved before normalize_usage_allowed() strips it
    requested_external_contexts: list[Literal[
        "source_book", "slide_blueprint", "proposal", "attachment_pack"
    ]] = Field(default_factory=list)

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
        "boq_line", "deliverables_annex", "scope_clause",
        "special_condition", "generated_supporting_artifact", "not_applicable",
    ] = "not_applicable"
    formal_deliverable: bool = False        # DERIVED: True only if boq_line or deliverables_annex
    pricing_line_item: bool = False         # DERIVED: True only if boq_line
    cross_cutting_workstream: bool = False  # DERIVED: special_condition/scope_clause AND not formal

    # Evidence quality (for external_methodology)
    relevance_class: Literal[
        "direct_topic", "adjacent_domain", "analogical", "not_classified"
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
    def derive_deliverable_flags(self):
        self.formal_deliverable = self.deliverable_origin in ("boq_line", "deliverables_annex")
        self.pricing_line_item = self.deliverable_origin == "boq_line"
        self.cross_cutting_workstream = (
            self.deliverable_origin in ("special_condition", "scope_clause")
            and not self.formal_deliverable
        )
        return self
```

### Usage normalization

`usage_allowed` is computed/validated, never manually trusted:

```python
def normalize_usage_allowed(claim: ClaimProvenance) -> list[str]:
    if claim.verification_status in ("internal_unverified", "forbidden"):
        return ["internal_gap_appendix"]
    if can_use_as_proof_point(claim):
        return claim.usage_allowed
    return ["internal_gap_appendix"]
```

### Context-specific gates

```python
def can_use_as_proof_point(claim: ClaimProvenance) -> bool:
    """Strictest gate: proof columns, capability evidence, slide proof_points."""
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
        if claim.requires_client_naming_permission and claim.client_naming_permission is not True:
            return False
        if claim.requires_partner_naming_permission and claim.partner_naming_permission is not True:
            return False
        if claim.scope_summary_allowed_for_proposal is False:
            return False
        return True

    return False  # proposal_option, generated_inference: never proof points


def can_use_in_source_book_analysis(
    claim: ClaimProvenance,
    section_type: Literal[
        "client_facing_body", "internal_bid_notes",
        "internal_gap_appendix", "evidence_gap_register"
    ],
) -> bool:
    """Source book body: analysis, problem framing, methodology design."""
    if claim.verification_status == "forbidden":
        return False
    if section_type in ("internal_gap_appendix", "evidence_gap_register"):
        return True
    if section_type == "internal_bid_notes":
        return claim.claim_kind != "forbidden"

    # client_facing_body rules:
    if claim.claim_kind == "rfp_fact":
        return True
    if claim.claim_kind == "external_methodology":
        if claim.verification_status == "externally_verified":
            return claim.relevance_class in ("direct_topic", "adjacent_domain", "analogical")
        if claim.verification_status == "partially_verified":
            return (
                claim.relevance_class != "analogical"
                and claim.evidence_role in ("methodology_support", "risk_or_assumption_support")
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
    """Slide blueprints: more restrictive than source book."""
    if claim.verification_status == "forbidden":
        return False
    if claim.claim_kind in ("rfp_fact", "external_methodology", "internal_company_claim"):
        return can_use_as_proof_point(claim)
    return False


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
```

---

## Section 2: Claim Registry, Typed Ledgers, and Pipeline Data Flow

### Global ClaimRegistry

One canonical claim store. The four typed ledgers are views, not independent sources of truth.

```python
class ClaimRegistry(DeckForgeBaseModel):
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
        return [c for c in self.claims.values() if c.claim_kind == "internal_company_claim"]

    @property
    def external_methodology(self) -> list[ClaimProvenance]:
        return [c for c in self.claims.values() if c.claim_kind == "external_methodology"]

    @property
    def proposal_options(self) -> list[ClaimProvenance]:
        return [c for c in self.claims.values() if c.claim_kind == "proposal_option"]

    @property
    def generated_inferences(self) -> list[ClaimProvenance]:
        return [c for c in self.claims.values() if c.claim_kind == "generated_inference"]
```

### Typed Ledgers (validated views)

```python
class RFPFactLedger(DeckForgeBaseModel):
    entries: list[ClaimProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kinds(self):
        for claim in self.entries:
            assert claim.claim_kind == "rfp_fact"
            assert claim.source_kind == "rfp_document"
            assert claim.verification_status == "verified_from_rfp"
        return self

class BidderEvidenceLedger(DeckForgeBaseModel):
    entries: list[ClaimProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kinds(self):
        for claim in self.entries:
            assert claim.claim_kind == "internal_company_claim"
            assert claim.source_kind == "internal_backend"
        return self

class ExternalMethodologyLedger(DeckForgeBaseModel):
    entries: list[ClaimProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kinds(self):
        for claim in self.entries:
            assert claim.claim_kind == "external_methodology"
            assert claim.source_kind == "external_source"
        return self

class ProposalOptionLedger(DeckForgeBaseModel):
    entries: list[ClaimProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kinds(self):
        for claim in self.entries:
            assert claim.claim_kind == "proposal_option"
        return self
```

### ClaimLedgerBundle

Single canonical claim package passed through the pipeline:

```python
class ClaimLedgerBundle(DeckForgeBaseModel):
    registry: ClaimRegistry
    rfp_fact_ledger: RFPFactLedger
    bidder_evidence_ledger: BidderEvidenceLedger
    external_methodology_ledger: ExternalMethodologyLedger
    proposal_option_ledger: ProposalOptionLedger
    compliance_index: ComplianceIndex | None = None
```

### Structured Compliance Index

Built BEFORE the DOCX, consumed by the validator:

```python
class ComplianceIndexEntry(DeckForgeBaseModel):
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
    def derive_gates(self):
        if self.response_status in ("covered_by_declaration", "covered_by_response_text"):
            self.content_conformance_pass = True
        if self.response_status == "covered_pending_attachment":
            self.content_conformance_pass = True
            self.submission_pack_ready = self.attachment_verified
        if self.response_status == "not_applicable":
            self.content_conformance_pass = bool(self.not_applicable_rationale)
        return self


class ComplianceIndex(DeckForgeBaseModel):
    entries: list[ComplianceIndexEntry] = Field(default_factory=list)
```

### Pipeline Data Flow

```
RFP PDF
  │
  ▼
extract_rfp (context_agent)
  │ produces: RFPContext + RFPFactLedger
  │ registers: rfp_fact claims (dates, clauses, compliance reqs, deliverables, eval criteria)
  │ registers: generated_inference claims for inferred fields (portal, award if no eval sheet)
  │
  ▼
route_rfp (routing service)
  │ reads: RFPContext
  │ produces: RoutingReport (multi-label domains: primary + secondary)
  │ selects: packs (jurisdiction + all matching domain packs + client-type)
  │
  ▼
build_evidence_pack (external_research agent)
  │ reads: RFPContext, RoutingReport, selected packs
  │ produces: ExternalMethodologyLedger (each source classified: direct/adjacent/analogical)
  │ enforces: coverage gate (minimum required direct sources per domain)
  │
  ▼
build_claim_ledger (proposal_strategy + hard_requirement_extractor)
  │ reads: RFPContext, RFPFactLedger, ExternalMethodologyLedger
  │ produces: BidderEvidenceLedger (all internal claims default internal_unverified)
  │ produces: ProposalOptionLedger (numeric commitments, design choices)
  │ produces: ComplianceIndex (structured, not regex-based)
  │ classifies: deliverables (formal vs workstream vs special condition)
  │
  ▼
draft_source_book (writer)
  │ reads: ClaimLedgerBundle + RoutingReport + packs
  │ enforces: can_use_in_source_book_analysis(claim, section_type) per claim
  │ enforces: can_use_as_proof_point() for any proof column
  │ routes: unverified internal claims → internal gap appendix only
  │ detects: unregistered numeric commitments → register + relocate/fail
  │
  ▼
draft_slide_blueprint (writer stage 2a)
  │ reads: SourceBook + ClaimLedgerBundle
  │ enforces: can_use_in_slide_blueprint() for every proof_point
  │ enforces: can_use_in_speaker_notes() for labelled inferences
  │ blocks: PRJ-*/CLI-*/CLM-* unless internal_verified + permissioned
  │ resolves: every proof_point to a ClaimProvenance via registry.resolve_proof_point()
  │
  ▼
validate_conformance (conformance_validator)
  │ reads: SourceBook + ComplianceIndex + HardRequirements
  │ primary: checks ComplianceIndex JSON (structured, content_conformance_pass)
  │ fallback: Arabic alias dictionary scan (diagnostic only)
  │ scans: rendered ArtifactSections for forbidden leakage
  │ produces: ConformanceReport
  │
  ▼
gate_artifacts (final gate)
  │ reads: ConformanceReport + ReviewerScore + EvidenceCoverage + ForbiddenScan + ClaimRegistry + rendered sections
  │ enforces: ALL gates must pass for proposal_ready = True
  │ labels: "DRAFT — NOT PROPOSAL READY" if any gate fails
```

---

## Section 3: Gates, Validators, Forbidden-Claim Scanner, and Artifact Final Gate

### Forbidden Internal-Claim Leakage Validator

Section-path-aware scanner using structured `ArtifactSection`:

```python
class ArtifactSection(DeckForgeBaseModel):
    section_path: str
    section_type: Literal[
        "client_facing_body", "proof_column", "slide_body",
        "slide_proof_points", "speaker_notes",
        "internal_gap_appendix", "internal_bid_notes",
        "evidence_ledger", "drafting_notes"
    ]
    text: str

FORBIDDEN_ID_PATTERNS = [
    r"\bPRJ-\d+\b",
    r"\bCLI-\d+\b",
    r"\bCLM-\d+\b",
    r"INTERNAL_PROOF_PLACEHOLDER",
    r"ENGINE\s*2\s*REQUIRED",
    r"إثبات داخلي مطلوب",
    r"قيد الاستكمال من سجلات",
]

FORBIDDEN_SEMANTIC_PHRASES = [
    "خبرة موثقة في العمل مع سدايا",
    "تعاون موثق مع اليونسكو",
    "مشروع سابق مع سدايا واليونسكو",
    "documented experience with SDAIA",
    "documented collaboration with UNESCO",
]

INTERNAL_ONLY_SECTION_TYPES = {
    "internal_gap_appendix", "drafting_notes",
    "evidence_ledger", "internal_bid_notes"
}

class ForbiddenLeakageViolation(DeckForgeBaseModel):
    pattern: str
    matched_text: str
    location: str
    section_type: str
    severity: Literal["critical", "major"] = "critical"
    linked_claim_id: str | None = None

def scan_for_forbidden_leakage(
    section: ArtifactSection,
    registry: ClaimRegistry | None = None,
) -> list[ForbiddenLeakageViolation]:
    if section.section_type in INTERNAL_ONLY_SECTION_TYPES:
        return []

    violations = []
    for pattern in FORBIDDEN_ID_PATTERNS:
        for match in re.finditer(pattern, section.text, re.IGNORECASE):
            violations.append(ForbiddenLeakageViolation(
                pattern=pattern,
                matched_text=match.group(),
                location=section.section_path,
                section_type=section.section_type,
            ))

    for phrase in FORBIDDEN_SEMANTIC_PHRASES:
        if phrase in section.text:
            # Registry-aware: check if linked claim is actually verified
            if registry:
                linked = registry.resolve_proof_point(phrase)
                if linked and can_use_as_proof_point(linked):
                    continue  # verified + permissioned: allow
            violations.append(ForbiddenLeakageViolation(
                pattern=f"semantic:{phrase}",
                matched_text=phrase,
                location=section.section_path,
                section_type=section.section_type,
            ))

    return violations
```

**Hard gate:** `if len(forbidden_violations) > 0: reject. No exception.`

### Evidence Coverage Gate

```python
class EvidenceCoverageRequirement(DeckForgeBaseModel):
    topic: str
    minimum_direct_sources: int
    found_direct: int = 0
    found_adjacent: int = 0
    found_analogical: int = 0
    status: Literal["met", "not_met"] = "not_met"
    missing_reason: str = ""

    @model_validator(mode="after")
    def compute_status(self):
        # Only direct sources count toward minimum
        self.status = "met" if self.found_direct >= self.minimum_direct_sources else "not_met"
        return self

class EvidenceCoverageReport(DeckForgeBaseModel):
    requirements: list[EvidenceCoverageRequirement] = Field(default_factory=list)
    status: Literal["pass", "fail"] = "fail"

    @model_validator(mode="after")
    def compute_status(self):
        self.status = "pass" if all(r.status == "met" for r in self.requirements) else "fail"
        return self
```

### Artifact Final Gate

```python
class GateFailure(DeckForgeBaseModel):
    code: str
    severity: Literal["critical", "major", "minor"]
    message: str
    affected_artifact: str | None = None
    claim_id: str | None = None

class ArtifactGateDecision(DeckForgeBaseModel):
    decision: Literal["approve", "reject"]
    proposal_ready: bool
    deck_generation_allowed: bool
    artifact_label: str
    failures: list[GateFailure] = Field(default_factory=list)

def final_artifact_gate(
    conformance_report: ConformanceReport,
    reviewer_score: SourceBookReview,
    evidence_coverage: EvidenceCoverageReport,
    forbidden_scan: list[ForbiddenLeakageViolation],
    claim_registry: ClaimRegistry,
    rendered_sections: list[ArtifactSection],
) -> ArtifactGateDecision:

    failures = []

    if conformance_report.conformance_status != "pass":
        failures.append(GateFailure(
            code="CONFORMANCE_FAIL",
            severity="critical",
            message=f"conformance_status={conformance_report.conformance_status}",
        ))

    if conformance_report.conformance_forbidden_claims > 0:
        failures.append(GateFailure(
            code="FORBIDDEN_CLAIMS",
            severity="critical",
            message=f"forbidden_claims={conformance_report.conformance_forbidden_claims}",
        ))

    if not reviewer_score.pass_threshold_met:
        failures.append(GateFailure(
            code="REVIEWER_THRESHOLD",
            severity="major",
            message=f"reviewer_threshold_met=False (score={reviewer_score.overall_score})",
        ))

    if evidence_coverage.status != "pass":
        failures.append(GateFailure(
            code="EVIDENCE_COVERAGE",
            severity="critical",
            message=f"evidence_coverage={evidence_coverage.status}",
        ))

    if len(forbidden_scan) > 0:
        failures.append(GateFailure(
            code="FORBIDDEN_LEAKAGE",
            severity="critical",
            message=f"forbidden_leakage={len(forbidden_scan)} violations",
        ))

    # Scan rendered artifacts for unverified claims (actual output, not registry only)
    for section in rendered_sections:
        section_violations = scan_for_forbidden_leakage(section, claim_registry)
        for v in section_violations:
            failures.append(GateFailure(
                code="RENDERED_LEAKAGE",
                severity="critical",
                message=f"{v.matched_text} in {v.location}",
                claim_id=v.linked_claim_id,
            ))

    if any(f.severity in ("critical", "major") for f in failures):
        return ArtifactGateDecision(
            decision="reject",
            proposal_ready=False,
            deck_generation_allowed=False,
            artifact_label="DRAFT — NOT PROPOSAL READY",
            failures=failures,
        )

    return ArtifactGateDecision(
        decision="approve",
        proposal_ready=True,
        deck_generation_allowed=True,
        artifact_label="PROPOSAL READY",
        failures=failures,
    )
```

---

## Section 4: Routing, Domain Packs, Deliverable Classifier, Portal Guard, Source Hierarchy

### Multi-Label Routing with Weighted Scoring

```python
class RFPClassification(DeckForgeBaseModel):
    jurisdiction: str = "unknown"
    sector: Literal["public_sector", "private_sector", "semi_government", "unknown"] = "unknown"
    client_type: str = ""
    primary_domains: list[str] = Field(default_factory=list)
    secondary_domains: list[str] = Field(default_factory=list)
    primary_domain: str = ""  # backward compat
    regulatory_frame: str = "none_identified"
    evaluator_pattern: str = ""
    proof_types_needed: list[str] = Field(default_factory=list)
    language: str = "ar"
    confidence: float = 0.0
    alternate_classifications: list[dict] = Field(default_factory=list)
```

**Weighted keyword scoring:**

```python
# Pack classification_keywords now use tiered weights:
# "strong": 5, "medium": 3, "weak": 1
# Domain included if score >= 3

GENERIC_DOMAINS = {"digital_transformation", "performance_management"}
SPECIFIC_DOMAINS = {"ai_governance_ethics", "unesco_unesco_ram", ...}

# If specific domains present, generic domains become secondary (not deleted)
if any(d in SPECIFIC_DOMAINS for d in all_domains):
    primary_domains = [d for d in all_domains if d not in GENERIC_DOMAINS]
    secondary_domains = [d for d in all_domains if d in GENERIC_DOMAINS]
else:
    primary_domains = all_domains
    secondary_domains = []
```

**Pack selection:** selects ALL packs matching ANY primary or secondary domain.

### Skeleton Domain Packs

Six new packs in `src/packs/` with `"status": "skeleton"`, strong classification keywords (tiered strong/medium/weak), forbidden assumptions, and search query seeds. Full keyword sets specified in approved Q3 answer.

**Thin-pack handling:**

```python
if pack.status == "skeleton":
    # DO NOT inject: evaluator_insights, methodology_patterns, regulatory_references
    # DO inject: domain labels, forbidden_assumptions, search_query_seeds
    writer_context.thin_pack_warning = "..."
```

### Formal Deliverable Classifier

```python
class DeliverableClassification(DeckForgeBaseModel):
    id: str
    name: str
    origin: Literal[
        "boq_line", "deliverables_annex", "scope_clause",
        "special_condition", "generated_supporting_artifact",
    ]
    formal_deliverable: bool = False
    pricing_line_item: bool = False
    cross_cutting_workstream: bool = False
    registered_as_claim: str = ""

    @model_validator(mode="after")
    def derive_flags(self):
        self.formal_deliverable = self.origin in ("boq_line", "deliverables_annex")
        self.pricing_line_item = self.origin == "boq_line"
        self.cross_cutting_workstream = (
            self.origin in ("special_condition", "scope_clause")
            and not self.formal_deliverable
        )
        return self

# If LLM assigns D-N ID but origin is not formal:
if id_matches_d_number and origin not in ("boq_line", "deliverables_annex"):
    id = normalize_to_workstream_id(item)  # KT-1, GOV-1, MGMT-1
    formal_deliverable = False
```

### Portal Inference Guard

```python
class ExtractedTextSpan(DeckForgeBaseModel):
    text: str
    page: int = 0
    region_type: Literal["header", "footer", "body", "table", "logo", "unknown"] = "unknown"

PORTAL_BRANDS = {"Etimad", "اعتماد", "منصة اعتماد"}
TEMPLATE_OR_AUTHORITY_BRANDS = {"EXPRO", "اكسبرو", "NUPCO", "نوبكو"}

class PortalExtraction(DeckForgeBaseModel):
    portal_name: str = "البوابة الإلكترونية المعتمدة"
    portal_confidence: Literal[
        "explicit_submission_clause", "likely_from_context", "unknown_named_portal"
    ] = "unknown_named_portal"
    source_clause: str = ""
    inferred_from_logo: bool = False

# Portal can only be explicit if found in: body, table, submission_clause
# Not: header, footer, logo, watermark
# PORTAL_BRANDS (Etimad) may be real portals → explicit if in submission clause
# TEMPLATE_OR_AUTHORITY_BRANDS (EXPRO) → never infer as portal from logo/header
```

### Source Hierarchy and Conflict Resolver

**Field-specific hierarchy** (not one global order):

```python
FIELD_SOURCE_HIERARCHY = {
    "award_mechanism": [
        "evaluation_criteria_sheet", "rfp_booklet", "special_conditions",
        "contract_model", "general_terms", "model_inference",
    ],
    "scope": [
        "rfp_booklet", "scope_annex", "boq_pricing_table",
        "special_conditions", "contract_model",
    ],
    "pricing_line_items": [
        "boq_pricing_table", "rfp_booklet", "financial_offer_template",
    ],
    "legal_terms": [
        "special_conditions", "contract_model", "general_terms",
    ],
}

class SourceConflict(DeckForgeBaseModel):
    field: str
    value_a: str
    source_a: str
    value_b: str
    source_b: str
    resolution: str
    resolved_value: str
    conflict_note: str

# Conflict notes registered as generated_inference with limited usage:
# inference_allowed_context=["internal_bid_notes", "source_book_analysis"]
# requires_clarification=True if unresolved
```

---

## Section 5: Proposal Options, Engine 2 Contract, Regression Fixtures, Checkpoint Reporting

### Proposal Option Gating

Every option linked to ClaimProvenance via `claim_provenance_id`:

```python
class ProposalOption(DeckForgeBaseModel):
    option_id: str
    text: str
    claim_provenance_id: str  # links to ClaimRegistry
    category: Literal[
        "numeric_range", "methodology_choice", "resource_allocation",
        "scope_boundary", "timeline_assumption",
    ]
    approved_for_external_use: bool = False
    priced: bool = False
    approved_by: str | None = None
    pricing_impact_note: str = ""
```

**Numeric commitment detection** scans only client-facing sections, normalizes Arabic digits and range separators:

```python
def detect_unregistered_commitments(
    sections: list[ArtifactSection],
    registry: ClaimRegistry,
) -> list[str]:
    CLIENT_FACING_TYPES = {"client_facing_body", "slide_body", "slide_proof_points"}
    # Normalize Arabic-Indic digits, range separators (إلى / حتى / - / –)
    # Exclude numbers linked to rfp_fact claims
    # Return unregistered commitments found in client-facing sections
    ...
```

**Gate rule:** Unregistered numeric commitments in client-facing sections → reject (not just register).

### Engine 2 Contract Models

```python
class Engine2ProofRequest(DeckForgeBaseModel):
    claim_id: str
    claim_text: str
    requested_proof_type: Literal[
        "prior_project", "client_reference", "consultant_cv",
        "company_certificate", "legal_document", "case_study",
        "client_permission", "partner_permission",
    ]
    internal_ref: str | None = None
    requested_external_contexts: list[Literal[
        "source_book", "slide_blueprint", "proposal", "attachment_pack"
    ]] = Field(default_factory=list)
    requires_client_naming_permission: bool = False
    requires_partner_naming_permission: bool = False
    requires_scope_summary_permission: bool = False
    desired_external_wording: str | None = None
    anonymized_allowed: bool = True

class Engine2ProofResponse(DeckForgeBaseModel):
    claim_id: str
    verified: bool = False
    verification_status: Literal[
        "internal_verified", "internal_unverified", "not_found",
        "permission_denied", "insufficient_evidence",
    ] = "internal_unverified"
    client_name_disclosure_allowed: bool = False
    partner_name_disclosure_allowed: bool = False
    scope_summary_allowed_for_proposal: bool = False
    public_case_study_available: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    approved_public_wording: str | None = None
    anonymized_wording: str | None = None
    reviewer_notes: str | None = None

def default_engine2_response(request: Engine2ProofRequest) -> Engine2ProofResponse:
    return Engine2ProofResponse(
        claim_id=request.claim_id,
        reviewer_notes="Engine 2 not implemented. Claim blocked from proposal-facing use.",
    )

def build_engine2_shopping_list(registry: ClaimRegistry) -> list[Engine2ProofRequest]:
    """ONLY bidder evidence claims. NEVER RFP facts."""
    requests = []
    for claim in registry.claims.values():
        if claim.claim_kind != "internal_company_claim":
            continue
        if claim.source_kind != "internal_backend":
            continue
        if claim.verification_status != "internal_unverified":
            continue
        requests.append(Engine2ProofRequest(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            requested_proof_type=_infer_proof_type(claim),
            internal_ref=claim.source_refs[0].evidence_id if claim.source_refs else None,
            requested_external_contexts=claim.requested_external_contexts or ["source_book"],
            requires_client_naming_permission=claim.requires_client_naming_permission,
            requires_partner_naming_permission=claim.requires_partner_naming_permission,
            requires_scope_summary_permission=claim.scope_summary_allowed_for_proposal is not None,
        ))
    # Validate: no non-bidder claims
    for r in requests:
        c = registry.get(r.claim_id)
        assert c and c.claim_kind == "internal_company_claim"
    return requests
```

### Regression Fixtures

```
tests/fixtures/
├── sb-ar-1776112115/          # NCNP RFP
│   ├── raw_rfp.pdf (or extracted text)
│   ├── rfp_extraction.json
│   ├── claim_registry.json
│   ├── routing_report.json
│   ├── compliance_index.json
│   ├── evidence_coverage_report.json
│   ├── gate_decision.json
│   ├── source_book.docx
│   ├── conformance_report.json
│   ├── evidence_ledger.json
│   └── slide_blueprint_from_source_book.json
│
└── sb-ar-1777280086/          # UNESCO AI Ethics
    ├── (same structure)
```

**Regression tests run the new pipeline, not only inspect old outputs:**

```python
# Two modes:
# 1. fixture_asserts_old_failure_detected — proves the old bug existed
# 2. pipeline_asserts_new_output_fixed — proves the new pipeline blocks it

def test_prj_leakage_blocked_in_new_pipeline():
    result = run_pipeline_on_fixture("sb-ar-1777280086")
    for section in result.client_facing_sections:
        assert not re.search(r"\bPRJ-\d+\b", section.text)
        assert not re.search(r"\bCLI-\d+\b", section.text)

def test_rfp_facts_never_in_engine2_list():
    result = run_pipeline_on_fixture("sb-ar-1776112115")
    rfp_ids = {c.claim_id for c in result.registry.rfp_facts}
    e2_ids = {r.claim_id for r in result.engine2_shopping_list}
    assert rfp_ids.isdisjoint(e2_ids)

def test_training_not_formal_deliverable_unless_boq():
    result = run_pipeline_on_fixture("sb-ar-1777280086")
    for d in result.deliverable_classifications:
        if "تدريب" in d.name or "نقل المعرفة" in d.name:
            if d.origin not in ("boq_line", "deliverables_annex"):
                assert not d.formal_deliverable
                assert not d.id.startswith("D-")

def test_portal_not_from_logo():
    result = run_pipeline_on_fixture("sb-ar-1777280086")
    if result.portal.inferred_from_logo:
        assert result.portal.portal_name == "البوابة الإلكترونية المعتمدة"

def test_compliance_structured_check():
    result = run_pipeline_on_fixture("sb-ar-1776112115")
    for req_id in ["HR-L1-002", "HR-L1-003", "HR-L1-004", "HR-L1-005"]:
        entry = next((e for e in result.compliance_index.entries if e.requirement_id == req_id), None)
        assert entry and entry.content_conformance_pass

def test_routing_specific_domains():
    result = run_pipeline_on_fixture("sb-ar-1777280086")
    assert "ai_governance_ethics" in result.routing.classification.primary_domains
    assert "digital_transformation" not in result.routing.classification.primary_domains

def test_evidence_analogical_not_counted_as_direct():
    result = run_pipeline_on_fixture("sb-ar-1777280086")
    for req in result.evidence_coverage.requirements:
        if req.found_analogical > 0 and req.found_direct < req.minimum_direct_sources:
            assert req.status == "not_met"

def test_degraded_not_proposal_ready():
    result = run_pipeline_on_fixture("sb-ar-1777280086")
    assert result.gate.decision == "reject"
    assert result.gate.proposal_ready is False
    assert "DRAFT" in result.gate.artifact_label

def test_slide_proof_points_resolved_and_verified():
    result = run_pipeline_on_fixture("sb-ar-1777280086")
    for slide in result.slide_blueprints:
        for proof in slide.proof_points:
            claim = result.registry.resolve_proof_point(proof)
            assert claim is not None, f"Slide {slide.slide_number}: unresolved proof {proof}"
            assert can_use_as_proof_point(claim), f"Slide {slide.slide_number}: {proof} not verified"
```

### Checkpoint Reporting Format

```
Session ID:          sb-ar-XXXXXXXXXX
Output path:         output/sb-ar-XXXXXXXXXX/
Slice:               1 | 2 | 3 | 4 | 5
Slice status:        pass | fail
Pipeline status:     SUCCESS | DEGRADED | FAILED
Conformance status:  pass | fail | blocked
Final acceptance:    approve | reject
Forbidden claims:    0
Evidence coverage:   pass | fail
Routing labels:      primary: [...], secondary: [...]
Deck allowed:        yes | no

Critical failures:
  - CODE: message (claim_id if applicable)

Major failures:
  - CODE: message

Remaining conformance IDs:
  - HR-L1-xxx: reason | severity | regression or pre-existing | responsible module

Forbidden claim IDs:
  - CLAIM-xxx: reason and location

Evidence coverage:
  - topic_1: X direct / Y adjacent / Z analogical → met | not_met
  - topic_2: ...

NEW IDs (if any):
  - HR-XXX-YYY [REAL MISS | REGRESSION]
    Cause: <task>
    Evidence: <quote or "absent">
    Action: <keep | needs decision>
```

---

## Files Affected

| Module | Current File | Changes |
|---|---|---|
| Claim models | `src/models/source_book.py` (new: `src/models/claim_provenance.py`) | New ClaimProvenance, ClaimRegistry, typed ledgers, ComplianceIndex |
| Evidence extractor | `src/agents/source_book/evidence_extractor.py` | Replaced by registry-based claim classification |
| Conformance validator | `src/agents/source_book/conformance_validator.py` | Rewritten: ComplianceIndex-first, ArtifactSection scanning |
| Coherence validator | `src/agents/source_book/coherence_validator.py` | Updated to use claim provenance gates |
| Writer | `src/agents/source_book/writer.py` | Enforces context gates, detects numeric commitments |
| Orchestrator | `src/agents/source_book/orchestrator.py` | Passes ClaimLedgerBundle, calls final gate |
| Routing models | `src/models/routing.py` | Multi-label domains (primary/secondary) |
| Routing service | `src/services/routing.py` | Weighted scoring, issuing-entity tiebreak, multi-pack selection |
| Source book export | `src/services/source_book_export.py` | Routing appendix suppression, artifact labelling |
| Hard requirement extractor | `src/services/hard_requirement_extractor.py` | Deliverable classifier, compliance index builder |
| Pipeline graph | `src/pipeline/graph.py` | ClaimLedgerBundle threading, final gate wiring |
| Packs | `src/packs/*.json` | 6 new skeleton packs |
| Engine 2 contract | `src/models/engine2_contract.py` (new) | Request/response models, default resolver |
| Gates | `src/services/artifact_gates.py` (new) | All context gates, forbidden scanner, final gate |
| Tests | `tests/` | Regression fixtures + all specified tests |

## Existing Code Retired

- `AssertionLabel` enum → replaced by `ClaimProvenance.claim_kind`
- `EvidenceLedgerEntry` → replaced by `ClaimProvenance`
- `ClassifiedClaim` → replaced by `ClaimProvenance`
- `_pass1_deterministic` English keyword scanning → `ComplianceIndex` structured check
- Inline `verifiability_status` classification in `evidence_extractor.py` → `ClaimRegistry`-based
- Single `evidence_ledger` → split into 4 typed ledgers via `ClaimLedgerBundle`
