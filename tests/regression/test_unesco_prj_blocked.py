"""UNESCO regression — PRJ-001 / CLI- / CLM- blocked from client-facing content.

Slice 2.4: prove that the new pipeline logic (Pass 5 leakage scanner +
slide proof-point gating) blocks the leakage that exists in the frozen
UNESCO fixture. Tests work strictly against frozen artifacts — no fresh
pipeline run.

Two channels are exercised:
  1. Source Book body text → render_source_book_sections → Pass 5 scanner
     produces FORBIDDEN-LEAKAGE failures with PRJ-001.
  2. Slide blueprints (UNESCO frozen) → gate_slide_proof_points with an
     empty registry → PRJ-001 / CLI- / CLM- proof references are dropped.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.source_book.conformance_validator import validate_conformance
from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.common import BilingualText
from src.models.rfp import RFPContext
from src.models.source_book import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    RFPInterpretation,
    SlideBlueprintEntry,
    SourceBook,
)
from src.services.artifact_gates import gate_slide_proof_points

from tests.fixtures.fixture_loader import load_docx_text


_UNESCO = "sb-ar-1777280086"


def _patch_pass3():
    return patch(
        "src.agents.source_book.conformance_validator._pass3_semantic_checks",
        AsyncMock(return_value=[]),
    )


def _minimal_rfp() -> RFPContext:
    return RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )


def _load_unesco_blueprints_as_entries() -> list[SlideBlueprintEntry]:
    """Adapt the frozen blueprint JSON (which uses evidence_ids /
    bullet_points / slide_title fields) into SlideBlueprintEntry by
    mapping evidence_ids → proof_points + must_have_evidence."""
    raw = json.loads(
        Path(f"tests/fixtures/{_UNESCO}/slide_blueprint_from_source_book.json").read_text(
            encoding="utf-8"
        )
    )
    entries: list[SlideBlueprintEntry] = []
    for i, item in enumerate(raw):
        evidence_ids = item.get("evidence_ids") or []
        entries.append(SlideBlueprintEntry(
            slide_number=i + 1,
            section=item.get("section_id") or "",
            title=item.get("slide_title") or "",
            key_message=item.get("key_message") or "",
            bullet_logic=item.get("bullet_points") or [],
            proof_points=list(evidence_ids),
            must_have_evidence=list(evidence_ids),
            visual_guidance=item.get("visual_guidance") or "",
        ))
    return entries


# ── (1) Source Book body — Pass 5 catches PRJ-001 ──────────────────────


@pytest.mark.asyncio
async def test_unesco_docx_text_in_client_body_flagged_by_pass5() -> None:
    """The frozen UNESCO source_book.docx contains 'PRJ-001'. When that
    text is rendered into a client-facing SourceBook section and run
    through the new validator, Pass 5 produces FORBIDDEN-LEAKAGE."""
    docx_text = load_docx_text(_UNESCO)
    assert "PRJ-001" in docx_text, "Fixture invariant: PRJ-001 must be present"

    sb = SourceBook(
        rfp_name="UNESCO",
        client_name="UNESCO",
        rfp_interpretation=RFPInterpretation(
            # Use the leaking sentence directly so the scan target is
            # explicit. The full docx is too large to embed here, but
            # the fixture text is the same source.
            objective_and_scope=docx_text,
        ),
    )

    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )

    leakage_failures = [
        f for f in report.forbidden_claims
        if f.requirement_id == "FORBIDDEN-LEAKAGE"
    ]
    assert len(leakage_failures) >= 1
    assert any("PRJ-001" in f.failure_reason for f in leakage_failures), (
        f"PRJ-001 must be flagged in client-facing body; "
        f"failures={[f.failure_reason[:80] for f in leakage_failures]}"
    )


@pytest.mark.asyncio
async def test_unesco_prj_in_evidence_ledger_is_internal_and_exempt() -> None:
    """PRJ-001 is permitted in the evidence_ledger / internal_gap_appendix
    sections. The scanner exempts them per design Section 3."""
    sb = SourceBook(
        rfp_name="UNESCO",
        client_name="UNESCO",
        evidence_ledger=EvidenceLedger(
            entries=[
                EvidenceLedgerEntry(
                    claim_id="PRJ-001",
                    claim_text="prior SDAIA project — Engine 2 verification required",
                    source_type="internal",
                ),
            ],
        ),
    )
    with _patch_pass3():
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[],
            rfp_context=_minimal_rfp(),
            uploaded_documents=[],
        )
    leakage_failures = [
        f for f in report.forbidden_claims
        if f.requirement_id == "FORBIDDEN-LEAKAGE"
    ]
    assert leakage_failures == []


# ── (2) Slide blueprints — gate_slide_proof_points drops PRJ ──────────


def test_unesco_blueprints_prj_dropped_from_proof_points() -> None:
    blueprints = _load_unesco_blueprints_as_entries()
    # Confirm the fixture invariant: at least one blueprint references PRJ-001
    has_prj = any(
        any(re.search(r"\bPRJ-\d+\b", p) for p in bp.proof_points)
        for bp in blueprints
    )
    assert has_prj, "Fixture invariant: PRJ-001 must be in some proof_points"

    # Empty registry → every PRJ/CLI/CLM is unresolved and must be dropped.
    registry = ClaimRegistry()
    gated, violations = gate_slide_proof_points(blueprints, registry)

    surviving_prj = [
        v
        for bp in gated
        for v in (bp.proof_points + bp.must_have_evidence)
        if re.search(r"\b(PRJ|CLI|CLM)-\d+\b", v)
    ]
    assert surviving_prj == [], (
        f"Internal-claim identifiers must not survive gating: {surviving_prj[:5]}"
    )

    # And the gating helper must have reported them as violations
    assert any(
        re.search(r"\b(PRJ|CLI|CLM)-\d+\b", v.proof_point) for v in violations
    )


def test_unesco_blueprints_with_verified_external_keep_ext_drop_prj() -> None:
    """When EXT-* are registered as verified external_methodology and
    PRJ-* are NOT registered (or are unverified), only EXT-* survive."""
    blueprints = _load_unesco_blueprints_as_entries()
    registry = ClaimRegistry()
    # Inject every distinct EXT-* id from the fixture as a verified
    # external_methodology claim with the proof-point-allowed evidence_role.
    seen_ext: set[str] = set()
    for bp in blueprints:
        for p in bp.proof_points:
            if re.match(r"^EXT-\d+$", p):
                seen_ext.add(p)
    for ext_id in seen_ext:
        registry.register(ClaimProvenance(
            claim_id=ext_id,
            text=ext_id,
            claim_kind="external_methodology",
            source_kind="external_source",
            verification_status="externally_verified",
            relevance_class="direct_topic",
            evidence_role="methodology_support",
        ))

    gated, violations = gate_slide_proof_points(blueprints, registry)

    # EXT-* survive
    surviving_ids = {
        p
        for bp in gated
        for p in bp.proof_points
        if re.match(r"^[A-Z]+-\d+$", p)
    }
    assert seen_ext.issubset(surviving_ids), (
        f"Verified EXT- ids should survive; missing={seen_ext - surviving_ids}"
    )

    # No PRJ / CLI / CLM survive
    forbidden_survivors = {
        p for p in surviving_ids if re.match(r"^(PRJ|CLI|CLM)-", p)
    }
    assert forbidden_survivors == set()


def test_unesco_blueprints_prj_survives_only_when_registry_has_verified_internal() -> None:
    """Sanity check: if PRJ-001 IS registered as a verified+permissioned
    internal claim, the gate keeps it. This guards against the fix being
    too aggressive (false-positive blocking)."""
    blueprints = _load_unesco_blueprints_as_entries()
    registry = ClaimRegistry()
    registry.register(ClaimProvenance(
        claim_id="PRJ-001",
        text="prior SDAIA program",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_verified",
        evidence_role="bidder_capability_proof",
        requires_client_naming_permission=True,
        client_naming_permission=True,
        scope_summary_allowed_for_proposal=True,
    ))
    gated, _violations = gate_slide_proof_points(blueprints, registry)

    survives = any(
        "PRJ-001" in (bp.proof_points + bp.must_have_evidence)
        for bp in gated
    )
    assert survives, (
        "Verified+permissioned PRJ-001 must survive the gate — the fix "
        "is targeted at unverified PRJ leakage, not all PRJ references."
    )
