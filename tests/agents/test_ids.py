"""Tests for src/utils/ids.py — validates ID generation per Appendix C."""

from src.utils.ids import (
    next_claim_id,
    next_compliance_id,
    next_deliverable_id,
    next_doc_id,
    next_gap_id,
    next_scope_id,
    next_section_id,
    next_slide_id,
    next_waiver_id,
    reset_counters,
)


def test_claim_id_format():
    reset_counters()
    assert next_claim_id() == "CLM-0001"
    assert next_claim_id() == "CLM-0002"


def test_gap_id_format():
    reset_counters()
    assert next_gap_id() == "GAP-001"


def test_slide_id_format():
    reset_counters()
    assert next_slide_id() == "S-001"
    assert next_slide_id() == "S-002"


def test_section_id_format():
    reset_counters()
    assert next_section_id() == "SEC-01"


def test_doc_id_format():
    reset_counters()
    assert next_doc_id() == "DOC-001"


def test_scope_id_format():
    reset_counters()
    assert next_scope_id() == "SCOPE-001"


def test_deliverable_id_format():
    reset_counters()
    assert next_deliverable_id() == "DEL-001"


def test_compliance_id_format():
    reset_counters()
    assert next_compliance_id() == "COMP-001"


def test_waiver_id_format():
    reset_counters()
    assert next_waiver_id() == "WVR-001"


def test_reset_counters():
    reset_counters()
    next_claim_id()
    next_claim_id()
    reset_counters()
    assert next_claim_id() == "CLM-0001"


def test_ids_are_sequential():
    reset_counters()
    ids = [next_doc_id() for _ in range(5)]
    assert ids == ["DOC-001", "DOC-002", "DOC-003", "DOC-004", "DOC-005"]
