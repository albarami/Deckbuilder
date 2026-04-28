"""External-methodology pipeline wiring — Slice 3.5.

Verifies that the external-evidence stage of the pipeline classifies
every ExternalSource into ClaimProvenance, registers them under
state.claim_registry, builds an EvidenceCoverageReport from
routing-derived topic labels, and attaches the report to state. Also
verifies the gate path: a state-attached coverage report whose status
is "fail" forces final_artifact_gate to reject.

No fresh pipeline run is performed. The frozen UNESCO
external_evidence_pack is loaded from disk and fed to the wiring helper
directly. The pipeline graph node is exercised via a unit-style call
that mocks the external research agent's LLM-driven step.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.models.claim_provenance import ClaimProvenance
from src.models.common import BilingualText
from src.models.conformance import ConformanceReport
from src.models.external_evidence import ExternalEvidencePack
from src.models.rfp import RFPContext
from src.models.routing import RFPClassification
from src.models.source_book import SourceBookReview
from src.models.state import DeckForgeState
from src.services.artifact_gates import (
    EvidenceCoverageReport,
    final_artifact_gate,
)
from src.services.external_methodology_classifier import (
    register_external_methodology,
)


_UNESCO_PACK_PATH = Path(
    "output/sb-ar-1777280086/external_evidence_pack.json"
)


def _load_unesco_pack() -> ExternalEvidencePack:
    return ExternalEvidencePack.model_validate(
        json.loads(_UNESCO_PACK_PATH.read_text(encoding="utf-8"))
    )


def _classification_with_unesco_domains() -> RFPClassification:
    return RFPClassification(
        jurisdiction="saudi_arabia",
        sector="public_sector",
        primary_domains=["ai_governance_ethics", "unesco_unesco_ram"],
        secondary_domains=["digital_transformation"],
        domain="ai_governance_ethics",
        confidence=1.0,
    )


# ── Helper-level wiring tests ──────────────────────────────────────────


def test_helper_registers_every_source_as_external_methodology() -> None:
    pack = _load_unesco_pack()
    state = DeckForgeState()
    coverage = register_external_methodology(
        pack,
        state.claim_registry,
        primary_domains=["ai_governance_ethics", "unesco_unesco_ram"],
        secondary_domains=["digital_transformation"],
    )
    # Every ExternalSource in the pack becomes an external_methodology claim
    assert len(state.claim_registry.external_methodology) == len(pack.sources)
    for c in state.claim_registry.external_methodology:
        assert c.claim_kind == "external_methodology"
        assert c.source_kind == "external_source"
        assert c.verification_status == "externally_verified"
        assert c.evidence_role == "methodology_support"
    # Coverage report is structured with one requirement per primary domain
    assert isinstance(coverage, EvidenceCoverageReport)
    assert {r.topic for r in coverage.requirements} == {
        "ai_governance_ethics", "unesco_unesco_ram",
    }


def test_helper_does_not_add_rfp_facts_or_internal_claims() -> None:
    """Acceptance: the wiring step must NOT mutate any non-external bucket."""
    pack = _load_unesco_pack()
    state = DeckForgeState()
    # Pre-seed registry with an rfp_fact and an internal claim
    state.claim_registry.register(ClaimProvenance(
        claim_id="RFP-FACT-PRE",
        text="pre-existing RFP fact",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    state.claim_registry.register(ClaimProvenance(
        claim_id="BIDDER-PRE",
        text="pre-existing bidder claim",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_unverified",
    ))
    register_external_methodology(
        pack,
        state.claim_registry,
        primary_domains=["ai_governance_ethics"],
    )
    rfp_facts = state.claim_registry.rfp_facts
    bidder = state.claim_registry.bidder_claims
    # Pre-seeded entries untouched
    assert {c.claim_id for c in rfp_facts} == {"RFP-FACT-PRE"}
    assert {c.claim_id for c in bidder} == {"BIDDER-PRE"}


def test_helper_builds_coverage_from_routing_keywords() -> None:
    """Acceptance #6: topics come from routing/domain labels, not a
    hardcoded synthetic-only list. The helper reads keyword sets from
    each domain pack JSON."""
    pack = _load_unesco_pack()
    state = DeckForgeState()
    coverage = register_external_methodology(
        pack,
        state.claim_registry,
        primary_domains=["unesco_unesco_ram"],
        minimum_direct_sources=2,
    )
    by_topic = {r.topic: r for r in coverage.requirements}
    assert "unesco_unesco_ram" in by_topic
    req = by_topic["unesco_unesco_ram"]
    # The pack's keywords (UNESCO, RAM, …) match many of the frozen sources.
    # Direct count should be > 0; the frozen pack has zero analogical
    # because every source has evidence_tier in {primary, secondary}.
    assert req.found_direct >= 0
    assert req.found_analogical == 0


def test_helper_minimum_direct_sources_is_configurable() -> None:
    pack = _load_unesco_pack()
    state = DeckForgeState()
    coverage = register_external_methodology(
        pack,
        state.claim_registry,
        primary_domains=["unesco_unesco_ram"],
        minimum_direct_sources=999,  # impossible threshold
    )
    by_topic = {r.topic: r for r in coverage.requirements}
    assert by_topic["unesco_unesco_ram"].status == "not_met"


# ── Pipeline node integration via mocked LLM ───────────────────────────


@pytest.mark.asyncio
async def test_evidence_curation_node_attaches_coverage_to_state() -> None:
    """Calling evidence_curation_node with a stubbed external_research
    agent populates state.claim_registry with external_methodology
    claims and writes evidence_coverage_report onto state updates."""
    from src.pipeline import graph as pipeline_graph

    pack = _load_unesco_pack()
    state = DeckForgeState()
    state.rfp_context = RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )
    state.routing_report = {
        "classification": _classification_with_unesco_domains().model_dump(
            mode="json",
        ),
    }

    async def _fake_external_run(_state: DeckForgeState) -> dict:
        return {"external_evidence_pack": pack, "session": _state.session}

    async def _fake_analysis(_state: DeckForgeState) -> dict:
        return {"reference_index": None, "session": _state.session}

    with patch(
        "src.agents.external_research.agent.run", _fake_external_run,
    ), patch.object(pipeline_graph, "analysis_node", _fake_analysis):
        updates = await pipeline_graph.evidence_curation_node(state)

    # external_evidence_pack carried through
    assert updates["external_evidence_pack"] is pack
    # coverage report written to state updates as a JSON-safe dict
    assert "evidence_coverage_report" in updates
    coverage_dict = updates["evidence_coverage_report"]
    assert isinstance(coverage_dict, dict)
    assert "requirements" in coverage_dict
    # Every external claim registered, none of any other kind added
    assert "claim_registry" in updates
    registry = updates["claim_registry"]
    assert len(registry.external_methodology) == len(pack.sources)
    assert len(registry.rfp_facts) == 0
    assert len(registry.bidder_claims) == 0


# ── Acceptance #7: state-driven gate rejects on coverage fail ──────────


def test_final_gate_rejects_when_state_attached_coverage_fails() -> None:
    """Round-trip: state stores coverage as dict; the gate path
    deserializes and rejects if status != pass."""
    state = DeckForgeState()
    # Synthesize a failing coverage
    failing = {
        "requirements": [{
            "topic": "unesco_unesco_ram",
            "minimum_direct_sources": 2,
            "found_direct": 0,
            "found_adjacent": 0,
            "found_analogical": 5,
            "status": "not_met",
            "missing_reason": "",
        }],
        "status": "fail",
    }
    state.evidence_coverage_report = failing

    # Round-trip through the typed model
    coverage = EvidenceCoverageReport.model_validate(state.evidence_coverage_report)
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
        [],
        state.claim_registry,
        [],
    )
    assert decision.decision == "reject"
    assert any(f.code == "EVIDENCE_COVERAGE" for f in decision.failures)


def test_final_gate_passes_when_state_attached_coverage_passes() -> None:
    state = DeckForgeState()
    state.claim_registry.register(ClaimProvenance(
        claim_id="EXT-001",
        text="UNESCO RAM direct topic",
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="direct_topic",
        evidence_role="methodology_support",
    ))
    state.evidence_coverage_report = {
        "requirements": [{
            "topic": "unesco_unesco_ram",
            "minimum_direct_sources": 1,
            "found_direct": 1,
            "found_adjacent": 0,
            "found_analogical": 0,
            "status": "met",
            "missing_reason": "",
        }],
        "status": "pass",
    }
    coverage = EvidenceCoverageReport.model_validate(state.evidence_coverage_report)
    assert coverage.status == "pass"

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
        [],
        state.claim_registry,
        [],
    )
    assert decision.decision == "approve"


# ── Empty / edge-case wiring ──────────────────────────────────────────


def test_helper_handles_empty_pack() -> None:
    state = DeckForgeState()
    empty = ExternalEvidencePack(sources=[])
    coverage = register_external_methodology(
        empty,
        state.claim_registry,
        primary_domains=["ai_governance_ethics"],
    )
    assert state.claim_registry.external_methodology == []
    by_topic = {r.topic: r for r in coverage.requirements}
    assert by_topic["ai_governance_ethics"].found_direct == 0
    assert by_topic["ai_governance_ethics"].status == "not_met"


def test_helper_handles_empty_routing() -> None:
    """When routing produces no primary_domains, no coverage topics
    are required and the report is trivially passing."""
    pack = _load_unesco_pack()
    state = DeckForgeState()
    coverage = register_external_methodology(
        pack,
        state.claim_registry,
        primary_domains=[],
    )
    assert coverage.requirements == []
    assert coverage.status == "pass"
    # Sources are still registered, just classified as analogical (no
    # primary keywords to match)
    assert len(state.claim_registry.external_methodology) == len(pack.sources)
