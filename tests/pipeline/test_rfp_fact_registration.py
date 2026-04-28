"""RFP fact registration into ClaimRegistry — Slice 1.5.

These tests prove that:
  * RFPContext is converted into rfp_fact ClaimProvenance entries with
    verification_status="verified_from_rfp".
  * build_engine2_shopping_list excludes every rfp_fact claim — RFP facts
    must NEVER appear in the Engine 2 shopping list.
  * The shopping list reads requested_external_contexts from the claim
    field (not from usage_allowed, which is normalized to internal-only).
"""
from __future__ import annotations

from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.common import BilingualText
from src.models.engine2_contract import build_engine2_shopping_list
from src.models.rfp import (
    ComplianceRequirement,
    Deliverable,
    EvaluationCriteria,
    KeyDates,
    ProjectTimeline,
    RFPContext,
    SubmissionFormat,
)
from src.services.rfp_fact_registrar import register_rfp_facts


def _ncnp_like_rfp() -> RFPContext:
    return RFPContext(
        rfp_name=BilingualText(ar="نموذج عقد NCNP", en="NCNP Contract"),
        issuing_entity=BilingualText(ar="هيئة سعودية", en="Saudi Authority"),
        mandate=BilingualText(ar="وصف المهمة", en="Mandate"),
        deliverables=[
            Deliverable(id="D-1", description=BilingualText(ar="مخرج 1", en="Deliverable 1")),
        ],
        compliance_requirements=[
            ComplianceRequirement(
                id="CR-1",
                requirement=BilingualText(
                    ar="السجل التجاري", en="Commercial registration",
                ),
                mandatory=True,
            ),
        ],
        key_dates=KeyDates(
            submission_deadline="2026-05-15",
            inquiry_deadline="2026-05-01",
        ),
        submission_format=SubmissionFormat(
            bank_guarantee_required=True,
            separate_envelopes=True,
        ),
        evaluation_criteria=EvaluationCriteria(
            award_mechanism="pass_fail_then_lowest_price",
        ),
        project_timeline=ProjectTimeline(
            total_duration="12 شهراً",
            total_duration_months=12,
        ),
    )


def test_register_rfp_facts_creates_rfp_fact_claims() -> None:
    rfp = _ncnp_like_rfp()
    registry = ClaimRegistry()
    register_rfp_facts(rfp, registry)
    facts = registry.rfp_facts
    assert len(facts) >= 5, f"expected ≥5 rfp_fact claims, got {len(facts)}"
    for c in facts:
        assert c.claim_kind == "rfp_fact"
        assert c.source_kind == "rfp_document"
        assert c.verification_status == "verified_from_rfp"


def test_register_rfp_facts_includes_dates_and_bid_bond() -> None:
    rfp = _ncnp_like_rfp()
    registry = ClaimRegistry()
    register_rfp_facts(rfp, registry)
    texts = " ".join(c.text for c in registry.rfp_facts)
    assert "2026-05-15" in texts  # submission_deadline
    assert any(
        "guarantee" in c.text.lower() or "ضمان" in c.text
        for c in registry.rfp_facts
    ), "Bid bond / bank guarantee should be registered as an RFP fact"


def test_register_rfp_facts_includes_compliance_requirements() -> None:
    rfp = _ncnp_like_rfp()
    registry = ClaimRegistry()
    register_rfp_facts(rfp, registry)
    fact_texts = " ".join(c.text for c in registry.rfp_facts)
    assert "Commercial registration" in fact_texts or "السجل التجاري" in fact_texts


def test_register_rfp_facts_includes_evaluation_criteria() -> None:
    rfp = _ncnp_like_rfp()
    registry = ClaimRegistry()
    register_rfp_facts(rfp, registry)
    fact_texts = " ".join(c.text for c in registry.rfp_facts)
    assert "pass_fail_then_lowest_price" in fact_texts


def test_register_rfp_facts_includes_contract_duration() -> None:
    rfp = _ncnp_like_rfp()
    registry = ClaimRegistry()
    register_rfp_facts(rfp, registry)
    fact_texts = " ".join(c.text for c in registry.rfp_facts)
    assert "12" in fact_texts


def test_rfp_facts_not_in_engine2_shopping_list() -> None:
    """The single most important Slice 1 invariant."""
    registry = ClaimRegistry()
    registry.register(ClaimProvenance(
        claim_id="RFP-FACT-001",
        text="مدة العقد 12 شهراً",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    registry.register(ClaimProvenance(
        claim_id="BIDDER-001",
        text="SG prior project",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_unverified",
        requested_external_contexts=["source_book", "slide_blueprint"],
    ))
    shopping = build_engine2_shopping_list(registry)
    ids = {r.claim_id for r in shopping}
    assert "RFP-FACT-001" not in ids
    assert "BIDDER-001" in ids
    bidder_req = next(r for r in shopping if r.claim_id == "BIDDER-001")
    assert bidder_req.requested_external_contexts == ["source_book", "slide_blueprint"]


def test_rfp_registered_facts_excluded_from_shopping_list() -> None:
    """Combined integration: registering RFP facts + building shopping list."""
    rfp = _ncnp_like_rfp()
    registry = ClaimRegistry()
    register_rfp_facts(rfp, registry)
    # Also register one bidder claim that *should* go to Engine 2
    registry.register(ClaimProvenance(
        claim_id="BIDDER-XYZ",
        text="SG has prior SDAIA project",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_unverified",
        requested_external_contexts=["source_book"],
    ))
    shopping = build_engine2_shopping_list(registry)
    rfp_ids = {c.claim_id for c in registry.rfp_facts}
    shopping_ids = {r.claim_id for r in shopping}
    # No RFP fact may leak into the shopping list
    assert rfp_ids.isdisjoint(shopping_ids), (
        f"RFP facts leaked into Engine 2 shopping list: "
        f"{rfp_ids & shopping_ids}"
    )
    assert "BIDDER-XYZ" in shopping_ids


def test_shopping_list_skips_already_verified_internal_claims() -> None:
    registry = ClaimRegistry()
    registry.register(ClaimProvenance(
        claim_id="BIDDER-VERIFIED",
        text="SG verified project",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_verified",
    ))
    shopping = build_engine2_shopping_list(registry)
    assert "BIDDER-VERIFIED" not in {r.claim_id for r in shopping}


def test_shopping_list_excludes_external_methodology() -> None:
    registry = ClaimRegistry()
    registry.register(ClaimProvenance(
        claim_id="EXT-001",
        text="UNESCO RAM",
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status="externally_verified",
    ))
    registry.register(ClaimProvenance(
        claim_id="OPT-001",
        text="5-8 countries",
        claim_kind="proposal_option",
        source_kind="model_generated",
        verification_status="proposal_option",
    ))
    shopping = build_engine2_shopping_list(registry)
    ids = {r.claim_id for r in shopping}
    assert "EXT-001" not in ids
    assert "OPT-001" not in ids
