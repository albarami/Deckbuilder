"""Tests for evidence ledger reconciliation with ClaimRegistry.

The legacy evidence extractor assigns CLM-* IDs to everything. When
a legacy entry references an RFP fact already registered in the
ClaimRegistry, reconciliation must:
- add typed provenance fields (claim_kind, source_kind, verification_status)
- map to the registry claim_id
- NOT leave the entry implying it is an internal company claim
"""

from __future__ import annotations

import pytest

from src.models.claim_provenance import ClaimProvenance, ClaimRegistry, SourceReference
from src.models.source_book import EvidenceLedgerEntry
from src.services.ledger_reconciliation import reconcile_ledger_with_registry


def _registry_with_rfp_facts() -> ClaimRegistry:
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="RFP-FACT-COMPLIANCE-CR-1",
        text="تقديم العروض باللغة العربية",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
        source_refs=[SourceReference(clause="compliance_requirements[CR-1]")],
    ))
    reg.register(ClaimProvenance(
        claim_id="RFP-FACT-DELIV-DEL-001",
        text="Deliverable DEL-001: assessment report",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
        source_refs=[SourceReference(clause="deliverables[DEL-001]")],
    ))
    reg.register(ClaimProvenance(
        claim_id="RFP-FACT-DATE-001",
        text="submission_deadline: 1447-11-08",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    return reg


def _make_legacy_entry(claim_id: str, source_ref: str, text: str) -> EvidenceLedgerEntry:
    return EvidenceLedgerEntry(
        claim_id=claim_id,
        claim_text=text,
        source_type="internal",
        source_reference=source_ref,
        confidence=0.9,
        verifiability_status="gap",
        verification_note="Check reference_index",
    )


def test_rfp_compliance_entry_reconciled_to_verified():
    """CLM-COMP-001 referencing HR-L1-001 / CR-1 must become verified_from_rfp."""
    reg = _registry_with_rfp_facts()
    entries = [
        _make_legacy_entry(
            "CLM-COMP-001",
            "كراسة شروط المنافسة — البند COMP-001 (HR-L1-001)",
            "تقديم العروض باللغة العربية",
        ),
    ]
    reconciled = reconcile_ledger_with_registry(entries, reg)
    e = reconciled[0]
    assert e.verifiability_status == "verified"
    assert "DIRECT_RFP_FACT" in (e.verification_note or "")
    assert e.claim_kind == "rfp_fact"
    assert e.source_kind == "rfp_document"
    assert e.registry_claim_id == "RFP-FACT-COMPLIANCE-CR-1"


def test_rfp_deliverable_entry_reconciled():
    """CLM-DEL-001 referencing HR-L1-031 / DEL-001 must become verified_from_rfp."""
    reg = _registry_with_rfp_facts()
    entries = [
        _make_legacy_entry(
            "CLM-DEL-001",
            "كراسة شروط المنافسة — DEL-001 (HR-L1-031)",
            "تقييم الوضع الراهن",
        ),
    ]
    reconciled = reconcile_ledger_with_registry(entries, reg)
    e = reconciled[0]
    assert e.verifiability_status == "verified"
    assert e.claim_kind == "rfp_fact"
    assert e.registry_claim_id == "RFP-FACT-DELIV-DEL-001"


def test_internal_project_entry_not_reconciled():
    """CLM-PRJ-001 referencing a real project must NOT become rfp_fact."""
    reg = _registry_with_rfp_facts()
    entries = [
        _make_legacy_entry(
            "CLM-PRJ-001",
            "Strategic Gears — قاعدة المشاريع PRJ-001",
            "مشروع دعم تنفيذ الاستراتيجية",
        ),
    ]
    reconciled = reconcile_ledger_with_registry(entries, reg)
    e = reconciled[0]
    assert e.verifiability_status != "verified" or "DIRECT_RFP_FACT" not in (e.verification_note or "")
    assert e.claim_kind != "rfp_fact"


def test_external_evidence_entry_not_reconciled():
    """EXT-001 should keep its original classification."""
    reg = _registry_with_rfp_facts()
    entries = [
        EvidenceLedgerEntry(
            claim_id="EXT-001",
            claim_text="UNESCO RAM framework",
            source_type="external",
            source_reference="UNESCO AI Ethics Toolkit 2025",
            confidence=0.9,
            verifiability_status="verified",
            verification_note="External source",
        ),
    ]
    reconciled = reconcile_ledger_with_registry(entries, reg)
    e = reconciled[0]
    assert e.source_type == "external"
    assert e.claim_id == "EXT-001"


def test_unmatched_clm_entry_unchanged():
    """CLM entry that doesn't match any registry fact stays unchanged."""
    reg = _registry_with_rfp_facts()
    entries = [
        _make_legacy_entry(
            "CLM-MISC-001",
            "unknown source",
            "some unmatched claim",
        ),
    ]
    reconciled = reconcile_ledger_with_registry(entries, reg)
    e = reconciled[0]
    assert e.verifiability_status == "gap"
    assert not hasattr(e, "claim_kind") or e.claim_kind is None
