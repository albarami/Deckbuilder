"""Numeric commitment detector — Slice 4.2.

Scans client-facing ArtifactSection text for numeric ranges (and
singletons attached to scope-shaping nouns) and resolves each detected
commitment against the ClaimRegistry + ProposalOptionRegistry.

Resolution rules:
  * an RFP fact whose text contains the canonical numeric form → "rfp_fact"
  * an approved ProposalOption whose claim's text contains the canonical
    form → "approved_option"
  * everything else → "unresolved"

Internal-only sections (internal_gap_appendix, internal_bid_notes,
evidence_ledger, drafting_notes) are not scanned because numeric
commitments there are not addressed to the client.
"""
from __future__ import annotations

from src.models.claim_provenance import (
    ClaimProvenance,
    ClaimRegistry,
    ProposalOption,
    ProposalOptionRegistry,
)
from src.services.artifact_gates import ArtifactSection
from src.services.numeric_commitment_detector import (
    NumericCommitment,
    detect_numeric_commitments,
)


def _section(text: str, *, kind: str = "client_facing_body") -> ArtifactSection:
    return ArtifactSection(
        section_path="x/y",
        section_type=kind,  # type: ignore[arg-type]
        text=text,
    )


def _rfp_fact(claim_id: str, text: str) -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    )


def _option_claim(claim_id: str = "OPT-RANGE-001", text: str = "5-8 countries") -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="proposal_option",
        source_kind="model_generated",
        verification_status="proposal_option",
    )


def _approved_option(claim_id: str = "OPT-RANGE-001", text: str = "5-8 countries") -> ProposalOption:
    return ProposalOption(
        option_id=claim_id,
        text=text,
        claim_provenance_id=claim_id,
        category="numeric_range",
        approved_for_external_use=True,
        priced=True,
        approved_by="bid_director",
    )


def _unapproved_option(claim_id: str = "OPT-RANGE-002", text: str = "5-8 countries") -> ProposalOption:
    return ProposalOption(
        option_id=claim_id,
        text=text,
        claim_provenance_id=claim_id,
        category="numeric_range",
        approved_for_external_use=False,
    )


# ── Range detection — ASCII digits ────────────────────────────────────


def test_ascii_range_with_hyphen_detected() -> None:
    sections = [_section("We will cover 5-8 countries in scope.")]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert len(found) == 1
    nc = found[0]
    assert nc.text.startswith("5-8") or nc.canonical == "5-8"
    assert nc.canonical == "5-8"
    assert nc.resolution == "unresolved"


def test_range_with_to_detected() -> None:
    sections = [_section("Engagement spans 5 to 8 weeks.")]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert any(nc.canonical == "5-8" for nc in found)


def test_range_with_endash_detected() -> None:
    sections = [_section("Cohort size 12–18 participants per session.")]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert any(nc.canonical == "12-18" for nc in found)


# ── Range detection — Arabic forms ────────────────────────────────────


def test_arabic_indic_range_detected() -> None:
    sections = [_section("نغطي ٥-٨ دول في النطاق.")]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert any(nc.canonical == "5-8" for nc in found)


def test_arabic_ila_separator_detected() -> None:
    sections = [_section("ندعم من ٥ إلى ٨ دول.")]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert any(nc.canonical == "5-8" for nc in found)


def test_arabic_hatta_separator_detected() -> None:
    sections = [_section("المدة ٦ حتى ٩ أشهر.")]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert any(nc.canonical == "6-9" for nc in found)


# ── Section scoping ───────────────────────────────────────────────────


def test_internal_only_sections_not_scanned() -> None:
    """Internal sections may carry options/commitments the bid team is
    still negotiating; they should not be flagged here."""
    sections = [
        _section("5-8 countries", kind="internal_bid_notes"),
        _section("5-8 countries", kind="internal_gap_appendix"),
        _section("5-8 countries", kind="evidence_ledger"),
        _section("5-8 countries", kind="drafting_notes"),
    ]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert found == []


def test_slide_body_and_proof_points_scanned() -> None:
    sections = [
        _section("5-8 countries", kind="slide_body"),
        _section("5-8 countries", kind="slide_proof_points"),
        _section("5-8 countries", kind="proof_column"),
    ]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert len(found) >= 3
    assert all(nc.canonical == "5-8" for nc in found)


# ── Resolution: rfp_fact wins ─────────────────────────────────────────


def test_resolves_to_rfp_fact() -> None:
    """Acceptance #3: numbers tied to an rfp_fact resolve cleanly."""
    reg = ClaimRegistry()
    reg.register(_rfp_fact("RFP-FACT-DUR", "Contract duration: 12 months"))
    sections = [_section("Engagement runs 12 months end to end.")]
    found = detect_numeric_commitments(
        sections, reg, ProposalOptionRegistry(),
    )
    rfp_resolutions = [nc for nc in found if nc.resolution == "rfp_fact"]
    assert any(nc.resolved_claim_id == "RFP-FACT-DUR" for nc in rfp_resolutions)


# ── Resolution: approved option wins ──────────────────────────────────


def test_resolves_to_approved_option() -> None:
    claim_reg = ClaimRegistry()
    claim_reg.register(_option_claim("OPT-RANGE-001", "Pilot scope: 5-8 countries"))
    opt_reg = ProposalOptionRegistry()
    opt_reg.register(_approved_option("OPT-RANGE-001", "Pilot scope: 5-8 countries"))
    sections = [_section("Pilot scope: 5-8 countries.")]
    found = detect_numeric_commitments(sections, claim_reg, opt_reg)
    approved = [nc for nc in found if nc.resolution == "approved_option"]
    assert approved
    assert approved[0].resolved_option_id == "OPT-RANGE-001"


def test_unapproved_option_does_not_resolve() -> None:
    """Acceptance #5: an option with approved_for_external_use=False
    cannot resolve a client-facing commitment."""
    claim_reg = ClaimRegistry()
    claim_reg.register(_option_claim("OPT-RANGE-002", "Pilot: 5-8 countries"))
    opt_reg = ProposalOptionRegistry()
    opt_reg.register(_unapproved_option("OPT-RANGE-002", "Pilot: 5-8 countries"))
    sections = [_section("Pilot: 5-8 countries.")]
    found = detect_numeric_commitments(sections, claim_reg, opt_reg)
    assert all(nc.resolution == "unresolved" for nc in found)


def test_priced_option_unapproved_still_blocked() -> None:
    """Pricing alone does not approve; client-facing use needs both
    priced=True AND approved_for_external_use=True (acceptance #5+#6)."""
    claim_reg = ClaimRegistry()
    claim_reg.register(_option_claim("OPT-PRICED", "5-8 countries"))
    opt_reg = ProposalOptionRegistry()
    opt_reg.register(ProposalOption(
        option_id="OPT-PRICED",
        text="5-8 countries",
        claim_provenance_id="OPT-PRICED",
        category="numeric_range",
        priced=True,
        approved_for_external_use=False,
    ))
    sections = [_section("5-8 countries.")]
    found = detect_numeric_commitments(sections, claim_reg, opt_reg)
    assert all(nc.resolution == "unresolved" for nc in found)


# ── Edge cases ────────────────────────────────────────────────────────


def test_no_numeric_content_yields_empty_list() -> None:
    sections = [_section("No numbers here, just prose.")]
    assert detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    ) == []


def test_multiple_commitments_in_same_section() -> None:
    sections = [_section("We propose 5-8 countries and 3-4 sectors.")]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    canonicals = {nc.canonical for nc in found}
    assert canonicals == {"5-8", "3-4"}


def test_dates_are_excluded() -> None:
    """Dates like 2024-2026 are commitments to a date range, but
    parsing them as numeric scope is noisy. Skip 4-digit ranges."""
    sections = [_section("Project runs 2024-2026 cycle.")]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    # Year ranges are not flagged as scope commitments
    assert not any(nc.canonical == "2024-2026" for nc in found)


def test_violation_carries_section_metadata() -> None:
    sections = [
        ArtifactSection(
            section_path="proposed_solution/methodology_overview",
            section_type="client_facing_body",
            text="Phased rollout across 5-8 countries.",
        ),
    ]
    found = detect_numeric_commitments(
        sections, ClaimRegistry(), ProposalOptionRegistry(),
    )
    assert isinstance(found[0], NumericCommitment)
    assert found[0].section_path == "proposed_solution/methodology_overview"
    assert found[0].section_type == "client_facing_body"
