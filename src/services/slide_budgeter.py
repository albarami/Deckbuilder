"""Phase 7 — Section-Level Slide Budgeting.

Before layout routing, the SlideBudgeter determines exact slide counts
per section.  Rendering never decides section depth on the fly.

Budget determines:
- Exact slide count per section
- Exact number of methodology overview / focused / detail slides
  (driven by MethodologyBlueprint)
- Exact number of case-study slides (driven by CaseStudySelectionResult)
- Exact number of team slides (driven by TeamSelectionResult)
- Exact number of governance / timeline / compliance slides
- Exact number of company profile slides (driven by
  HouseInclusionPolicy.company_profile_depth)

Budget must be computed BEFORE manifest construction.  The manifest is
built from the budget.  Layout routing receives the budget as input.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.methodology_blueprint import MethodologyBlueprint
from src.models.proposal_manifest import (
    HouseInclusionPolicy,
    get_company_profile_ids,
    get_ksa_context_ids,
)
from src.services.selection_policies import (
    CaseStudySelectionResult,
    TeamSelectionResult,
)


# ── Exceptions ──────────────────────────────────────────────────────────


class BudgetValidationError(RuntimeError):
    """Raised when slide budget fails validation."""


# ── Data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SectionBudget:
    """Budget for one proposal section."""

    section_id: str
    slide_count: int
    breakdown: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SlideBudget:
    """Complete slide budget for the proposal."""

    total_slides: int
    section_budgets: dict[str, SectionBudget] = field(default_factory=dict)

    def get_section(self, section_id: str) -> SectionBudget:
        """Get budget for a section.  Fail-closed on missing."""
        if section_id not in self.section_budgets:
            raise BudgetValidationError(
                f"No budget for section '{section_id}'"
            )
        return self.section_budgets[section_id]

    @property
    def section_ids(self) -> list[str]:
        """Ordered section IDs in the budget."""
        return list(self.section_budgets.keys())


# ── Budget computation ──────────────────────────────────────────────────


def compute_slide_budget(
    inclusion_policy: HouseInclusionPolicy,
    methodology_blueprint: MethodologyBlueprint,
    case_study_result: CaseStudySelectionResult,
    team_result: TeamSelectionResult,
    *,
    understanding_slides: int = 3,
    timeline_slides: int = 2,
    governance_slides: int = 1,
) -> SlideBudget:
    """Compute the complete slide budget for a proposal.

    Parameters
    ----------
    inclusion_policy : HouseInclusionPolicy
        Determines company profile depth, KSA inclusion, etc.
    methodology_blueprint : MethodologyBlueprint
        Determines exact methodology slide structure.
    case_study_result : CaseStudySelectionResult
        Determines case study count.
    team_result : TeamSelectionResult
        Determines team bio count.
    understanding_slides : int
        Number of understanding/problem statement slides (section_01).
    timeline_slides : int
        Number of timeline/deliverable slides (section_04).
    governance_slides : int
        Number of governance slides (section_06).

    Returns
    -------
    SlideBudget
        Complete budget with per-section breakdowns.

    Raises
    ------
    BudgetValidationError
        If any count is outside allowed ranges.
    """
    sections: dict[str, SectionBudget] = {}

    # ── Cover section ────────────────────────────────────────────────
    # proposal_cover + intro_message + toc_agenda = 3 A2 shells
    cover_count = 3
    sections["cover"] = SectionBudget(
        section_id="cover",
        slide_count=cover_count,
        breakdown={
            "proposal_cover": 1,
            "intro_message": 1,
            "toc_agenda": 1,
        },
    )

    # ── Section 01: Understanding ────────────────────────────────────
    if understanding_slides < 1:
        raise BudgetValidationError(
            f"understanding_slides must be >= 1, got {understanding_slides}"
        )
    sec01_breakdown: dict[str, int] = {
        "divider": 1,
        "content": understanding_slides,
    }
    sections["section_01"] = SectionBudget(
        section_id="section_01",
        slide_count=1 + understanding_slides,
        breakdown=sec01_breakdown,
    )

    # ── Section 02: Why Strategic Gears ──────────────────────────────
    # KSA context slides (only for geography == "ksa")
    ksa_count = 0
    if inclusion_policy.include_ksa_context:
        ksa_count = len(get_ksa_context_ids())

    # Case studies from selection result
    cs_count = len(case_study_result.selected)
    min_cs, max_cs = inclusion_policy.case_study_count
    if cs_count < min_cs or cs_count > max_cs:
        raise BudgetValidationError(
            f"Case study count {cs_count} outside policy range "
            f"[{min_cs}, {max_cs}]"
        )

    # Service dividers (1 if we have case studies)
    svc_divider_count = 1 if cs_count > 0 else 0

    sec02_breakdown: dict[str, int] = {
        "divider": 1,
        "ksa_context": ksa_count,
        "case_studies": cs_count,
        "service_dividers": svc_divider_count,
    }
    sections["section_02"] = SectionBudget(
        section_id="section_02",
        slide_count=1 + ksa_count + cs_count + svc_divider_count,
        breakdown=sec02_breakdown,
    )

    # ── Section 03: Methodology ──────────────────────────────────────
    meth_overview = 1
    meth_focused = sum(len(p.focused_layouts) for p in methodology_blueprint.phases)
    meth_detail = sum(len(p.detail_layouts) for p in methodology_blueprint.phases)
    meth_total = meth_overview + meth_focused + meth_detail

    sec03_breakdown: dict[str, int] = {
        "divider": 1,
        "overview": meth_overview,
        "focused": meth_focused,
        "detail": meth_detail,
    }
    sections["section_03"] = SectionBudget(
        section_id="section_03",
        slide_count=1 + meth_total,
        breakdown=sec03_breakdown,
    )

    # ── Section 04: Timeline & Outcome ───────────────────────────────
    if timeline_slides < 1:
        raise BudgetValidationError(
            f"timeline_slides must be >= 1, got {timeline_slides}"
        )
    sec04_breakdown: dict[str, int] = {
        "divider": 1,
        "content": timeline_slides,
    }
    sections["section_04"] = SectionBudget(
        section_id="section_04",
        slide_count=1 + timeline_slides,
        breakdown=sec04_breakdown,
    )

    # ── Section 05: Team ─────────────────────────────────────────────
    team_count = len(team_result.selected)
    min_t, max_t = inclusion_policy.team_bio_count
    if team_count < min_t or team_count > max_t:
        raise BudgetValidationError(
            f"Team bio count {team_count} outside policy range "
            f"[{min_t}, {max_t}]"
        )

    # Leadership slide (only in standard/full)
    leadership_count = 1 if inclusion_policy.include_leadership else 0

    sec05_breakdown: dict[str, int] = {
        "divider": 1,
        "leadership": leadership_count,
        "team_bios": team_count,
    }
    sections["section_05"] = SectionBudget(
        section_id="section_05",
        slide_count=1 + leadership_count + team_count,
        breakdown=sec05_breakdown,
    )

    # ── Section 06: Governance ───────────────────────────────────────
    if governance_slides < 1:
        raise BudgetValidationError(
            f"governance_slides must be >= 1, got {governance_slides}"
        )
    sec06_breakdown: dict[str, int] = {
        "divider": 1,
        "content": governance_slides,
    }
    sections["section_06"] = SectionBudget(
        section_id="section_06",
        slide_count=1 + governance_slides,
        breakdown=sec06_breakdown,
    )

    # ── Company Profile ──────────────────────────────────────────────
    profile_ids = get_company_profile_ids(inclusion_policy.company_profile_depth)
    profile_count = len(profile_ids)

    # Services overview (only in full mode)
    svc_overview_count = 1 if inclusion_policy.include_services_overview else 0

    cp_breakdown: dict[str, int] = {
        "profile_slides": profile_count,
        "services_overview": svc_overview_count,
    }
    sections["company_profile"] = SectionBudget(
        section_id="company_profile",
        slide_count=profile_count + svc_overview_count,
        breakdown=cp_breakdown,
    )

    # ── Closing ──────────────────────────────────────────────────────
    # know_more + contact = 2 slides
    closing_count = 2
    sections["closing"] = SectionBudget(
        section_id="closing",
        slide_count=closing_count,
        breakdown={
            "know_more": 1,
            "contact": 1,
        },
    )

    # ── Total ────────────────────────────────────────────────────────
    total = sum(sb.slide_count for sb in sections.values())

    return SlideBudget(
        total_slides=total,
        section_budgets=sections,
    )


# ── Validation ──────────────────────────────────────────────────────────


def validate_budget(budget: SlideBudget) -> list[str]:
    """Validate structural integrity of a SlideBudget.

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []

    # Total must match sum of sections
    section_sum = sum(sb.slide_count for sb in budget.section_budgets.values())
    if budget.total_slides != section_sum:
        errors.append(
            f"total_slides ({budget.total_slides}) != sum of sections ({section_sum})"
        )

    # Every section must have positive slide count
    for sid, sb in budget.section_budgets.items():
        if sb.slide_count < 1:
            errors.append(f"Section '{sid}' has {sb.slide_count} slides (must be >= 1)")

    # Breakdown must sum to slide_count
    for sid, sb in budget.section_budgets.items():
        if sb.breakdown:
            bk_sum = sum(sb.breakdown.values())
            if bk_sum != sb.slide_count:
                errors.append(
                    f"Section '{sid}' breakdown sum ({bk_sum}) != "
                    f"slide_count ({sb.slide_count})"
                )

    return errors
