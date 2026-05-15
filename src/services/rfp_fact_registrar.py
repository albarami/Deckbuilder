"""RFP fact registrar — Slice 1.5.

Walks an RFPContext and registers every directly-extractable RFP fact
(dates, bid bond, deliverables, compliance requirements, contract
duration, evaluation criteria, language rules, etc.) into a ClaimRegistry
as ``rfp_fact`` claims.

Default verification_status is ``verified_from_rfp``. However, when the
source document came from degraded OCR (extraction_quality != CLEAN),
verification_status is downgraded to ``partially_verified`` and a flag
``source_refs[].clause`` notes the OCR origin. This addresses an audit
finding (Salim, 2026-05-13) that fabricated values from degraded OCR
regions were being tagged at confidence 1.0 verified_from_rfp.

These claims (regardless of verification_status) must NEVER be sent to
Engine 2 for proof-shopping — they are RFP-side facts identified by
``claim_kind="rfp_fact"``, not bidder claims that need verification.
"""
from __future__ import annotations

from src.models.claim_provenance import (
    ClaimProvenance,
    ClaimRegistry,
    SourceReference,
)
from src.models.enums import ExtractionQuality
from src.models.rfp import RFPContext
from src.models.state import UploadedDocument


def _ocr_is_degraded(uploaded_documents: list[UploadedDocument] | None) -> bool:
    """Return True if ANY uploaded RFP doc was OCR'd at degraded quality.

    Conservative all-or-nothing: if the RFP intake includes any document
    that wasn't cleanly extracted, we treat the entire RFPContext as
    OCR-sourced because per-field provenance to specific documents isn't
    tracked at this layer.
    """
    if not uploaded_documents:
        return False
    return any(
        doc.extraction_quality != ExtractionQuality.CLEAN
        for doc in uploaded_documents
    )


def _build_rfp_fact_factory(
    ocr_degraded: bool,
    source_quotes: dict[str, str] | None = None,
):
    """Return a `_make_rfp_fact` closure with OCR-degradation status baked in.

    When ocr_degraded=True, every fact produced by the returned factory is
    tagged `partially_verified` instead of `verified_from_rfp`, and its
    source_ref clause is annotated with an OCR_DEGRADED marker.

    When ``source_quotes`` is provided (Salim audit primitive #4: verbatim
    source-span contract), the factory looks up the dotted-path source
    location in the dict and embeds the verbatim quote in the
    SourceReference.clause. The reviewer agent uses these quotes to
    mechanically verify each fact against the original RFP text.
    """
    status = "partially_verified" if ocr_degraded else "verified_from_rfp"
    quotes = source_quotes or {}

    def _make_rfp_fact(
        claim_id: str,
        text: str,
        *,
        source_location: str = "",
        deliverable_origin: str = "not_applicable",
    ) -> ClaimProvenance:
        quote = quotes.get(source_location, "")
        # Build the clause: location + optional verbatim quote + optional
        # OCR-degraded marker. Format keeps the location head-of-clause so
        # downstream tools that look it up still work, but appends the
        # quote for the reviewer to verify.
        if quote and source_location:
            clause = f"{source_location} :: \"{quote}\""
        else:
            clause = source_location
        if ocr_degraded and source_location:
            clause = f"{clause} [OCR_DEGRADED — manual verification required]"
        return ClaimProvenance(
            claim_id=claim_id,
            text=text,
            claim_kind="rfp_fact",
            source_kind="rfp_document",
            verification_status=status,
            evidence_role="requirement_source",
            source_refs=(
                [SourceReference(file="rfp", clause=clause)]
                if source_location
                else []
            ),
            deliverable_origin=deliverable_origin,  # type: ignore[arg-type]
        )

    return _make_rfp_fact


def register_rfp_facts(
    rfp: RFPContext,
    registry: ClaimRegistry,
    *,
    uploaded_documents: list[UploadedDocument] | None = None,
) -> None:
    """Register RFP-side facts as ``rfp_fact`` claims in ``registry``.

    Idempotent per claim_id: calling twice with the same RFP overwrites
    rather than duplicates because ClaimRegistry.register replaces by id.

    When ``uploaded_documents`` is provided and any of them has
    extraction_quality != CLEAN, all registered facts are tagged
    ``partially_verified`` instead of ``verified_from_rfp``. See module
    docstring for rationale.
    """
    ocr_degraded = _ocr_is_degraded(uploaded_documents)
    # Salim audit primitive #4: thread verbatim source quotes through to claims
    source_quotes = getattr(rfp, "source_quotes", None) or {}
    _make_rfp_fact = _build_rfp_fact_factory(ocr_degraded, source_quotes)
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
