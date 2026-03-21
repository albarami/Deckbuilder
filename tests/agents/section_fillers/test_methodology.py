"""Tests for methodology filler — unit-tested with mocked LLM.

Verifies:
- Correct entry count (1 overview + N focused + detail per phase)
- Entry types are b_variable
- 4-phase placeholder mapping (OVERVIEW_4_MAP / FOCUSED_4_MAP)
- 3-phase placeholder mapping (OVERVIEW_3_MAP / FOCUSED_3_MAP)
- Detail injection maps to distinct BODY placeholders (42, 43, 44)
- Semantic Scholar + Perplexity enrichment degrade gracefully
- LLM error produces error output
- Methodology blueprint is required
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.section_fillers.base import SectionFillerInput
from src.agents.section_fillers.g2_schemas import (
    Bullets_2_4,
    Bullets_3_5,
    MethodologyDetailSlide,
    MethodologyFocusedSlide,
    MethodologyOutput,
    MethodologyOverviewSlide,
    PhaseContent,
)
from src.agents.section_fillers.methodology import (
    DETAIL_MAP,
    FOCUSED_3_MAP,
    OVERVIEW_3_MAP,
    OVERVIEW_4_MAP,
    MethodologyFiller,
    build_detail_injection,
    build_focused_injection,
    build_overview_injection,
)
from src.models.enums import Language
from src.models.methodology_blueprint import MethodologyBlueprint, PhaseBlueprint
from src.services.source_pack import DocumentEvidence, SourcePack


def _make_blueprint(phase_count: int = 4) -> MethodologyBlueprint:
    phases = []
    layout_suffix = "4" if phase_count >= 4 else "3"
    for i in range(phase_count):
        num = i + 1
        detail_layouts = ["methodology_detail"] if num <= 2 else []
        phases.append(PhaseBlueprint(
            phase_id=f"phase_{num:02d}",
            phase_number=num,
            phase_name_en=f"Phase {num}",
            phase_name_ar=f"المرحلة {num}",
            overview_layout=f"methodology_overview_{layout_suffix}",
            focused_layouts=[f"methodology_focused_{layout_suffix}"],
            detail_layouts=detail_layouts,
            activities=[f"Activity {j}" for j in range(1, 4)],
            deliverables=[f"Deliverable {j}" for j in range(1, 3)],
        ))
    return MethodologyBlueprint(phase_count=phase_count, phases=phases)


def _make_input(phase_count: int = 4) -> SectionFillerInput:
    bp = _make_blueprint(phase_count)
    slide_count = 1 + sum(
        len(p.focused_layouts) + len(p.detail_layouts) for p in bp.phases
    )
    layout_suffix = "4" if phase_count >= 4 else "3"
    return SectionFillerInput(
        section_id="section_03",
        slide_count=slide_count,
        recommended_layouts=[
            f"methodology_overview_{layout_suffix}",
            f"methodology_focused_{layout_suffix}",
        ],
        output_language=Language.EN,
        methodology_blueprint=bp,
        source_pack=SourcePack(
            total_people=3,
            documents=[
                DocumentEvidence(
                    doc_id="DOC-001",
                    title="RFP",
                    content_text="Digital transformation requirements...",
                    char_count=40,
                ),
            ],
        ),
        win_themes=["proven methodology", "sector expertise"],
    )


def _make_phase_content(phase_num: int, title: str | None = None) -> PhaseContent:
    return PhaseContent(
        phase_number=phase_num,
        phase_title=title or f"Phase {phase_num} Title",
        phase_activities=Bullets_3_5(items=[
            f"Activity {phase_num}.{j}" for j in range(1, 4)
        ]),
    )


def _make_llm_output(phase_count: int = 4) -> MethodologyOutput:
    grid_count = min(phase_count, 4)
    phases = [_make_phase_content(i + 1) for i in range(grid_count)]

    focused_slides = [
        MethodologyFocusedSlide(
            title=f"Phase {i + 1} Focus",
            focused_phase_number=i + 1,
            subtitle=f"Focus on Phase {i + 1}",
            phases=phases,
        )
        for i in range(grid_count)
    ]

    detail_slides = [
        MethodologyDetailSlide(
            title=f"Phase {i + 1} Detail",
            phase_number=i + 1,
            activities=Bullets_3_5(items=[
                f"Activity {i + 1}.{j}" for j in range(1, 4)
            ]),
            deliverables=Bullets_3_5(items=[
                f"Deliverable {i + 1}.{j}" for j in range(1, 4)
            ]),
            frameworks=Bullets_2_4(items=[
                "TOGAF", "PMBOK",
            ]),
        )
        for i in range(grid_count)
    ]

    return MethodologyOutput(
        section_id="section_03",
        language="en",
        overview=MethodologyOverviewSlide(
            title="Methodology Overview",
            subtitle="Our Delivery Approach",
            phases=phases,
        ),
        focused_slides=focused_slides,
        detail_slides=detail_slides,
    )


class TestMethodologyFiller4Phase:
    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_produces_correct_entry_count(self, mock_llm, _sch, _ppx):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(4))
        filler = MethodologyFiller()
        inp = _make_input(4)
        result = await filler.fill(inp)
        assert result.success
        # 1 overview + 4 focused + 2 detail (phases 1,2 have detail_layouts)
        assert len(result.entries) == 7

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_entries_are_b_variable(self, mock_llm, _sch, _ppx):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(4))
        filler = MethodologyFiller()
        result = await filler.fill(_make_input(4))
        for entry in result.entries:
            assert entry.entry_type == "b_variable"
            assert entry.section_id == "section_03"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_overview_entry_uses_overview_4_layout(self, mock_llm, _sch, _ppx):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(4))
        filler = MethodologyFiller()
        result = await filler.fill(_make_input(4))
        overview_entry = result.entries[0]
        assert overview_entry.semantic_layout_id == "methodology_overview_4"
        assert overview_entry.asset_id == "methodology_overview"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_focused_entries_have_methodology_phase(self, mock_llm, _sch, _ppx):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(4))
        filler = MethodologyFiller()
        result = await filler.fill(_make_input(4))
        focused = [e for e in result.entries if "focused" in e.asset_id]
        assert len(focused) == 4
        for i, entry in enumerate(focused):
            assert entry.methodology_phase == f"phase_{i + 1:02d}"
            assert entry.semantic_layout_id == "methodology_focused_4"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_detail_entries_present(self, mock_llm, _sch, _ppx):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(4))
        filler = MethodologyFiller()
        result = await filler.fill(_make_input(4))
        details = [e for e in result.entries if "detail" in e.asset_id]
        assert len(details) == 2
        for entry in details:
            assert entry.semantic_layout_id == "methodology_detail"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_llm_error_produces_error_output(self, mock_llm, _sch, _ppx):
        mock_llm.side_effect = RuntimeError("API timeout")
        filler = MethodologyFiller()
        result = await filler.fill(_make_input(4))
        assert not result.success
        assert len(result.errors) == 1
        assert "API timeout" in result.errors[0]

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_requires_blueprint(self, mock_llm, _sch, _ppx):
        inp = SectionFillerInput(
            section_id="section_03",
            slide_count=5,
            recommended_layouts=["methodology_overview_4"],
            output_language=Language.EN,
            methodology_blueprint=None,
        )
        filler = MethodologyFiller()
        result = await filler.fill(inp)
        assert not result.success
        assert "methodology_blueprint" in result.errors[0].lower()


class TestMethodologyFiller3Phase:
    """Tests for 3-phase methodology using methodology_overview_3/focused_3."""

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_3phase_uses_overview_3_layout(self, mock_llm, _sch, _ppx):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(3))
        filler = MethodologyFiller()
        result = await filler.fill(_make_input(3))
        assert result.success
        overview = result.entries[0]
        assert overview.semantic_layout_id == "methodology_overview_3"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_3phase_focused_uses_focused_3_layout(self, mock_llm, _sch, _ppx):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(3))
        filler = MethodologyFiller()
        result = await filler.fill(_make_input(3))
        focused = [e for e in result.entries if "focused" in e.asset_id]
        assert len(focused) == 3
        for entry in focused:
            assert entry.semantic_layout_id == "methodology_focused_3"

    @pytest.mark.asyncio
    @patch("src.agents.section_fillers.methodology._get_perplexity_context", return_value="")
    @patch("src.agents.section_fillers.methodology._get_scholar_context", return_value="")
    @patch("src.agents.section_fillers.methodology.call_llm")
    async def test_3phase_correct_entry_count(self, mock_llm, _sch, _ppx):
        mock_llm.return_value = AsyncMock(parsed=_make_llm_output(3))
        filler = MethodologyFiller()
        result = await filler.fill(_make_input(3))
        # 1 overview + 3 focused + 2 detail (phases 1,2) = 6
        assert len(result.entries) == 6


class TestOverviewInjection4Phase:
    def test_overview_maps_phase_titles_to_correct_indices(self):
        phases = [_make_phase_content(i, f"Phase {i}") for i in range(1, 5)]
        overview = MethodologyOverviewSlide(
            title="Overview Title",
            subtitle="Test Subtitle",
            phases=phases,
        )
        result = build_overview_injection(overview, 4)
        body = result["body_contents"]

        # Subtitle at index 13
        assert body[OVERVIEW_4_MAP["subtitle"]] == "Test Subtitle"
        # Phase 1 title at correct index
        assert body[OVERVIEW_4_MAP["phase_1_title"]] == "Phase 1"
        # Phase 1 content (activities joined)
        assert "Activity 1.1" in body[OVERVIEW_4_MAP["phase_1_content"]]
        # Phase 4 title
        assert body[OVERVIEW_4_MAP["phase_4_title"]] == "Phase 4"
        # Phase 3 title at index 37 (4-phase specific)
        assert body[37] == "Phase 3"

    def test_overview_handles_fewer_phases_than_map(self):
        # Need at least 3 phases for MethodologyOverviewSlide validation
        # so test with raw build function by passing phases directly
        overview = MethodologyOverviewSlide(
            title="Overview",
            subtitle="Test",
            phases=[_make_phase_content(i, f"Phase {i}") for i in range(1, 4)],
        )
        result = build_overview_injection(overview, 1)
        body = result["body_contents"]
        assert body[OVERVIEW_4_MAP["phase_1_title"]] == "Phase 1"
        # Phase 2+ keys should NOT be present (only 1 phase in grid)
        assert OVERVIEW_4_MAP["phase_2_title"] not in body


class TestOverviewInjection3Phase:
    """Verify 3-phase overview uses OVERVIEW_3_MAP, not OVERVIEW_4_MAP."""

    def test_3phase_overview_maps_to_correct_indices(self):
        phases = [_make_phase_content(i, f"Phase {i}") for i in range(1, 4)]
        overview = MethodologyOverviewSlide(
            title="Overview",
            subtitle="3-Phase Overview",
            phases=phases,
        )
        result = build_overview_injection(overview, 3)
        body = result["body_contents"]

        # 3-phase map: phase 3 maps to idx 42/43, NOT 37/39
        assert body[OVERVIEW_3_MAP["phase_1_title"]] == "Phase 1"
        assert body[OVERVIEW_3_MAP["phase_2_title"]] == "Phase 2"
        assert body[OVERVIEW_3_MAP["phase_3_title"]] == "Phase 3"
        assert "Activity 3.1" in body[OVERVIEW_3_MAP["phase_3_content"]]
        # Idx 37 and 39 should NOT be present (those are 4-phase only)
        assert 37 not in body
        assert 39 not in body

    def test_3phase_overview_subtitle_at_correct_index(self):
        phases = [_make_phase_content(i, f"P{i}") for i in range(1, 4)]
        overview = MethodologyOverviewSlide(
            title="Overview",
            subtitle="Test",
            phases=phases,
        )
        result = build_overview_injection(overview, 3)
        assert result["body_contents"][13] == "Test"


class TestFocusedInjection:
    def test_focused_4phase_has_title_and_body_contents(self):
        phases = [_make_phase_content(i) for i in range(1, 5)]
        focused = MethodologyFocusedSlide(
            title="Discovery",
            focused_phase_number=1,
            phases=phases,
        )
        result = build_focused_injection(focused, 4)
        assert result["title"] == "Discovery"
        assert isinstance(result["body_contents"], dict)

    def test_focused_3phase_maps_to_correct_indices(self):
        phases = [_make_phase_content(i, f"Phase {i}") for i in range(1, 4)]
        focused = MethodologyFocusedSlide(
            title="Phase 3 Focus",
            focused_phase_number=3,
            phases=phases,
        )
        result = build_focused_injection(focused, 3)
        body = result["body_contents"]
        # 3-phase: phase 3 maps to idx 42/43
        assert body[FOCUSED_3_MAP["phase_3_title"]] == "Phase 3"
        assert "Activity 3.1" in body[FOCUSED_3_MAP["phase_3_content"]]
        # Idx 37/39 should NOT be present
        assert 37 not in body
        assert 39 not in body


class TestDetailInjection:
    def test_detail_maps_to_distinct_placeholders(self):
        detail = MethodologyDetailSlide(
            title="Execution",
            phase_number=1,
            activities=Bullets_3_5(items=[
                "Implement solution", "Conduct testing", "Deploy to production",
            ]),
            deliverables=Bullets_3_5(items=[
                "Delivered system", "Test report", "Deployment guide",
            ]),
            frameworks=Bullets_2_4(items=["Agile", "TOGAF"]),
        )
        result = build_detail_injection(detail)
        assert result["title"] == "Execution"
        body = result["body_contents"]
        # Each placeholder gets distinct content
        assert "Implement solution" in body[DETAIL_MAP["activities"]]
        assert "Delivered system" in body[DETAIL_MAP["deliverables"]]
        assert "Agile" in body[DETAIL_MAP["frameworks"]]
        # Verify the actual indices
        assert "Implement solution" in body[42]
        assert "Delivered system" in body[43]
        assert "Agile" in body[44]

    def test_detail_content_not_duplicated(self):
        """Each placeholder gets unique content, not the same text."""
        detail = MethodologyDetailSlide(
            title="Build",
            phase_number=1,
            activities=Bullets_3_5(items=[
                "Code the app", "Write unit tests", "Integration test",
            ]),
            deliverables=Bullets_3_5(items=[
                "Working software", "Test results", "CI pipeline",
            ]),
            frameworks=Bullets_2_4(items=["Scrum", "DevOps"]),
        )
        result = build_detail_injection(detail)
        body = result["body_contents"]
        values = list(body.values())
        # All values should be distinct
        assert len(values) == len(set(values))
