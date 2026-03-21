"""Tests for understanding filler — unit-tested with mocked LLM."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.section_fillers.base import SectionFillerInput
from src.agents.section_fillers.g2_schemas import (
    Bullets_2_3,
    Bullets_3_4,
    Bullets_4_6,
    FourBoxSlide,
    HeadingDescriptionContentSlide,
    TwoColumnSlide,
    UnderstandingOutput,
)
from src.agents.section_fillers.understanding import (
    UnderstandingFiller,
    _build_evidence_context,
)
from src.models.enums import Language
from src.services.source_pack import DocumentEvidence, SourcePack


def _make_input(
    slide_count: int = 3,
) -> SectionFillerInput:
    return SectionFillerInput(
        section_id="section_01",
        slide_count=slide_count,
        recommended_layouts=[
            "layout_heading_and_two_content_with_tiltes",
            "layout_heading_and_4_boxes_of_content",
        ],
        output_language=Language.EN,
        win_themes=["deep sector expertise", "proven track record"],
        source_pack=SourcePack(
            total_people=5,
            total_projects=10,
            documents=[
                DocumentEvidence(
                    doc_id="DOC-001",
                    title="RFP Document",
                    content_text="The Ministry requires digital transformation...",
                    char_count=50,
                ),
            ],
        ),
    )


def _make_llm_output() -> UnderstandingOutput:
    return UnderstandingOutput(
        section_id="section_01",
        language="en",
        slide_1_strategic_context=TwoColumnSlide(
            title="Strategic Context",
            left_subtitle="Current Landscape",
            left_evidence=Bullets_3_4(items=[
                "Digital maturity at early stage",
                "Legacy systems across departments",
                "Growing citizen expectations",
            ]),
            right_subtitle="Strategic Imperatives",
            right_evidence=Bullets_3_4(items=[
                "Vision 2030 digital targets",
                "Cross-agency integration mandate",
                "Data-driven decision making",
            ]),
        ),
        slide_2_core_challenges=FourBoxSlide(
            title="Core Challenges",
            box_1=Bullets_2_3(items=[
                "Fragmented IT infrastructure",
                "Limited interoperability",
            ]),
            box_2=Bullets_2_3(items=[
                "Skills gap in digital roles",
                "Change resistance in workforce",
            ]),
            box_3=Bullets_2_3(items=[
                "Data silos across departments",
                "No unified data governance",
            ]),
            box_4=Bullets_2_3(items=[
                "Cybersecurity compliance gaps",
                "Regulatory complexity growing",
            ]),
        ),
        slide_3_success_definition=HeadingDescriptionContentSlide(
            title="Defining Success",
            description="Success means measurable outcomes across all pillars.",
            outcomes=Bullets_4_6(items=[
                "90% digital service adoption",
                "50% process automation rate",
                "Zero critical security incidents",
                "All departments on unified platform",
            ]),
        ),
    )


class TestUnderstandingFiller:
    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.understanding.call_llm")
    async def test_produces_correct_entry_count(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = UnderstandingFiller()
        result = await filler.fill(_make_input(3))
        assert result.success
        assert len(result.entries) == 3

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.understanding.call_llm")
    async def test_entries_are_b_variable(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = UnderstandingFiller()
        result = await filler.fill(_make_input(3))
        for entry in result.entries:
            assert entry.entry_type == "b_variable"
            assert entry.section_id == "section_01"
            assert entry.injection_data is not None

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.understanding.call_llm")
    async def test_slide_1_layout(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = UnderstandingFiller()
        result = await filler.fill(_make_input(3))
        assert result.entries[0].semantic_layout_id == "layout_heading_and_two_content_with_tiltes"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.understanding.call_llm")
    async def test_slide_2_layout(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = UnderstandingFiller()
        result = await filler.fill(_make_input(3))
        assert result.entries[1].semantic_layout_id == "layout_heading_and_4_boxes_of_content"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.understanding.call_llm")
    async def test_slide_3_layout(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = UnderstandingFiller()
        result = await filler.fill(_make_input(3))
        assert result.entries[2].semantic_layout_id == "layout_heading_description_and_content_box"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.understanding.call_llm")
    async def test_injection_data_has_title(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = UnderstandingFiller()
        result = await filler.fill(_make_input(3))
        for entry in result.entries:
            assert "title" in entry.injection_data

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.understanding.call_llm")
    async def test_llm_error_produces_error_output(self, mock_llm):
        mock_llm.side_effect = RuntimeError("API timeout")
        filler = UnderstandingFiller()
        result = await filler.fill(_make_input(3))
        assert not result.success
        assert len(result.errors) == 1
        assert "API timeout" in result.errors[0]

    def test_evidence_context_includes_source_pack(self):
        inp = _make_input()
        ctx = _build_evidence_context(inp)
        assert "DOC-001" in ctx
        assert "digital transformation" in ctx

    def test_evidence_context_includes_win_themes(self):
        inp = _make_input()
        ctx = _build_evidence_context(inp)
        assert "deep sector expertise" in ctx

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.understanding.call_llm")
    async def test_asset_ids_are_sequential(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = UnderstandingFiller()
        result = await filler.fill(_make_input(3))
        assert result.entries[0].asset_id == "understanding_01"
        assert result.entries[1].asset_id == "understanding_02"
        assert result.entries[2].asset_id == "understanding_03"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.understanding.call_llm")
    async def test_uses_valid_model(self, mock_llm):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output())
        filler = UnderstandingFiller()
        assert filler.model_name == "claude-opus-4-6"
