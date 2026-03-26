"""Proposal Source Book and Source Book Review schemas.

The Source Book is a 7-section structured document that captures all proposal
reasoning, evidence, and slide-by-slide blueprints. It is the central artifact
reviewed at Gate 3 before slide generation begins.

The SourceBookReview captures the Reviewer/Red Team critique with per-section
scoring and rewrite instructions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import DeckForgeBaseModel

# ──────────────────────────────────────────────────────────────
# Source Book sections (7 sections per design doc Section 7.1)
# ──────────────────────────────────────────────────────────────


class RFPInterpretation(DeckForgeBaseModel):
    """Section 1: RFP Interpretation."""

    objective_and_scope: str = ""
    constraints_and_compliance: str = ""
    unstated_evaluator_priorities: str = ""
    probable_scoring_logic: str = ""
    key_compliance_requirements: list[str] = Field(default_factory=list)


class ClientProblemFraming(DeckForgeBaseModel):
    """Section 2: Client Problem Framing."""

    current_state_challenge: str = ""
    why_it_matters_now: str = ""
    transformation_logic: str = ""
    risk_if_unchanged: str = ""


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
    """Row in Section 3.2: Named Consultants & Role Relevance."""

    name: str = ""
    role: str = ""
    relevance: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    years_experience: int | None = None
    education: list[str] = Field(default_factory=list)
    domain_expertise: list[str] = Field(default_factory=list)
    prior_employers: list[str] = Field(default_factory=list)


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
        "verified", "partially_verified", "unverified", "gap",
    ] = "unverified"
    verification_note: str = ""


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
