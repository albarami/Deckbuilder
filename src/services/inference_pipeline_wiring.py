"""Pipeline wiring for generated_inference services — Slice 5.5.

Three helpers, each turning a Slice-5 service output into
``ClaimProvenance(claim_kind="generated_inference")`` entries on
``state.claim_registry``:

* :func:`register_portal_inference` — runs the portal guard. Explicit
  body/table portal mentions become rfp_fact claims (the portal IS
  what the RFP says); inferred / default placeholders register a
  generated_inference with ``inference_allowed_context``
  restricted to ``["internal_bid_notes"]`` so the placeholder cannot
  reach client-facing text.

* :func:`classify_extracted_deliverables` — walks
  ``state.rfp_context.deliverables`` and reflects each item as an
  rfp_fact ClaimProvenance with the correct ``deliverable_origin``.
  When the origin is non-formal (scope_clause / special_condition),
  the id is normalized to a workstream prefix and a generated_inference
  records the reclassification.

* :func:`resolve_extracted_field_conflicts` — for every
  ``SourceConflict`` whose ``requires_clarification`` is True,
  registers a generated_inference noting the unresolved disagreement
  with limited contexts so it never lands in client-facing text.

:func:`wire_generated_inferences` chains all three.
"""
from __future__ import annotations

from src.models.claim_provenance import (
    ClaimProvenance,
    SourceReference,
)
from src.models.state import DeckForgeState
from src.services.deliverable_classifier import (
    DeliverableClassification,
    normalize_to_workstream_id,
)
from src.services.portal_inference_guard import (
    ExtractedTextSpan,
    PortalExtraction,
    extract_portal,
)
from src.services.source_hierarchy_conflict import SourceConflict


# ── Portal wiring ─────────────────────────────────────────────────────


def register_portal_inference(
    state: DeckForgeState,
    spans: list[ExtractedTextSpan],
) -> PortalExtraction:
    """Run portal guard on ``spans`` and reflect the outcome onto
    ``state.claim_registry``.

    * ``explicit_submission_clause`` → register an ``rfp_fact``
      ClaimProvenance for the portal name.
    * any other confidence → register a labelled
      ``generated_inference`` with
      ``inference_allowed_context=["internal_bid_notes"]`` so the
      placeholder is never published client-side.
    """
    portal = extract_portal(spans)

    if portal.portal_confidence == "explicit_submission_clause":
        state.claim_registry.register(ClaimProvenance(
            claim_id=f"RFP-FACT-PORTAL-{portal.portal_name[:32]}",
            text=f"Portal: {portal.portal_name}",
            claim_kind="rfp_fact",
            source_kind="rfp_document",
            verification_status="verified_from_rfp",
            evidence_role="requirement_source",
            source_refs=[SourceReference(
                file="rfp",
                clause=portal.source_clause or "submission_clause",
            )],
        ))
        return portal

    # Inferred / unknown → labelled generated_inference, internal-only.
    note = (
        "Portal inferred (no explicit submission clause). "
        f"Default placeholder: {portal.portal_name}"
    )
    if portal.inferred_from_logo:
        note += " — brand seen only in logo/header/footer/watermark."
    state.claim_registry.register(ClaimProvenance(
        claim_id="INFERRED-PORTAL-001",
        text=note,
        claim_kind="generated_inference",
        source_kind="model_generated",
        verification_status="generated_inference",
        evidence_role="risk_or_assumption_support",
        inference_label_present=True,
        inference_allowed_context=["internal_bid_notes"],
        requires_clarification=True,
    ))
    return portal


# ── Deliverable wiring ───────────────────────────────────────────────


def classify_extracted_deliverables(
    state: DeckForgeState,
    *,
    origins: dict[str, str] | None = None,
    default_origin: str = "deliverables_annex",
) -> list[DeliverableClassification]:
    """Reflect each ``state.rfp_context.deliverables`` item as a
    properly-classified rfp_fact ClaimProvenance.

    The optional ``origins`` map (``{deliverable_id: origin_str}``)
    tags items the bid team / future agent has placed in scope-clause
    or special-condition buckets. Unspecified items fall back to
    ``default_origin`` which is ``deliverables_annex`` (formal). When
    normalization rewrites a D-N id to a workstream prefix, a
    generated_inference is emitted recording the reclassification so
    the bid team can audit the move.
    """
    origins = origins or {}
    if state.rfp_context is None:
        return []

    classifications: list[DeliverableClassification] = []

    for d in state.rfp_context.deliverables:
        descr_en = (d.description.en or "").strip()
        descr_ar = (d.description.ar or "").strip()
        name = descr_en or descr_ar or d.id
        origin = origins.get(d.id, default_origin)

        new_id = normalize_to_workstream_id(d.id, name, origin)
        classification = DeliverableClassification(
            id=new_id,
            name=name,
            origin=origin,  # type: ignore[arg-type]
        )
        classifications.append(classification)

        # Remove the old (formal) rfp_fact entry if Slice 1.5 already
        # created one under D-* and the id has now been normalized.
        if new_id != d.id:
            old_claim_id = f"RFP-FACT-DELIV-{d.id}"
            if old_claim_id in state.claim_registry.claims:
                # Pydantic dict — pop in place.
                state.claim_registry.claims.pop(old_claim_id, None)

        state.claim_registry.register(ClaimProvenance(
            claim_id=f"RFP-FACT-DELIV-{new_id}",
            text=f"Deliverable {new_id}: {name}",
            claim_kind="rfp_fact",
            source_kind="rfp_document",
            verification_status="verified_from_rfp",
            evidence_role="requirement_source",
            deliverable_origin=origin,  # type: ignore[arg-type]
            source_refs=[SourceReference(
                file="rfp",
                clause=f"deliverables[{d.id}]",
            )],
        ))

        if new_id != d.id:
            state.claim_registry.register(ClaimProvenance(
                claim_id=f"INFERENCE-DELIV-{d.id}-RENAME",
                text=(
                    f"Deliverable id {d.id} normalized to {new_id} because "
                    f"origin={origin!r} is not formal "
                    f"(boq_line/deliverables_annex)."
                ),
                claim_kind="generated_inference",
                source_kind="model_generated",
                verification_status="generated_inference",
                evidence_role="risk_or_assumption_support",
                inference_label_present=True,
                inference_allowed_context=["internal_bid_notes"],
            ))
    return classifications


# ── Source-hierarchy conflict wiring ─────────────────────────────────


def resolve_extracted_field_conflicts(
    state: DeckForgeState,
    *,
    conflicts: list[SourceConflict],
) -> list[ClaimProvenance]:
    """For every ``SourceConflict`` whose ``requires_clarification`` is
    True, register a labelled ``generated_inference`` with restricted
    contexts so it cannot be published client-side without explicit
    bid-team approval.
    """
    out: list[ClaimProvenance] = []
    for i, conflict in enumerate(conflicts):
        if not conflict.requires_clarification:
            continue
        claim = ClaimProvenance(
            claim_id=f"INFERENCE-CONFLICT-{conflict.field}-{i:03d}",
            text=(
                f"Source conflict on field {conflict.field!r} requires "
                f"clarification: {conflict.value_a!r} ({conflict.source_a}) "
                f"vs {conflict.value_b!r} ({conflict.source_b}). "
                f"{conflict.conflict_note}"
            ),
            claim_kind="generated_inference",
            source_kind="model_generated",
            verification_status="generated_inference",
            evidence_role="risk_or_assumption_support",
            inference_label_present=True,
            inference_allowed_context=["internal_bid_notes"],
            requires_clarification=True,
        )
        state.claim_registry.register(claim)
        out.append(claim)
    return out


# ── Combined wiring entry point ──────────────────────────────────────


def wire_generated_inferences(
    state: DeckForgeState,
    *,
    portal_spans: list[ExtractedTextSpan] | None = None,
    deliverable_origins: dict[str, str] | None = None,
    conflicts: list[SourceConflict] | None = None,
) -> None:
    """Convenience entry: runs all three Slice-5.5 helpers in order.

    Each input is optional — passing None / empty leaves that bucket
    untouched. The pipeline node uses this entry point so the wiring
    is idempotent across passes.
    """
    if portal_spans is not None:
        register_portal_inference(state, portal_spans)
    classify_extracted_deliverables(state, origins=deliverable_origins or {})
    resolve_extracted_field_conflicts(state, conflicts=conflicts or [])
