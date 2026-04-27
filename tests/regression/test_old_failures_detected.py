"""Prove the old bugs EXIST in frozen fixtures.

These tests should PASS — they detect known bad behavior that the
claim-provenance architecture is designed to fix.
"""

import re

import pytest

from tests.fixtures.fixture_loader import (
    load_conformance_report,
    load_docx_text,
    load_evidence_ledger,
    load_slide_blueprints,
)


# ── NCNP fixture (sb-ar-1776112115) ─────────────────────────────


def test_ncnp_has_9_conformance_failures():
    """The old conformance validator reports 9 failures due to
    English-vs-Arabic keyword scanning false negatives."""
    cr = load_conformance_report("sb-ar-1776112115")
    assert cr["hard_requirements_failed"] == 9


def test_ncnp_evidence_ledger_marks_rfp_facts_as_gaps():
    """Direct RFP facts (HR-L1-*, CR-*) are incorrectly marked as
    'gap' in the evidence ledger instead of verified_from_rfp."""
    ledger = load_evidence_ledger("sb-ar-1776112115")
    gap_entries = [
        e
        for e in ledger["entries"]
        if e.get("verifiability_status") == "gap"
    ]
    rfp_source_gaps = [
        e
        for e in gap_entries
        if "HR-L1" in e.get("source_reference", "")
        or "CR-" in e.get("source_reference", "")
        or "SI-" in e.get("source_reference", "")
    ]
    assert len(rfp_source_gaps) >= 5, (
        f"Expected >=5 RFP facts incorrectly as gaps, found {len(rfp_source_gaps)}"
    )


def test_ncnp_compliance_items_present_in_docx_but_validator_misses():
    """Arabic compliance terms ARE present in the DOCX, proving the
    validator false-negatives are scan-target bugs."""
    text = load_docx_text("sb-ar-1776112115")
    assert "السجل التجاري" in text, "Commercial registration present"
    assert "الزكاة" in text, "Zakat present"
    assert "السعودة" in text, "Saudization present"
    assert "D-20" in text, "D-20 deliverable present"
    assert "D-21" in text, "D-21 deliverable present"


# ── UNESCO AI Ethics fixture (sb-ar-1777280086) ─────────────────


def test_unesco_conformance_stuck_at_10():
    """The validator reports 10 failures across 5 writer passes."""
    cr = load_conformance_report("sb-ar-1777280086")
    assert cr["hard_requirements_failed"] >= 10


def test_unesco_has_prj_leakage_in_docx():
    """PRJ-001 appears in the source book DOCX — the forbidden-claim
    leakage that the new architecture must block."""
    text = load_docx_text("sb-ar-1777280086")
    assert re.search(r"\bPRJ-\d+\b", text), (
        "PRJ ID should be present in old fixture (known leakage)"
    )


def test_unesco_has_cli_leakage_in_slide_blueprints():
    """CLI-* IDs appear as proof points or text in slide blueprints."""
    blueprints = load_slide_blueprints("sb-ar-1777280086")
    all_text = " ".join(
        str(bp.get("key_message", ""))
        + " ".join(bp.get("bullet_points") or [])
        + " ".join(str(p) for p in (bp.get("proof_points") or []))
        for bp in blueprints
    )
    # Either CLI or PRJ IDs should be present in old blueprints
    has_internal_ids = bool(
        re.search(r"\bCLI-\d+\b", all_text)
        or re.search(r"\bPRJ-\d+\b", all_text)
        or "Engine 2" in all_text
        or "المحرك الثاني" in all_text
    )
    assert has_internal_ids, (
        "Old blueprint should contain internal IDs or Engine 2 references"
    )


def test_unesco_evidence_ledger_marks_rfp_facts_as_gaps():
    """Direct RFP facts are marked as 'gap' in the UNESCO evidence
    ledger, same as the NCNP fixture."""
    ledger = load_evidence_ledger("sb-ar-1777280086")
    gap_entries = [
        e
        for e in ledger["entries"]
        if e.get("verifiability_status") == "gap"
    ]
    rfp_ref_gaps = [
        e
        for e in gap_entries
        if "HR-L1" in e.get("source_reference", "")
        or "CR-" in e.get("source_reference", "")
    ]
    assert len(rfp_ref_gaps) >= 2, (
        f"Expected >=2 RFP facts as gaps, found {len(rfp_ref_gaps)}"
    )
