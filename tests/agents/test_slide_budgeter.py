"""Tests for Phase 7 — slide_budgeter.py.

Tests budget computation, per-section breakdowns, range validation,
methodology-driven counts, policy-driven company profile depth,
KSA inclusion, and structural integrity validation.
"""

from __future__ import annotations

import pytest

from src.models.methodology_blueprint import build_methodology_blueprint
from src.models.proposal_manifest import build_inclusion_policy
from src.services.selection_policies import (
    CaseStudySelectionResult,
    SelectedAsset,
    TeamSelectionResult,
)
from src.services.slide_budgeter import (
    BudgetValidationError,
    SectionBudget,
    SlideBudget,
    compute_slide_budget,
    validate_budget,
)

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_phases(count: int, *, activity_count: int = 2) -> list[dict]:
    return [
        {
            "phase_name_en": f"Phase {i + 1}",
            "phase_name_ar": f"المرحلة {i + 1}",
            "activities": [f"activity_{j}" for j in range(activity_count)],
            "deliverables": [f"deliverable_{j}" for j in range(2)],
            "governance_tier": "Steering Committee",
        }
        for i in range(count)
    ]


def _cs_result(count: int) -> CaseStudySelectionResult:
    """Create a CaseStudySelectionResult with `count` selected assets."""
    return CaseStudySelectionResult(
        selected=tuple(
            SelectedAsset(
                asset_id=f"cs_{i}",
                ranking_score=5.0 - i * 0.1,
                inclusion_reason=f"test selection {i}",
            )
            for i in range(count)
        ),
        excluded=(),
    )


def _team_result(count: int) -> TeamSelectionResult:
    """Create a TeamSelectionResult with `count` selected members."""
    return TeamSelectionResult(
        selected=tuple(
            SelectedAsset(
                asset_id=f"team_{i}",
                ranking_score=5.0 - i * 0.1,
                inclusion_reason=f"test selection {i}",
            )
            for i in range(count)
        ),
        excluded=(),
    )


def _standard_budget(
    *,
    geography: str = "ksa",
    proposal_mode: str = "standard",
    cs_count: int = 4,
    team_count: int = 3,
    phase_count: int = 4,
    activity_count: int = 2,
    understanding_slides: int = 3,
    timeline_slides: int = 2,
    governance_slides: int = 1,
) -> SlideBudget:
    """Build a standard budget for testing."""
    policy = build_inclusion_policy(proposal_mode, geography, "banking",
                                    case_study_count=(1, 12),
                                    team_bio_count=(1, 6))
    meth = build_methodology_blueprint(phase_count, _make_phases(phase_count, activity_count=activity_count))
    return compute_slide_budget(
        policy, meth,
        _cs_result(cs_count), _team_result(team_count),
        understanding_slides=understanding_slides,
        timeline_slides=timeline_slides,
        governance_slides=governance_slides,
    )


# ── SectionBudget ───────────────────────────────────────────────────────


class TestSectionBudget:
    def test_frozen(self):
        sb = SectionBudget(section_id="cover", slide_count=3)
        with pytest.raises(AttributeError):
            sb.slide_count = 99  # type: ignore[misc]

    def test_default_breakdown(self):
        sb = SectionBudget(section_id="cover", slide_count=3)
        assert sb.breakdown == {}


# ── SlideBudget ─────────────────────────────────────────────────────────


class TestSlideBudget:
    def test_frozen(self):
        budget = SlideBudget(total_slides=10)
        with pytest.raises(AttributeError):
            budget.total_slides = 99  # type: ignore[misc]

    def test_get_section(self):
        budget = _standard_budget()
        sb = budget.get_section("cover")
        assert sb.section_id == "cover"
        assert sb.slide_count == 3

    def test_get_section_missing_raises(self):
        budget = _standard_budget()
        with pytest.raises(BudgetValidationError, match="phantom"):
            budget.get_section("phantom")

    def test_section_ids_ordered(self):
        budget = _standard_budget()
        ids = budget.section_ids
        assert ids[0] == "cover"
        assert "section_03" in ids
        assert "company_profile" in ids
        assert ids[-1] == "closing"


# ── Budget computation ──────────────────────────────────────────────────


class TestComputeBudget:
    def test_cover_always_3(self):
        budget = _standard_budget()
        cover = budget.get_section("cover")
        assert cover.slide_count == 3
        assert cover.breakdown["proposal_cover"] == 1
        assert cover.breakdown["intro_message"] == 1
        assert cover.breakdown["toc_agenda"] == 1

    def test_closing_always_2(self):
        budget = _standard_budget()
        closing = budget.get_section("closing")
        assert closing.slide_count == 2
        assert closing.breakdown["know_more"] == 1
        assert closing.breakdown["contact"] == 1

    def test_understanding_section(self):
        budget = _standard_budget(understanding_slides=4)
        sec01 = budget.get_section("section_01")
        assert sec01.breakdown["divider"] == 1
        assert sec01.breakdown["content"] == 4
        assert sec01.slide_count == 5

    def test_understanding_min_1(self):
        with pytest.raises(BudgetValidationError, match="understanding_slides"):
            _standard_budget(understanding_slides=0)

    def test_timeline_section(self):
        budget = _standard_budget(timeline_slides=3)
        sec04 = budget.get_section("section_04")
        assert sec04.breakdown["divider"] == 1
        assert sec04.breakdown["content"] == 3
        assert sec04.slide_count == 4

    def test_timeline_min_1(self):
        with pytest.raises(BudgetValidationError, match="timeline_slides"):
            _standard_budget(timeline_slides=0)

    def test_governance_section(self):
        budget = _standard_budget(governance_slides=2)
        sec06 = budget.get_section("section_06")
        assert sec06.breakdown["divider"] == 1
        assert sec06.breakdown["content"] == 2
        assert sec06.slide_count == 3

    def test_governance_min_1(self):
        with pytest.raises(BudgetValidationError, match="governance_slides"):
            _standard_budget(governance_slides=0)

    def test_total_is_sum_of_sections(self):
        budget = _standard_budget()
        section_sum = sum(sb.slide_count for sb in budget.section_budgets.values())
        assert budget.total_slides == section_sum


# ── Methodology-driven section 03 ──────────────────────────────────────


class TestMethodologyBudget:
    def test_3_phase_no_details(self):
        budget = _standard_budget(phase_count=3, activity_count=2)
        sec03 = budget.get_section("section_03")
        assert sec03.breakdown["overview"] == 1
        assert sec03.breakdown["focused"] == 3
        assert sec03.breakdown["detail"] == 0
        assert sec03.slide_count == 1 + 1 + 3 + 0  # divider + overview + focused

    def test_4_phase_with_details(self):
        budget = _standard_budget(phase_count=4, activity_count=5)
        sec03 = budget.get_section("section_03")
        assert sec03.breakdown["overview"] == 1
        assert sec03.breakdown["focused"] == 4
        assert sec03.breakdown["detail"] == 4  # each phase gets 1 detail
        assert sec03.slide_count == 1 + 1 + 4 + 4  # divider + overview + focused + detail

    def test_5_phase_mixed_activities(self):
        """5 phases, only some with enough activities for details."""
        phases = []
        for i in range(5):
            phases.append({
                "phase_name_en": f"Phase {i + 1}",
                "phase_name_ar": f"المرحلة {i + 1}",
                "activities": [f"act_{j}" for j in range(5 if i < 2 else 2)],
                "deliverables": ["d1"],
                "governance_tier": "SC",
            })
        policy = build_inclusion_policy("standard", "ksa", "banking",
                                        case_study_count=(1, 12),
                                        team_bio_count=(1, 6))
        meth = build_methodology_blueprint(5, phases)
        budget = compute_slide_budget(
            policy, meth,
            _cs_result(4), _team_result(3),
        )
        sec03 = budget.get_section("section_03")
        assert sec03.breakdown["detail"] == 2  # only first 2 phases have >3 activities
        assert sec03.breakdown["focused"] == 5


# ── Case study budget (section_02) ──────────────────────────────────────


class TestCaseStudyBudget:
    def test_case_study_count_in_budget(self):
        budget = _standard_budget(cs_count=6)
        sec02 = budget.get_section("section_02")
        assert sec02.breakdown["case_studies"] == 6

    def test_case_study_below_min_raises(self):
        policy = build_inclusion_policy("standard", "ksa", "banking",
                                        case_study_count=(4, 12),
                                        team_bio_count=(1, 6))
        meth = build_methodology_blueprint(3, _make_phases(3))
        with pytest.raises(BudgetValidationError, match="Case study count"):
            compute_slide_budget(
                policy, meth,
                _cs_result(2), _team_result(3),
            )

    def test_case_study_above_max_raises(self):
        policy = build_inclusion_policy("standard", "ksa", "banking",
                                        case_study_count=(1, 5),
                                        team_bio_count=(1, 6))
        meth = build_methodology_blueprint(3, _make_phases(3))
        with pytest.raises(BudgetValidationError, match="Case study count"):
            compute_slide_budget(
                policy, meth,
                _cs_result(8), _team_result(3),
            )

    def test_service_divider_when_case_studies_present(self):
        budget = _standard_budget(cs_count=4)
        sec02 = budget.get_section("section_02")
        assert sec02.breakdown["service_dividers"] == 1

    def test_no_service_divider_when_no_case_studies(self):
        policy = build_inclusion_policy("standard", "ksa", "banking",
                                        case_study_count=(0, 12),
                                        team_bio_count=(1, 6))
        meth = build_methodology_blueprint(3, _make_phases(3))
        budget = compute_slide_budget(
            policy, meth,
            _cs_result(0), _team_result(3),
        )
        sec02 = budget.get_section("section_02")
        assert sec02.breakdown["service_dividers"] == 0


# ── KSA context (section_02) ────────────────────────────────────────────


class TestKsaBudget:
    def test_ksa_geography_includes_context(self):
        budget = _standard_budget(geography="ksa")
        sec02 = budget.get_section("section_02")
        assert sec02.breakdown["ksa_context"] == 4  # 4 KSA context IDs

    def test_international_excludes_ksa_context(self):
        budget = _standard_budget(geography="international")
        sec02 = budget.get_section("section_02")
        assert sec02.breakdown["ksa_context"] == 0

    def test_gcc_excludes_ksa_context(self):
        budget = _standard_budget(geography="gcc")
        sec02 = budget.get_section("section_02")
        assert sec02.breakdown["ksa_context"] == 0


# ── Team budget (section_05) ────────────────────────────────────────────


class TestTeamBudget:
    def test_team_count_in_budget(self):
        budget = _standard_budget(team_count=4)
        sec05 = budget.get_section("section_05")
        assert sec05.breakdown["team_bios"] == 4

    def test_leadership_in_standard(self):
        budget = _standard_budget(proposal_mode="standard")
        sec05 = budget.get_section("section_05")
        assert sec05.breakdown["leadership"] == 1

    def test_no_leadership_in_lite(self):
        budget = _standard_budget(proposal_mode="lite")
        sec05 = budget.get_section("section_05")
        assert sec05.breakdown["leadership"] == 0

    def test_team_below_min_raises(self):
        policy = build_inclusion_policy("standard", "ksa", "banking",
                                        case_study_count=(1, 12),
                                        team_bio_count=(3, 6))
        meth = build_methodology_blueprint(3, _make_phases(3))
        with pytest.raises(BudgetValidationError, match="Team bio count"):
            compute_slide_budget(
                policy, meth,
                _cs_result(4), _team_result(1),
            )


# ── Company profile budget ──────────────────────────────────────────────


class TestCompanyProfileBudget:
    def test_lite_profile_3_slides(self):
        budget = _standard_budget(proposal_mode="lite")
        cp = budget.get_section("company_profile")
        assert cp.breakdown["profile_slides"] == 3
        assert cp.breakdown["services_overview"] == 0

    def test_standard_profile_8_slides(self):
        budget = _standard_budget(proposal_mode="standard")
        cp = budget.get_section("company_profile")
        assert cp.breakdown["profile_slides"] == 8

    def test_full_profile_13_plus_services(self):
        budget = _standard_budget(proposal_mode="full")
        cp = budget.get_section("company_profile")
        assert cp.breakdown["profile_slides"] == 13
        assert cp.breakdown["services_overview"] == 1
        assert cp.slide_count == 14


# ── Budget validation ───────────────────────────────────────────────────


class TestValidateBudget:
    def test_valid_budget_no_errors(self):
        budget = _standard_budget()
        errors = validate_budget(budget)
        assert errors == []

    def test_total_mismatch_flagged(self):
        # Manually construct with wrong total
        sb = SectionBudget(section_id="cover", slide_count=3,
                           breakdown={"a": 1, "b": 2})
        budget = SlideBudget(
            total_slides=999,
            section_budgets={"cover": sb},
        )
        errors = validate_budget(budget)
        assert any("total_slides" in e for e in errors)

    def test_breakdown_mismatch_flagged(self):
        sb = SectionBudget(
            section_id="cover",
            slide_count=5,  # breakdown sums to 3
            breakdown={"a": 1, "b": 2},
        )
        budget = SlideBudget(
            total_slides=5,
            section_budgets={"cover": sb},
        )
        errors = validate_budget(budget)
        assert any("breakdown sum" in e for e in errors)

    def test_zero_slide_section_flagged(self):
        sb = SectionBudget(section_id="empty", slide_count=0)
        budget = SlideBudget(
            total_slides=0,
            section_budgets={"empty": sb},
        )
        errors = validate_budget(budget)
        assert any("must be >= 1" in e for e in errors)


# ── End-to-end budget ranges ────────────────────────────────────────────


class TestBudgetRanges:
    def test_lite_proposal_total(self):
        """Lite proposal is smaller than standard."""
        lite = _standard_budget(proposal_mode="lite", cs_count=4, team_count=2)
        standard = _standard_budget(proposal_mode="standard", cs_count=4, team_count=3)
        assert lite.total_slides < standard.total_slides

    def test_full_proposal_total(self):
        """Full proposal is larger than standard."""
        standard = _standard_budget(proposal_mode="standard", cs_count=4, team_count=3)
        full = _standard_budget(proposal_mode="full", cs_count=8, team_count=5)
        assert full.total_slides > standard.total_slides

    def test_all_sections_present(self):
        budget = _standard_budget()
        expected = {
            "cover", "section_01", "section_02", "section_03",
            "section_04", "section_05", "section_06",
            "company_profile", "closing",
        }
        assert set(budget.section_ids) == expected

    def test_every_section_has_positive_count(self):
        budget = _standard_budget()
        for sid, sb in budget.section_budgets.items():
            assert sb.slide_count >= 1, f"Section '{sid}' has {sb.slide_count} slides"

    def test_all_breakdowns_sum_correctly(self):
        budget = _standard_budget()
        errors = validate_budget(budget)
        assert errors == []
