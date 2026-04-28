"""Tests for Why SG filler — unit-tested with mocked LLM."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.section_fillers.base import SectionFillerInput
from src.agents.section_fillers.why_sg import (
    WhySGFiller,
    WhySGOutput,
    WhySGSlide,
    _build_evidence_context,
)
from src.models.enums import Language
from src.services.source_pack import (
    PersonSummary,
    ProjectSummary,
    SourcePack,
)


def _make_input(slide_count: int = 1) -> SectionFillerInput:
    return SectionFillerInput(
        section_id="section_02",
        slide_count=slide_count,
        recommended_layouts=["content_heading_desc"],
        output_language=Language.EN,
        source_pack=SourcePack(
            total_people=2,
            total_projects=3,
            people=[
                PersonSummary(
                    person_id="PER-001",
                    name="Alice Smith",
                    current_role="Principal Consultant",
                    company="Strategic Gears",
                    years_experience=15,
                    certifications=["PMP", "TOGAF"],
                    domain_expertise=["strategy"],
                    project_ids=["PRJ-001"],
                ),
            ],
            projects=[
                ProjectSummary(
                    project_id="PRJ-001",
                    project_name="Digital Transformation",
                    client="Ministry of Finance",
                    sector="government",
                    country="KSA",
                    outcomes=["Cost reduction 30%"],
                    methodologies=["Agile"],
                    technologies=["SAP"],
                    team_size=12,
                    duration_months=18,
                ),
            ],
        ),
        win_themes=["deep sector expertise", "proven track record"],
    )


def _make_llm_output(count: int = 1) -> WhySGOutput:
    return WhySGOutput(slides=[
        WhySGSlide(
            slide_title=f"Why SG Slide {i + 1}",
            slide_body=f"Why SG content for slide {i + 1}.",
        )
        for i in range(count)
    ])


class TestWhySGFiller:
    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.why_sg.call_llm")
    async def test_produces_correct_entry_count(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(2))
        filler = WhySGFiller()
        result = await filler.fill(_make_input(2))
        assert result.success
        assert len(result.entries) == 2

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.why_sg.call_llm")
    async def test_entries_are_b_variable(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(1))
        filler = WhySGFiller()
        result = await filler.fill(_make_input(1))
        for entry in result.entries:
            assert entry.entry_type == "b_variable"
            assert entry.section_id == "section_02"
            assert entry.semantic_layout_id == "content_heading_desc"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.why_sg.call_llm")
    async def test_asset_ids_are_sequential(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(2))
        filler = WhySGFiller()
        result = await filler.fill(_make_input(2))
        assert result.entries[0].asset_id == "why_sg_01"
        assert result.entries[1].asset_id == "why_sg_02"

    @pytest.mark.asyncio
    async def test_zero_budget_returns_empty(self):
        filler = WhySGFiller()
        result = await filler.fill(_make_input(0))
        assert result.success is False  # 0 entries = not success
        assert len(result.entries) == 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.why_sg.call_llm")
    async def test_injection_data_has_title_and_body(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(1))
        filler = WhySGFiller()
        result = await filler.fill(_make_input(1))
        data = result.entries[0].injection_data
        assert "title" in data
        assert "body" in data

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.why_sg.call_llm")
    async def test_llm_error_produces_error_output(self, mock_llm):
        mock_llm.side_effect = RuntimeError("API timeout")
        filler = WhySGFiller()
        result = await filler.fill(_make_input(1))
        assert not result.success
        assert "API timeout" in result.errors[0]

    def test_evidence_context_includes_projects(self):
        inp = _make_input()
        ctx = _build_evidence_context(inp)
        assert "Digital Transformation" in ctx
        assert "Ministry of Finance" in ctx

    def test_evidence_context_includes_people(self):
        inp = _make_input()
        ctx = _build_evidence_context(inp)
        assert "Alice Smith" in ctx
        assert "PMP" in ctx

    def test_evidence_context_includes_win_themes(self):
        inp = _make_input()
        ctx = _build_evidence_context(inp)
        assert "deep sector expertise" in ctx
