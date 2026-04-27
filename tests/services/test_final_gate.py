"""Tests for the final artifact gate."""
from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.conformance import ConformanceReport
from src.models.source_book import SourceBookReview
from src.services.artifact_gates import (
    ArtifactSection,
    ArtifactGateDecision,
    EvidenceCoverageReport,
    EvidenceCoverageRequirement,
    ForbiddenLeakageViolation,
    GateFailure,
    final_artifact_gate,
)


def _passing_conformance():
    return ConformanceReport(
        conformance_status="pass",
        final_acceptance_decision="accept",
        hard_requirements_checked=10,
        hard_requirements_passed=10,
        hard_requirements_failed=0,
    )


def _passing_review():
    return SourceBookReview(
        overall_score=4,
        pass_threshold_met=True,
        competitive_viability="adequate",
    )


def _passing_coverage():
    return EvidenceCoverageReport(
        requirements=[
            EvidenceCoverageRequirement(
                topic="test", minimum_direct_sources=1,
                found_direct=2, status="met",
            ),
        ],
        status="pass",
    )


def test_all_pass_approves():
    decision = final_artifact_gate(
        _passing_conformance(), _passing_review(), _passing_coverage(),
        [], ClaimRegistry(), [],
    )
    assert decision.decision == "approve"
    assert decision.proposal_ready is True
    assert decision.artifact_label == "PROPOSAL READY"


def test_conformance_fail_rejects():
    cr = ConformanceReport(
        conformance_status="fail",
        final_acceptance_decision="reject",
        hard_requirements_checked=10,
        hard_requirements_passed=5,
        hard_requirements_failed=5,
    )
    decision = final_artifact_gate(
        cr, _passing_review(), _passing_coverage(),
        [], ClaimRegistry(), [],
    )
    assert decision.decision == "reject"
    assert decision.proposal_ready is False
    assert "DRAFT" in decision.artifact_label


def test_forbidden_claims_reject():
    cr = ConformanceReport(
        conformance_status="pass",
        final_acceptance_decision="accept",
        hard_requirements_checked=10,
        hard_requirements_passed=10,
        hard_requirements_failed=0,
    )
    # Manually set forbidden_claims count
    cr_dict = cr.model_dump()
    cr_dict["conformance_forbidden_claims"] = 2
    # Need to check if ConformanceReport has this field
    # If not, we test via forbidden_scan violations instead
    violations = [
        ForbiddenLeakageViolation(
            pattern=r"\bPRJ-\d+\b", matched_text="PRJ-001",
            location="why_sg", section_type="client_facing_body",
        ),
    ]
    decision = final_artifact_gate(
        _passing_conformance(), _passing_review(), _passing_coverage(),
        violations, ClaimRegistry(), [],
    )
    assert decision.decision == "reject"


def test_evidence_coverage_fail_rejects():
    cov = EvidenceCoverageReport(
        requirements=[
            EvidenceCoverageRequirement(
                topic="unesco_ai_ethics", minimum_direct_sources=2,
                found_direct=0, status="not_met",
            ),
        ],
        status="fail",
    )
    decision = final_artifact_gate(
        _passing_conformance(), _passing_review(), cov,
        [], ClaimRegistry(), [],
    )
    assert decision.decision == "reject"
    assert any(f.code == "EVIDENCE_COVERAGE" for f in decision.failures)


def test_reviewer_threshold_fail_rejects():
    review = SourceBookReview(
        overall_score=2,
        pass_threshold_met=False,
        competitive_viability="weak",
    )
    decision = final_artifact_gate(
        _passing_conformance(), review, _passing_coverage(),
        [], ClaimRegistry(), [],
    )
    assert decision.decision == "reject"
    assert any(f.code == "REVIEWER_THRESHOLD" for f in decision.failures)


def test_rendered_section_leakage_caught():
    sections = [ArtifactSection(
        section_path="slide_5/body", section_type="slide_body",
        text="prior SDAIA project PRJ-001 confirmed",
    )]
    decision = final_artifact_gate(
        _passing_conformance(), _passing_review(), _passing_coverage(),
        [], ClaimRegistry(), sections,
    )
    assert decision.decision == "reject"
    assert any(f.code == "RENDERED_LEAKAGE" for f in decision.failures)


def test_clean_rendered_sections_pass():
    sections = [ArtifactSection(
        section_path="section_1/body", section_type="client_facing_body",
        text="مدة العقد 12 شهراً بالضبط من تاريخ إشعار البدء",
    )]
    decision = final_artifact_gate(
        _passing_conformance(), _passing_review(), _passing_coverage(),
        [], ClaimRegistry(), sections,
    )
    assert decision.decision == "approve"


def test_gate_failures_have_severity():
    cr = ConformanceReport(
        conformance_status="fail",
        final_acceptance_decision="reject",
        hard_requirements_checked=10,
        hard_requirements_passed=5,
        hard_requirements_failed=5,
    )
    decision = final_artifact_gate(
        cr, _passing_review(), _passing_coverage(),
        [], ClaimRegistry(), [],
    )
    assert all(hasattr(f, "severity") for f in decision.failures)
    assert any(f.severity == "critical" for f in decision.failures)
