"""Ledger reconciliation — normalize legacy evidence extractor output against ClaimRegistry.

The legacy evidence_extractor.py LLM pass audits Source Book prose and
assigns CLM-* IDs to everything it finds. It does not read the
ClaimRegistry, so RFP facts (dates, compliance requirements,
deliverables, scope items) get misclassified as internal company claims.

This module reconciles legacy EvidenceLedgerEntry objects against the
ClaimRegistry so that:
- RFP facts carry claim_kind="rfp_fact", source_kind="rfp_document",
  verifiability_status="verified", and a registry_claim_id link.
- Internal company claims keep their original classification.
- External evidence entries are not modified.

No RFP-specific logic. Matching is by structured ID patterns
(HR-L1-*, CR-*, COMP-*, DEL-*, SCOPE-*) cross-referenced against
registry claim_ids and source_refs.
"""

from __future__ import annotations

import logging
import re

from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.source_book import EvidenceLedgerEntry

logger = logging.getLogger(__name__)

# Patterns in source_reference that indicate the entry references an
# RFP-side requirement, not an internal company claim.
_RFP_SOURCE_PATTERNS = re.compile(
    r"\bHR-L\d-\d+\b|"
    r"\bCR-\d+\b|"
    r"\bCOMP-\d+\b|"
    r"\bDEL-\d+\b|"
    r"\bSCOPE-\d+\b",
    re.IGNORECASE,
)


def _find_matching_rfp_fact(
    entry: EvidenceLedgerEntry,
    registry: ClaimRegistry,
) -> ClaimProvenance | None:
    """Find the registry rfp_fact that best matches a legacy ledger entry.

    Matching strategy (in priority order):
    1. source_reference contains an ID (HR-L1-031, CR-1, DEL-001, COMP-005,
       SCOPE-003) that appears in a registered rfp_fact's claim_id or
       source_refs[].clause.
    2. Exact claim_text substring match against a registered rfp_fact.
    """
    src_ref = entry.source_reference or ""

    # Extract structured IDs from the legacy entry's source_reference
    ids_in_ref = _RFP_SOURCE_PATTERNS.findall(src_ref)

    for rfp_fact in registry.rfp_facts:
        # Match by ID in source_reference → registry claim_id
        for ref_id in ids_in_ref:
            if ref_id.upper() in rfp_fact.claim_id.upper():
                return rfp_fact
            # Also check source_refs clauses
            for sref in rfp_fact.source_refs:
                if ref_id.upper() in (sref.clause or "").upper():
                    return rfp_fact
            # Also check rfp_fact text for the ID (handles cross-system
            # ID references, e.g. legacy has HR-L1-001, registry text
            # may reference the same requirement differently)
            if ref_id.upper() in rfp_fact.text.upper():
                return rfp_fact

    # Fallback: substantial claim_text overlap (≥60% of shorter text
    # tokens match). This catches cases where ID systems differ but the
    # actual RFP fact text is the same.
    if entry.claim_text and len(entry.claim_text) > 20:
        entry_tokens = set(entry.claim_text.split())
        for rfp_fact in registry.rfp_facts:
            if not rfp_fact.text or len(rfp_fact.text) < 10:
                continue
            fact_tokens = set(rfp_fact.text.split())
            smaller = min(len(entry_tokens), len(fact_tokens)) or 1
            overlap = len(entry_tokens & fact_tokens) / smaller
            if overlap >= 0.6:
                return rfp_fact

    return None


def reconcile_ledger_with_registry(
    entries: list[EvidenceLedgerEntry],
    registry: ClaimRegistry,
) -> list[EvidenceLedgerEntry]:
    """Reconcile legacy evidence ledger entries against ClaimRegistry.

    For each entry that matches a registered rfp_fact:
    - Set verifiability_status = "verified"
    - Set claim_kind = "rfp_fact"
    - Set source_kind = "rfp_document"
    - Set registry_claim_id to the matching fact's claim_id
    - Add DIRECT_RFP_FACT note to verification_note

    Entries that do not match any rfp_fact are returned unchanged.
    External entries (source_type="external") are never reconciled.

    Returns a new list — does not mutate input entries.
    """
    reconciled: list[EvidenceLedgerEntry] = []
    reconciled_count = 0

    for entry in entries:
        # Never reconcile external entries
        if entry.source_type == "external":
            reconciled.append(entry)
            continue

        matched_fact = _find_matching_rfp_fact(entry, registry)

        if matched_fact:
            # Create a reconciled copy with typed provenance fields
            updated = entry.model_copy(update={
                "verifiability_status": "verified",
                "verification_note": (
                    f"[DIRECT_RFP_FACT] Verified from RFP — "
                    f"{matched_fact.claim_id}"
                ),
                "claim_kind": "rfp_fact",
                "source_kind": "rfp_document",
                "registry_claim_id": matched_fact.claim_id,
            })
            reconciled.append(updated)
            reconciled_count += 1
        else:
            reconciled.append(entry)

    if reconciled_count:
        logger.info(
            "Ledger reconciliation: %d/%d entries reconciled as rfp_fact",
            reconciled_count,
            len(entries),
        )

    return reconciled
