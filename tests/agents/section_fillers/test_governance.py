"""Tests for governance filler — unit-tested with mocked LLM."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.section_fillers.base import SectionFillerInput
from src.agents.section_fillers.g2_schemas import (
    Bullets_2_3,
    Bullets_2_4,
    Bullets_3_4,
    EscalationBlock,
    GovernanceOutput,
    GovernanceTier,
    QualityGate,
    ReportingBlock,
)
from src.agents.section_fillers.governance import (
    GovernanceFiller,
    GovernanceStructureSlide,
    QAReportingSlide,
    _build_governance_context,
)
from src.models.enums import Language
from src.models.methodology_blueprint import MethodologyBlueprint, PhaseBlueprint
from src.services.source_pack import SourcePack


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
                governance_tier="Project Board",
            ),
            PhaseBlueprint(
                phase_id="phase_02",
                phase_number=2,
                phase_name_en="Design",
                phase_name_ar="التصميم",
                overview_layout="methodology_overview_3",
                governance_tier="Steering Committee",
            ),
            PhaseBlueprint(
                phase_id="phase_03",
                phase_number=3,
                phase_name_en="Delivery",
                phase_name_ar="التسليم",
                overview_layout="methodology_overview_3",
                governance_tier="Steering Committee",
            ),
        ],
        governance_touchpoints={
            "phase_01": "Project Board",
            "phase_02": "Steering Committee",
        },
    )


def _make_input(slide_count: int = 2) -> SectionFillerInput:
    return SectionFillerInput(
        section_id="section_06",
        slide_count=slide_count,
        recommended_layouts=["layout_heading_and_4_boxes_of_content"],
        output_language=Language.EN,
        methodology_blueprint=_make_blueprint(),
        source_pack=SourcePack(total_people=3),
        win_themes=["strong governance"],
    )


def _make_tier(name: str = "Steering Committee") -> GovernanceTier:
    return GovernanceTier(
        tier_name=name,
        members="CIO, Project Director, PMO Lead",
        cadence="Monthly",
        responsibilities=Bullets_2_4(items=[
            "Strategic oversight",
            "Budget approval",
            "Risk escalation",
        ]),
    )


def _make_llm_output() -> GovernanceOutput:
    return GovernanceOutput(
        section_id="section_06",
        language="en",
        slide_1_structure=GovernanceStructureSlide(
            title="Project Governance Framework",
            tier_1=_make_tier("Steering Committee"),
            tier_2=_make_tier("Project Board"),
            tier_3=_make_tier("Working Teams"),
            escalation=EscalationBlock(
                tier_name="Escalation Triggers",
                triggers=Bullets_3_4(items=[
                    "Budget overrun >10%",
                    "Schedule delay >2 weeks",
                    "Critical risk materialized",
                ]),
            ),
        ),
        slide_2_qa_reporting=QAReportingSlide(
            title="QA & Reporting Framework",
            left_subtitle="Reporting Cadence",
            reporting_blocks=[
                ReportingBlock(
                    cadence="Weekly",
                    report_name="Status Report",
                    audience="Project Board",
                    items=Bullets_2_3(items=[
                        "Progress vs plan",
                        "Risk register updates",
                    ]),
                ),
                ReportingBlock(
                    cadence="Monthly",
                    report_name="Executive Summary",
                    audience="Steering Committee",
                    items=Bullets_2_3(items=[
                        "KPI dashboard",
                        "Budget utilization",
                    ]),
                ),
            ],
            right_subtitle="Quality Gates",
            quality_gates=[
                QualityGate(
                    gate_name="Phase Gate Review",
                    criteria=Bullets_2_3(items=[
                        "Deliverables complete",
                        "Acceptance criteria met",
                    ]),
                    sign_off_authority="Project Director",
                ),
                QualityGate(
                    gate_name="Go-Live Readiness",
                    criteria=Bullets_2_3(items=[
                        "UAT sign-off obtained",
                        "Production environment ready",
                    ]),
                    sign_off_authority="CIO",
                ),
            ],
        ),
    )


class TestGovernanceFiller:
    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.governance.call_llm")
    async def test_produces_correct_entry_count(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = GovernanceFiller()
        result = await filler.fill(_make_input(2))
        assert result.success
        assert len(result.entries) == 2

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.governance.call_llm")
    async def test_entries_are_b_variable(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = GovernanceFiller()
        result = await filler.fill(_make_input(2))
        for entry in result.entries:
            assert entry.entry_type == "b_variable"
            assert entry.section_id == "section_06"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.governance.call_llm")
    async def test_asset_ids_are_sequential(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = GovernanceFiller()
        result = await filler.fill(_make_input(2))
        assert result.entries[0].asset_id == "governance_01"
        assert result.entries[1].asset_id == "governance_02"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.governance.call_llm")
    async def test_slide_1_layout(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = GovernanceFiller()
        result = await filler.fill(_make_input(2))
        assert result.entries[0].semantic_layout_id == "layout_heading_and_4_boxes_of_content"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.governance.call_llm")
    async def test_slide_2_layout(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = GovernanceFiller()
        result = await filler.fill(_make_input(2))
        assert result.entries[1].semantic_layout_id == "layout_heading_and_two_content_with_tiltes"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.governance.call_llm")
    async def test_injection_data_has_title_and_body_contents(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = GovernanceFiller()
        result = await filler.fill(_make_input(2))
        data = result.entries[0].injection_data
        assert "title" in data
        assert "body_contents" in data

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.governance.call_llm")
    async def test_llm_error_produces_error_output(self, mock_llm):
        mock_llm.side_effect = RuntimeError("API timeout")
        filler = GovernanceFiller()
        result = await filler.fill(_make_input(2))
        assert not result.success
        assert "API timeout" in result.errors[0]

    def test_governance_context_includes_tiers(self):
        inp = _make_input()
        ctx = _build_governance_context(inp)
        assert "Project Board" in ctx
        assert "Steering Committee" in ctx

    def test_governance_context_includes_touchpoints(self):
        inp = _make_input()
        ctx = _build_governance_context(inp)
        assert "phase_01" in ctx
        assert "phase_02" in ctx

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.governance.call_llm")
    async def test_uses_opus_model(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = GovernanceFiller()
        assert filler.model_name == "claude-opus-4-6"
