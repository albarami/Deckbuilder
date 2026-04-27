"""Tests for context-specific usage gates and normalize_usage_allowed."""
import pytest

from src.models.claim_provenance import ClaimProvenance
from src.services.artifact_gates import (
    can_use_as_proof_point,
    can_use_in_client_proposal,
    can_use_in_internal_gap_appendix,
    can_use_in_slide_blueprint,
    can_use_in_source_book_analysis,
    can_use_in_speaker_notes,
    normalize_usage_allowed,
)


# ── can_use_as_proof_point ───────────────────────────────────────


def test_rfp_fact_is_proof_point():
    c = ClaimProvenance(
        claim_id="RFP-FACT-001", text="test",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    )
    assert can_use_as_proof_point(c) is True


def test_unverified_internal_not_proof_point():
    c = ClaimProvenance(
        claim_id="BIDDER-001", text="SG experience",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_unverified",
    )
    assert can_use_as_proof_point(c) is False


def test_verified_internal_needs_client_permission():
    c = ClaimProvenance(
        claim_id="BIDDER-002", text="SDAIA project",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_verified",
        requires_client_naming_permission=True,
        client_naming_permission=False,
    )
    assert can_use_as_proof_point(c) is False


def test_verified_internal_needs_partner_permission():
    c = ClaimProvenance(
        claim_id="BIDDER-003", text="UNESCO partnership",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_verified",
        requires_partner_naming_permission=True,
        partner_naming_permission=False,
    )
    assert can_use_as_proof_point(c) is False


def test_verified_internal_with_all_permissions_is_proof():
    c = ClaimProvenance(
        claim_id="BIDDER-004", text="SDAIA project",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_verified",
        requires_client_naming_permission=True,
        client_naming_permission=True,
        requires_partner_naming_permission=True,
        partner_naming_permission=True,
        scope_summary_allowed_for_proposal=True,
    )
    assert can_use_as_proof_point(c) is True


def test_verified_internal_scope_blocked():
    c = ClaimProvenance(
        claim_id="BIDDER-005", text="SDAIA project",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_verified",
        scope_summary_allowed_for_proposal=False,
    )
    assert can_use_as_proof_point(c) is False


def test_external_methodology_only_as_methodology_support():
    c = ClaimProvenance(
        claim_id="EXT-001", text="UNESCO RAM",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="direct_topic",
        evidence_role="bidder_capability_proof",
    )
    assert can_use_as_proof_point(c) is False


def test_external_methodology_correct_role():
    c = ClaimProvenance(
        claim_id="EXT-002", text="UNESCO RAM",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="direct_topic",
        evidence_role="methodology_support",
    )
    assert can_use_as_proof_point(c) is True


def test_external_analogical_not_proof():
    c = ClaimProvenance(
        claim_id="EXT-003", text="WHO health governance",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="analogical",
        evidence_role="methodology_support",
    )
    assert can_use_as_proof_point(c) is False


def test_proposal_option_never_proof():
    c = ClaimProvenance(
        claim_id="OPT-001", text="5-8 countries",
        claim_kind="proposal_option", source_kind="model_generated",
        verification_status="proposal_option",
    )
    assert can_use_as_proof_point(c) is False


def test_generated_inference_never_proof():
    c = ClaimProvenance(
        claim_id="INF-001", text="Portal: EXPRO",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
    )
    assert can_use_as_proof_point(c) is False


def test_forbidden_never_proof():
    c = ClaimProvenance(
        claim_id="BAD-001", text="fabricated",
        claim_kind="internal_company_claim", source_kind="model_generated",
        verification_status="forbidden",
    )
    assert can_use_as_proof_point(c) is False


# ── can_use_in_source_book_analysis ──────────────────────────────


def test_generated_inference_needs_label_for_client_body():
    c = ClaimProvenance(
        claim_id="INF-002", text="Award mechanism likely pass/fail",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=False,
    )
    assert can_use_in_source_book_analysis(c, "client_facing_body") is False


def test_generated_inference_labelled_allowed_in_analysis():
    c = ClaimProvenance(
        claim_id="INF-003", text="Award mechanism likely pass/fail",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=True,
        inference_allowed_context=["source_book_analysis"],
    )
    assert can_use_in_source_book_analysis(c, "client_facing_body") is True


def test_anything_allowed_in_internal_gap_appendix_section():
    c = ClaimProvenance(
        claim_id="BIDDER-010", text="unverified",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_unverified",
    )
    assert can_use_in_source_book_analysis(c, "internal_gap_appendix") is True


def test_unverified_internal_blocked_in_client_body():
    c = ClaimProvenance(
        claim_id="BIDDER-011", text="unverified",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_unverified",
    )
    assert can_use_in_source_book_analysis(c, "client_facing_body") is False


def test_proposal_option_blocked_in_client_body():
    c = ClaimProvenance(
        claim_id="OPT-002", text="15 interviews",
        claim_kind="proposal_option", source_kind="model_generated",
        verification_status="proposal_option",
    )
    assert can_use_in_source_book_analysis(c, "client_facing_body") is False


def test_analogical_partially_verified_blocked_in_client_body():
    c = ClaimProvenance(
        claim_id="EXT-010", text="WHO health workforce governance",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="partially_verified",
        relevance_class="analogical",
        evidence_role="methodology_support",
    )
    assert can_use_in_source_book_analysis(c, "client_facing_body") is False


def test_adjacent_partially_verified_allowed_as_methodology():
    c = ClaimProvenance(
        claim_id="EXT-011", text="GCC AI governance report",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="partially_verified",
        relevance_class="adjacent_domain",
        evidence_role="methodology_support",
    )
    assert can_use_in_source_book_analysis(c, "client_facing_body") is True


# ── can_use_in_slide_blueprint ───────────────────────────────────


def test_slide_blueprint_blocks_generated_inference():
    c = ClaimProvenance(
        claim_id="INF-004", text="inferred",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=True,
    )
    assert can_use_in_slide_blueprint(c) is False


def test_slide_blueprint_blocks_proposal_option():
    c = ClaimProvenance(
        claim_id="OPT-003", text="5 workshops",
        claim_kind="proposal_option", source_kind="model_generated",
        verification_status="proposal_option",
    )
    assert can_use_in_slide_blueprint(c) is False


def test_slide_blueprint_allows_verified_rfp_fact():
    c = ClaimProvenance(
        claim_id="RFP-002", text="12 months",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    )
    assert can_use_in_slide_blueprint(c) is True


# ── can_use_in_speaker_notes ────────────────────────────────────


def test_speaker_notes_allows_labelled_inference():
    c = ClaimProvenance(
        claim_id="INF-005", text="inferred",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=True,
        inference_allowed_context=["speaker_notes"],
    )
    assert can_use_in_speaker_notes(c) is True


def test_speaker_notes_blocks_unlabelled_inference():
    c = ClaimProvenance(
        claim_id="INF-006", text="inferred",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=False,
    )
    assert can_use_in_speaker_notes(c) is False


# ── normalize_usage_allowed ──────────────────────────────────────


def test_normalize_blocks_unverified():
    c = ClaimProvenance(
        claim_id="BIDDER-020", text="test",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_unverified",
        usage_allowed=["source_book", "slide_blueprint"],
    )
    assert normalize_usage_allowed(c) == ["internal_gap_appendix"]


def test_normalize_blocks_forbidden():
    c = ClaimProvenance(
        claim_id="BAD-002", text="test",
        claim_kind="internal_company_claim", source_kind="model_generated",
        verification_status="forbidden",
        usage_allowed=["proposal"],
    )
    assert normalize_usage_allowed(c) == ["internal_gap_appendix"]


def test_normalize_keeps_verified_usage():
    c = ClaimProvenance(
        claim_id="RFP-003", text="test",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
        usage_allowed=["source_book", "slide_blueprint"],
    )
    assert normalize_usage_allowed(c) == ["source_book", "slide_blueprint"]


# ── internal gap appendix always allows ──────────────────────────


def test_internal_gap_appendix_allows_everything():
    c = ClaimProvenance(
        claim_id="BAD-003", text="forbidden",
        claim_kind="internal_company_claim", source_kind="model_generated",
        verification_status="forbidden",
    )
    assert can_use_in_internal_gap_appendix(c) is True
