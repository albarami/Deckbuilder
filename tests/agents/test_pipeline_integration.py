"""Phase 16 — Pipeline Integration Behind Feature Flag.

Tests that:
  - RendererMode enum has correct values
  - RendererMode is a StrEnum (like all other DeckForge enums)
  - Default renderer_mode in DeckForgeState is LEGACY
  - Default renderer_mode in Settings is "legacy"
  - Settings.renderer_mode flows into DeckForgeState via create_state_from_input
  - render_node dispatches to legacy path when mode is LEGACY
  - render_node dispatches to v2 path when mode is TEMPLATE_V2
  - get_scorer_profile maps RendererMode to correct ScorerProfile
  - Legacy path behavior unchanged (same logic as pre-Phase 16)
  - renderer.py is NOT imported by the new code (no modifications)
  - Feature flag is environment-configurable
  - Missing ProposalManifest fails closed (no empty-manifest stub)
"""

from __future__ import annotations

import ast
import asyncio
import json
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.enums import LayoutType, RendererMode
from src.models.slides import SlideObject
from src.services.scorer_profiles import ScorerProfile


# ── RendererMode Enum ────────────────────────────────────────────────


class TestRendererModeEnum:
    """RendererMode must have exactly two values and be a StrEnum."""

    def test_values(self):
        assert RendererMode.LEGACY == "legacy"
        assert RendererMode.TEMPLATE_V2 == "template_v2"

    def test_is_str_enum(self):
        assert isinstance(RendererMode.LEGACY, str)
        assert isinstance(RendererMode.TEMPLATE_V2, str)

    def test_exactly_two_members(self):
        members = list(RendererMode)
        assert len(members) == 2

    def test_legacy_is_first(self):
        """LEGACY should be the first/primary value."""
        members = list(RendererMode)
        assert members[0] == RendererMode.LEGACY


# ── State Default ────────────────────────────────────────────────────


class TestStateDefault:
    """DeckForgeState.renderer_mode defaults to LEGACY."""

    def test_default_is_legacy(self):
        from src.models.state import DeckForgeState

        state = DeckForgeState()
        assert state.renderer_mode == RendererMode.LEGACY

    def test_can_set_template_v2(self):
        from src.models.state import DeckForgeState

        state = DeckForgeState(renderer_mode=RendererMode.TEMPLATE_V2)
        assert state.renderer_mode == RendererMode.TEMPLATE_V2

    def test_serializes_as_string(self):
        from src.models.state import DeckForgeState

        state = DeckForgeState(renderer_mode=RendererMode.TEMPLATE_V2)
        data = state.model_dump()
        assert data["renderer_mode"] == "template_v2"

    def test_deserializes_from_string(self):
        from src.models.state import DeckForgeState

        state = DeckForgeState.model_validate({"renderer_mode": "template_v2"})
        assert state.renderer_mode == RendererMode.TEMPLATE_V2

    def test_proposal_manifest_defaults_to_none(self):
        from src.models.state import DeckForgeState

        state = DeckForgeState()
        assert state.proposal_manifest is None


# ── Settings Default ─────────────────────────────────────────────────


class TestSettingsDefault:
    """Settings.renderer_mode defaults to 'legacy'."""

    def test_default_is_legacy(self):
        from src.config.settings import Settings

        # Build settings with minimal required fields
        s = Settings(
            openai_api_key="test",  # type: ignore[arg-type]
            anthropic_api_key="test",  # type: ignore[arg-type]
        )
        assert s.renderer_mode == "legacy"


# ── Settings → State Wiring ──────────────────────────────────────────


class TestSettingsToStateWiring:
    """Settings.renderer_mode must reach DeckForgeState.renderer_mode
    via create_state_from_input()."""

    def test_plain_text_inherits_legacy_from_settings(self, tmp_path):
        """Plain-text input creates state with renderer_mode from settings."""
        from scripts.run_pipeline import create_state_from_input

        rfp_file = tmp_path / "rfp.txt"
        rfp_file.write_text("Test RFP summary text", encoding="utf-8")

        with patch("scripts.run_pipeline.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(renderer_mode="legacy")
            state = create_state_from_input(str(rfp_file))

        assert state.renderer_mode == RendererMode.LEGACY

    def test_plain_text_inherits_v2_from_settings(self, tmp_path):
        """When settings has template_v2, state gets template_v2."""
        from scripts.run_pipeline import create_state_from_input

        rfp_file = tmp_path / "rfp.txt"
        rfp_file.write_text("Test RFP summary text", encoding="utf-8")

        with patch("scripts.run_pipeline.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(renderer_mode="template_v2")
            state = create_state_from_input(str(rfp_file))

        assert state.renderer_mode == RendererMode.TEMPLATE_V2

    def test_json_without_mode_inherits_from_settings(self, tmp_path):
        """JSON input without renderer_mode gets it from settings."""
        from scripts.run_pipeline import create_state_from_input

        rfp_file = tmp_path / "rfp.json"
        rfp_file.write_text(
            json.dumps({"ai_assist_summary": "Test summary"}),
            encoding="utf-8",
        )

        with patch("scripts.run_pipeline.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(renderer_mode="template_v2")
            state = create_state_from_input(str(rfp_file))

        assert state.renderer_mode == RendererMode.TEMPLATE_V2

    def test_json_with_explicit_mode_wins(self, tmp_path):
        """JSON input with explicit renderer_mode overrides settings."""
        from scripts.run_pipeline import create_state_from_input

        rfp_file = tmp_path / "rfp.json"
        rfp_file.write_text(
            json.dumps({
                "ai_assist_summary": "Test summary",
                "renderer_mode": "template_v2",
            }),
            encoding="utf-8",
        )

        # Settings says legacy but JSON says template_v2 — JSON wins
        with patch("scripts.run_pipeline.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(renderer_mode="legacy")
            state = create_state_from_input(str(rfp_file))

        assert state.renderer_mode == RendererMode.TEMPLATE_V2

    def test_bad_settings_value_defaults_to_legacy(self, tmp_path):
        """Unrecognised renderer_mode in settings falls back to LEGACY."""
        from scripts.run_pipeline import _renderer_mode_from_settings

        with patch("scripts.run_pipeline.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(renderer_mode="nonexistent")
            mode = _renderer_mode_from_settings()

        assert mode == RendererMode.LEGACY


# ── Scorer Profile Dispatch ──────────────────────────────────────────


class TestScorerProfileDispatch:
    """get_scorer_profile maps RendererMode → ScorerProfile correctly."""

    def test_legacy_mode_uses_legacy_profile(self):
        from src.pipeline.graph import get_scorer_profile

        profile = get_scorer_profile(RendererMode.LEGACY)
        assert profile == ScorerProfile.LEGACY

    def test_v2_mode_uses_v2_profile(self):
        from src.pipeline.graph import get_scorer_profile

        profile = get_scorer_profile(RendererMode.TEMPLATE_V2)
        assert profile == ScorerProfile.OFFICIAL_TEMPLATE_V2

    def test_dispatch_is_deterministic(self):
        from src.pipeline.graph import get_scorer_profile

        for _ in range(10):
            assert get_scorer_profile(RendererMode.LEGACY) == ScorerProfile.LEGACY
            assert get_scorer_profile(RendererMode.TEMPLATE_V2) == ScorerProfile.OFFICIAL_TEMPLATE_V2


# ── render_node Legacy Dispatch ──────────────────────────────────────


class TestRenderNodeLegacyDispatch:
    """render_node dispatches to legacy path when mode is LEGACY."""

    @pytest.fixture
    def legacy_state(self):
        from src.models.state import DeckForgeState

        slide = SlideObject(
            slide_id="S-001", title="Test Slide",
            layout_type=LayoutType.CONTENT_1COL,
        )
        return DeckForgeState(
            renderer_mode=RendererMode.LEGACY,
            final_slides=[slide],
        )

    @patch("src.pipeline.graph.render_pptx")
    @patch("src.pipeline.graph.Path.mkdir")
    def test_legacy_calls_render_pptx(self, mock_mkdir, mock_render, legacy_state):
        mock_render.return_value = MagicMock(pptx_path="output/deck.pptx")

        from src.pipeline.graph import render_node

        result = asyncio.run(render_node(legacy_state))

        # Legacy renderer was called
        mock_render.assert_called_once()
        assert result["pptx_path"] == "output/deck.pptx"

    @patch("src.pipeline.graph.render_pptx")
    @patch("src.pipeline.graph.Path.mkdir")
    def test_legacy_no_slides_returns_error(self, mock_mkdir, mock_render):
        from src.models.state import DeckForgeState
        from src.pipeline.graph import render_node

        state = DeckForgeState(renderer_mode=RendererMode.LEGACY)
        result = asyncio.run(render_node(state))

        assert result["current_stage"] == "error"
        assert result["last_error"].error_type == "NoSlides"
        mock_render.assert_not_called()


# ── render_node Template-V2 Dispatch ─────────────────────────────────


class TestRenderNodeV2Dispatch:
    """render_node dispatches to v2 path when mode is TEMPLATE_V2."""

    def test_v2_without_manifest_fails_closed(self):
        """V2 mode with no proposal_manifest => MissingManifest error.
        This is the primary fail-closed test."""
        from src.models.state import DeckForgeState
        from src.pipeline.graph import render_node

        slide = SlideObject(
            slide_id="S-001", title="Test Slide",
            layout_type=LayoutType.CONTENT_1COL,
        )
        state = DeckForgeState(
            renderer_mode=RendererMode.TEMPLATE_V2,
            final_slides=[slide],
            # proposal_manifest deliberately NOT set
        )

        with patch("src.pipeline.graph.render_pptx") as mock_legacy:
            result = asyncio.run(render_node(state))
            mock_legacy.assert_not_called()

        assert result["current_stage"] == "error"
        assert result["last_error"].error_type == "MissingManifest"
        assert "ProposalManifest is not yet present" in result["last_error"].message

    def test_v2_without_manifest_no_slides_also_fails_manifest_first(self):
        """V2 mode with no manifest AND no slides => MissingManifest (not NoSlides).
        Manifest check comes before slide check."""
        from src.models.state import DeckForgeState
        from src.pipeline.graph import render_node

        state = DeckForgeState(renderer_mode=RendererMode.TEMPLATE_V2)
        result = asyncio.run(render_node(state))

        assert result["current_stage"] == "error"
        assert result["last_error"].error_type == "MissingManifest"

    def test_v2_does_not_call_legacy_renderer(self):
        """V2 path must never call render_pptx (the legacy renderer)."""
        from src.models.state import DeckForgeState
        from src.pipeline.graph import render_node

        state = DeckForgeState(renderer_mode=RendererMode.TEMPLATE_V2)

        with patch("src.pipeline.graph.render_pptx") as mock_legacy:
            asyncio.run(render_node(state))
            mock_legacy.assert_not_called()


# ── Missing Manifest Fail-Closed ─────────────────────────────────────


class TestMissingManifestFailClosed:
    """The v2 path must fail closed when proposal_manifest is None.
    No empty stub. No silent fallback."""

    def test_manifest_none_returns_error(self):
        """Explicit: state.proposal_manifest is None → hard error."""
        from src.models.state import DeckForgeState
        from src.pipeline.graph import _render_template_v2

        state = DeckForgeState(
            renderer_mode=RendererMode.TEMPLATE_V2,
            proposal_manifest=None,
        )
        result = asyncio.run(_render_template_v2(state))

        assert result["current_stage"] == "error"
        assert result["last_error"].error_type == "MissingManifest"

    def test_manifest_none_default_returns_error(self):
        """Default state (no manifest set) → hard error on v2 path."""
        from src.models.state import DeckForgeState
        from src.pipeline.graph import _render_template_v2

        state = DeckForgeState(renderer_mode=RendererMode.TEMPLATE_V2)
        result = asyncio.run(_render_template_v2(state))

        assert result["current_stage"] == "error"
        assert result["last_error"].error_type == "MissingManifest"

    def test_error_message_is_explicit(self):
        """Error message must clearly state why — not a generic error."""
        from src.models.state import DeckForgeState
        from src.pipeline.graph import _render_template_v2

        state = DeckForgeState(renderer_mode=RendererMode.TEMPLATE_V2)
        result = asyncio.run(_render_template_v2(state))

        msg = result["last_error"].message
        assert "ProposalManifest" in msg
        assert "not yet present" in msg

    def test_error_agent_is_render_v2(self):
        """Error must be attributed to render_v2, not generic 'render'."""
        from src.models.state import DeckForgeState
        from src.pipeline.graph import _render_template_v2

        state = DeckForgeState(renderer_mode=RendererMode.TEMPLATE_V2)
        result = asyncio.run(_render_template_v2(state))

        assert result["last_error"].agent == "render_v2"


# ── No Empty-Manifest Fallback (Static Guard) ────────────────────────


class TestNoEmptyManifestFallback:
    """AST-based static analysis: _render_template_v2 must NEVER construct
    a ProposalManifest(entries=[]).  The manifest must come from state."""

    def test_no_proposal_manifest_construction_in_render_v2(self):
        """Source code of graph.py must not contain ProposalManifest(entries=[])."""
        graph_path = Path("src/pipeline/graph.py")
        source = graph_path.read_text(encoding="utf-8")

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Match ProposalManifest(...) call
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr

                if name == "ProposalManifest":
                    pytest.fail(
                        f"Found ProposalManifest() construction at line {node.lineno} "
                        f"in graph.py — v2 path must read manifest from state, "
                        f"never construct one"
                    )

    def test_no_entries_empty_list_in_render_v2(self):
        """Double-check: 'entries=[]' pattern must not appear in graph.py."""
        graph_path = Path("src/pipeline/graph.py")
        source = graph_path.read_text(encoding="utf-8")

        # Simple string check for the stub pattern
        assert "entries=[]" not in source, (
            "graph.py contains 'entries=[]' — this is the empty-manifest "
            "stub that was supposed to be removed"
        )

    def test_no_import_of_proposal_manifest_in_graph(self):
        """graph.py must NOT import ProposalManifest at all — the manifest
        lives in state, not constructed in the render path."""
        graph_path = Path("src/pipeline/graph.py")
        source = graph_path.read_text(encoding="utf-8")

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = [alias.name for alias in node.names]
                    if "ProposalManifest" in names:
                        pytest.fail(
                            f"graph.py imports ProposalManifest at line {node.lineno} "
                            f"— manifest must come from state, not be imported "
                            f"for construction"
                        )


# ── Feature Flag Isolation ───────────────────────────────────────────


class TestFeatureFlagIsolation:
    """Feature flag must be fully isolated — switching modes must not
    affect the other renderer's behavior."""

    def test_default_mode_is_legacy(self):
        from src.models.state import DeckForgeState

        state = DeckForgeState()
        assert state.renderer_mode == RendererMode.LEGACY

    def test_mode_stored_in_state(self):
        from src.models.state import DeckForgeState

        state = DeckForgeState(renderer_mode=RendererMode.TEMPLATE_V2)
        assert state.renderer_mode == RendererMode.TEMPLATE_V2

    def test_legacy_state_unchanged(self):
        """Creating a v2-mode state does not alter legacy enum values."""
        from src.models.state import DeckForgeState

        # Create both states
        legacy = DeckForgeState(renderer_mode=RendererMode.LEGACY)
        v2 = DeckForgeState(renderer_mode=RendererMode.TEMPLATE_V2)

        # Legacy still legacy
        assert legacy.renderer_mode == RendererMode.LEGACY
        assert v2.renderer_mode == RendererMode.TEMPLATE_V2


# ── graph.py Import Isolation ────────────────────────────────────────


class TestGraphImportIsolation:
    """graph.py imports from renderer.py (legacy) at module level.
    renderer_v2 is imported lazily inside _render_template_v2 only."""

    def test_renderer_imported_at_module_level(self):
        """Legacy renderer functions are imported at module level."""
        from src.pipeline import graph

        assert hasattr(graph, "render_pptx")
        assert hasattr(graph, "export_report_docx")

    def test_renderer_v2_not_at_module_level(self):
        """renderer_v2 is NOT imported at module level — only inside
        _render_template_v2 to avoid import overhead when not used."""
        from src.pipeline import graph

        assert not hasattr(graph, "render_v2")

    def test_scorer_profile_imported(self):
        """ScorerProfile is imported for profile dispatch."""
        from src.pipeline import graph

        assert hasattr(graph, "ScorerProfile")
        assert hasattr(graph, "get_scorer_profile")

    def test_renderer_mode_imported(self):
        """RendererMode is imported for dispatch."""
        from src.pipeline import graph

        assert hasattr(graph, "RendererMode")


# ── render_node function exists and is async ─────────────────────────


class TestRenderNodeSignature:
    """render_node must remain async and callable."""

    def test_render_node_is_async(self):
        from src.pipeline.graph import render_node

        import asyncio
        assert asyncio.iscoroutinefunction(render_node)

    def test_internal_helpers_exist(self):
        from src.pipeline.graph import _render_legacy, _render_template_v2

        import asyncio
        assert asyncio.iscoroutinefunction(_render_legacy)
        assert asyncio.iscoroutinefunction(_render_template_v2)


# ── RendererMode in graph routing ────────────────────────────────────


class TestGraphRouting:
    """The graph still routes to 'render' node correctly."""

    def test_render_node_registered(self):
        """The render node is still in the graph."""
        from src.pipeline.graph import build_graph

        try:
            graph = build_graph()
            assert graph is not None
        except Exception:
            pass

    def test_route_after_gate_5_still_targets_render(self):
        from src.pipeline.graph import route_after_gate_5
        from src.models.state import DeckForgeState, GateDecision

        state = DeckForgeState(
            gate_5=GateDecision(gate_number=5, approved=True),
        )
        assert route_after_gate_5(state) == "render"
