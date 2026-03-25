"""Graph-level integration test for section_fill_node.

Proves the full pipeline flow through section_fill_node:
  1. Section budgets enter the node
  2. Fillers run (mocked)
  3. Manifest is rebuilt with filler injection data
  4. Manifest is validated (validate_manifest)
  5. Validated manifest is stored on state
  6. Downstream node receives that manifest

Uses mocked fillers — no live LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.models.enums import Language
from src.models.proposal_manifest import (
    ContentSourcePolicy,
    ManifestEntry,
    ProposalManifest,
    validate_manifest,
)
from src.models.slide_blueprint import SlideBlueprint, SlideBlueprintEntry
from src.models.state import DeckForgeState
from src.services.slide_budgeter import SectionBudget, SlideBudget

# ── Helpers ────────────────────────────────────────────────────────────


def _make_manifest_entry(
    entry_type: str,
    asset_id: str,
    section_id: str,
    layout: str = "content_heading_desc",
    injection_data: dict | None = None,
) -> ManifestEntry:
    """Build a ManifestEntry with sensible defaults."""
    policy_map = {
        "a1_clone": ContentSourcePolicy.INSTITUTIONAL_REUSE,
        "b_variable": ContentSourcePolicy.PROPOSAL_SPECIFIC,
        "pool_clone": ContentSourcePolicy.APPROVED_ASSET_POOL,
    }
    return ManifestEntry(
        entry_type=entry_type,
        asset_id=asset_id,
        semantic_layout_id=layout,
        content_source_policy=policy_map.get(
            entry_type, ContentSourcePolicy.PROPOSAL_SPECIFIC,
        ),
        section_id=section_id,
        injection_data=injection_data,
    )


def _make_state_with_manifest_and_budget() -> DeckForgeState:
    """Build a DeckForgeState with a valid manifest + slide budget.

    Manifest: cover(a1) → section_01(b_variable x2) → section_02(a1)
    Budget: section_01 has 2 content slides.
    """
    manifest = ProposalManifest(entries=[
        _make_manifest_entry("a1_clone", "main_cover", "cover"),
        _make_manifest_entry("b_variable", "understanding_01", "section_01"),
        _make_manifest_entry("b_variable", "understanding_02", "section_01"),
        _make_manifest_entry("a1_clone", "why_sg", "section_02",
                             layout="content_heading_desc"),
    ])

    budget = SlideBudget(
        total_slides=4,
        section_budgets={
            "section_01": SectionBudget(
                section_id="section_01",
                slide_count=2,
                breakdown={"content": 2},
            ),
        },
    )

    blueprint = SlideBlueprint(
        entries=[
            SlideBlueprintEntry(
                section_id="S05",
                section_name="Understanding of Project",
                ownership="dynamic",
                slide_title="Understanding",
                key_message="Key message 1",
            ),
            SlideBlueprintEntry(
                section_id="S05",
                section_name="Understanding of Project",
                ownership="dynamic",
                slide_title="Context",
                key_message="Key message 2",
            ),
        ],
    )

    return DeckForgeState(
        proposal_manifest=manifest,
        slide_budget=budget,
        slide_blueprint=blueprint,
        output_language=Language.EN,
    )


def _make_filler_entries() -> list[ManifestEntry]:
    """Filler output: 2 entries with injection data for section_01."""
    return [
        _make_manifest_entry(
            "b_variable", "understanding_01", "section_01",
            injection_data={"title": "Deep Understanding", "body": "Content A"},
        ),
        _make_manifest_entry(
            "b_variable", "understanding_02", "section_01",
            injection_data={"title": "Strategic Context", "body": "Content B"},
        ),
    ]


# ── Tests ──────────────────────────────────────────────────────────────


class TestSectionFillNodeGraphLevel:
    """Graph-level tests exercising section_fill_node end-to-end."""

    @pytest.mark.asyncio
    async def test_full_flow_happy_path(self):
        """Full flow: budget enters → fillers run → manifest rebuilt → validated → stored."""
        from src.agents.section_fillers.orchestrator import OrchestratorResult
        from src.pipeline.graph import section_fill_node

        state = _make_state_with_manifest_and_budget()
        original_entry_count = len(state.proposal_manifest.entries)

        # Mock the orchestrator to return our filler entries
        mock_result = OrchestratorResult(
            entries_by_section={"section_01": _make_filler_entries()},
            errors=[],
        )

        with patch(
            "src.agents.section_fillers.orchestrator.run_section_fillers",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_fillers:
            result = await section_fill_node(state)

        # 1. Fillers were called (budget entered the node)
        mock_fillers.assert_awaited_once()
        call_kwargs = mock_fillers.call_args
        assert call_kwargs is not None

        # 2. Manifest is present in result
        assert "proposal_manifest" in result
        updated_manifest = result["proposal_manifest"]
        assert isinstance(updated_manifest, ProposalManifest)

        # 3. Entry count is preserved (budget invariant)
        assert len(updated_manifest.entries) == original_entry_count

        # 4. Manifest is valid (validate_manifest passes)
        errors = validate_manifest(updated_manifest)
        assert errors == [], f"Manifest validation failed: {errors}"

        # 5. Injection data was merged into b_variable entries
        section_01_entries = [
            e for e in updated_manifest.entries
            if e.section_id == "section_01" and e.entry_type == "b_variable"
        ]
        assert len(section_01_entries) == 2
        for entry in section_01_entries:
            assert entry.injection_data is not None
            assert "title" in entry.injection_data
            assert "body" in entry.injection_data

        # 6. Non-variable entries are untouched
        cover = updated_manifest.entries[0]
        assert cover.asset_id == "main_cover"
        assert cover.entry_type == "a1_clone"

    @pytest.mark.asyncio
    async def test_invalid_manifest_fails_closed(self):
        """If rebuilt manifest fails validation, node returns error."""
        from src.agents.section_fillers.orchestrator import OrchestratorResult
        from src.pipeline.graph import section_fill_node

        state = _make_state_with_manifest_and_budget()

        # Return entries with FORBIDDEN policy — will fail validation
        bad_entries = [
            ManifestEntry(
                entry_type="b_variable",
                asset_id="understanding_01",
                semantic_layout_id="content_heading_desc",
                content_source_policy=ContentSourcePolicy.FORBIDDEN_TEMPLATE_EXAMPLE,
                section_id="section_01",
                injection_data={"title": "Bad", "body": "Bad"},
            ),
            ManifestEntry(
                entry_type="b_variable",
                asset_id="understanding_02",
                semantic_layout_id="content_heading_desc",
                content_source_policy=ContentSourcePolicy.FORBIDDEN_TEMPLATE_EXAMPLE,
                section_id="section_01",
                injection_data={"title": "Bad2", "body": "Bad2"},
            ),
        ]

        mock_result = OrchestratorResult(
            entries_by_section={"section_01": bad_entries},
            errors=[],
        )

        with patch(
            "src.agents.section_fillers.orchestrator.run_section_fillers",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await section_fill_node(state)

        # Must fail closed
        assert result["current_stage"].value == "error"
        assert result["last_error"].error_type == "ManifestValidationFailed"
        assert "proposal_manifest" not in result

    @pytest.mark.asyncio
    async def test_budget_matches_manifest_succeeds(self):
        """When manifest entry count == budget.total_slides, node succeeds."""
        from src.agents.section_fillers.orchestrator import OrchestratorResult
        from src.pipeline.graph import section_fill_node

        # Default helper: 4 manifest entries, budget.total_slides=4
        state = _make_state_with_manifest_and_budget()
        assert len(state.proposal_manifest.entries) == state.slide_budget.total_slides

        mock_result = OrchestratorResult(
            entries_by_section={"section_01": _make_filler_entries()},
            errors=[],
        )

        with patch(
            "src.agents.section_fillers.orchestrator.run_section_fillers",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await section_fill_node(state)

        # Succeeds — manifest stored, no error
        assert "proposal_manifest" in result
        assert len(result["proposal_manifest"].entries) == 4

    @pytest.mark.asyncio
    async def test_budget_mismatch_fails_closed(self):
        """When manifest entry count != budget.total_slides, node fails with ManifestBudgetMismatch."""
        from src.agents.section_fillers.orchestrator import OrchestratorResult
        from src.pipeline.graph import section_fill_node

        # Build state where budget.total_slides (99) != manifest entries (4)
        manifest = ProposalManifest(entries=[
            _make_manifest_entry("a1_clone", "main_cover", "cover"),
            _make_manifest_entry("b_variable", "understanding_01", "section_01"),
            _make_manifest_entry("b_variable", "understanding_02", "section_01"),
            _make_manifest_entry("a1_clone", "why_sg", "section_02",
                                 layout="content_heading_desc"),
        ])
        # Budget says 99 slides — does NOT match 4 manifest entries
        budget = SlideBudget(
            total_slides=99,
            section_budgets={
                "section_01": SectionBudget(
                    section_id="section_01",
                    slide_count=2,
                    breakdown={"content": 2},
                ),
            },
        )
        blueprint = SlideBlueprint(
            entries=[
                SlideBlueprintEntry(
                    section_id="S05",
                    section_name="Understanding of Project",
                    ownership="dynamic",
                    slide_title="t",
                    key_message="k",
                ),
                SlideBlueprintEntry(
                    section_id="S05",
                    section_name="Understanding of Project",
                    ownership="dynamic",
                    slide_title="t",
                    key_message="k",
                ),
            ],
        )
        state = DeckForgeState(
            proposal_manifest=manifest,
            slide_budget=budget,
            slide_blueprint=blueprint,
            output_language=Language.EN,
        )

        mock_result = OrchestratorResult(
            entries_by_section={"section_01": _make_filler_entries()},
            errors=[],
        )

        with patch(
            "src.agents.section_fillers.orchestrator.run_section_fillers",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await section_fill_node(state)

        # Must fail closed with ManifestBudgetMismatch
        assert result["current_stage"].value == "error"
        assert result["last_error"].error_type == "ManifestBudgetMismatch"
        assert "99" in result["last_error"].message
        assert "proposal_manifest" not in result

    @pytest.mark.asyncio
    async def test_downstream_receives_validated_manifest(self):
        """Simulate: section_fill stores manifest → downstream reads it."""
        from src.agents.section_fillers.orchestrator import OrchestratorResult
        from src.pipeline.graph import section_fill_node

        state = _make_state_with_manifest_and_budget()

        mock_result = OrchestratorResult(
            entries_by_section={"section_01": _make_filler_entries()},
            errors=[],
        )

        with patch(
            "src.agents.section_fillers.orchestrator.run_section_fillers",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await section_fill_node(state)

        # Simulate LangGraph state merge: downstream node gets updated manifest
        updated_manifest = result["proposal_manifest"]

        # Downstream can validate it again — still passes
        errors = validate_manifest(updated_manifest)
        assert errors == []

        # Downstream can iterate entries
        assert updated_manifest.total_slides == 4
        assert "section_01" in updated_manifest.section_ids

        # All b_variable entries in section_01 have injection data
        for entry in updated_manifest.entries:
            if entry.entry_type == "b_variable" and entry.section_id == "section_01":
                assert entry.injection_data is not None

    @pytest.mark.asyncio
    async def test_missing_budget_fails_closed(self):
        """If slide_budget is None, node fails with MissingInputs."""
        from src.pipeline.graph import section_fill_node

        state = DeckForgeState(
            proposal_manifest=ProposalManifest(entries=[]),
            slide_budget=None,
        )
        result = await section_fill_node(state)
        assert result["current_stage"].value == "error"
        assert result["last_error"].error_type == "MissingInputs"
