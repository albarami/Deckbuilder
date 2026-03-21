"""G2 Filler Output Schemas — structured, typed output for all section fillers.

Every filler output must be a Pydantic-validated structured object that maps
directly to template placeholder indices.  No free-form text.  No paragraphs.
Every ``list[dict]`` is banned — use typed submodels only.

Reference: docs/plans/2026-03-20-phase-g2-filler-output-schema.md (approved)
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Constants ────────────────────────────────────────────────────────────

APPROVED_ENGLISH_TERMS = frozenset({
    "Strategic Gears", "SAP", "Oracle", "Microsoft", "Azure", "AWS",
    "TOGAF", "ITIL", "COBIT", "PMP", "ISO", "KPI", "API", "SLA",
    "PMO", "ERP", "CRM", "AI", "IoT", "RPA", "MBA", "PhD",
})

ESSAY_TRANSITIONS = frozenset({
    "in addition", "furthermore", "moreover", "it is worth noting",
    "it should be noted", "as mentioned", "additionally", "consequently",
    "nevertheless", "notwithstanding",
})


# ── Shared validators ────────────────────────────────────────────────────


def _validate_bullet_items(items: list[str]) -> list[str]:
    """Shared bullet validation: word count + essay transition check."""
    for bullet in items:
        word_count = len(bullet.split())
        if word_count > 25:
            raise ValueError(f"Bullet exceeds 25 words: {word_count}")
        lower = bullet.lower().strip()
        for transition in ESSAY_TRANSITIONS:
            if lower.startswith(transition):
                raise ValueError(f"Essay transition detected: '{transition}'")
    return items


def contains_unapproved_english(
    text: str, language: Literal["en", "ar"],
) -> bool:
    """Check if Arabic-mode text contains unapproved English words."""
    if language != "ar":
        return False
    english_words = re.findall(r"[a-zA-Z]{2,}", text)
    for word in english_words:
        if (
            word not in APPROVED_ENGLISH_TERMS
            and word.upper() not in APPROVED_ENGLISH_TERMS
        ):
            return True
    return False


# ── Section-specific bullet list types ───────────────────────────────────
# Each enforces its own min/max item count at the schema level.


class BulletList(BaseModel):
    """Generic bullet list: 2..6 items, 25 words max per bullet."""

    items: list[str] = Field(min_length=2, max_length=6)

    @field_validator("items")
    @classmethod
    def validate_bullets(cls, v: list[str]) -> list[str]:
        return _validate_bullet_items(v)


class Bullets_2_3(BaseModel):
    """Constrained bullet list: 2..3 items."""

    items: list[str] = Field(min_length=2, max_length=3)

    @field_validator("items")
    @classmethod
    def validate_bullets(cls, v: list[str]) -> list[str]:
        return _validate_bullet_items(v)


class Bullets_2_4(BaseModel):
    """Constrained bullet list: 2..4 items."""

    items: list[str] = Field(min_length=2, max_length=4)

    @field_validator("items")
    @classmethod
    def validate_bullets(cls, v: list[str]) -> list[str]:
        return _validate_bullet_items(v)


class Bullets_3_4(BaseModel):
    """Constrained bullet list: 3..4 items."""

    items: list[str] = Field(min_length=3, max_length=4)

    @field_validator("items")
    @classmethod
    def validate_bullets(cls, v: list[str]) -> list[str]:
        return _validate_bullet_items(v)


class Bullets_3_5(BaseModel):
    """Constrained bullet list: 3..5 items."""

    items: list[str] = Field(min_length=3, max_length=5)

    @field_validator("items")
    @classmethod
    def validate_bullets(cls, v: list[str]) -> list[str]:
        return _validate_bullet_items(v)


class Bullets_4_6(BaseModel):
    """Constrained bullet list: 4..6 items."""

    items: list[str] = Field(min_length=4, max_length=6)

    @field_validator("items")
    @classmethod
    def validate_bullets(cls, v: list[str]) -> list[str]:
        return _validate_bullet_items(v)


# ── Base slide and filler types ──────────────────────────────────────────


class SlideOutput(BaseModel):
    """Single slide output from any filler.  Title max 10 words."""

    title: str = Field(max_length=80, description="Slide title - max 10 words")

    @field_validator("title")
    @classmethod
    def validate_title_length(cls, v: str) -> str:
        if len(v.split()) > 10:
            raise ValueError(f"Title exceeds 10 words: {len(v.split())}")
        return v


class FillerOutput(BaseModel):
    """Base output for all section fillers."""

    section_id: str
    language: Literal["en", "ar"]


# ── Introduction Message ─────────────────────────────────────────────────


class IntroMessageSlide(BaseModel):
    """Introduction message - multi-field engagement card.

    Title override: engagement titles may be up to 12 words (longer than
    the standard 10-word limit) because they include the full project name.
    Does NOT inherit from SlideOutput (which enforces 10-word limit).
    """

    title: str = Field(
        max_length=120, description="Engagement title - max 12 words",
    )
    client_name: str = Field(
        max_length=60, description="Client organization full name",
    )
    scope_line: str = Field(
        max_length=100, description="1-line engagement scope, max 15 words",
    )
    attr_duration: str = Field(max_length=30, description='e.g., "16 weeks"')
    attr_sector: str = Field(
        max_length=30, description='e.g., "Government / ICT"',
    )
    attr_geography: str = Field(
        max_length=30, description='e.g., "KSA - Riyadh"',
    )
    attr_service_line: str = Field(
        max_length=30, description='e.g., "Digital Transformation Advisory"',
    )

    @field_validator("title")
    @classmethod
    def validate_intro_title_length(cls, v: str) -> str:
        """Allow up to 12 words for engagement titles."""
        if len(v.split()) > 12:
            raise ValueError(
                f"Intro title exceeds 12 words: {len(v.split())}",
            )
        return v

    @field_validator("scope_line")
    @classmethod
    def validate_scope_words(cls, v: str) -> str:
        if len(v.split()) > 15:
            raise ValueError(
                f"Scope line exceeds 15 words: {len(v.split())}",
            )
        return v


class IntroMessageOutput(FillerOutput):
    """Full intro message filler output."""

    slide: IntroMessageSlide


# ── Table of Contents ────────────────────────────────────────────────────


class TocRow(BaseModel):
    """Single row in the table of contents."""

    section_number: int = Field(ge=1)
    section_name: str = Field(max_length=60)


class TocSlide(SlideOutput):
    """Table of contents slide."""

    rows: list[TocRow] = Field(min_length=3, max_length=15)


class TocOutput(FillerOutput):
    """Full ToC filler output."""

    slide: TocSlide


# ── Understanding ────────────────────────────────────────────────────────


class TwoColumnSlide(SlideOutput):
    """Understanding Slide 1 - Strategic Context with two evidence columns."""

    left_subtitle: str = Field(max_length=40, description="Left column label")
    left_evidence: Bullets_3_4 = Field(
        description="3-4 evidence points for left column",
    )
    right_subtitle: str = Field(
        max_length=40, description="Right column label",
    )
    right_evidence: Bullets_3_4 = Field(
        description="3-4 evidence points for right column",
    )


class FourBoxSlide(SlideOutput):
    """Understanding Slide 2 - Core Challenges in 4 quadrants."""

    box_1: Bullets_2_3 = Field(description="Challenge cluster 1: 2-3 bullets")
    box_2: Bullets_2_3 = Field(description="Challenge cluster 2: 2-3 bullets")
    box_3: Bullets_2_3 = Field(description="Challenge cluster 3: 2-3 bullets")
    box_4: Bullets_2_3 = Field(description="Challenge cluster 4: 2-3 bullets")


class HeadingDescriptionContentSlide(SlideOutput):
    """Understanding Slide 3 - Success Definition with description + outcomes."""

    description: str = Field(
        max_length=200,
        description="1-2 sentence framing, max 30 words",
    )
    outcomes: Bullets_4_6 = Field(
        description="4-6 measurable outcomes as labeled bullets",
    )

    @field_validator("description")
    @classmethod
    def validate_description_words(cls, v: str) -> str:
        if len(v.split()) > 30:
            raise ValueError(
                f"Description exceeds 30 words: {len(v.split())}",
            )
        return v


class UnderstandingOutput(FillerOutput):
    """Full understanding filler output - 3 slides with distinct layouts."""

    slide_1_strategic_context: TwoColumnSlide
    slide_2_core_challenges: FourBoxSlide
    slide_3_success_definition: HeadingDescriptionContentSlide


# ── Methodology ──────────────────────────────────────────────────────────


class PhaseContent(BaseModel):
    """Content for a single methodology phase."""

    phase_number: int = Field(ge=1, le=5)
    phase_title: str = Field(
        max_length=40, description="Short phase name, max 5 words",
    )
    phase_activities: Bullets_3_5 = Field(
        description="3-5 bullet activities for this phase",
    )

    @field_validator("phase_title")
    @classmethod
    def validate_phase_title_words(cls, v: str) -> str:
        if len(v.split()) > 5:
            raise ValueError(
                f"Phase title exceeds 5 words: {len(v.split())}",
            )
        return v


class MethodologyOverviewSlide(SlideOutput):
    """Methodology overview - grid with up to 4 phases."""

    subtitle: str = Field(
        max_length=60, description="Methodology approach name",
    )
    phases: list[PhaseContent] = Field(
        min_length=3,
        max_length=4,
        description="Phases for the overview grid (max 4)",
    )
    cross_cutting_themes: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Enablers / cross-cutting themes",
    )

    @field_validator("phases")
    @classmethod
    def validate_phase_numbers_in_grid(
        cls, v: list[PhaseContent],
    ) -> list[PhaseContent]:
        numbers = [p.phase_number for p in v]
        if max(numbers) > 4:
            raise ValueError(
                "Overview grid only supports phases 1-4. "
                "Phase 5 uses overflow.",
            )
        if len(set(numbers)) != len(numbers):
            raise ValueError(
                f"Duplicate phase numbers in overview: {numbers}",
            )
        return v


class MethodologyFocusedSlide(SlideOutput):
    """Methodology focused phase - same grid, one phase highlighted."""

    focused_phase_number: int = Field(
        ge=1, le=4,
        description="Which phase is highlighted on this slide",
    )
    subtitle: str = Field(default="", max_length=60)
    phases: list[PhaseContent] = Field(min_length=3, max_length=4)
    cross_cutting_themes: list[str] = Field(
        default_factory=list, max_length=4,
    )

    @field_validator("phases")
    @classmethod
    def validate_focused_phases(
        cls, v: list[PhaseContent],
    ) -> list[PhaseContent]:
        numbers = [p.phase_number for p in v]
        if max(numbers) > 4:
            raise ValueError("Focused grid only supports phases 1-4.")
        return v


class MethodologyDetailSlide(SlideOutput):
    """Methodology detail - 3-column deep dive into a single phase."""

    phase_number: int = Field(ge=1, le=5)
    activities: Bullets_3_5 = Field(description="3-5 specific work items")
    deliverables: Bullets_3_5 = Field(description="3-5 named outputs")
    frameworks: Bullets_2_4 = Field(
        description="2-4 methodologies, standards, or tools",
    )


class MethodologyOutput(FillerOutput):
    """Full methodology filler output.

    Phase count rules (enforced by model_validator):
    - 3 grid phases + no overflow = valid 3-phase engagement
    - 4 grid phases + no overflow = valid 4-phase engagement
    - 4 grid phases + overflow (phase_number=5) = valid 5-phase engagement
    - All other combinations = FAIL
    """

    overview: MethodologyOverviewSlide
    focused_slides: list[MethodologyFocusedSlide] = Field(
        min_length=3,
        max_length=4,
        description="One focused slide per phase in the grid",
    )
    detail_slides: list[MethodologyDetailSlide] = Field(
        min_length=3,
        max_length=4,
        description="Detail slides for phases in the grid",
    )
    phase_5_overflow: MethodologyDetailSlide | None = Field(
        default=None,
        description=(
            "Phase 5 overflow detail slide. "
            "Present ONLY for 5-phase engagements."
        ),
    )

    @model_validator(mode="after")
    def validate_phase_count_consistency(self) -> MethodologyOutput:
        """Enforce exact phase-count rules across all sub-components."""
        grid_phase_count = len(self.overview.phases)
        focused_count = len(self.focused_slides)
        detail_count = len(self.detail_slides)
        has_overflow = self.phase_5_overflow is not None

        if grid_phase_count not in (3, 4):
            raise ValueError(
                f"Overview grid must have 3 or 4 phases, "
                f"got {grid_phase_count}",
            )
        if focused_count != grid_phase_count:
            raise ValueError(
                f"Focused slide count ({focused_count}) must match "
                f"overview phase count ({grid_phase_count})",
            )
        if detail_count != grid_phase_count:
            raise ValueError(
                f"Detail slide count ({detail_count}) must match "
                f"overview phase count ({grid_phase_count})",
            )
        if grid_phase_count == 3 and has_overflow:
            raise ValueError(
                "3-phase engagement must NOT have phase_5_overflow.",
            )
        if grid_phase_count == 4 and has_overflow:
            if self.phase_5_overflow.phase_number != 5:  # type: ignore[union-attr]
                raise ValueError(
                    f"phase_5_overflow must be phase 5, "
                    f"got phase {self.phase_5_overflow.phase_number}",  # type: ignore[union-attr]
                )
        return self

    @model_validator(mode="after")
    def validate_unique_focused_phases(self) -> MethodologyOutput:
        """Each focused slide must highlight a different phase."""
        numbers = [s.focused_phase_number for s in self.focused_slides]
        if len(set(numbers)) != len(numbers):
            raise ValueError(
                f"Duplicate focused phase numbers: {numbers}",
            )
        return self


# ── Timeline & Deliverables ──────────────────────────────────────────────


class TimelinePhaseBlock(BaseModel):
    """Single phase block for the timeline quadrant."""

    phase_number: int = Field(ge=1, le=5)
    phase_name: str = Field(max_length=40)
    week_range: str = Field(
        max_length=20, description="e.g., 'Weeks 1-4'",
    )
    key_activities: Bullets_2_3 = Field(
        description="2-3 key activities for this phase",
    )


class TimelineOverviewSlide(SlideOutput):
    """Timeline overview - 4 quadrant boxes, one phase per box."""

    box_1: TimelinePhaseBlock
    box_2: TimelinePhaseBlock
    box_3: TimelinePhaseBlock
    box_4: TimelinePhaseBlock

    @model_validator(mode="after")
    def validate_distinct_phases(self) -> TimelineOverviewSlide:
        numbers = {
            self.box_1.phase_number,
            self.box_2.phase_number,
            self.box_3.phase_number,
            self.box_4.phase_number,
        }
        if len(numbers) < 4:
            raise ValueError(
                "All 4 timeline boxes must have distinct phase numbers",
            )
        return self


class MilestoneColumn(BaseModel):
    """One column of milestone/deliverable content."""

    subtitle: str = Field(
        max_length=30, description="Column label, e.g., 'Phases 1-2'",
    )
    deliverables: BulletList = Field(
        description="Per-phase deliverables with decision gates",
    )


class MilestonesSlide(SlideOutput):
    """Milestones & Deliverables - two-column split."""

    left_column: MilestoneColumn = Field(
        description="Phases 1-2 deliverables",
    )
    right_column: MilestoneColumn = Field(
        description="Phases 3-5 deliverables (includes Phase 5 overflow)",
    )


class TimelineOutput(FillerOutput):
    """Full timeline filler output - 2 slides with multi-zone layouts."""

    slide_1_overview: TimelineOverviewSlide
    slide_2_milestones: MilestonesSlide


# ── Governance ───────────────────────────────────────────────────────────


class GovernanceTier(BaseModel):
    """Single governance tier for the 4-box grid."""

    tier_name: str = Field(
        max_length=30, description="e.g., STEERING COMMITTEE",
    )
    members: str = Field(max_length=60, description="Who participates")
    cadence: str = Field(
        max_length=20, min_length=1,
        description="Meeting frequency - required",
    )
    responsibilities: Bullets_2_4 = Field(
        description="2-4 key responsibilities",
    )


class EscalationBlock(BaseModel):
    """Escalation triggers for the 4th governance box."""

    tier_name: str = Field(default="ESCALATION TRIGGERS", max_length=30)
    triggers: Bullets_3_4 = Field(
        description="3-4 escalation conditions with authority levels",
    )


class GovernanceStructureSlide(SlideOutput):
    """Governance structure - 4-box grid (3 tiers + escalation)."""

    tier_1: GovernanceTier
    tier_2: GovernanceTier
    tier_3: GovernanceTier
    escalation: EscalationBlock


class ReportingBlock(BaseModel):
    """Single reporting cadence item."""

    cadence: str = Field(
        max_length=20, description="e.g., Weekly, Bi-weekly, Monthly",
    )
    report_name: str = Field(max_length=40)
    audience: str = Field(max_length=40)
    items: Bullets_2_3 = Field(
        description="2-3 content items for this report",
    )


class QualityGate(BaseModel):
    """Single quality gate definition."""

    gate_name: str = Field(max_length=40)
    criteria: Bullets_2_3 = Field(description="2-3 acceptance criteria")
    sign_off_authority: str = Field(max_length=40)


class QAReportingSlide(SlideOutput):
    """QA & Reporting - two-column: reporting cadence + quality gates."""

    left_subtitle: str = Field(
        default="Reporting Cadence", max_length=30,
    )
    reporting_blocks: list[ReportingBlock] = Field(
        min_length=2, max_length=4,
    )
    right_subtitle: str = Field(default="Quality Gates", max_length=30)
    quality_gates: list[QualityGate] = Field(min_length=2, max_length=4)


class GovernanceOutput(FillerOutput):
    """Full governance filler output - 2 slides with multi-zone layouts."""

    slide_1_structure: GovernanceStructureSlide
    slide_2_qa_reporting: QAReportingSlide
