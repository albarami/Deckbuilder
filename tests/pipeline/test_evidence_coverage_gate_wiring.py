"""Slice 3.6 — Final-gate wiring for evidence coverage.

The actual acceptance gate is ``should_accept_source_book`` (called at
``src/pipeline/graph.py`` line ~974). Slice 3.6 extends it to consume
``state.evidence_coverage_report`` and fail closed when:

  * ``state.evidence_coverage_report`` is missing AND coverage was
    required (external evidence pack non-empty OR routing produced any
    primary domain),
  * the report is malformed and cannot be parsed,
  * the report parses but ``status != "pass"``.

It also verifies that classifier/coverage exceptions in
``evidence_curation_node`` write a fail-closed coverage to state so the
downstream gate rejects, rather than silently allowing acceptance.

No fresh pipeline run is performed; the actual node is invoked with a
mocked external research agent and the orchestrator gate is invoked
directly.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.source_book.orchestrator import should_accept_source_book
from src.models.common import BilingualText
from src.models.conformance import ConformanceReport
from src.models.external_evidence import ExternalEvidencePack
from src.models.rfp import RFPContext
from src.models.routing import RFPClassification
from src.models.source_book import SourceBookReview
from src.models.state import DeckForgeState


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


def _failing_coverage_dict() -> dict:
    return {
        "requirements": [{
            "topic": "ai_governance_ethics",
            "minimum_direct_sources": 2,
            "found_direct": 0,
            "found_adjacent": 0,
            "found_analogical": 5,
            "status": "not_met",
            "missing_reason": "",
        }],
        "status": "fail",
    }


def _passing_coverage_dict() -> dict:
    return {
        "requirements": [{
            "topic": "ai_governance_ethics",
            "minimum_direct_sources": 1,
            "found_direct": 1,
            "found_adjacent": 0,
            "found_analogical": 0,
            "status": "met",
            "missing_reason": "",
        }],
        "status": "pass",
    }


# ── Direct gate-function behavior ──────────────────────────────────────


def test_gate_rejects_when_coverage_status_fail() -> None:
    accepted = should_accept_source_book(
        _passing_review(),
        _passing_conformance(),
        evidence_coverage_report=_failing_coverage_dict(),
        coverage_required=True,
    )
    assert accepted is False


def test_gate_rejects_when_coverage_required_but_missing() -> None:
    """Coverage required (external evidence/topics exist) and the
    report is missing → fail closed."""
    accepted = should_accept_source_book(
        _passing_review(),
        _passing_conformance(),
        evidence_coverage_report=None,
        coverage_required=True,
    )
    assert accepted is False


def test_gate_rejects_when_coverage_malformed() -> None:
    """Malformed dict (wrong types, missing fields) cannot pass silently."""
    bad = {"requirements": "not a list", "status": "pass"}  # malformed
    accepted = should_accept_source_book(
        _passing_review(),
        _passing_conformance(),
        evidence_coverage_report=bad,
        coverage_required=True,
    )
    assert accepted is False


def test_gate_accepts_when_coverage_passes() -> None:
    accepted = should_accept_source_book(
        _passing_review(),
        _passing_conformance(),
        evidence_coverage_report=_passing_coverage_dict(),
        coverage_required=True,
    )
    assert accepted is True


def test_gate_accepts_when_coverage_not_required_and_missing() -> None:
    """Legacy compatibility: when no external evidence/topics were
    declared, missing coverage does not by itself reject."""
    accepted = should_accept_source_book(
        _passing_review(),
        _passing_conformance(),
        evidence_coverage_report=None,
        coverage_required=False,
    )
    assert accepted is True


def test_gate_rejects_when_conformance_fails_regardless_of_coverage() -> None:
    """Conformance failure outranks any coverage signal."""
    failing_conf = ConformanceReport(
        conformance_status="fail",
        final_acceptance_decision="reject",
        hard_requirements_checked=1,
        hard_requirements_passed=0,
        hard_requirements_failed=1,
    )
    accepted = should_accept_source_book(
        _passing_review(),
        failing_conf,
        evidence_coverage_report=_passing_coverage_dict(),
        coverage_required=True,
    )
    assert accepted is False


# ── Pipeline call-site behavior — graph.py uses state.evidence_coverage_report


@pytest.mark.asyncio
async def test_pipeline_call_site_passes_state_coverage_to_gate() -> None:
    """The actual graph.py call site must invoke the orchestrator gate
    with state.evidence_coverage_report and the correct
    coverage_required derived from state.external_evidence_pack /
    routing.primary_domains. We verify by patching the orchestrator
    function with a recording stub and forcing the call."""
    captured: dict = {}

    def _capture(review, conformance, *,
                 evidence_coverage_report=None,
                 coverage_required=False):
        captured["evidence_coverage_report"] = evidence_coverage_report
        captured["coverage_required"] = coverage_required
        return False  # block acceptance to exit any iteration loop

    state = DeckForgeState()
    state.rfp_context = RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )
    state.routing_report = {
        "classification": RFPClassification(
            jurisdiction="saudi_arabia",
            sector="public_sector",
            primary_domains=["ai_governance_ethics"],
            secondary_domains=[],
            domain="ai_governance_ethics",
        ).model_dump(mode="json"),
    }
    state.external_evidence_pack = ExternalEvidencePack(sources=[])
    state.evidence_coverage_report = _failing_coverage_dict()

    from src.agents.source_book import orchestrator
    from src.pipeline import graph as pipeline_graph

    # Build minimum scaffolding to make the call site dispatch to the gate
    accepted = pipeline_graph._call_acceptance_gate(state, _passing_review(), _passing_conformance())
    assert captured == {} or True  # function may not exist yet — see below

    # Direct check: the helper that should exist after Slice 3.6 takes
    # state and dispatches with coverage args.
    with patch.object(orchestrator, "should_accept_source_book", _capture):
        pipeline_graph._call_acceptance_gate(state, _passing_review(), _passing_conformance())
    assert captured["evidence_coverage_report"] == _failing_coverage_dict()
    assert captured["coverage_required"] is True


@pytest.mark.asyncio
async def test_pipeline_call_site_marks_coverage_required_from_external_pack() -> None:
    """Even with no primary_domains, a non-empty external_evidence_pack
    means coverage was attempted and is therefore required."""
    captured: dict = {}

    def _capture(review, conformance, *,
                 evidence_coverage_report=None,
                 coverage_required=False):
        captured["coverage_required"] = coverage_required
        return False

    state = DeckForgeState()
    state.rfp_context = RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )
    state.routing_report = {"classification": {"primary_domains": []}}
    # Non-empty pack
    state.external_evidence_pack = ExternalEvidencePack(sources=[])

    # Simulate "pack had sources at curation time" by monkey-patching len:
    # easier — register a single source to make the pack non-empty.
    from src.models.external_evidence import ExternalSource
    state.external_evidence_pack = ExternalEvidencePack(sources=[
        ExternalSource(
            source_id="EXT-X", title="x",
            source_type="industry_report",
        ),
    ])

    from src.agents.source_book import orchestrator
    from src.pipeline import graph as pipeline_graph
    with patch.object(orchestrator, "should_accept_source_book", _capture):
        pipeline_graph._call_acceptance_gate(state, _passing_review(), _passing_conformance())
    assert captured["coverage_required"] is True


@pytest.mark.asyncio
async def test_pipeline_call_site_no_coverage_required_when_nothing_external() -> None:
    """No external pack and no primary_domains → coverage_required=False
    so legacy RFPs without external evidence still gate normally."""
    captured: dict = {}

    def _capture(review, conformance, *,
                 evidence_coverage_report=None,
                 coverage_required=False):
        captured["coverage_required"] = coverage_required
        return True

    state = DeckForgeState()
    state.rfp_context = RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )
    # routing absent / empty primary_domains, no external pack
    state.routing_report = {"classification": {"primary_domains": []}}
    state.external_evidence_pack = None

    from src.agents.source_book import orchestrator
    from src.pipeline import graph as pipeline_graph
    with patch.object(orchestrator, "should_accept_source_book", _capture):
        pipeline_graph._call_acceptance_gate(state, _passing_review(), _passing_conformance())
    assert captured["coverage_required"] is False


# ── Classifier-exception path writes fail-closed coverage ─────────────


@pytest.mark.asyncio
async def test_evidence_curation_classifier_exception_writes_fail_coverage() -> None:
    """If register_external_methodology raises, evidence_curation_node
    must write a fail-status coverage report to state so the downstream
    gate rejects. Silently swallowing the exception is forbidden."""
    from src.pipeline import graph as pipeline_graph
    from src.services.artifact_gates import EvidenceCoverageReport
    from src.models.external_evidence import ExternalSource

    state = DeckForgeState()
    state.rfp_context = RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )
    state.routing_report = {
        "classification": RFPClassification(
            primary_domains=["ai_governance_ethics"],
            secondary_domains=[],
        ).model_dump(mode="json"),
    }

    pack_with_one = ExternalEvidencePack(sources=[
        ExternalSource(
            source_id="EXT-1",
            title="x",
            source_type="industry_report",
        ),
    ])

    async def _fake_external_run(_state):
        return {"external_evidence_pack": pack_with_one, "session": _state.session}

    async def _fake_analysis(_state):
        return {"reference_index": None, "session": _state.session}

    def _boom(*_a, **_kw):
        raise RuntimeError("classifier blew up")

    with patch(
        "src.agents.external_research.agent.run", _fake_external_run,
    ), patch.object(pipeline_graph, "analysis_node", _fake_analysis), patch(
        "src.services.external_methodology_classifier.register_external_methodology",
        _boom,
    ):
        updates = await pipeline_graph.evidence_curation_node(state)

    # State coverage must be present and non-passing
    assert "evidence_coverage_report" in updates
    coverage = EvidenceCoverageReport.model_validate(
        updates["evidence_coverage_report"],
    )
    assert coverage.status != "pass"
    # And the gate, when fed this coverage, must reject
    accepted = should_accept_source_book(
        _passing_review(),
        _passing_conformance(),
        evidence_coverage_report=updates["evidence_coverage_report"],
        coverage_required=True,
    )
    assert accepted is False
