"""Pipeline wiring for generated_inference services — Slice 5.5.

The Slice-5 services (portal guard, deliverable classifier, source-
hierarchy resolver) are useful only if they fire during the actual
pipeline. This file exercises three wiring helpers and the
``context_node`` integration that runs them after RFP extraction.

Acceptance:
  * portal — never promoted from logo/header/footer/template-authority
    brands; explicit body/table mention becomes an rfp_fact; inferred
    placeholder becomes a labelled generated_inference with limited
    context (internal_bid_notes only) so it never reaches client text;
  * deliverables — boq_line / deliverables_annex stay formal D-* with
    pricing flags; scope_clause / special_condition normalize to
    workstream prefixes (TRAIN-N / KT-N / GOV-N / MGMT-N / WS-N) and
    register a generated_inference noting the reclassification;
  * source-hierarchy — unresolved field conflicts register a
    generated_inference with requires_clarification=True and
    restricted external usage;
  * Pass 7 fed by the post-wiring state still rejects unlabelled or
    wrong-context inferences;
  * generated_inference claims still never pass can_use_as_proof_point;
  * the wiring touches only the generated_inference bucket — RFP
    facts, internal claims, external methodology, and proposal options
    pass through unchanged.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.source_book.conformance_validator import validate_conformance
from src.agents.source_book.orchestrator import should_accept_source_book
from src.models.claim_provenance import (
    ClaimProvenance,
    ClaimRegistry,
    ProposalOption,
    ProposalOptionRegistry,
)
from src.models.common import BilingualText
from src.models.rfp import (
    Deliverable,
    RFPContext,
)
from src.models.source_book import (
    ProposedSolution,
    RFPInterpretation,
    SourceBook,
    SourceBookReview,
)
from src.models.state import DeckForgeState
from src.services.artifact_gates import can_use_as_proof_point
from src.services.inference_pipeline_wiring import (
    classify_extracted_deliverables,
    register_portal_inference,
    resolve_extracted_field_conflicts,
    wire_generated_inferences,
)
from src.services.portal_inference_guard import ExtractedTextSpan
from src.services.source_hierarchy_conflict import resolve_source_conflict


def _patch_pass3():
    return patch(
        "src.agents.source_book.conformance_validator._pass3_semantic_checks",
        AsyncMock(return_value=[]),
    )


def _empty_rfp() -> RFPContext:
    return RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )


# ── Portal wiring ─────────────────────────────────────────────────────


def test_portal_explicit_body_clause_becomes_rfp_fact() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    register_portal_inference(state, spans=[
        ExtractedTextSpan(
            text="Submit your offer through منصة اعتماد by 2026-05-15.",
            region_type="body",
        ),
    ])
    rfp_portal = [
        c for c in state.claim_registry.rfp_facts
        if "اعتماد" in c.text or "Etimad" in c.text or "portal" in c.text.lower()
    ]
    assert rfp_portal, "Explicit Etimad body clause must register as rfp_fact"
    # No generated_inference for portal
    assert not any(
        "portal" in (c.text or "").lower()
        and c.claim_kind == "generated_inference"
        for c in state.claim_registry.generated_inferences
    )


def test_portal_logo_only_does_not_become_rfp_fact() -> None:
    """Etimad in a logo region must never produce an rfp_fact for the
    portal — it produces a generated_inference for transparency."""
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    register_portal_inference(state, spans=[
        ExtractedTextSpan(text="Etimad", region_type="logo"),
    ])
    rfp_portal = [
        c for c in state.claim_registry.rfp_facts
        if c.text.lower().startswith("portal:")
    ]
    assert rfp_portal == []
    # Generated inference instead, with restricted context
    inf = [
        c for c in state.claim_registry.generated_inferences
        if "portal" in (c.text or "").lower()
    ]
    assert inf, "Inferred-from-logo portal must register a generated_inference"
    assert inf[0].inference_label_present is True
    assert "source_book_analysis" not in inf[0].inference_allowed_context
    assert "slide_blueprint" not in inf[0].inference_allowed_context
    assert "internal_bid_notes" in inf[0].inference_allowed_context


def test_portal_template_brand_in_logo_does_not_become_portal() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    register_portal_inference(state, spans=[
        ExtractedTextSpan(text="EXPRO", region_type="logo"),
    ])
    # No rfp_fact, no generated_inference suggesting EXPRO is the portal
    portal_facts = [
        c for c in state.claim_registry.rfp_facts
        if "EXPRO" in c.text
    ]
    portal_inferences = [
        c for c in state.claim_registry.generated_inferences
        if "EXPRO" in c.text
    ]
    assert portal_facts == []
    assert portal_inferences == []


def test_portal_template_brand_in_body_does_not_become_portal() -> None:
    """Even body presence of EXPRO/NUPCO must not name a portal."""
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    register_portal_inference(state, spans=[
        ExtractedTextSpan(
            text="The procurement is published under the EXPRO framework.",
            region_type="body",
        ),
    ])
    rfp_portal = [
        c for c in state.claim_registry.rfp_facts
        if "EXPRO" in c.text and c.text.lower().startswith("portal:")
    ]
    assert rfp_portal == []


def test_portal_no_signal_yields_default_inference() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    register_portal_inference(state, spans=[
        ExtractedTextSpan(text="Generic prose nothing portal.", region_type="body"),
    ])
    inf = [
        c for c in state.claim_registry.generated_inferences
        if "portal" in (c.text or "").lower()
    ]
    assert inf
    assert inf[0].inference_label_present is True


# ── Deliverable wiring ───────────────────────────────────────────────


def test_deliverable_boq_origin_stays_formal_d_id() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    state.rfp_context.deliverables = [
        Deliverable(
            id="D-1",
            description=BilingualText(en="Investment Promotion Strategy Report", ar=""),
        ),
    ]
    classify_extracted_deliverables(
        state,
        origins={"D-1": "boq_line"},
    )
    delivs = [
        c for c in state.claim_registry.rfp_facts
        if c.claim_id.startswith("RFP-FACT-DELIV-D-1")
    ]
    assert delivs
    c = delivs[0]
    assert c.deliverable_origin == "boq_line"
    assert c.formal_deliverable is True
    assert c.pricing_line_item is True


def test_deliverable_scope_clause_normalized_and_inferred() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    state.rfp_context.deliverables = [
        Deliverable(
            id="D-3",
            description=BilingualText(
                en="Training and knowledge transfer", ar="",
            ),
        ),
    ]
    classify_extracted_deliverables(
        state,
        origins={"D-3": "scope_clause"},
    )
    # The original D-3 rfp_fact must be replaced by a workstream id
    delivs = [
        c for c in state.claim_registry.rfp_facts
        if c.claim_id.startswith("RFP-FACT-DELIV-")
    ]
    assert delivs
    workstream = delivs[0]
    # New id no longer D-* — workstream prefix
    assert "D-3" not in workstream.claim_id
    assert workstream.formal_deliverable is False
    assert workstream.cross_cutting_workstream is True
    # And a generated_inference noting the reclassification
    inf = [
        c for c in state.claim_registry.generated_inferences
        if "D-3" in c.text and "normalized" in c.text.lower()
    ]
    assert inf, "Reclassification must register a generated_inference"
    assert inf[0].inference_label_present is True


def test_deliverable_special_condition_workstream_governance() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    state.rfp_context.deliverables = [
        Deliverable(
            id="D-9",
            description=BilingualText(en="Governance committee charter", ar=""),
        ),
    ]
    classify_extracted_deliverables(
        state,
        origins={"D-9": "special_condition"},
    )
    delivs = [
        c for c in state.claim_registry.rfp_facts
        if c.claim_id.startswith("RFP-FACT-DELIV-")
    ]
    assert any("GOV-9" in c.claim_id for c in delivs)


def test_deliverable_default_origin_is_annex_when_not_specified() -> None:
    """When the caller does not specify an origin, we default to
    deliverables_annex (formal). This preserves Slice-1.5 behavior for
    callers that haven't yet adopted explicit origin tagging."""
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    state.rfp_context.deliverables = [
        Deliverable(
            id="D-7",
            description=BilingualText(en="Final report", ar=""),
        ),
    ]
    classify_extracted_deliverables(state, origins={})
    delivs = [
        c for c in state.claim_registry.rfp_facts
        if c.claim_id.startswith("RFP-FACT-DELIV-")
    ]
    assert delivs and delivs[0].deliverable_origin == "deliverables_annex"
    assert delivs[0].formal_deliverable is True


# ── Source-hierarchy conflict wiring ─────────────────────────────────


def test_unresolved_conflict_creates_clarification_inference() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    conflict = resolve_source_conflict(
        field="award_mechanism",
        value_a="A",
        source_a="random_email_thread",
        value_b="B",
        source_b="phone_call_notes",
    )
    assert conflict.requires_clarification is True
    resolve_extracted_field_conflicts(state, conflicts=[conflict])
    inf = state.claim_registry.generated_inferences
    assert inf
    note = inf[0]
    assert note.requires_clarification is True
    # Limited contexts: never source_book_analysis / slide_blueprint
    assert "source_book_analysis" not in note.inference_allowed_context
    assert "slide_blueprint" not in note.inference_allowed_context
    assert note.inference_label_present is True


def test_resolved_conflict_does_not_create_inference() -> None:
    """When the resolver decides cleanly (one source wins), no
    clarification inference is created."""
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    conflict = resolve_source_conflict(
        field="award_mechanism",
        value_a="pass_fail",
        source_a="evaluation_criteria_sheet",
        value_b="weighted",
        source_b="rfp_booklet",
    )
    assert conflict.requires_clarification is False
    resolve_extracted_field_conflicts(state, conflicts=[conflict])
    assert state.claim_registry.generated_inferences == []


def test_no_conflicts_no_inferences() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    resolve_extracted_field_conflicts(state, conflicts=[])
    assert state.claim_registry.generated_inferences == []


# ── Combined wiring helper ───────────────────────────────────────────


def test_wire_generated_inferences_runs_all_three_helpers() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    state.rfp_context.deliverables = [
        Deliverable(id="D-3", description=BilingualText(
            en="Training and knowledge transfer", ar="",
        )),
    ]
    wire_generated_inferences(
        state,
        portal_spans=[ExtractedTextSpan(text="EXPRO", region_type="logo")],
        deliverable_origins={"D-3": "scope_clause"},
        conflicts=[resolve_source_conflict(
            field="not_known",
            value_a="A", source_a="x",
            value_b="B", source_b="y",
        )],
    )
    # All three signals present
    inferences = state.claim_registry.generated_inferences
    kinds = {
        "portal": any("portal" in c.text.lower() for c in inferences),
        "deliverable": any("normalized" in c.text.lower() for c in inferences),
        "conflict": any("clarification" in c.text.lower() for c in inferences),
    }
    assert all(kinds.values()), f"missing inference signals: {kinds}"


# ── Pipeline node integration ────────────────────────────────────────


@pytest.mark.asyncio
async def test_context_node_runs_inference_wiring() -> None:
    """context_node, after RFP extraction, calls wire_generated_inferences
    when the state carries the right extras (portal_spans, deliverable
    origins, conflict candidates). The agent is mocked so no LLM runs."""
    from src.pipeline import graph as pipeline_graph

    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    state.rfp_context.deliverables = [
        Deliverable(id="D-3", description=BilingualText(
            en="Training and knowledge transfer", ar="",
        )),
    ]
    # Pre-stash the wiring inputs onto state via attribute-like dict —
    # the node honors them through `state.pipeline_extras` when present.
    state.pipeline_extras = {
        "portal_spans": [
            ExtractedTextSpan(text="EXPRO", region_type="logo"),
        ],
        "deliverable_origins": {"D-3": "scope_clause"},
        "conflicts": [],
    }

    class _Result:
        rfp_context = state.rfp_context
        current_stage = state.current_stage
        session = state.session
        errors: list = []
        last_error = None

    async def _fake_context_run(_state):
        return _Result()

    async def _fake_extract_hard_reqs(*_a, **_kw):
        return []

    with patch(
        "src.agents.context.agent.run", _fake_context_run,
    ), patch(
        "src.services.hard_requirement_extractor.extract_hard_requirements",
        _fake_extract_hard_reqs,
    ):
        updates = await pipeline_graph.context_node(state)

    registry = updates.get("claim_registry")
    assert registry is not None
    inferences = registry.generated_inferences
    assert any("portal" in c.text.lower() for c in inferences)


# ── Pass 7 against pipeline-populated state ──────────────────────────


@pytest.mark.asyncio
async def test_pass7_rejects_pipeline_populated_unlabelled_inference() -> None:
    """Force-create an unlabelled inference via the wiring path
    (simulate a buggy bid team that blanked the label), feed the
    pipeline-populated registry to validate_conformance, assert
    Pass 7 fires."""
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    register_portal_inference(state, spans=[
        ExtractedTextSpan(text="Etimad", region_type="logo"),
    ])
    portal_inf = state.claim_registry.generated_inferences[0]
    # Strip the label that the helper added — simulate downstream
    # tampering that should be caught by Pass 7.
    state.claim_registry.register(ClaimProvenance(
        claim_id=portal_inf.claim_id,
        text=portal_inf.text,
        claim_kind="generated_inference",
        source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=False,
        inference_allowed_context=[],
    ))
    # Place the inference text into a client-facing section
    sb = SourceBook(
        rfp_name="X", client_name="X",
        rfp_interpretation=RFPInterpretation(
            objective_and_scope=portal_inf.text,
        ),
    )
    rfp = _empty_rfp()
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=rfp,
            uploaded_documents=[],
            claim_registry=state.claim_registry,
        )
    assert any(
        f.requirement_id == "UNLABELLED_INFERENCE"
        for f in report.forbidden_claims
    )
    assert report.conformance_status == "fail"
    assert should_accept_source_book(
        SourceBookReview(
            overall_score=4,
            pass_threshold_met=True,
            competitive_viability="adequate",
        ),
        report,
    ) is False


@pytest.mark.asyncio
async def test_pass7_passes_pipeline_populated_labelled_inference_in_correct_context() -> None:
    """An inference produced by the wiring helper has
    inference_allowed_context=["internal_bid_notes"]. If its text appears
    only in an internal section, Pass 7 does not flag."""
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    register_portal_inference(state, spans=[
        ExtractedTextSpan(text="Etimad", region_type="logo"),
    ])
    inf_text = state.claim_registry.generated_inferences[0].text

    from src.models.source_book import EvidenceLedger, EvidenceLedgerEntry

    sb = SourceBook(
        rfp_name="X", client_name="X",
        evidence_ledger=EvidenceLedger(entries=[
            EvidenceLedgerEntry(
                claim_id="CLM-1",
                claim_text=inf_text,
                source_type="internal",
            ),
        ]),
    )
    rfp = _empty_rfp()
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=rfp,
            uploaded_documents=[],
            claim_registry=state.claim_registry,
        )
    assert not any(
        f.requirement_id == "UNLABELLED_INFERENCE"
        for f in report.forbidden_claims
    )


# ── Bucket isolation ─────────────────────────────────────────────────


def test_wiring_does_not_mutate_other_claim_kinds() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    state.claim_registry.register(ClaimProvenance(
        claim_id="RFP-FACT-PRE", text="x",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    state.claim_registry.register(ClaimProvenance(
        claim_id="BIDDER-PRE", text="x",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_unverified",
    ))
    state.claim_registry.register(ClaimProvenance(
        claim_id="EXT-PRE", text="x",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
    ))
    state.proposal_options.register(ProposalOption(
        option_id="OPT-PRE", text="x",
        claim_provenance_id="OPT-PRE",
        category="numeric_range",
    ))
    state.claim_registry.register(ClaimProvenance(
        claim_id="OPT-PRE", text="x",
        claim_kind="proposal_option", source_kind="model_generated",
        verification_status="proposal_option",
    ))

    wire_generated_inferences(
        state,
        portal_spans=[ExtractedTextSpan(text="EXPRO", region_type="logo")],
        deliverable_origins={},
        conflicts=[],
    )

    # Pre-existing buckets unchanged
    assert {c.claim_id for c in state.claim_registry.rfp_facts} == {"RFP-FACT-PRE"}
    assert {c.claim_id for c in state.claim_registry.bidder_claims} == {"BIDDER-PRE"}
    assert {c.claim_id for c in state.claim_registry.external_methodology} == {"EXT-PRE"}
    assert {c.claim_id for c in state.claim_registry.proposal_options} == {"OPT-PRE"}


# ── Acceptance #2 still holds ────────────────────────────────────────


def test_pipeline_inference_never_proof_point() -> None:
    state = DeckForgeState()
    state.rfp_context = _empty_rfp()
    register_portal_inference(state, spans=[
        ExtractedTextSpan(text="Etimad", region_type="logo"),
    ])
    for c in state.claim_registry.generated_inferences:
        assert can_use_as_proof_point(c) is False
