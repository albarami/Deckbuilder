"""UNESCO evidence-coverage regression — Slice 3.4.

The frozen ``external_evidence_pack.json`` for sb-ar-1777280086 has 14
sources spanning UNESCO topics, governance, capacity building, knowledge
transfer, and digital government. This regression verifies:

  * the classifier converts the frozen pack into ClaimProvenance entries
    with explicit relevance_class
  * the coverage builder credits direct_topic claims toward the minimum
    AND ignores adjacent / analogical (Slice 3 acceptance #3, #6)
  * a synthetic "analogical-only" topic correctly fails the gate even
    when many analogical sources exist (acceptance #6 spelled out)
  * final_artifact_gate rejects on coverage failure (acceptance #7)

These tests do not run a fresh pipeline. The frozen pack is loaded
directly from ``output/sb-ar-1777280086/`` and classified in place.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.conformance import ConformanceReport
from src.models.external_evidence import ExternalEvidencePack
from src.models.source_book import SourceBookReview
from src.services.artifact_gates import (
    CoverageTopic,
    build_evidence_coverage_report,
    final_artifact_gate,
)
from src.services.external_methodology_classifier import (
    classify_external_evidence_pack,
)


_UNESCO_PACK_PATH = Path(
    "output/sb-ar-1777280086/external_evidence_pack.json"
)


def _load_unesco_pack() -> ExternalEvidencePack:
    data = json.loads(_UNESCO_PACK_PATH.read_text(encoding="utf-8"))
    return ExternalEvidencePack.model_validate(data)


def _classify_with_realistic_topics() -> ClaimRegistry:
    pack = _load_unesco_pack()
    return classify_external_evidence_pack(
        pack,
        primary_topics=["unesco", "ai ", "governance", "ethics"],
        adjacent_topics=[
            "digital government",
            "knowledge translation",
            "capacity building",
        ],
    )


# ── Classifier produces an explicit per-source relevance_class ────────


def test_unesco_pack_classifies_every_source() -> None:
    pack = _load_unesco_pack()
    assert len(pack.sources) == 14, "Fixture invariant: 14 frozen sources"
    reg = _classify_with_realistic_topics()
    assert len(reg.external_methodology) == 14
    for c in reg.external_methodology:
        assert c.claim_kind == "external_methodology"
        assert c.source_kind == "external_source"
        assert c.verification_status == "externally_verified"
        assert c.relevance_class in {
            "direct_topic", "adjacent_domain", "analogical",
        }


def test_unesco_classification_distribution() -> None:
    """Sanity check that the classifier separates direct vs adjacent.
    Frozen-fixture invariant: all 14 sources have evidence_tier in
    (primary, secondary) so none get the analogical hard-lock."""
    reg = _classify_with_realistic_topics()
    counts = {"direct_topic": 0, "adjacent_domain": 0, "analogical": 0}
    for c in reg.external_methodology:
        counts[c.relevance_class] += 1
    assert sum(counts.values()) == 14
    # At least some direct + some adjacent — exact split is fixture-dependent
    assert counts["direct_topic"] >= 1
    assert counts["adjacent_domain"] >= 1


# ── Coverage report from frozen pack ───────────────────────────────────


def test_unesco_coverage_built_from_classified_pack() -> None:
    reg = _classify_with_realistic_topics()
    report = build_evidence_coverage_report(reg, topics=[
        CoverageTopic(
            name="UNESCO",
            keywords=["UNESCO"],
            minimum_direct_sources=2,
        ),
        CoverageTopic(
            name="Knowledge transfer",
            keywords=["knowledge"],
            minimum_direct_sources=1,
        ),
        CoverageTopic(
            name="Hypothetical missing topic",
            keywords=["BLOCKCHAIN_QUANTUM_KARAOKE"],
            minimum_direct_sources=1,
        ),
    ])
    by_topic = {r.topic: r for r in report.requirements}
    # UNESCO sources are in the title (EXT-002, EXT-003 directly cited)
    assert by_topic["UNESCO"].found_direct >= 2
    assert by_topic["UNESCO"].status == "met"
    # The made-up topic has zero matching claims → not_met
    assert by_topic["Hypothetical missing topic"].status == "not_met"
    # Overall fails because at least one topic is not_met
    assert report.status == "fail"


# ── Acceptance #6: analogical never counts as direct ─────────────────


def test_analogical_only_topic_fails_regardless_of_count() -> None:
    """Even with five analogical UNESCO RAM references, a
    `minimum_direct_sources=1` topic stays not_met. This is the cleanest
    expression of acceptance criterion #6."""
    reg = ClaimRegistry()
    for i in range(5):
        reg.register(ClaimProvenance(
            claim_id=f"EXT-RAM-ANALOG-{i:03d}",
            text="UNESCO RAM analogical case",
            claim_kind="external_methodology",
            source_kind="external_source",
            verification_status="externally_verified",
            relevance_class="analogical",
            evidence_role="methodology_support",
        ))
    report = build_evidence_coverage_report(reg, topics=[
        CoverageTopic(
            name="UNESCO RAM",
            keywords=["unesco ram"],
            minimum_direct_sources=1,
        ),
    ])
    req = report.requirements[0]
    assert req.found_direct == 0
    assert req.found_analogical == 5
    assert req.status == "not_met"
    assert report.status == "fail"


def test_one_direct_outranks_any_count_of_analogical() -> None:
    """One direct_topic claim flips the topic to met even when many
    analogical claims also match. Confirms direct dominance."""
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="EXT-ONE-DIRECT",
        text="UNESCO RAM direct methodology source",
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="direct_topic",
        evidence_role="methodology_support",
    ))
    for i in range(5):
        reg.register(ClaimProvenance(
            claim_id=f"EXT-ANALOG-{i:03d}",
            text="UNESCO RAM analogical case",
            claim_kind="external_methodology",
            source_kind="external_source",
            verification_status="externally_verified",
            relevance_class="analogical",
            evidence_role="methodology_support",
        ))
    report = build_evidence_coverage_report(reg, topics=[
        CoverageTopic(
            name="UNESCO RAM",
            keywords=["unesco ram"],
            minimum_direct_sources=1,
        ),
    ])
    req = report.requirements[0]
    assert req.found_direct == 1
    assert req.found_analogical == 5
    assert req.status == "met"


# ── Acceptance #7: final gate rejects on coverage fail ───────────────


def test_final_gate_rejects_when_unesco_coverage_fails() -> None:
    reg = ClaimRegistry()
    # Only an analogical UNESCO RAM source exists
    reg.register(ClaimProvenance(
        claim_id="EXT-ANALOG-A",
        text="UNESCO RAM analogical only",
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="analogical",
        evidence_role="methodology_support",
    ))
    coverage = build_evidence_coverage_report(reg, topics=[
        CoverageTopic(
            name="UNESCO RAM",
            keywords=["unesco ram"],
            minimum_direct_sources=2,
        ),
    ])
    assert coverage.status == "fail"

    decision = final_artifact_gate(
        ConformanceReport(
            conformance_status="pass",
            final_acceptance_decision="accept",
            hard_requirements_checked=1,
            hard_requirements_passed=1,
            hard_requirements_failed=0,
        ),
        SourceBookReview(
            overall_score=4,
            pass_threshold_met=True,
            competitive_viability="adequate",
        ),
        coverage,
        [], reg, [],
    )
    assert decision.decision == "reject"
    assert decision.proposal_ready is False
    assert any(f.code == "EVIDENCE_COVERAGE" for f in decision.failures)


# ── Acceptance #4: analogical methodology cannot be a slide proof point ──


def test_unesco_analogical_methodology_blocked_from_slide() -> None:
    """An analogical UNESCO RAM reference cannot survive
    gate_slide_proof_points. Same registry as above; slide blueprint
    references the analogical id; gate drops it."""
    from src.models.source_book import SlideBlueprintEntry
    from src.services.artifact_gates import gate_slide_proof_points

    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="EXT-RAM-ANALOG",
        text="UNESCO RAM analogical",
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="analogical",
        evidence_role="methodology_support",
    ))
    bp = SlideBlueprintEntry(
        slide_number=12,
        title="UNESCO RAM proof",
        proof_points=["EXT-RAM-ANALOG"],
    )
    gated, violations = gate_slide_proof_points([bp], reg)
    assert gated[0].proof_points == []
    assert len(violations) == 1
    assert violations[0].verification_status == "externally_verified"
    assert violations[0].reason == "not_a_proof_point"
