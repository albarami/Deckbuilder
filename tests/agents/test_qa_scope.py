"""Tests for QA Agent scope — b_variable filtering in template_v2 mode.

Proves that:
  1. In TEMPLATE_V2 mode, only b_variable slides are sent to QA
  2. In LEGACY mode, all slides are sent to QA
  3. evidence_level field exists on QAIssue
  4. _get_variable_asset_ids correctly extracts b_variable asset IDs
  5. Provenance filtering uses manifest_asset_id (not slide_id)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.enums import LayoutType, RendererMode
from src.models.proposal_manifest import (
    ContentSourcePolicy,
    ManifestEntry,
    ProposalManifest,
)
from src.models.qa import DeckValidationSummary, QAIssue, QAResult
from src.models.slides import SlideObject, WrittenSlides
from src.models.state import DeckForgeState

# ── Helpers ────────────────────────────────────────────────────────────


def _make_slides(
    count: int = 5,
    manifest_asset_ids: list[str] | None = None,
) -> list[SlideObject]:
    """Build slide objects with sequential IDs and optional provenance."""
    slides = []
    for i in range(count):
        asset_id = (
            manifest_asset_ids[i]
            if manifest_asset_ids and i < len(manifest_asset_ids)
            else None
        )
        slides.append(
            SlideObject(
                slide_id=f"S-{i + 1:03d}",
                title=f"Slide {i}",
                layout_type=LayoutType.CONTENT_1COL,
                manifest_asset_id=asset_id,
            )
        )
    return slides


def _make_manifest_with_variable_ids(variable_ids: list[str]) -> ProposalManifest:
    """Build a manifest with a mix of a1_clone and b_variable entries."""
    entries = []
    for vid in variable_ids:
        entries.append(ManifestEntry(
            entry_type="b_variable",
            asset_id=vid,
            semantic_layout_id="content_heading_desc",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
            section_id="section_01",
        ))
    # Add some non-variable entries
    entries.append(ManifestEntry(
        entry_type="a1_clone",
        asset_id="main_cover",
        semantic_layout_id="proposal_cover",
        content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
        section_id="cover",
    ))
    return ProposalManifest(entries=entries)


def _make_qa_result(slide_count: int) -> QAResult:
    """Minimal QA result for mocking."""
    return QAResult(
        slide_validations=[],
        deck_summary=DeckValidationSummary(total_slides=slide_count),
    )


# ── Tests ──────────────────────────────────────────────────────────────


class TestGetVariableAssetIds:
    """_get_variable_asset_ids extracts correct IDs."""

    def test_extracts_b_variable_ids(self):
        from src.agents.qa.agent import _get_variable_asset_ids

        manifest = _make_manifest_with_variable_ids(
            ["understanding_01", "methodology_overview"]
        )
        state = DeckForgeState(proposal_manifest=manifest)
        ids = _get_variable_asset_ids(state)
        assert ids == {"understanding_01", "methodology_overview"}

    def test_excludes_non_variable_entries(self):
        from src.agents.qa.agent import _get_variable_asset_ids

        manifest = _make_manifest_with_variable_ids(["understanding_01"])
        state = DeckForgeState(proposal_manifest=manifest)
        ids = _get_variable_asset_ids(state)
        assert "main_cover" not in ids

    def test_no_manifest_returns_empty(self):
        from src.agents.qa.agent import _get_variable_asset_ids

        state = DeckForgeState(proposal_manifest=None)
        ids = _get_variable_asset_ids(state)
        assert ids == set()


class TestQAV2ScopeFiltering:
    """In TEMPLATE_V2 mode, only b_variable slides are validated.

    Uses manifest_asset_id provenance (not slide_id) for filtering.
    """

    @pytest.mark.asyncio
    @patch("src.agents.qa.agent.call_llm")
    async def test_v2_mode_filters_by_manifest_provenance(self, mock_llm):
        """Only slides with matching manifest_asset_id sent to QA."""
        mock_llm.return_value = AsyncMock(
            parsed=_make_qa_result(2),
            input_tokens=100,
            output_tokens=200,
        )

        variable_ids = ["understanding_01", "methodology_overview"]
        # 5 slides: only 2 have manifest_asset_id matching b_variable entries
        all_slides = _make_slides(
            5,
            manifest_asset_ids=[
                "understanding_01",       # b_variable — should be sent
                None,                     # no provenance — skipped
                "methodology_overview",   # b_variable — should be sent
                None,                     # no provenance — skipped
                None,                     # no provenance — skipped
            ],
        )
        manifest = _make_manifest_with_variable_ids(variable_ids)

        state = DeckForgeState(
            renderer_mode=RendererMode.TEMPLATE_V2,
            written_slides=WrittenSlides(slides=all_slides),
            proposal_manifest=manifest,
        )

        from src.agents.qa.agent import run
        await run(state)

        call_args = mock_llm.call_args
        user_msg = json.loads(call_args.kwargs["user_message"])
        sent_ids = [s["manifest_asset_id"] for s in user_msg["slides"]]

        assert "understanding_01" in sent_ids
        assert "methodology_overview" in sent_ids
        assert len(sent_ids) == 2

    @pytest.mark.asyncio
    @patch("src.agents.qa.agent.call_llm")
    async def test_v2_slide_id_mismatch_uses_provenance(self, mock_llm):
        """slide_id != asset_id but manifest_asset_id enables correct filtering."""
        mock_llm.return_value = AsyncMock(
            parsed=_make_qa_result(3),
            input_tokens=100,
            output_tokens=200,
        )

        variable_ids = ["understanding_01", "understanding_02", "methodology_overview"]
        # Slides have S-NNN slide_ids (different namespace) but correct manifest_asset_id
        all_slides = _make_slides(
            3,
            manifest_asset_ids=variable_ids,
        )
        manifest = _make_manifest_with_variable_ids(variable_ids)

        state = DeckForgeState(
            renderer_mode=RendererMode.TEMPLATE_V2,
            written_slides=WrittenSlides(slides=all_slides),
            proposal_manifest=manifest,
        )

        from src.agents.qa.agent import run
        await run(state)

        call_args = mock_llm.call_args
        user_msg = json.loads(call_args.kwargs["user_message"])
        # All 3 should be sent despite S-NNN != understanding_01
        assert len(user_msg["slides"]) == 3

    @pytest.mark.asyncio
    @patch("src.agents.qa.agent.call_llm")
    async def test_legacy_mode_sends_all_slides(self, mock_llm):
        """Legacy mode sends all slides (unchanged behavior)."""
        mock_llm.return_value = AsyncMock(
            parsed=_make_qa_result(5),
            input_tokens=100,
            output_tokens=200,
        )

        all_slides = _make_slides(5)

        state = DeckForgeState(
            renderer_mode=RendererMode.LEGACY,
            written_slides=WrittenSlides(slides=all_slides),
        )

        from src.agents.qa.agent import run
        await run(state)

        call_args = mock_llm.call_args
        user_msg = json.loads(call_args.kwargs["user_message"])
        assert len(user_msg["slides"]) == 5


class TestQAV2StrictScope:
    """In TEMPLATE_V2 mode, missing manifest → zero slides, never all."""

    @pytest.mark.asyncio
    @patch("src.agents.qa.agent.call_llm")
    async def test_v2_no_manifest_sends_zero_slides(self, mock_llm):
        """v2 mode with no manifest → zero slides sent to LLM."""
        mock_llm.return_value = AsyncMock(
            parsed=_make_qa_result(0),
            input_tokens=100,
            output_tokens=200,
        )

        all_slides = _make_slides(5)  # 5 slides available

        state = DeckForgeState(
            renderer_mode=RendererMode.TEMPLATE_V2,
            written_slides=WrittenSlides(slides=all_slides),
            proposal_manifest=None,  # no manifest
        )

        from src.agents.qa.agent import run
        await run(state)

        call_args = mock_llm.call_args
        user_msg = json.loads(call_args.kwargs["user_message"])
        # Strict: zero slides, NOT 5
        assert len(user_msg["slides"]) == 0

    @pytest.mark.asyncio
    @patch("src.agents.qa.agent.call_llm")
    async def test_v2_empty_variable_ids_sends_zero_slides(self, mock_llm):
        """v2 mode with manifest but no b_variable entries → zero slides."""
        mock_llm.return_value = AsyncMock(
            parsed=_make_qa_result(0),
            input_tokens=100,
            output_tokens=200,
        )

        all_slides = _make_slides(5)
        # Manifest with only a1_clone entries — no b_variable
        manifest = _make_manifest_with_variable_ids([])

        state = DeckForgeState(
            renderer_mode=RendererMode.TEMPLATE_V2,
            written_slides=WrittenSlides(slides=all_slides),
            proposal_manifest=manifest,
        )

        from src.agents.qa.agent import run
        await run(state)

        call_args = mock_llm.call_args
        user_msg = json.loads(call_args.kwargs["user_message"])
        # Strict: zero slides, NOT 5
        assert len(user_msg["slides"]) == 0


class TestEvidenceLevelField:
    """QAIssue has evidence_level field."""

    def test_evidence_level_defaults_to_empty(self):
        issue = QAIssue(
            type="UNGROUNDED_CLAIM",
            location="body",
            explanation="test",
            action="remove",
        )
        assert issue.evidence_level == ""

    def test_evidence_level_sourced(self):
        issue = QAIssue(
            type="UNGROUNDED_CLAIM",
            location="body",
            explanation="SG-specific claim",
            action="add reference",
            evidence_level="sourced",
        )
        assert issue.evidence_level == "sourced"

    def test_evidence_level_llm_knowledge(self):
        issue = QAIssue(
            type="UNGROUNDED_CLAIM",
            location="body",
            explanation="framework reference",
            action="accepted as LLM knowledge",
            evidence_level="llm_knowledge",
        )
        assert issue.evidence_level == "llm_knowledge"
