"""Evidence coverage builder — Slice 3.2.

Builds an EvidenceCoverageReport from a ClaimRegistry by counting
external_methodology claims per topic, bucketed by relevance_class.

Acceptance invariants tested here:
  * direct sources count toward the minimum; adjacent and analogical
    do NOT;
  * a topic with only analogical sources is not_met regardless of
    how many analogical sources exist;
  * coverage report status fails if ANY required topic is not_met;
  * final_artifact_gate rejects on coverage fail.
"""
from __future__ import annotations

from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.conformance import ConformanceReport
from src.models.source_book import SourceBookReview
from src.services.artifact_gates import (
    CoverageTopic,
    EvidenceCoverageReport,
    EvidenceCoverageRequirement,
    build_evidence_coverage_report,
    final_artifact_gate,
)


def _ext_claim(
    claim_id: str,
    text: str,
    *,
    relevance: str = "direct_topic",
    role: str = "methodology_support",
) -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status="externally_verified",
        relevance_class=relevance,  # type: ignore[arg-type]
        evidence_role=role,  # type: ignore[arg-type]
    )


# ── Direct counts vs adjacent/analogical ──────────────────────────────


def test_topic_met_when_direct_count_at_minimum() -> None:
    reg = ClaimRegistry()
    reg.register(_ext_claim("EXT-001", "UNESCO RAM evaluation", relevance="direct_topic"))
    reg.register(_ext_claim("EXT-002", "UNESCO RAM country review", relevance="direct_topic"))
    report = build_evidence_coverage_report(
        reg,
        topics=[CoverageTopic(name="UNESCO RAM", keywords=["unesco ram"], minimum_direct_sources=2)],
    )
    assert report.status == "pass"
    req = report.requirements[0]
    assert req.found_direct == 2
    assert req.status == "met"


def test_topic_not_met_when_only_analogical() -> None:
    """Acceptance #6: analogical sources do not satisfy direct minimums."""
    reg = ClaimRegistry()
    for i in range(5):  # five analogical sources still fail a min=1 direct
        reg.register(_ext_claim(
            f"EXT-{i:03d}",
            "UNESCO RAM analogical case",
            relevance="analogical",
        ))
    report = build_evidence_coverage_report(
        reg,
        topics=[CoverageTopic(name="UNESCO RAM", keywords=["unesco ram"], minimum_direct_sources=1)],
    )
    assert report.status == "fail"
    req = report.requirements[0]
    assert req.found_direct == 0
    assert req.found_analogical == 5
    assert req.status == "not_met"


def test_topic_not_met_when_only_adjacent() -> None:
    """Adjacent sources also do not satisfy direct minimums."""
    reg = ClaimRegistry()
    reg.register(_ext_claim("EXT-100", "AI ethics adjacent paper", relevance="adjacent_domain"))
    report = build_evidence_coverage_report(
        reg,
        topics=[CoverageTopic(name="AI ethics", keywords=["ai ethics"], minimum_direct_sources=1)],
    )
    assert report.status == "fail"
    req = report.requirements[0]
    assert req.found_direct == 0
    assert req.found_adjacent == 1
    assert req.status == "not_met"


def test_mixed_counts_bucketed_correctly() -> None:
    reg = ClaimRegistry()
    reg.register(_ext_claim("EXT-1", "AI ethics primary", relevance="direct_topic"))
    reg.register(_ext_claim("EXT-2", "AI ethics adjacent", relevance="adjacent_domain"))
    reg.register(_ext_claim("EXT-3", "AI ethics analogical", relevance="analogical"))
    report = build_evidence_coverage_report(
        reg,
        topics=[CoverageTopic(name="AI ethics", keywords=["ai ethics"], minimum_direct_sources=1)],
    )
    req = report.requirements[0]
    assert req.found_direct == 1
    assert req.found_adjacent == 1
    assert req.found_analogical == 1
    assert req.status == "met"


def test_multiple_topics_one_failing_marks_overall_fail() -> None:
    reg = ClaimRegistry()
    reg.register(_ext_claim("EXT-A", "AI ethics paper", relevance="direct_topic"))
    reg.register(_ext_claim("EXT-B", "Capacity building paper", relevance="adjacent_domain"))
    report = build_evidence_coverage_report(
        reg,
        topics=[
            CoverageTopic(name="AI ethics", keywords=["ai ethics"], minimum_direct_sources=1),
            CoverageTopic(name="Capacity building", keywords=["capacity building"], minimum_direct_sources=1),
        ],
    )
    assert report.status == "fail"
    by_topic = {r.topic: r for r in report.requirements}
    assert by_topic["AI ethics"].status == "met"
    assert by_topic["Capacity building"].status == "not_met"


def test_no_keyword_match_yields_zero_counts() -> None:
    reg = ClaimRegistry()
    reg.register(_ext_claim("EXT-1", "Coffee shop study", relevance="direct_topic"))
    report = build_evidence_coverage_report(
        reg,
        topics=[CoverageTopic(name="AI ethics", keywords=["ai ethics"], minimum_direct_sources=1)],
    )
    req = report.requirements[0]
    assert req.found_direct == 0
    assert req.found_adjacent == 0
    assert req.found_analogical == 0
    assert req.status == "not_met"


# ── Empty / edge cases ────────────────────────────────────────────────


def test_empty_registry_yields_zeroes() -> None:
    report = build_evidence_coverage_report(
        ClaimRegistry(),
        topics=[CoverageTopic(name="X", keywords=["x"], minimum_direct_sources=1)],
    )
    assert report.status == "fail"
    assert report.requirements[0].found_direct == 0


def test_no_topics_yields_pass() -> None:
    """Convention: with zero required topics, coverage trivially passes
    (the ``all`` of an empty list is True)."""
    reg = ClaimRegistry()
    report = build_evidence_coverage_report(reg, topics=[])
    assert report.status == "pass"
    assert report.requirements == []


def test_only_external_methodology_claims_counted() -> None:
    """Other claim kinds (rfp_fact, internal_company_claim) are ignored
    by the coverage builder even if their text matches the keyword."""
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="RFP-FACT-001",
        text="UNESCO RAM mandated by RFP",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    reg.register(ClaimProvenance(
        claim_id="BIDDER-001",
        text="UNESCO RAM consulting experience",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_verified",
    ))
    report = build_evidence_coverage_report(
        reg,
        topics=[CoverageTopic(name="UNESCO RAM", keywords=["unesco ram"], minimum_direct_sources=1)],
    )
    req = report.requirements[0]
    assert req.found_direct == 0
    assert req.status == "not_met"


# ── Acceptance #7: final_artifact_gate rejects on coverage fail ───────


def _passing_conformance() -> ConformanceReport:
    return ConformanceReport(
        conformance_status="pass",
        final_acceptance_decision="accept",
        hard_requirements_checked=1,
        hard_requirements_passed=1,
        hard_requirements_failed=0,
    )


def _passing_review() -> SourceBookReview:
    return SourceBookReview(
        overall_score=4,
        pass_threshold_met=True,
        competitive_viability="adequate",
    )


def test_final_artifact_gate_rejects_when_coverage_fails() -> None:
    reg = ClaimRegistry()
    reg.register(_ext_claim("EXT-A", "Analogical only", relevance="analogical"))
    coverage = build_evidence_coverage_report(
        reg,
        topics=[CoverageTopic(
            name="UNESCO RAM",
            keywords=["analogical"],
            minimum_direct_sources=1,
        )],
    )
    assert coverage.status == "fail"

    decision = final_artifact_gate(
        _passing_conformance(),
        _passing_review(),
        coverage,
        [], reg, [],
    )
    assert decision.decision == "reject"
    assert decision.proposal_ready is False
    assert "DRAFT" in decision.artifact_label
    assert any(f.code == "EVIDENCE_COVERAGE" for f in decision.failures)


def test_final_artifact_gate_passes_when_coverage_meets_minimums() -> None:
    reg = ClaimRegistry()
    reg.register(_ext_claim("EXT-A", "Direct one", relevance="direct_topic"))
    reg.register(_ext_claim("EXT-B", "Direct two", relevance="direct_topic"))
    coverage = build_evidence_coverage_report(
        reg,
        topics=[CoverageTopic(name="X", keywords=["direct"], minimum_direct_sources=2)],
    )
    assert coverage.status == "pass"

    decision = final_artifact_gate(
        _passing_conformance(),
        _passing_review(),
        coverage,
        [], reg, [],
    )
    assert decision.decision == "approve"
    assert decision.proposal_ready is True
