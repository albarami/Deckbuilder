"""Tests for ComplianceIndex and ComplianceIndexEntry."""
from src.models.claim_provenance import ComplianceIndex, ComplianceIndexEntry


def test_covered_by_declaration_passes_content():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-002",
        requirement_text="Commercial registration",
        response_status="covered_by_declaration",
        arabic_aliases=["السجل التجاري"],
    )
    assert e.content_conformance_pass is True
    assert e.submission_pack_ready is False


def test_covered_pending_attachment_passes_content_not_submission():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-003",
        requirement_text="Zakat certificate",
        response_status="covered_pending_attachment",
        attachment_required=True,
        attachment_verified=False,
    )
    assert e.content_conformance_pass is True
    assert e.submission_pack_ready is False


def test_attachment_verified_passes_both():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-003",
        requirement_text="Zakat certificate",
        response_status="covered_pending_attachment",
        attachment_required=True,
        attachment_verified=True,
    )
    assert e.content_conformance_pass is True
    assert e.submission_pack_ready is True


def test_covered_by_response_text_passes_content():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-008",
        requirement_text="Arabic language requirement",
        response_status="covered_by_response_text",
    )
    assert e.content_conformance_pass is True


def test_missing_fails_content():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-099",
        requirement_text="Unknown",
        response_status="missing",
    )
    assert e.content_conformance_pass is False


def test_not_applicable_needs_rationale():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-050",
        requirement_text="NA item",
        response_status="not_applicable",
        not_applicable_rationale="",
    )
    assert e.content_conformance_pass is False


def test_not_applicable_with_rationale_passes():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-050",
        requirement_text="NA item",
        response_status="not_applicable",
        not_applicable_rationale="Not relevant to this bid type",
    )
    assert e.content_conformance_pass is True


def test_compliance_index_holds_entries():
    idx = ComplianceIndex(entries=[
        ComplianceIndexEntry(
            requirement_id="HR-L1-002",
            requirement_text="Commercial registration",
            response_status="covered_by_declaration",
        ),
        ComplianceIndexEntry(
            requirement_id="HR-L1-003",
            requirement_text="Zakat",
            response_status="missing",
        ),
    ])
    assert len(idx.entries) == 2
    passed = [e for e in idx.entries if e.content_conformance_pass]
    assert len(passed) == 1
