"""Tests for section fill orchestrator — mocked fillers."""

import pytest

from src.agents.section_fillers.base import (
    BaseSectionFiller,
    SectionFillerOutput,
    make_variable_entry,
)
from src.agents.section_fillers.orchestrator import (
    FILLER_REGISTRY,
    OrchestratorResult,
    _get_slide_count,
    run_section_fillers,
)
from src.services.slide_budgeter import SectionBudget, SlideBudget


def _make_budget(
    understanding: int = 3,
    why_sg: int = 1,
    methodology: int = 7,
    timeline: int = 2,
    governance: int = 1,
) -> SlideBudget:
    return SlideBudget(
        total_slides=50,
        section_budgets={
            "section_01": SectionBudget(
                section_id="section_01",
                slide_count=understanding + 1,
                breakdown={"divider": 1, "content": understanding},
            ),
            "section_02": SectionBudget(
                section_id="section_02",
                slide_count=why_sg + 3,
                breakdown={"divider": 1, "a1_clones": 2, "why_sg_variable": why_sg},
            ),
            "section_03": SectionBudget(
                section_id="section_03",
                slide_count=methodology + 1,
                breakdown={
                    "divider": 1,
                    "overview": 1,
                    "focused": (methodology - 1) // 2,
                    "detail": methodology - 1 - (methodology - 1) // 2,
                },
            ),
            "section_04": SectionBudget(
                section_id="section_04",
                slide_count=timeline + 1,
                breakdown={"divider": 1, "content": timeline},
            ),
            "section_06": SectionBudget(
                section_id="section_06",
                slide_count=governance + 1,
                breakdown={"divider": 1, "content": governance},
            ),
        },
    )


def _make_filler_output(section_id: str, count: int) -> SectionFillerOutput:
    entries = [
        make_variable_entry(
            asset_id=f"{section_id}_entry_{i}",
            semantic_layout_id="content_heading_content",
            section_id=section_id,
            injection_data={"title": f"Title {i}", "body": f"Body {i}"},
        )
        for i in range(count)
    ]
    return SectionFillerOutput(section_id=section_id, entries=entries)


class TestGetSlideCount:
    def test_returns_content_count(self):
        budget = _make_budget(understanding=3)
        assert _get_slide_count(budget, "section_01") == 3

    def test_returns_why_sg_variable(self):
        budget = _make_budget(why_sg=2)
        assert _get_slide_count(budget, "section_02") == 2

    def test_returns_methodology_total(self):
        budget = _make_budget(methodology=7)
        assert _get_slide_count(budget, "section_03") == 7

    def test_missing_section_returns_zero(self):
        budget = SlideBudget(total_slides=0, section_budgets={})
        assert _get_slide_count(budget, "section_99") == 0


class TestOrchestratorResult:
    def test_all_entries_sorted_by_section(self):
        result = OrchestratorResult(
            entries_by_section={
                "section_04": [make_variable_entry(
                    "t1", "content_heading_content", "section_04", {"title": "T"},
                )],
                "section_01": [make_variable_entry(
                    "u1", "content_heading_content", "section_01", {"title": "U"},
                )],
            },
        )
        all_e = result.all_entries
        assert all_e[0].section_id == "section_01"
        assert all_e[1].section_id == "section_04"

    def test_success_when_entries_present(self):
        result = OrchestratorResult(
            entries_by_section={
                "section_01": [make_variable_entry(
                    "u1", "content_heading_content", "section_01", {"title": "T"},
                )],
            },
        )
        assert result.success

    def test_not_success_when_empty(self):
        result = OrchestratorResult()
        assert not result.success


class TestRunSectionFillers:
    @pytest.mark.asyncio
    async def test_dispatches_to_all_registered_fillers(self, monkeypatch):
        budget = _make_budget()

        async def mock_fill(self, filler_input):
            count = filler_input.slide_count
            return _make_filler_output(filler_input.section_id, count)

        monkeypatch.setattr(BaseSectionFiller, "fill", mock_fill)

        result = await run_section_fillers(budget)

        assert result.success
        assert len(result.entries_by_section) == 5
        assert len(result.all_entries) == 14  # 3+1+7+2+1

    @pytest.mark.asyncio
    async def test_skips_zero_budget_sections(self, monkeypatch):
        budget = _make_budget(why_sg=0, governance=0)

        dispatched_sections: list[str] = []

        async def mock_fill(self, filler_input):
            dispatched_sections.append(filler_input.section_id)
            count = filler_input.slide_count
            return _make_filler_output(filler_input.section_id, count)

        monkeypatch.setattr(BaseSectionFiller, "fill", mock_fill)

        await run_section_fillers(budget)

        assert "section_02" not in dispatched_sections
        assert "section_06" not in dispatched_sections
        assert len(dispatched_sections) == 3

    @pytest.mark.asyncio
    async def test_collects_errors_from_failed_fillers(self, monkeypatch):
        budget = SlideBudget(
            total_slides=4,
            section_budgets={
                "section_01": SectionBudget(
                    section_id="section_01",
                    slide_count=4,
                    breakdown={"divider": 1, "content": 3},
                ),
            },
        )

        async def mock_fill(self, filler_input):
            return SectionFillerOutput(
                section_id="section_01",
                errors=["UnderstandingFiller: API timeout"],
            )

        monkeypatch.setattr(BaseSectionFiller, "fill", mock_fill)

        result = await run_section_fillers(budget)
        assert not result.success
        assert len(result.errors) == 1
        assert "API timeout" in result.errors[0]


# ── IntroductionFiller deferral ────────────────────────────────────────
#
# IntroductionFiller (section_00) is NOT registered in FILLER_REGISTRY.
# Architectural reason: the intro slide is built as entry_type="a2_shell"
# with section_id="cover" in both manifest_builder.py and slide_budgeter.py.
# section_fill_node only replaces b_variable entries, so registering
# section_00 in the orchestrator would be dead code — the filler output
# would never reach the rendered slide.
#
# Live wiring requires refactoring:
#   1. slide_budgeter: add section_00 budget, remove intro from cover
#   2. manifest_builder: create section_00 b_variable placeholder
#   3. section_fill_node: no change needed (already handles b_variable)
#
# This is deferred to a future step.


class TestIntroductionFillerDeferred:
    """Proves IntroductionFiller is explicitly NOT in the live pipeline."""

    def test_section_00_not_in_filler_registry(self):
        """section_00 must NOT be in FILLER_REGISTRY (deferred)."""
        assert "section_00" not in FILLER_REGISTRY

    def test_only_live_sections_registered(self):
        """Only sections with b_variable manifest entries are registered."""
        expected = {"section_01", "section_02", "section_03",
                    "section_04", "section_06"}
        assert set(FILLER_REGISTRY.keys()) == expected


# ── Multi_body title contract ──────────────────────────────────────────


class TestMultiBodyTitleContract:
    """Proves multi_body fillers emit 'title' (str) matching renderer contract.

    The renderer's _inject_content reads data.get("title", "") for multi_body
    dispatch. If fillers emit 'title_contents' instead, titles are LOST.
    These tests prove the LIVE injection builders produce the correct key.
    """

    def test_understanding_slide_1_emits_title_string(self):
        """Understanding slide 1 injection must have 'title' as string."""
        from src.agents.section_fillers.g2_schemas import (
            Bullets_3_4,
            TwoColumnSlide,
        )
        from src.agents.section_fillers.understanding import (
            build_slide_1_injection,
        )

        slide = TwoColumnSlide(
            title="Test Title",
            left_subtitle="Left",
            left_evidence=Bullets_3_4(items=["A", "B", "C"]),
            right_subtitle="Right",
            right_evidence=Bullets_3_4(items=["X", "Y", "Z"]),
        )
        data = build_slide_1_injection(slide)
        assert "title" in data
        assert isinstance(data["title"], str)
        assert data["title"] == "Test Title"
        assert "title_contents" not in data

    def test_understanding_slide_2_emits_title_string(self):
        """Understanding slide 2 injection must have 'title' as string."""
        from src.agents.section_fillers.g2_schemas import (
            Bullets_2_3,
            FourBoxSlide,
        )
        from src.agents.section_fillers.understanding import (
            build_slide_2_injection,
        )

        slide = FourBoxSlide(
            title="Challenges",
            box_1=Bullets_2_3(items=["A", "B"]),
            box_2=Bullets_2_3(items=["C", "D"]),
            box_3=Bullets_2_3(items=["E", "F"]),
            box_4=Bullets_2_3(items=["G", "H"]),
        )
        data = build_slide_2_injection(slide)
        assert isinstance(data["title"], str)
        assert "title_contents" not in data

    def test_timeline_slide_1_emits_title_string(self):
        """Timeline slide 1 injection must have 'title' as string."""
        from src.agents.section_fillers.g2_schemas import (
            Bullets_2_3,
            TimelineOverviewSlide,
            TimelinePhaseBlock,
        )
        from src.agents.section_fillers.timeline import (
            build_slide_1_injection,
        )

        def _block(n: int) -> TimelinePhaseBlock:
            return TimelinePhaseBlock(
                phase_number=n,
                phase_name=f"Phase {n}",
                week_range=f"Weeks {n}-{n+3}",
                key_activities=Bullets_2_3(items=["Act A", "Act B"]),
            )

        slide = TimelineOverviewSlide(
            title="Timeline",
            box_1=_block(1),
            box_2=_block(2),
            box_3=_block(3),
            box_4=_block(4),
        )
        data = build_slide_1_injection(slide)
        assert isinstance(data["title"], str)
        assert "title_contents" not in data

    def test_timeline_slide_2_emits_title_string(self):
        """Timeline slide 2 injection must have 'title' as string."""
        from src.agents.section_fillers.g2_schemas import (
            BulletList,
            MilestoneColumn,
            MilestonesSlide,
        )
        from src.agents.section_fillers.timeline import (
            build_slide_2_injection,
        )

        slide = MilestonesSlide(
            title="Milestones",
            left_column=MilestoneColumn(
                subtitle="Left",
                deliverables=BulletList(items=["D1", "D2"]),
            ),
            right_column=MilestoneColumn(
                subtitle="Right",
                deliverables=BulletList(items=["D3", "D4"]),
            ),
        )
        data = build_slide_2_injection(slide)
        assert isinstance(data["title"], str)
        assert "title_contents" not in data

    def test_governance_slide_1_emits_title_string(self):
        """Governance slide 1 injection must have 'title' as string."""
        from src.agents.section_fillers.g2_schemas import (
            Bullets_2_4,
            Bullets_3_4,
            EscalationBlock,
            GovernanceStructureSlide,
            GovernanceTier,
        )
        from src.agents.section_fillers.governance import (
            build_slide_1_injection,
        )

        def _tier(name: str) -> GovernanceTier:
            return GovernanceTier(
                tier_name=name,
                members="Members",
                cadence="Weekly",
                responsibilities=Bullets_2_4(items=["Resp A", "Resp B"]),
            )

        slide = GovernanceStructureSlide(
            title="Governance",
            tier_1=_tier("STEERING"),
            tier_2=_tier("PROJECT"),
            tier_3=_tier("WORKING"),
            escalation=EscalationBlock(
                triggers=Bullets_3_4(items=["Trig A", "Trig B", "Trig C"]),
            ),
        )
        data = build_slide_1_injection(slide)
        assert isinstance(data["title"], str)
        assert "title_contents" not in data

    def test_governance_slide_2_emits_title_string(self):
        """Governance slide 2 injection must have 'title' as string."""
        from src.agents.section_fillers.g2_schemas import (
            Bullets_2_3,
            QAReportingSlide,
            QualityGate,
            ReportingBlock,
        )
        from src.agents.section_fillers.governance import (
            build_slide_2_injection,
        )

        slide = QAReportingSlide(
            title="QA Framework",
            reporting_blocks=[
                ReportingBlock(
                    cadence="Weekly",
                    report_name="Status",
                    audience="Board",
                    items=Bullets_2_3(items=["Item A", "Item B"]),
                ),
                ReportingBlock(
                    cadence="Monthly",
                    report_name="Dashboard",
                    audience="Steering",
                    items=Bullets_2_3(items=["Item C", "Item D"]),
                ),
            ],
            quality_gates=[
                QualityGate(
                    gate_name="Exit Gate",
                    criteria=Bullets_2_3(items=["Crit A", "Crit B"]),
                    sign_off_authority="Board",
                ),
                QualityGate(
                    gate_name="Go-Live Gate",
                    criteria=Bullets_2_3(items=["Crit C", "Crit D"]),
                    sign_off_authority="Steering",
                ),
            ],
        )
        data = build_slide_2_injection(slide)
        assert isinstance(data["title"], str)
        assert "title_contents" not in data
