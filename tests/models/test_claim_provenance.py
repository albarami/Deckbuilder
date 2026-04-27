"""Tests for ClaimProvenance and SourceReference core models."""
import pytest

from src.models.claim_provenance import ClaimProvenance, SourceReference


def test_rfp_fact_defaults():
    c = ClaimProvenance(
        claim_id="RFP-FACT-001",
        text="مدة العقد 12 شهراً",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    )
    assert c.usage_allowed == ["internal_gap_appendix"]
    assert c.formal_deliverable is False
    assert c.requires_client_naming_permission is False
    assert c.requested_external_contexts == []


def test_internal_claim_defaults_to_unverified():
    c = ClaimProvenance(
        claim_id="BIDDER-CLAIM-001",
        text="SG has prior SDAIA experience",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_unverified",
    )
    assert c.verification_status == "internal_unverified"
    assert c.client_naming_permission is None
    assert c.requested_external_contexts == []


def test_requested_external_contexts_preserved():
    c = ClaimProvenance(
        claim_id="BIDDER-CLAIM-002",
        text="SG prior SDAIA project",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_unverified",
        requested_external_contexts=["source_book", "slide_blueprint"],
    )
    assert c.requested_external_contexts == ["source_book", "slide_blueprint"]
    assert c.usage_allowed == ["internal_gap_appendix"]


def test_usage_allowed_accepts_internal_destinations():
    c = ClaimProvenance(
        claim_id="OPT-001",
        text="5-8 countries",
        claim_kind="proposal_option",
        source_kind="model_generated",
        verification_status="proposal_option",
        usage_allowed=["internal_bid_notes", "proposal_option_ledger"],
    )
    assert "internal_bid_notes" in c.usage_allowed
    assert "proposal_option_ledger" in c.usage_allowed


def test_deliverable_flags_derived_from_origin():
    c = ClaimProvenance(
        claim_id="RFP-FACT-010",
        text="D-1 Design document",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
        deliverable_origin="boq_line",
    )
    assert c.formal_deliverable is True
    assert c.pricing_line_item is True
    assert c.cross_cutting_workstream is False


def test_special_condition_is_workstream_not_deliverable():
    c = ClaimProvenance(
        claim_id="RFP-FACT-011",
        text="Training and knowledge transfer",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
        deliverable_origin="special_condition",
    )
    assert c.formal_deliverable is False
    assert c.pricing_line_item is False
    assert c.cross_cutting_workstream is True


def test_source_refs_list_based():
    c = ClaimProvenance(
        claim_id="RFP-FACT-002",
        text="test",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
        source_refs=[
            SourceReference(file="rfp.pdf", page="7", clause="جدول المواعيد"),
            SourceReference(file="rfp.pdf", page="12", clause="شروط التقديم"),
        ],
    )
    assert len(c.source_refs) == 2
    assert c.source_refs[0].page == "7"


def test_forbidden_status():
    c = ClaimProvenance(
        claim_id="BAD-001",
        text="fabricated claim",
        claim_kind="internal_company_claim",
        source_kind="model_generated",
        verification_status="forbidden",
        blocked_reason="Fabricated by LLM",
    )
    assert c.verification_status == "forbidden"
    assert c.blocked_reason == "Fabricated by LLM"


def test_inference_controls():
    c = ClaimProvenance(
        claim_id="INF-001",
        text="Award mechanism likely pass/fail",
        claim_kind="generated_inference",
        source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=True,
        inference_allowed_context=["source_book_analysis", "internal_bid_notes"],
    )
    assert c.inference_label_present is True
    assert "source_book_analysis" in c.inference_allowed_context
