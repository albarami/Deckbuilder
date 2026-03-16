"""Evidence Provenance Checker — M10.8.

Deterministic cross-reference checker that verifies evidence bundles
referenced by slides are not PLACEHOLDER on proof-bearing layouts.

This is a pre-render validation — it runs inside submission_qa alongside
lint and density checks. It NEVER mutates slides or evidence bundles.
"""

from __future__ import annotations

from src.models.enums import (
    DeckMode,
    DensityViolationSeverity,
    EvidenceStrength,
    LayoutType,
)
from src.models.slides import SlideObject
from src.models.submission import (
    EvidenceBundle,
    EvidenceProvenanceResult,
    ProvenanceIssue,
    SlideBrief,
)

# Layouts that carry proof claims and need real evidence
_PROOF_LAYOUTS: frozenset[LayoutType] = frozenset({
    LayoutType.CONTENT_1COL,
    LayoutType.CONTENT_2COL,
    LayoutType.STAT_CALLOUT,
    LayoutType.COMPARISON,
    LayoutType.COMPLIANCE_MATRIX,
    LayoutType.FRAMEWORK,
    LayoutType.TEAM,
    LayoutType.TIMELINE,
})

# Structural layouts that never carry evidence
_STRUCTURAL_LAYOUTS: frozenset[LayoutType] = frozenset({
    LayoutType.TITLE,
    LayoutType.AGENDA,
    LayoutType.SECTION,
    LayoutType.CLOSING,
})

BLOCKER = DensityViolationSeverity.BLOCKER
WARNING = DensityViolationSeverity.WARNING
INFO = DensityViolationSeverity.INFO


def check_evidence_provenance(
    *,
    slides: list[SlideObject],
    evidence_bundles: list[EvidenceBundle],
    briefs: list[SlideBrief] | None,
    deck_mode: DeckMode,
) -> EvidenceProvenanceResult:
    """Check evidence provenance for all slides.

    Cross-references slide.evidence_bundle_refs against evidence bundle
    strength. PLACEHOLDER bundles on proof layouts produce BLOCKERs in
    CLIENT_SUBMISSION mode.

    Args:
        slides: List of SlideObject to check.
        evidence_bundles: All available evidence bundles.
        briefs: Optional slide briefs for fallback bundle refs.
        deck_mode: CLIENT_SUBMISSION or INTERNAL_REVIEW.

    Returns:
        EvidenceProvenanceResult with issues, counts, and summary.
    """
    if not slides:
        return EvidenceProvenanceResult(summary="No slides to check")

    # Build lookup maps
    bundle_map = {
        eb.bundle_id: eb for eb in (evidence_bundles or [])
    }

    brief_map = {}
    if briefs:
        brief_map = {b.slide_id: b for b in briefs}

    is_client = deck_mode == DeckMode.CLIENT_SUBMISSION
    issues = []

    for slide in slides:
        # Skip structural layouts
        if slide.layout_type in _STRUCTURAL_LAYOUTS:
            continue

        # Get bundle refs from slide, fallback to brief
        bundle_refs = slide.evidence_bundle_refs
        if not bundle_refs and slide.slide_id in brief_map:
            bundle_refs = brief_map[slide.slide_id].evidence_bundle_refs

        if not bundle_refs:
            continue

        is_proof = slide.layout_type in _PROOF_LAYOUTS

        for bundle_id in bundle_refs:
            bundle = bundle_map.get(bundle_id)

            if bundle is None:
                # Orphan reference
                issues.append(
                    ProvenanceIssue(
                        slide_id=slide.slide_id,
                        bundle_id=bundle_id,
                        bundle_strength=EvidenceStrength.PLACEHOLDER,
                        rule="orphan_bundle_ref",
                        severity=WARNING if is_client else INFO,
                        message=f"Bundle {bundle_id} referenced by "
                                f"{slide.slide_id} not found in evidence bundles.",
                    )
                )
                continue

            if bundle.strength != EvidenceStrength.PLACEHOLDER:
                continue

            # PLACEHOLDER bundle found
            if is_proof:
                issues.append(
                    ProvenanceIssue(
                        slide_id=slide.slide_id,
                        bundle_id=bundle_id,
                        bundle_strength=bundle.strength,
                        rule="placeholder_on_proof_slide",
                        severity=BLOCKER if is_client else WARNING,
                        message=f"PLACEHOLDER bundle {bundle_id} on proof slide "
                                f"{slide.slide_id} ({slide.layout_type}).",
                    )
                )
            else:
                issues.append(
                    ProvenanceIssue(
                        slide_id=slide.slide_id,
                        bundle_id=bundle_id,
                        bundle_strength=bundle.strength,
                        rule="placeholder_on_content_slide",
                        severity=WARNING if is_client else INFO,
                        message=f"PLACEHOLDER bundle {bundle_id} on content slide "
                                f"{slide.slide_id} ({slide.layout_type}).",
                    )
                )

    blocker_count = sum(1 for i in issues if i.severity == BLOCKER)
    warning_count = sum(1 for i in issues if i.severity == WARNING)

    summary_parts = [f"Provenance: {blocker_count}B/{warning_count}W"]
    if blocker_count > 0:
        blocker_ids = list(
            dict.fromkeys(
                i.slide_id for i in issues if i.severity == BLOCKER
            )
        )
        summary_parts.append(f"blockers on: {', '.join(blocker_ids)}")

    return EvidenceProvenanceResult(
        issues=issues,
        blocker_count=blocker_count,
        warning_count=warning_count,
        summary=" | ".join(summary_parts),
    )
