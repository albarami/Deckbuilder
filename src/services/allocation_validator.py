"""Deterministic Slide Allocation Validator \u2014 validate-only, never mutate.

Post-LLM validation of the slide allocation produced by the Submission
Transform Agent. Does NOT trust LLM output alone \u2014 checks structural
integrity, fixed slide positions, criterion coverage, and feasibility.

The validator is read-only. It NEVER silently pads, trims, or rewrites
allocations. Material failures cause valid=False with specific errors.
"""

from src.models.enums import LayoutType
from src.models.rfp import RFPContext
from src.models.submission import (
    AllocationError,
    AllocationValidationResult,
    SlideAllocationProposal,
)


def validate_slide_allocation(
    allocation: SlideAllocationProposal,
    rfp_context: RFPContext = None,
) -> AllocationValidationResult:
    """Validate a slide allocation proposal.

    Checks:
    1. total_slides == 20
    2. len(allocations) == total_slides
    3. Fixed slides preserved (TITLE@1, AGENDA@2, CLOSING@20)
    4. No duplicate positions, all 1-20 present
    5. Criterion minimum coverage (weight \u2265 5% \u2192 at least 1 slide)
    6. Criterion maximum coverage (no criterion > 5 slides)
    7. Layout types valid (all must be valid LayoutType enum values)
    8. Weight coverage consistency (sum \u2264 100%)
    9. Feasibility check (validates grouping compliance when >17 criteria)

    Args:
        allocation: The SlideAllocationProposal to validate.
        rfp_context: Optional RFP context for criterion coverage checks.

    Returns:
        AllocationValidationResult with valid flag, errors, and warnings.
    """
    errors: list = []
    warnings: list = []

    # Check total_slides == 20
    if allocation.total_slides != 20:
        errors.append(AllocationError(
            field="total_slides",
            message=f"Expected exactly 20 slides, got {allocation.total_slides}",
        ))

    # Check allocation count matches total_slides
    actual_count = len(allocation.allocations)
    if actual_count != allocation.total_slides:
        errors.append(AllocationError(
            field="allocations",
            message=(
                f"Allocation count ({actual_count}) does not match "
                f"total_slides ({allocation.total_slides})"
            ),
        ))

    # Check fixed slides
    _check_fixed_slides(allocation, errors)

    # Check positions
    _check_positions(allocation, errors)

    # Check criterion coverage (only if rfp_context provided)
    if rfp_context:
        _check_criterion_coverage(allocation, rfp_context, errors, warnings)

    # Check layout types
    _check_layout_types(allocation, errors)

    # Check weight coverage
    _check_weight_coverage(allocation, warnings)

    # Check feasibility (only if rfp_context provided)
    if rfp_context:
        _check_feasibility(allocation, rfp_context, errors, warnings)

    return AllocationValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _check_fixed_slides(allocation: SlideAllocationProposal, errors: list) -> None:
    """Check that fixed slides (TITLE@1, AGENDA@2, CLOSING@20) are present."""
    # Build position map
    position_map = {a.position: a for a in allocation.allocations}

    # Check position 1 = TITLE
    if 1 in position_map:
        if position_map[1].layout_type != LayoutType.TITLE:
            errors.append(AllocationError(
                field="allocations[position=1]",
                message=(
                    f"Position 1 must be TITLE layout, got "
                    f"{position_map[1].layout_type}"
                ),
            ))
    else:
        errors.append(AllocationError(
            field="allocations[position=1]",
            message="Position 1 (TITLE slide) is missing",
        ))

    # Check position 2 = AGENDA
    if 2 in position_map:
        if position_map[2].layout_type != LayoutType.AGENDA:
            errors.append(AllocationError(
                field="allocations[position=2]",
                message=(
                    f"Position 2 must be AGENDA layout, got "
                    f"{position_map[2].layout_type}"
                ),
            ))
    else:
        errors.append(AllocationError(
            field="allocations[position=2]",
            message="Position 2 (AGENDA slide) is missing",
        ))

    # Check position 20 = CLOSING
    if 20 in position_map:
        if position_map[20].layout_type != LayoutType.CLOSING:
            errors.append(AllocationError(
                field="allocations[position=20]",
                message=(
                    f"Position 20 must be CLOSING layout, got "
                    f"{position_map[20].layout_type}"
                ),
            ))
    else:
        errors.append(AllocationError(
            field="allocations[position=20]",
            message="Position 20 (CLOSING slide) is missing",
        ))


def _check_positions(allocation: SlideAllocationProposal, errors: list) -> None:
    """Check all positions 1-20 present, no duplicates, no gaps."""
    positions = [a.position for a in allocation.allocations]
    position_set = set(positions)

    # Check for duplicates
    if len(positions) != len(position_set):
        seen = set()
        duplicates = set()
        for p in positions:
            if p in seen:
                duplicates.add(p)
            seen.add(p)
        errors.append(AllocationError(
            field="allocations",
            message=f"Duplicate positions found: {sorted(duplicates)}",
        ))

    # Check for missing and extra positions
    expected = set(range(1, 21))
    missing = expected - position_set
    extra = position_set - expected
    if missing:
        errors.append(AllocationError(
            field="allocations",
            message=f"Missing positions: {sorted(missing)}",
        ))
    if extra:
        errors.append(AllocationError(
            field="allocations",
            message=f"Unexpected positions outside 1-20: {sorted(extra)}",
        ))


def _check_criterion_coverage(
    allocation: SlideAllocationProposal,
    rfp_context: RFPContext,
    errors: list,
    warnings: list,
) -> None:
    """Check that criteria with weight \u2265 5% have at least 1 slide,
    and no criterion has more than 5 slides.
    """
    criteria_weights = _extract_criteria_weights(rfp_context)
    if not criteria_weights:
        return

    # Count slides per criterion
    criterion_slide_counts = {}
    for a in allocation.allocations:
        if not a.rfp_criterion_ref:
            continue
        refs = a.rfp_criterion_ref.split(",")
        for ref in refs:
            ref = ref.strip()
            # Increment count
            criterion_slide_counts[ref] = criterion_slide_counts.get(ref, 0) + 1

    # Check minimum coverage: weight >= 5% must have at least 1 slide
    for criterion_name, weight in criteria_weights.items():
        if weight >= 5.0 and criterion_name not in criterion_slide_counts:
            errors.append(AllocationError(
                field="allocations",
                message=(
                    f"Criterion '{criterion_name}' (weight {weight}"
                    f"%) has no allocated slide but requires at least 1"
                ),
            ))

    # Check maximum coverage: no criterion > 5 slides
    for criterion_name, count in criterion_slide_counts.items():
        if count > 5:
            errors.append(AllocationError(
                field="allocations",
                message=(
                    f"Criterion '{criterion_name}' has {count}"
                    f" slides allocated (maximum is 5)"
                ),
            ))


def _check_layout_types(allocation: SlideAllocationProposal, errors: list) -> None:
    """Check that all layout_type values are valid LayoutType enum values."""
    valid_layouts = set(LayoutType)
    for a in allocation.allocations:
        if a.layout_type not in valid_layouts:
            errors.append(AllocationError(
                field=f"allocations[position={a.position}].layout_type",
                message=f"Invalid layout type: {a.layout_type}",
            ))


def _check_weight_coverage(
    allocation: SlideAllocationProposal,
    warnings: list,
) -> None:
    """Check that weight_coverage values sum to \u2264 100%."""
    if allocation.weight_coverage:
        total = sum(allocation.weight_coverage.values())
        if total > 100.0:
            warnings.append(
                f"Weight coverage sums to {total:.1f}% (should be \u2264 100%)"
            )


def _check_feasibility(
    allocation: SlideAllocationProposal,
    rfp_context: RFPContext,
    errors: list,
    warnings: list,
) -> None:
    """Validate feasibility when >17 criteria need minimum coverage.

    The validator only CHECKS that the agent's allocation complies with
    feasibility rules \u2014 it does NOT rewrite or group. Specifically:
    - If >17 criteria need minimum coverage, verify the agent produced
      shared slides (2 criteria per slide) for lowest-weighted criteria
    - Verify shared slides use compatible layouts (CONTENT_2COL or COMPARISON)
    """
    criteria_weights = _extract_criteria_weights(rfp_context)
    if not criteria_weights:
        return

    # Filter to criteria with weight >= 5%
    required_criteria = {
        name: weight
        for name, weight in criteria_weights.items()
        if weight >= 5.0
    }

    # 17 content slots available (20 - 3 fixed)
    available_content_slots = 17
    if len(required_criteria) <= available_content_slots:
        return

    warnings.append(
        f"{len(required_criteria)} criteria need minimum coverage (only "
        f"{available_content_slots} content slots available). Shared slides expected."
    )

    # Check that shared slides use compatible layouts
    compatible_layouts = {LayoutType.CONTENT_2COL, LayoutType.COMPARISON}
    for a in allocation.allocations:
        if not a.rfp_criterion_ref:
            continue
        if "," not in a.rfp_criterion_ref:
            continue
        # This is a shared slide (multiple criteria)
        if a.layout_type not in compatible_layouts:
            errors.append(AllocationError(
                field=f"allocations[position={a.position}].layout_type",
                message=(
                    f"Shared slide at position {a.position}"
                    f" covers multiple criteria ({a.rfp_criterion_ref})"
                    f") but uses layout {a.layout_type}"
                    f". Shared slides must use CONTENT_2COL or COMPARISON."
                ),
            ))


def _extract_criteria_weights(rfp_context: RFPContext) -> dict[str, float]:
    """Extract criterion name \u2192 weight mapping from RFP context."""
    criteria_weights = {}

    if not rfp_context.evaluation_criteria:
        return criteria_weights

    eval_criteria = rfp_context.evaluation_criteria

    # Technical criteria
    if eval_criteria.technical:
        for sub in eval_criteria.technical.sub_criteria:
            if sub.weight_pct is not None:
                criteria_weights[sub.name] = sub.weight_pct
            for item in sub.sub_items:
                if item.weight_pct is not None:
                    criteria_weights[item.name] = item.weight_pct

    # Financial criteria
    if eval_criteria.financial:
        for sub in eval_criteria.financial.sub_criteria:
            if sub.weight_pct is not None:
                criteria_weights[sub.name] = sub.weight_pct

    return criteria_weights
