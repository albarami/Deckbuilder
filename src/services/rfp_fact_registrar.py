"""RFP fact registrar — Slice 1.5.

Walks an RFPContext and registers every directly-extractable RFP fact
(dates, bid bond, deliverables, compliance requirements, contract
duration, evaluation criteria, language rules, etc.) into a ClaimRegistry
as ``rfp_fact`` claims with ``verification_status="verified_from_rfp"``.

These claims must NEVER be sent to Engine 2 for proof-shopping — they
are RFP-side facts, not bidder claims that need verification.
"""
from __future__ import annotations

from src.models.claim_provenance import (
    ClaimProvenance,
    ClaimRegistry,
    SourceReference,
)
from src.models.rfp import RFPContext


def _make_rfp_fact(
    claim_id: str,
    text: str,
    *,
    source_location: str = "",
    deliverable_origin: str = "not_applicable",
) -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
        evidence_role="requirement_source",
        source_refs=(
            [SourceReference(file="rfp", clause=source_location)]
            if source_location
            else []
        ),
        deliverable_origin=deliverable_origin,  # type: ignore[arg-type]
    )


def register_rfp_facts(rfp: RFPContext, registry: ClaimRegistry) -> None:
    """Register RFP-side facts as ``rfp_fact`` claims in ``registry``.

    Idempotent per claim_id: calling twice with the same RFP overwrites
    rather than duplicates because ClaimRegistry.register replaces by id.
    """
    fact_seq = 0

    def next_id(prefix: str) -> str:
        nonlocal fact_seq
        fact_seq += 1
        return f"RFP-FACT-{prefix}-{fact_seq:03d}"

    # ── Key dates ────────────────────────────────────────────────────
    if rfp.key_dates is not None:
        kd = rfp.key_dates
        date_fields = (
            ("submission_deadline", kd.submission_deadline),
            ("inquiry_deadline", kd.inquiry_deadline),
            ("bid_opening", kd.bid_opening),
            ("expected_award", kd.expected_award),
            ("service_start", kd.service_start),
        )
        for label, value in date_fields:
            if value:
                registry.register(
                    _make_rfp_fact(
                        claim_id=next_id("DATE"),
                        text=f"{label}: {value}",
                        source_location=f"key_dates.{label}",
                    )
                )

    # ── Submission format / bid bond ─────────────────────────────────
    sf = rfp.submission_format
    if sf is not None:
        if sf.bank_guarantee_required:
            registry.register(
                _make_rfp_fact(
                    claim_id=next_id("BIDBOND"),
                    text="Bank guarantee (bid bond) required — ضمان بنكي مطلوب",
                    source_location="submission_format.bank_guarantee_required",
                )
            )
        if sf.separate_envelopes:
            registry.register(
                _make_rfp_fact(
                    claim_id=next_id("ENV"),
                    text=(
                        "Separate technical and financial envelopes required"
                    ),
                    source_location="submission_format.separate_envelopes",
                )
            )
        for extra in sf.additional_requirements:
            registry.register(
                _make_rfp_fact(
                    claim_id=next_id("SUBFMT"),
                    text=f"Submission requirement: {extra}",
                    source_location="submission_format.additional_requirements",
                )
            )

    # ── Compliance requirements ─────────────────────────────────────
    for cr in rfp.compliance_requirements:
        # Use the structured Arabic text first when available; fall back to English.
        descr_ar = (cr.requirement.ar or "").strip()
        descr_en = (cr.requirement.en or "").strip()
        descr = descr_ar if descr_ar else descr_en
        if not descr:
            continue
        text = (
            f"Compliance requirement: {descr_en}"
            if descr_en
            else f"Compliance requirement: {descr}"
        )
        if descr_ar and descr_ar != descr_en:
            text = f"{text} ({descr_ar})"
        registry.register(
            _make_rfp_fact(
                claim_id=f"RFP-FACT-COMPLIANCE-{cr.id}",
                text=text,
                source_location=f"compliance_requirements[{cr.id}]",
            )
        )

    # ── Deliverables ────────────────────────────────────────────────
    for d in rfp.deliverables:
        descr_ar = (d.description.ar or "").strip()
        descr_en = (d.description.en or "").strip()
        descr = descr_en or descr_ar
        if not descr:
            continue
        registry.register(
            _make_rfp_fact(
                claim_id=f"RFP-FACT-DELIV-{d.id}",
                text=f"Deliverable {d.id}: {descr}",
                source_location=f"deliverables[{d.id}]",
                deliverable_origin="deliverables_annex",
            )
        )

    # ── Evaluation criteria ─────────────────────────────────────────
    ec = rfp.evaluation_criteria
    if ec is not None and ec.award_mechanism and ec.award_mechanism != "unknown":
        registry.register(
            _make_rfp_fact(
                claim_id=next_id("AWARD"),
                text=f"Award mechanism: {ec.award_mechanism}",
                source_location="evaluation_criteria.award_mechanism",
            )
        )

    # ── Project timeline / contract duration ─────────────────────────
    pt = rfp.project_timeline
    if pt is not None:
        if pt.total_duration_months is not None:
            registry.register(
                _make_rfp_fact(
                    claim_id=next_id("DURATION"),
                    text=f"Contract duration: {pt.total_duration_months} months",
                    source_location="project_timeline.total_duration_months",
                )
            )
        if pt.total_duration:
            registry.register(
                _make_rfp_fact(
                    claim_id=next_id("DURTEXT"),
                    text=f"Contract duration text: {pt.total_duration}",
                    source_location="project_timeline.total_duration",
                )
            )

    # ── Language / source language rule ─────────────────────────────
    if rfp.source_language is not None:
        # source_language may be a plain string (use_enum_values=True) or an enum
        lang = (
            rfp.source_language.value
            if hasattr(rfp.source_language, "value")
            else str(rfp.source_language)
        )
        registry.register(
            _make_rfp_fact(
                claim_id=next_id("LANG"),
                text=f"RFP source language: {lang}",
                source_location="source_language",
            )
        )
