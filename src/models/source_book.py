"""Proposal Source Book and Source Book Review schemas.

The Source Book is a 7-section structured document that captures all proposal
reasoning, evidence, and slide-by-slide blueprints. It is the central artifact
reviewed at Gate 3 before slide generation begins.

The SourceBookReview captures the Reviewer/Red Team critique with per-section
scoring and rewrite instructions.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from .common import DeckForgeBaseModel


# ──────────────────────────────────────────────────────────────
# Assertion classification (Engine 1 evidence discipline)
# ──────────────────────────────────────────────────────────────


class AssertionLabel(str, Enum):
    """Classification label for every substantive claim in the source book.

    DIRECT_RFP_FACT: explicitly grounded in uploaded RFP text.
    INFERENCE: reasoned conclusion from RFP structure/patterns, not stated.
    EXTERNAL_BENCHMARK: sourced from external research, support only.
    INTERNAL_PROOF_PLACEHOLDER: flags future internal enrichment, not proof.
    """

    DIRECT_RFP_FACT = "DIRECT_RFP_FACT"
    INFERENCE = "INFERENCE"
    EXTERNAL_BENCHMARK = "EXTERNAL_BENCHMARK"
    INTERNAL_PROOF_PLACEHOLDER = "INTERNAL_PROOF_PLACEHOLDER"


class ClassifiedClaim(DeckForgeBaseModel):
    """A substantive claim with its assertion classification."""

    claim_text: str = ""
    label: AssertionLabel = AssertionLabel.INFERENCE
    basis: str = ""  # What grounds this claim (RFP clause, pattern, source)
    confidence: Literal["high", "medium", "low"] = "medium"


class ComplianceRow(DeckForgeBaseModel):
    """Structured compliance-to-requirement row for evaluator-facing matrices."""

    requirement_id: str = ""  # e.g. COMP-001
    requirement_text: str = ""
    sg_response: str = ""
    evidence_ref: str = ""  # CLM-xxxx / EXT-xxx
    label: AssertionLabel = AssertionLabel.DIRECT_RFP_FACT


class DeliveryControlRow(DeckForgeBaseModel):
    """Delivery-control matrix row for requirement-dense RFPs."""

    control_area: str = ""
    rfp_requirement: str = ""
    proposed_mechanism: str = ""
    verification_method: str = ""
    label: AssertionLabel = AssertionLabel.DIRECT_RFP_FACT


class EvaluationHypothesis(DeckForgeBaseModel):
    """Structured evaluation model row — used when weights absent from RFP."""

    criterion: str = ""
    basis: str = ""  # Why we believe this criterion matters
    confidence: Literal["high", "medium", "low"] = "medium"
    label: AssertionLabel = AssertionLabel.INFERENCE
    weight_estimate: str = ""  # e.g. "~30%" or "unknown"


class CoherenceResult(DeckForgeBaseModel):
    """Output of the cross-section coherence validator."""

    issues: list[str] = Field(default_factory=list)
    governance_naming_consistent: bool = True
    evidence_posture_consistent: bool = True
    compliance_carried_through: bool = True
    absolutes_found: list[str] = Field(default_factory=list)
    absolutes_softened: int = 0

# ──────────────────────────────────────────────────────────────
# Source Book sections (7 sections per design doc Section 7.1)
# ──────────────────────────────────────────────────────────────


class _Section1Prose(DeckForgeBaseModel):
    """Split call 1: RFP interpretation prose fields.

    Focused schema so the LLM dedicates full output budget to substantive
    forensic analysis instead of splitting attention with complex nested types.
    """

    objective_and_scope: str = ""
    constraints_and_compliance: str = ""
    unstated_evaluator_priorities: str = ""
    probable_scoring_logic: str = ""
    key_compliance_requirements: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reject_empty_prose(self) -> "_Section1Prose":
        """Reject empty prose — forces LLM retry."""
        word_count = len(self.objective_and_scope.split())
        if word_count < 20:
            raise ValueError(
                f"objective_and_scope is empty or too short ({word_count} words). "
                f"Must produce 4-5 paragraphs of forensic RFP analysis."
            )
        return self


class _Section1Classification(DeckForgeBaseModel):
    """Split call 2: RFP interpretation structured classification fields.

    Focused schema so the LLM dedicates full output budget to producing
    rich structured evidence rows instead of competing with prose fields.
    """

    explicit_requirements: list[ClassifiedClaim] = Field(default_factory=list)
    inferred_requirements: list[ClassifiedClaim] = Field(default_factory=list)
    external_support: list[ClassifiedClaim] = Field(default_factory=list)
    compliance_rows: list[ComplianceRow] = Field(default_factory=list)
    delivery_control_rows: list[DeliveryControlRow] = Field(default_factory=list)
    evaluation_hypotheses: list[EvaluationHypothesis] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reject_empty_classification(self) -> "_Section1Classification":
        """Reject empty classification — forces LLM retry."""
        if len(self.compliance_rows) < 3:
            raise ValueError(
                f"compliance_rows has only {len(self.compliance_rows)} rows. "
                f"Must produce at least 8 structured compliance rows."
            )
        return self


class RFPInterpretation(DeckForgeBaseModel):
    """Section 1: RFP Interpretation.

    Assembled from two split LLM calls (_Section1Prose + _Section1Classification)
    so each call gets a focused schema and full token budget.
    """

    objective_and_scope: str = ""
    constraints_and_compliance: str = ""
    unstated_evaluator_priorities: str = ""
    probable_scoring_logic: str = ""
    key_compliance_requirements: list[str] = Field(default_factory=list)
    # Structured evidence fields (Engine 1 discipline)
    explicit_requirements: list[ClassifiedClaim] = Field(default_factory=list)
    inferred_requirements: list[ClassifiedClaim] = Field(default_factory=list)
    external_support: list[ClassifiedClaim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    compliance_rows: list[ComplianceRow] = Field(default_factory=list)
    delivery_control_rows: list[DeliveryControlRow] = Field(default_factory=list)
    evaluation_hypotheses: list[EvaluationHypothesis] = Field(default_factory=list)


class ClientProblemFraming(DeckForgeBaseModel):
    """Section 2: Client Problem Framing.

    No validator here — this class is used as a default_factory in SourceBook
    and SourceBookSection2, so it must be constructable with empty defaults.
    """

    current_state_challenge: str = ""
    why_it_matters_now: str = ""
    transformation_logic: str = ""
    risk_if_unchanged: str = ""


class _Section2Validated(DeckForgeBaseModel):
    """LLM response model for Section 2 — validated wrapper.

    Used as response_model in call_llm() so the validator fires on LLM output.
    NOT used for default construction or storage — only for LLM calls.
    """

    current_state_challenge: str = ""
    why_it_matters_now: str = ""
    transformation_logic: str = ""
    risk_if_unchanged: str = ""

    @model_validator(mode="after")
    def _reject_empty_framing(self) -> "_Section2Validated":
        """Reject empty or partial problem framing — forces LLM retry.

        All 4 fields must have substantive content. Partial truncation
        (e.g., only current_state_challenge filled) is rejected.
        """
        fields = {
            "current_state_challenge": self.current_state_challenge,
            "why_it_matters_now": self.why_it_matters_now,
            "transformation_logic": self.transformation_logic,
            "risk_if_unchanged": self.risk_if_unchanged,
        }
        for name, value in fields.items():
            word_count = len(value.split())
            if word_count < 15:
                raise ValueError(
                    f"{name} is empty or too short ({word_count} words). "
                    f"All 4 problem framing fields must have substantive content."
                )
        return self


class CapabilityMapping(DeckForgeBaseModel):
    """Row in Section 3.1: Capability-to-RFP Mapping table.

    evidence_ids SHOULD reference CLM-xxxx IDs when available.
    Empty list is allowed when evidence is thin — the Reviewer
    will flag missing evidence during the scoring pass.
    """

    rfp_requirement: str = ""
    sg_capability: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    strength: Literal["strong", "moderate", "weak", "gap"] = "moderate"


class ConsultantProfile(DeckForgeBaseModel):
    """Row in Section 3.2: Named Consultants.

    evidence_ids SHOULD reference CLM-xxxx IDs when available.
    Empty list is allowed when evidence is thin — the Reviewer
    will flag missing evidence during the scoring pass.

    staffing_status indicates the certainty level:
    - confirmed_candidate: authoritative source confirms availability
    - recommended_candidate: suggested fit from internal docs / prior proposals
    - open_role_profile: no reliable named person, define ideal profile
    """

    name: str = ""
    role: str = ""
    staffing_status: Literal[
        "confirmed_candidate", "recommended_candidate", "open_role_profile",
    ] = "recommended_candidate"
    relevance: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    years_experience: int | None = None
    education: list[str] = Field(default_factory=list)
    domain_expertise: list[str] = Field(default_factory=list)
    prior_employers: list[str] = Field(default_factory=list)
    justification: str = ""
    source_of_recommendation: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"


class ProjectExperience(DeckForgeBaseModel):
    """Row in Section 3.3: Relevant Project Experience.

    evidence_ids SHOULD reference CLM-xxxx IDs when available.
    Empty list is allowed when evidence is thin — the Reviewer
    will flag missing evidence during the scoring pass.
    """

    project_name: str = ""
    client: str = ""
    outcomes: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    sector: str = ""
    duration: str = ""
    methodologies: list[str] = Field(default_factory=list)


class WhyStrategicGears(DeckForgeBaseModel):
    """Section 3: Why Strategic Gears."""

    capability_mapping: list[CapabilityMapping] = Field(default_factory=list)
    named_consultants: list[ConsultantProfile] = Field(default_factory=list)
    project_experience: list[ProjectExperience] = Field(default_factory=list)
    certifications_and_compliance: list[str] = Field(default_factory=list)


class ExternalEvidenceEntry(DeckForgeBaseModel):
    """Row in Section 4 tables."""

    source_id: str = ""  # EXT-xxx
    title: str = ""
    year: int = 0
    relevance: str = ""
    key_finding: str = ""
    source_type: Literal[
        "academic_paper", "industry_report", "benchmark",
        "case_study", "framework",
    ] = "industry_report"


class ExternalEvidenceSection(DeckForgeBaseModel):
    """Section 4: External Evidence."""

    entries: list[ExternalEvidenceEntry] = Field(default_factory=list)
    coverage_assessment: str = ""


class PhaseDetail(DeckForgeBaseModel):
    """Per-phase detail in Section 5.2."""

    phase_name: str = ""
    activities: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    governance: str = ""


class ProposedSolution(DeckForgeBaseModel):
    """Section 5: Proposed Solution."""

    methodology_overview: str = ""
    phase_details: list[PhaseDetail] = Field(default_factory=list)
    governance_framework: str = ""
    timeline_logic: str = ""
    value_case_and_differentiation: str = ""
    # Structured evidence fields for benchmark governance
    benchmark_references: list[ClassifiedClaim] = Field(default_factory=list)


class SlideBlueprintEntry(DeckForgeBaseModel):
    """One slide blueprint in Section 6.

    When must_have_evidence is non-empty, proof_points must also be
    non-empty — slides with required evidence must declare their proof points.
    """

    slide_number: int = 0
    section: str = ""
    layout: str = ""
    purpose: str = ""
    title: str = ""
    key_message: str = ""
    bullet_logic: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)  # CLM-xxxx / EXT-xxx refs
    visual_guidance: str = ""
    must_have_evidence: list[str] = Field(default_factory=list)
    forbidden_content: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def proof_points_required_when_must_have(self) -> SlideBlueprintEntry:
        """Auto-populate proof_points from must_have_evidence if omitted by LLM."""
        if self.must_have_evidence and not self.proof_points:
            self.proof_points = list(self.must_have_evidence)
        return self


class EvidenceLedgerEntry(DeckForgeBaseModel):
    """Row in Section 7: Evidence Ledger."""

    claim_id: str = ""
    claim_text: str = ""
    source_type: Literal["internal", "external"] = "internal"
    source_reference: str = ""
    confidence: float = 0.0
    verifiability_status: Literal[
        "verified", "verified_from_rfp", "partially_verified", "unverified", "gap",
    ] = "unverified"
    verification_note: str = ""

    # Typed provenance fields — populated by ledger reconciliation when
    # a legacy CLM-* entry maps to a registered ClaimProvenance.
    # None = not reconciled (legacy behavior preserved).
    claim_kind: str | None = None
    source_kind: str | None = None
    registry_claim_id: str | None = None


class EvidenceLedger(DeckForgeBaseModel):
    """Section 7: Evidence Ledger."""

    entries: list[EvidenceLedgerEntry] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Source Book (top-level)
# ──────────────────────────────────────────────────────────────


class SourceBook(DeckForgeBaseModel):
    """Proposal Source Book — 7-section structured document.

    Generated by the Source Book Writer agent, reviewed by the
    Reviewer/Red Team agent. Approved at Gate 3.
    """

    # Metadata
    client_name: str = ""
    rfp_name: str = ""
    language: str = "en"
    generation_date: str = ""

    # 7 sections
    rfp_interpretation: RFPInterpretation = Field(default_factory=RFPInterpretation)
    client_problem_framing: ClientProblemFraming = Field(default_factory=ClientProblemFraming)
    why_strategic_gears: WhyStrategicGears = Field(default_factory=WhyStrategicGears)
    external_evidence: ExternalEvidenceSection = Field(default_factory=ExternalEvidenceSection)
    proposed_solution: ProposedSolution = Field(default_factory=ProposedSolution)
    slide_blueprints: list[SlideBlueprintEntry] = Field(default_factory=list)
    evidence_ledger: EvidenceLedger = Field(default_factory=EvidenceLedger)

    # Iteration metadata
    pass_number: int = 1
    reviewer_feedback: str = ""
    requirement_density: Literal["high", "medium", "low"] = "medium"
    coherence: CoherenceResult = Field(default_factory=CoherenceResult)


class SourceBookSections67(DeckForgeBaseModel):
    """Combined Stage 2 output (kept for backward compatibility in tests)."""

    slide_blueprints: list[SlideBlueprintEntry] = Field(default_factory=list)
    evidence_ledger: EvidenceLedger = Field(default_factory=EvidenceLedger)


class SourceBookSection6(DeckForgeBaseModel):
    """Stage 2a output: Section 6 (slide blueprints only).

    Generated in a dedicated LLM call with Sections 1-5 as context,
    ensuring the full token budget is available for blueprint depth.
    """

    slide_blueprints: list[SlideBlueprintEntry] = Field(default_factory=list)


class SourceBookSection7(DeckForgeBaseModel):
    """Stage 2b output: Section 7 (evidence ledger only).

    Generated in a dedicated LLM call with Sections 1-5 + blueprints
    as context, ensuring full token budget for evidence coverage.
    """

    evidence_ledger: EvidenceLedger = Field(default_factory=EvidenceLedger)


# ──────────────────────────────────────────────────────────────
# Split-call models for deep content generation
# ──────────────────────────────────────────────────────────────


class SourceBookSections12(DeckForgeBaseModel):
    """Stage 1a output: Sections 1-2 (RFP Interpretation + Problem Framing).

    Generated in a dedicated LLM call so each section gets full prose depth.
    Also captures metadata fields (client_name, rfp_name, language).

    DEPRECATED: Kept for backward compatibility. New runs use
    SourceBookSection1 + SourceBookSection2 separately.
    """

    client_name: str = ""
    rfp_name: str = ""
    language: str = "en"
    generation_date: str = ""
    rfp_interpretation: RFPInterpretation = Field(default_factory=RFPInterpretation)
    client_problem_framing: ClientProblemFraming = Field(default_factory=ClientProblemFraming)


class SourceBookSection1(DeckForgeBaseModel):
    """Stage 1a output: Section 1 (RFP Interpretation) + metadata.

    Dedicated call so Section 1 gets full token budget for deep
    RFP analysis, compliance mapping, and evaluator logic.
    """

    client_name: str = ""
    rfp_name: str = ""
    language: str = "en"
    generation_date: str = ""
    rfp_interpretation: RFPInterpretation = Field(default_factory=RFPInterpretation)
    requirement_density: Literal["high", "medium", "low"] = "medium"


class SourceBookSection2(DeckForgeBaseModel):
    """Stage 1b output: Section 2 (Client Problem Framing).

    Dedicated call so Section 2 gets full token budget for deep
    problem diagnosis, urgency drivers, and transformation logic.
    """

    client_problem_framing: ClientProblemFraming = Field(default_factory=ClientProblemFraming)


class SourceBookSection3(DeckForgeBaseModel):
    """Stage 1b output: Section 3 (Why Strategic Gears).

    Dedicated call with full token budget for team profiles, project
    experience, and capability mapping.
    """

    why_strategic_gears: WhyStrategicGears = Field(default_factory=WhyStrategicGears)


class SourceBookSection4(DeckForgeBaseModel):
    """Stage 1c output: Section 4 (External Evidence).

    Dedicated call to curate external evidence from evidence pack.
    """

    external_evidence: ExternalEvidenceSection = Field(default_factory=ExternalEvidenceSection)


class SourceBookSection5(DeckForgeBaseModel):
    """Stage 1d output: Section 5 (Proposed Solution / Methodology).

    This is the highest-weight section. Gets its own dedicated call
    with full token budget for deep methodology, governance, and timeline.
    """

    proposed_solution: ProposedSolution = Field(default_factory=ProposedSolution)


# ── Internal writer sub-models for Section 5 split generation ─────
# These are NOT part of the Source Book schema. They are used only
# inside the writer to split generation into two calls so each gets
# full 32K token budget. The outputs are merged into ProposedSolution.


class _Section5Methodology(DeckForgeBaseModel):
    """Internal: Call 1 of Section 5 split — methodology + phases.

    Owns: methodology_overview, phase_details.
    Does NOT generate governance, timeline, or value case.
    """

    methodology_overview: str = ""
    phase_details: list[PhaseDetail] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reject_empty_phases(self) -> "_Section5Methodology":
        """Reject empty phase_details — methodology must have execution structure."""
        if len(self.phase_details) < 2:
            raise ValueError(
                f"Section 5 phase_details has only {len(self.phase_details)} phases. "
                "The methodology must include at least 3-4 phases with activities, "
                "deliverables, and governance. Retry with full phase structure."
            )
        return self


class _Section5Governance(DeckForgeBaseModel):
    """Internal: Call 2 of Section 5 split — governance + timeline + value.

    Owns: governance_framework, timeline_logic, value_case_and_differentiation.
    Does NOT generate methodology or phases.
    """

    governance_framework: str = ""
    timeline_logic: str = ""
    value_case_and_differentiation: str = ""


# ──────────────────────────────────────────────────────────────
# Source Book Review (critique output)
# ──────────────────────────────────────────────────────────────


class SectionCritique(DeckForgeBaseModel):
    """Per-section critique from Reviewer/Red Team."""

    section_id: str = ""  # e.g. "rfp_interpretation", "why_strategic_gears"
    score: int = 3  # 1-5
    issues: list[str] = Field(default_factory=list)
    rewrite_instructions: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    fluff_detected: list[str] = Field(default_factory=list)


class SourceBookReview(DeckForgeBaseModel):
    """Reviewer/Red Team critique of the Source Book.

    Drives the iteration loop: if overall_score < 4 or any section < 3,
    the Source Book Writer rewrites with critique feedback.
    """

    section_critiques: list[SectionCritique] = Field(default_factory=list)
    overall_score: int = 3  # 1-5
    coherence_issues: list[str] = Field(default_factory=list)
    repetition_detected: list[str] = Field(default_factory=list)
    competitive_viability: Literal[
        "strong", "adequate", "weak", "not_competitive",
    ] = "adequate"
    pass_threshold_met: bool = False  # True if overall >= 4 and no section < 3
    rewrite_required: bool = True
