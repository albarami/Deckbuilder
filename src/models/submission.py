"""Submission Transformation Layer models — M10.6.

Data structures for the Submission Transformation Layer that converts
the internal Research Report into a client-ready Submission Source Pack.
"""

from dataclasses import dataclass

from pydantic import Field

from .common import DeckForgeBaseModel
from .enums import (
    BlockerType,
    BundleType,
    CompositionRuleCategory,
    ContentRouting,
    DensityBudget,
    DensityViolationSeverity,
    EvidenceStrength,
    LayoutType,
    LintSeverity,
    NoteSeverity,
    SlideTone,
    SubmissionQAStatus,
)


class ContentUnit(DeckForgeBaseModel):
    """Atomic routed content piece extracted from the Research Report."""

    unit_id: str
    content: str
    routing: ContentRouting
    source_claims: list[str] = Field(default_factory=list)
    evidence_bundle_ref: str = ""
    routing_reason: str = ""
    original_section_ref: str = ""


class EvidenceBundle(DeckForgeBaseModel):
    """Grouped evidence structure for richer slide writing."""

    bundle_id: str
    bundle_type: BundleType
    title: str
    content_unit_refs: list[str] = Field(default_factory=list)
    source_claims: list[str] = Field(default_factory=list)
    strength: EvidenceStrength = EvidenceStrength.MODERATE
    notes: str = ""


class SlideAllocation(DeckForgeBaseModel):
    """Dynamic allocation entry for a single slide position."""

    position: int
    purpose: str
    rfp_criterion_ref: str | None = None
    weight_pct: float = 0.0
    layout_type: LayoutType
    rationale: str = ""


class SlideAllocationProposal(DeckForgeBaseModel):
    """Dynamic 20-slide allocation weighted by RFP evaluation criteria."""

    allocations: list[SlideAllocation] = Field(default_factory=list)
    total_slides: int = 20
    weight_coverage: dict[str, float] = Field(default_factory=dict)


class SlideBrief(DeckForgeBaseModel):
    """Structured brief for a single slide — generated before drafting."""

    slide_position: int
    slide_id: str
    objective: str
    rfp_criterion_ref: str | None = None
    criterion_weight_pct: float = 0.0
    audience_note: str = ""
    key_message: str = ""
    evidence_bundle_refs: list[str] = Field(default_factory=list)
    content_unit_refs: list[str] = Field(default_factory=list)
    prohibited_content: list[str] = Field(default_factory=list)
    layout_type: LayoutType = LayoutType.CONTENT_1COL
    density_budget: DensityBudget = DensityBudget.STANDARD
    tone: SlideTone = SlideTone.PROFESSIONAL
    internal_note_allowance: bool = True


class SubmissionSourcePack(DeckForgeBaseModel):
    """Complete output of the Submission Transformation Layer."""

    content_units: list[ContentUnit] = Field(default_factory=list)
    evidence_bundles: list[EvidenceBundle] = Field(default_factory=list)
    slide_allocation: SlideAllocationProposal = Field(
        default_factory=SlideAllocationProposal
    )
    slide_briefs: list[SlideBrief] = Field(default_factory=list)


class InternalNote(DeckForgeBaseModel):
    """Internal-only note for workflow commentary, not client-facing."""

    note_id: str
    context: str
    note_text: str
    severity: NoteSeverity = NoteSeverity.INFO


class InternalNotePack(DeckForgeBaseModel):
    """Collection of internal notes from the transformation process."""

    notes: list[InternalNote] = Field(default_factory=list)


class UnresolvedIssue(DeckForgeBaseModel):
    """An issue that must be resolved before client submission."""

    issue_id: str
    description: str
    blocker_type: BlockerType
    affected_slides: list[str] = Field(default_factory=list)
    resolution_action: str = ""
    resolved: bool = False


class UnresolvedIssueRegistry(DeckForgeBaseModel):
    """Registry of unresolved issues — blocks client export if has_blockers."""

    issues: list[UnresolvedIssue] = Field(default_factory=list)
    has_blockers: bool = False


class LintIssue(DeckForgeBaseModel):
    """A single language lint issue found in slide text."""

    slide_id: str
    location: str
    matched_text: str
    rule: str
    severity: LintSeverity
    suggestion: str = ""


class LanguageLintResult(DeckForgeBaseModel):
    """Aggregated result from the proposal language linter."""

    issues: list[LintIssue] = Field(default_factory=list)
    blocker_count: int = 0
    warning_count: int = 0
    is_client_ready: bool = True


class DensityViolation(DeckForgeBaseModel):
    """A single density budget violation on a slide."""

    field: str
    actual: int
    limit: int
    severity: DensityViolationSeverity
    message: str


class SplitSuggestion(DeckForgeBaseModel):
    """Advisory suggestion to split an overloaded slide."""

    source_slide_id: str
    reason: str
    suggested_split_point: int
    estimated_slide_a_chars: int
    estimated_slide_b_chars: int


class CompressionSuggestion(DeckForgeBaseModel):
    """Advisory suggestion to compress a single bullet."""

    slide_id: str
    bullet_index: int
    original_text: str
    compressed_text: str
    chars_saved: int
    rule_applied: str


class SlideDensityScore(DeckForgeBaseModel):
    """Density score for a single slide."""

    slide_id: str
    layout_type: LayoutType
    density_budget: DensityBudget
    bullet_count: int
    total_chars: int
    max_bullet_chars: int
    budget_utilization_pct: float
    violations: list[DensityViolation] = Field(default_factory=list)
    split_suggestion: SplitSuggestion | None = None
    compression_suggestions: list[CompressionSuggestion] = Field(
        default_factory=list
    )
    passes: bool = True


class DensityResult(DeckForgeBaseModel):
    """Deck-level density scoring result."""

    slide_scores: list[SlideDensityScore] = Field(default_factory=list)
    total_violations: int = 0
    blocker_count: int = 0
    warning_count: int = 0
    slides_over_budget: int = 0
    split_suggestions_count: int = 0
    is_within_budget: bool = True
    summary: str = ""


class SubmissionQAResult(DeckForgeBaseModel):
    """Complete output of the Submission QA agent."""

    language_lint: LanguageLintResult = Field(
        default_factory=LanguageLintResult
    )
    density_result: DensityResult | None = None
    evidence_provenance: "EvidenceProvenanceResult | None" = None
    composition_result: "CompositionResult | None" = None
    unresolved_issues: UnresolvedIssueRegistry = Field(
        default_factory=UnresolvedIssueRegistry
    )
    status: SubmissionQAStatus = SubmissionQAStatus.READY
    summary: str = ""


class AllocationError(DeckForgeBaseModel):
    """A single allocation validation error."""

    field: str
    message: str


class AllocationValidationResult(DeckForgeBaseModel):
    """Result of deterministic slide allocation validation."""

    valid: bool
    errors: list[AllocationError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class ShapeInfo:
    """Extracted shape data from a rendered PPTX slide. Immutable snapshot."""

    shape_name: str
    shape_type: int
    left_in: float
    top_in: float
    width_in: float
    height_in: float
    has_text: bool = False
    text_content: str = ""
    font_sizes_pt: tuple[int, ...] = ()
    font_names: tuple[str, ...] = ()
    is_placeholder: bool = False
    placeholder_idx: int | None = None
    is_table: bool = False
    table_rows: int = 0
    table_cols: int = 0
    is_decorative: bool = False


class CompositionViolation(DeckForgeBaseModel):
    """A single composition rule violation on a slide."""

    slide_id: str
    rule: str
    category: CompositionRuleCategory
    severity: DensityViolationSeverity
    message: str
    shape_a: str = ""
    shape_b: str = ""
    actual_value: float = 0.0
    threshold: float = 0.0


class SlideCompositionScore(DeckForgeBaseModel):
    """Composition score for a single slide."""

    slide_id: str
    layout_type: LayoutType
    shape_count: int
    violations: list[CompositionViolation] = Field(default_factory=list)
    passes: bool = True


class CompositionResult(DeckForgeBaseModel):
    """Deck-level composition scoring result."""

    slide_scores: list[SlideCompositionScore] = Field(default_factory=list)
    total_violations: int = 0
    blocker_count: int = 0
    warning_count: int = 0
    slides_failing: int = 0
    failing_slide_ids: list[str] = Field(default_factory=list)
    top_rule_categories: list[str] = Field(default_factory=list)
    is_composition_clean: bool = True
    summary: str = ""


class ProvenanceIssue(DeckForgeBaseModel):
    """A single evidence provenance issue on a slide."""

    slide_id: str
    bundle_id: str
    bundle_strength: EvidenceStrength
    rule: str
    severity: DensityViolationSeverity
    message: str


class EvidenceProvenanceResult(DeckForgeBaseModel):
    """Result of evidence provenance checking."""

    issues: list[ProvenanceIssue] = Field(default_factory=list)
    blocker_count: int = 0
    warning_count: int = 0
    summary: str = ""
