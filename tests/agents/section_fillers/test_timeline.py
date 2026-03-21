"""Tests for timeline filler — unit-tested with mocked LLM."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.section_fillers.base import SectionFillerInput
from src.agents.section_fillers.g2_schemas import (
    BulletList,
    Bullets_2_3,
    MilestoneColumn,
    MilestonesSlide,
    TimelineOutput,
    TimelineOverviewSlide,
    TimelinePhaseBlock,
)
from src.agents.section_fillers.timeline import (
    TimelineFiller,
    _build_methodology_context,
)
from src.models.enums import Language
from src.models.methodology_blueprint import MethodologyBlueprint, PhaseBlueprint
from src.services.source_pack import DocumentEvidence, SourcePack


def _make_blueprint() -> MethodologyBlueprint:
    return MethodologyBlueprint(
        phase_count=3,
        phases=[
            PhaseBlueprint(
                phase_id="phase_01",
                phase_number=1,
                phase_name_en="Discovery",
                phase_name_ar="الاكتشاف",
                overview_layout="methodology_overview_3",
                activities=["Workshops", "Interviews"],
                deliverables=["Current state report"],
            ),
            PhaseBlueprint(
                phase_id="phase_02",
                phase_number=2,
                phase_name_en="Design",
                phase_name_ar="التصميم",
                overview_layout="methodology_overview_3",
                activities=["Architecture", "Prototyping"],
                deliverables=["Solution blueprint", "Prototype"],
            ),
            PhaseBlueprint(
                phase_id="phase_03",
                phase_number=3,
                phase_name_en="Delivery",
                phase_name_ar="التسليم",
                overview_layout="methodology_overview_3",
                activities=["Implementation", "Testing"],
                deliverables=["Deployed system", "Test report"],
            ),
        ],
        timeline_span="16 weeks",
    )


def _make_input(slide_count: int = 2) -> SectionFillerInput:
    return SectionFillerInput(
        section_id="section_04",
        slide_count=slide_count,
        recommended_layouts=["content_heading_desc"],
        output_language=Language.EN,
        methodology_blueprint=_make_blueprint(),
        source_pack=SourcePack(
            documents=[
                DocumentEvidence(
                    doc_id="DOC-001",
                    title="RFP",
                    content_text="Timeline: 4 months...",
                    char_count=22,
                ),
            ],
        ),
        win_themes=["rapid delivery"],
    )


def _make_phase_block(num: int) -> TimelinePhaseBlock:
    return TimelinePhaseBlock(
        phase_number=num,
        phase_name=f"Phase {num}",
        week_range=f"Weeks {(num - 1) * 4 + 1}-{num * 4}",
        key_activities=Bullets_2_3(items=[
            f"Activity {num}.1",
            f"Activity {num}.2",
        ]),
    )


def _make_llm_output() -> TimelineOutput:
    return TimelineOutput(
        section_id="section_04",
        language="en",
        slide_1_overview=TimelineOverviewSlide(
            title="Implementation Timeline",
            box_1=_make_phase_block(1),
            box_2=_make_phase_block(2),
            box_3=_make_phase_block(3),
            box_4=_make_phase_block(4),
        ),
        slide_2_milestones=MilestonesSlide(
            title="Key Milestones",
            left_column=MilestoneColumn(
                subtitle="Phases 1-2",
                deliverables=BulletList(items=[
                    "Current state report",
                    "Solution blueprint",
                ]),
            ),
            right_column=MilestoneColumn(
                subtitle="Phases 3-4",
                deliverables=BulletList(items=[
                    "Deployed system",
                    "Test report",
                ]),
            ),
        ),
    )


class TestTimelineFiller:
    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.timeline.call_llm")
    async def test_produces_correct_entry_count(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = TimelineFiller()
        result = await filler.fill(_make_input(2))
        assert result.success
        assert len(result.entries) == 2

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.timeline.call_llm")
    async def test_entries_are_b_variable(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = TimelineFiller()
        result = await filler.fill(_make_input(2))
        for entry in result.entries:
            assert entry.entry_type == "b_variable"
            assert entry.section_id == "section_04"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.timeline.call_llm")
    async def test_asset_ids_are_sequential(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = TimelineFiller()
        result = await filler.fill(_make_input(2))
        assert result.entries[0].asset_id == "timeline_01"
        assert result.entries[1].asset_id == "timeline_02"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.timeline.call_llm")
    async def test_slide_1_layout(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = TimelineFiller()
        result = await filler.fill(_make_input(2))
        assert result.entries[0].semantic_layout_id == "layout_heading_and_4_boxes_of_content"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.timeline.call_llm")
    async def test_slide_2_layout(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = TimelineFiller()
        result = await filler.fill(_make_input(2))
        assert result.entries[1].semantic_layout_id == "layout_heading_and_two_content_with_tiltes"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.timeline.call_llm")
    async def test_injection_data_has_title_and_body_contents(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = TimelineFiller()
        result = await filler.fill(_make_input(2))
        data = result.entries[0].injection_data
        assert "title" in data
        assert "body_contents" in data

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.timeline.call_llm")
    async def test_llm_error_produces_error_output(self, mock_llm):
        mock_llm.side_effect = RuntimeError("API timeout")
        filler = TimelineFiller()
        result = await filler.fill(_make_input(2))
        assert not result.success
        assert "API timeout" in result.errors[0]

    def test_methodology_context_includes_phases(self):
        inp = _make_input()
        ctx = _build_methodology_context(inp)
        assert "Discovery" in ctx
        assert "Design" in ctx
        assert "Delivery" in ctx
        assert "16 weeks" in ctx

    def test_methodology_context_includes_deliverables(self):
        inp = _make_input()
        ctx = _build_methodology_context(inp)
        assert "Current state report" in ctx
        assert "Solution blueprint" in ctx

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.timeline.call_llm")
    async def test_uses_valid_model(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = TimelineFiller()
        assert filler.model_name == "claude-opus-4-6"
