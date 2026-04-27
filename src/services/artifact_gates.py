"""Artifact gates — context-specific usage rules for claims in the pipeline.

Every claim must pass the appropriate gate before appearing in an artifact.
The gates form a hierarchy from most permissive (internal_gap_appendix)
to most restrictive (client_proposal / proof_point).

Architecture invariant:
    absence of Engine 2 verification defaults to internal_unverified = blocked.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.common import DeckForgeBaseModel

if TYPE_CHECKING:
    from src.models.conformance import ConformanceReport
    from src.models.source_book import SourceBookReview


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


# ── Artifact Section ─────────────────────────────────────────────


class ArtifactSection(DeckForgeBaseModel):
    """A section of a generated artifact, tagged by type for scanning."""

    section_path: str
    section_type: Literal[
        "client_facing_body",
        "proof_column",
        "slide_body",
        "slide_proof_points",
        "speaker_notes",
        "internal_gap_appendix",
        "internal_bid_notes",
        "evidence_ledger",
        "drafting_notes",
    ]
    text: str


# ── Forbidden Leakage Scanner ────────────────────────────────────


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
    "internal_gap_appendix",
    "drafting_notes",
    "evidence_ledger",
    "internal_bid_notes",
}


class ForbiddenLeakageViolation(DeckForgeBaseModel):
    """A single violation found by the forbidden scanner."""

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
    """Scan a section for forbidden internal-claim leakage.

    Returns empty list if section is an internal-only type.
    """
    if section.section_type in INTERNAL_ONLY_SECTION_TYPES:
        return []

    violations: list[ForbiddenLeakageViolation] = []

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


# ── Evidence Coverage ────────────────────────────────────────────


class EvidenceCoverageRequirement(DeckForgeBaseModel):
    """Coverage requirement for one evidence topic."""

    topic: str
    minimum_direct_sources: int
    found_direct: int = 0
    found_adjacent: int = 0
    found_analogical: int = 0
    status: Literal["met", "not_met"] = "not_met"
    missing_reason: str = ""

    @model_validator(mode="after")
    def compute_status(self) -> "EvidenceCoverageRequirement":
        object.__setattr__(
            self, "status",
            "met" if self.found_direct >= self.minimum_direct_sources else "not_met",
        )
        return self


class EvidenceCoverageReport(DeckForgeBaseModel):
    """Aggregated evidence coverage across all required topics."""

    requirements: list[EvidenceCoverageRequirement] = Field(default_factory=list)
    status: Literal["pass", "fail"] = "fail"

    @model_validator(mode="after")
    def compute_status(self) -> "EvidenceCoverageReport":
        all_met = all(r.status == "met" for r in self.requirements)
        object.__setattr__(self, "status", "pass" if all_met else "fail")
        return self


# ── Gate Failure ─────────────────────────────────────────────────


class GateFailure(DeckForgeBaseModel):
    """A single failure from the final gate."""

    code: str
    severity: Literal["critical", "major", "minor"]
    message: str
    affected_artifact: str | None = None
    claim_id: str | None = None


class ArtifactGateDecision(DeckForgeBaseModel):
    """Decision from the final artifact gate."""

    decision: Literal["approve", "reject"]
    proposal_ready: bool
    deck_generation_allowed: bool
    artifact_label: str
    failures: list[GateFailure] = Field(default_factory=list)


# ── Final Artifact Gate ──────────────────────────────────────────


def final_artifact_gate(
    conformance_report: "ConformanceReport",
    reviewer_score: "SourceBookReview",
    evidence_coverage: EvidenceCoverageReport,
    forbidden_scan: list[ForbiddenLeakageViolation],
    claim_registry: ClaimRegistry,
    rendered_sections: list[ArtifactSection],
) -> ArtifactGateDecision:
    """Final pipeline checkpoint. ALL gates must pass for proposal_ready.

    Checks: conformance, forbidden claims, reviewer threshold,
    evidence coverage, forbidden leakage, rendered artifact scanning.
    """
    failures: list[GateFailure] = []

    if conformance_report.conformance_status != "pass":
        failures.append(GateFailure(
            code="CONFORMANCE_FAIL",
            severity="critical",
            message=f"conformance_status={conformance_report.conformance_status}",
        ))

    forbidden_count = getattr(conformance_report, "conformance_forbidden_claims", 0)
    if forbidden_count and forbidden_count > 0:
        failures.append(GateFailure(
            code="FORBIDDEN_CLAIMS",
            severity="critical",
            message=f"forbidden_claims={forbidden_count}",
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

    # Scan rendered artifacts for forbidden leakage
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
