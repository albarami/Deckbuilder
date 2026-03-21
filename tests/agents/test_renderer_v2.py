"""Tests for Phase 13 — renderer_v2.py.

Tests manifest-driven orchestration, template-hash enforcement,
slide dispatch by entry type, content injection dispatch, and
the zero-legacy-imports / zero-shape-creation guardrails.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.proposal_manifest import (
    ContentSourcePolicy,
    ManifestEntry,
    ProposalManifest,
)
from src.services.renderer_v2 import (
    RenderResult,
    SlideRenderRecord,
    TemplateHashError,
    _enforce_template_hash,
    _inject_content,
    _render_a1_clone,
    _render_a2_shell,
    _render_b_variable,
    _render_pool_clone,
    render_v2,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _make_entry(
    entry_type: str = "a1_clone",
    asset_id: str = "test_asset",
    semantic_layout_id: str = "content_heading_desc",
    section_id: str = "cover",
    injection_data: dict | None = None,
    content_source_policy: ContentSourcePolicy = ContentSourcePolicy.INSTITUTIONAL_REUSE,
) -> ManifestEntry:
    return ManifestEntry(
        entry_type=entry_type,
        asset_id=asset_id,
        semantic_layout_id=semantic_layout_id,
        content_source_policy=content_source_policy,
        section_id=section_id,
        injection_data=injection_data,
    )


def _make_template_manager(template_hash: str = "abc123") -> MagicMock:
    tm = MagicMock()
    tm.template_hash = template_hash
    tm.clone_a1.return_value = MagicMock(name="a1_slide")
    tm.clone_a2.return_value = MagicMock(name="a2_slide")
    tm.clone_divider.return_value = MagicMock(name="divider_slide")
    tm.add_slide_from_layout.return_value = MagicMock(name="b_slide")
    tm.clone_slide.return_value = MagicMock(name="pool_slide")
    tm.save.return_value = Path("/fake/output.pptx")
    return tm


def _make_registry(template_hash: str = "abc123") -> MagicMock:
    reg = MagicMock()
    reg.template_hash = template_hash
    return reg


# ── SlideRenderRecord ──────────────────────────────────────────────────


class TestSlideRenderRecord:
    def test_frozen(self):
        r = SlideRenderRecord(
            manifest_index=0, entry_type="a1_clone",
            asset_id="test", semantic_layout_id="test",
            section_id="cover",
        )
        with pytest.raises(AttributeError):
            r.manifest_index = 1  # type: ignore[misc]

    def test_defaults(self):
        r = SlideRenderRecord(
            manifest_index=0, entry_type="a1_clone",
            asset_id="test", semantic_layout_id="test",
            section_id="cover",
        )
        assert r.injection_result is None
        assert r.sanitization_report is None
        assert r.fit_report is None
        assert r.error is None


# ── RenderResult ───────────────────────────────────────────────────────


class TestRenderResult:
    def test_success_when_no_errors(self):
        r = RenderResult(total_slides=5)
        assert r.success is True

    def test_failure_with_manifest_errors(self):
        r = RenderResult(total_slides=5, manifest_errors=["error"])
        assert r.success is False

    def test_failure_with_render_errors(self):
        r = RenderResult(total_slides=5, render_errors=["error"])
        assert r.success is False

    def test_failure_with_zero_slides(self):
        r = RenderResult()
        assert r.success is False

    def test_continuation_needed(self):
        fit_report = MagicMock()
        fit_report.any_continuation = True
        record = SlideRenderRecord(
            manifest_index=0, entry_type="b_variable",
            asset_id="test", semantic_layout_id="test",
            section_id="s1", fit_report=fit_report,
        )
        r = RenderResult(total_slides=1, records=[record])
        assert r.continuation_needed is True

    def test_no_continuation(self):
        r = RenderResult(total_slides=1)
        assert r.continuation_needed is False


# ── Template hash enforcement ──────────────────────────────────────────


class TestEnforceTemplateHash:
    def test_matching_hashes_pass(self):
        tm = _make_template_manager("hash_123")
        reg = _make_registry("hash_123")
        _enforce_template_hash(tm, reg)  # should not raise

    def test_mismatched_hashes_fail(self):
        tm = _make_template_manager("hash_A")
        reg = _make_registry("hash_B")
        with pytest.raises(TemplateHashError, match="mismatch"):
            _enforce_template_hash(tm, reg)

    def test_missing_template_hash_fails(self):
        tm = _make_template_manager("")
        reg = _make_registry("hash_B")
        with pytest.raises(TemplateHashError, match="missing"):
            _enforce_template_hash(tm, reg)

    def test_missing_registry_hash_fails(self):
        tm = _make_template_manager("hash_A")
        reg = _make_registry("")
        with pytest.raises(TemplateHashError, match="missing"):
            _enforce_template_hash(tm, reg)


# ── Slide dispatch ─────────────────────────────────────────────────────


class TestRenderA1Clone:
    def test_calls_clone_a1(self):
        entry = _make_entry(entry_type="a1_clone", asset_id="overview")
        tm = _make_template_manager()
        slide = _render_a1_clone(entry, tm)
        tm.clone_a1.assert_called_once_with("overview")
        assert slide is not None


class TestRenderA2Shell:
    def test_regular_a2_shell(self):
        entry = _make_entry(
            entry_type="a2_shell", asset_id="proposal_cover",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        )
        tm = _make_template_manager()
        allowlists = {"proposal_cover": MagicMock()}

        with patch("src.services.renderer_v2.get_allowlist") as mock_get, \
             patch("src.services.renderer_v2.sanitize_shell") as mock_san:
            mock_get.return_value = allowlists["proposal_cover"]
            mock_san.return_value = MagicMock(name="report")
            slide, report = _render_a2_shell(entry, tm, allowlists)

        tm.clone_a2.assert_called_once_with("proposal_cover")
        assert report is not None

    def test_section_divider_a2_shell(self):
        entry = _make_entry(
            entry_type="a2_shell", asset_id="section_divider_01",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        )
        tm = _make_template_manager()

        with patch("src.services.renderer_v2.get_allowlist") as mock_get, \
             patch("src.services.renderer_v2.sanitize_shell") as mock_san:
            mock_get.return_value = MagicMock()
            mock_san.return_value = MagicMock()
            slide, report = _render_a2_shell(entry, tm, {})

        tm.clone_divider.assert_called_once_with("01")


class TestRenderBVariable:
    def test_calls_add_slide_from_layout(self):
        entry = _make_entry(
            entry_type="b_variable",
            semantic_layout_id="methodology_overview_4",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        )
        tm = _make_template_manager()
        _render_b_variable(entry, tm)
        tm.add_slide_from_layout.assert_called_once_with("methodology_overview_4")


class TestRenderPoolClone:
    def test_with_source_slide_idx(self):
        entry = _make_entry(
            entry_type="pool_clone",
            injection_data={"source_slide_idx": 42},
            content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
        )
        tm = _make_template_manager()
        _render_pool_clone(entry, tm)
        tm.clone_slide.assert_called_once_with(42)

    def test_without_source_falls_back_to_layout(self):
        entry = _make_entry(
            entry_type="pool_clone",
            semantic_layout_id="case_study_cases",
            injection_data={},
            content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
        )
        tm = _make_template_manager()
        _render_pool_clone(entry, tm)
        tm.add_slide_from_layout.assert_called_once_with("case_study_cases")

    def test_none_injection_data_falls_back_to_layout(self):
        entry = _make_entry(
            entry_type="pool_clone",
            semantic_layout_id="team_two_members",
            content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
        )
        tm = _make_template_manager()
        _render_pool_clone(entry, tm)
        tm.add_slide_from_layout.assert_called_once_with("team_two_members")


# ── Content injection dispatch ─────────────────────────────────────────


class TestInjectContent:
    def _make_slide_and_contract(self, layout_id):
        slide = MagicMock()
        slide.placeholders = []
        contract = MagicMock()
        contract.semantic_layout_id = layout_id
        contract.required_placeholders = {}
        return slide, contract

    def test_no_injection_data_returns_none(self):
        entry = _make_entry(injection_data=None)
        slide, contract = self._make_slide_and_contract("content_heading_desc")
        result = _inject_content(slide, entry, contract)
        assert result is None

    def test_title_body_dispatch(self):
        entry = _make_entry(
            semantic_layout_id="content_heading_desc",
            injection_data={"title": "Test", "body": "Body text"},
        )
        slide, contract = self._make_slide_and_contract("content_heading_desc")

        with patch("src.services.renderer_v2.inject_title_body") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            mock_inj.assert_called_once()

    def test_center_title_dispatch(self):
        entry = _make_entry(
            semantic_layout_id="content_heading_only",
            injection_data={"title": "Framework"},
        )
        slide, contract = self._make_slide_and_contract("content_heading_only")

        with patch("src.services.renderer_v2.inject_center_title") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            mock_inj.assert_called_once()

    def test_proposal_cover_dispatch(self):
        entry = _make_entry(
            semantic_layout_id="proposal_cover",
            injection_data={"subtitle": "Strategy", "client_name": "Client"},
        )
        slide, contract = self._make_slide_and_contract("proposal_cover")

        with patch("src.services.renderer_v2.inject_proposal_cover") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            mock_inj.assert_called_once()

    def test_toc_table_dispatch(self):
        entry = _make_entry(
            semantic_layout_id="toc_table",
            injection_data={"title": "Agenda", "rows": [["1", "Intro"]]},
        )
        slide, contract = self._make_slide_and_contract("toc_table")

        with patch("src.services.renderer_v2.inject_toc_table") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            mock_inj.assert_called_once()

    def test_multi_body_dispatch(self):
        entry = _make_entry(
            semantic_layout_id="methodology_overview_4",
            injection_data={"title": "Phase 1", "body_contents": {13: "Text"}},
        )
        slide, contract = self._make_slide_and_contract("methodology_overview_4")

        with patch("src.services.renderer_v2.inject_multi_body") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            mock_inj.assert_called_once()

    def test_multi_body_forwards_exact_title_value(self):
        """Phase G: _inject_content forwards the exact title string to inject_multi_body.

        This is the critical contract test: fillers emit {"title": "..."} and
        the renderer must pass that exact value as the title= kwarg to
        inject_multi_body(). If the renderer reads a different key (e.g.
        title_contents), the title is silently lost.
        """
        known_title = "Strategic Context Analysis"
        known_body = {1: "Left content", 2: "Right content"}
        entry = _make_entry(
            semantic_layout_id="layout_heading_and_two_content_with_tiltes",
            injection_data={
                "title": known_title,
                "body_contents": known_body,
                "bold_leads": True,
            },
        )
        slide, contract = self._make_slide_and_contract(
            "layout_heading_and_two_content_with_tiltes",
        )

        with patch("src.services.renderer_v2.inject_multi_body") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            mock_inj.assert_called_once()
            call_kwargs = mock_inj.call_args
            # Verify the EXACT title value was forwarded
            assert call_kwargs.kwargs["title"] == known_title
            # Verify body_contents was also forwarded
            assert call_kwargs.kwargs["body_contents"] == known_body
            # Verify bold_leads was forwarded
            assert call_kwargs.kwargs["bold_leads"] is True

    def test_multi_body_defaults_empty_title_when_missing(self):
        """When injection_data has no 'title' key, empty string is forwarded."""
        entry = _make_entry(
            semantic_layout_id="methodology_overview_4",
            injection_data={"body_contents": {13: "Text"}},
        )
        slide, contract = self._make_slide_and_contract("methodology_overview_4")

        with patch("src.services.renderer_v2.inject_multi_body") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            call_kwargs = mock_inj.call_args
            assert call_kwargs.kwargs["title"] == ""

    def test_team_members_dispatch(self):
        entry = _make_entry(
            semantic_layout_id="team_two_members",
            injection_data={
                "member1_name": "Ahmed", "member1_role": "Partner",
                "member1_bio": "Expert",
            },
        )
        slide, contract = self._make_slide_and_contract("team_two_members")

        with patch("src.services.renderer_v2.inject_team_members") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            mock_inj.assert_called_once()

    def test_title_body_forwards_object_contents(self):
        """Phase G: _inject_content passes object_contents to inject_title_body."""
        obj_data = {1: "• Outcome 1\n• Outcome 2\n• Outcome 3"}
        entry = _make_entry(
            semantic_layout_id="layout_heading_description_and_content_box",
            injection_data={
                "title": "Success Definition",
                "body": "Engagement framing text",
                "object_contents": obj_data,
            },
        )
        slide, contract = self._make_slide_and_contract(
            "layout_heading_description_and_content_box",
        )

        with patch("src.services.renderer_v2.inject_title_body") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            mock_inj.assert_called_once()
            call_kwargs = mock_inj.call_args
            # Verify object_contents was passed with the exact value
            assert call_kwargs.kwargs["object_contents"] == obj_data

    def test_title_body_forwards_none_object_contents_when_absent(self):
        """When injection_data has no object_contents key, None is forwarded."""
        entry = _make_entry(
            semantic_layout_id="content_heading_desc",
            injection_data={"title": "Test", "body": "Body"},
        )
        slide, contract = self._make_slide_and_contract("content_heading_desc")

        with patch("src.services.renderer_v2.inject_title_body") as mock_inj:
            mock_inj.return_value = MagicMock()
            _inject_content(slide, entry, contract)
            call_kwargs = mock_inj.call_args
            assert call_kwargs.kwargs["object_contents"] is None

    def test_unknown_family_returns_none(self):
        entry = _make_entry(
            semantic_layout_id="nonexistent_layout",
            injection_data={"title": "Test"},
        )
        slide, contract = self._make_slide_and_contract("nonexistent_layout")
        result = _inject_content(slide, entry, contract)
        assert result is None


# ── Full render_v2 integration ─────────────────────────────────────────


class TestRenderV2:
    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock")
    @patch("src.services.renderer_v2.load_a2_allowlists")
    @patch("src.services.renderer_v2.validate_manifest")
    def test_hash_mismatch_stops_render(
        self, mock_validate, mock_allowlists, mock_contracts, mock_registry,
    ):
        mock_reg = _make_registry("hash_B")
        mock_registry.return_value = mock_reg

        tm = _make_template_manager("hash_A")
        manifest = ProposalManifest(entries=[])
        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))

        assert result.success is False
        assert any("mismatch" in e for e in result.render_errors)

    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock")
    @patch("src.services.renderer_v2.load_a2_allowlists")
    @patch("src.services.renderer_v2.validate_manifest")
    def test_manifest_errors_stop_render(
        self, mock_validate, mock_allowlists, mock_contracts, mock_registry,
    ):
        mock_registry.return_value = _make_registry("hash_A")
        mock_contracts.return_value = {}
        mock_allowlists.return_value = {}
        mock_validate.return_value = ["Section order violation"]

        tm = _make_template_manager("hash_A")
        manifest = ProposalManifest(entries=[])
        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))

        assert result.success is False
        assert "Section order violation" in result.manifest_errors

    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock")
    @patch("src.services.renderer_v2.load_a2_allowlists")
    @patch("src.services.renderer_v2.validate_manifest")
    @patch("src.services.renderer_v2.run_quality_gate")
    def test_successful_a1_render(
        self, mock_qg, mock_validate, mock_allowlists, mock_contracts,
        mock_registry,
    ):
        from src.services.quality_gate import QualityGateResult

        mock_registry.return_value = _make_registry("hash_A")
        mock_contracts.return_value = {}
        mock_allowlists.return_value = {}
        mock_validate.return_value = []  # no errors
        mock_qg.return_value = QualityGateResult(passed=True)

        tm = _make_template_manager("hash_A")
        entry = _make_entry(entry_type="a1_clone", asset_id="overview")
        manifest = ProposalManifest(entries=[entry])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))

        assert result.success is True
        assert result.total_slides == 1
        assert len(result.records) == 1
        assert result.records[0].entry_type == "a1_clone"
        assert result.records[0].error is None
        tm.clone_a1.assert_called_once_with("overview")
        tm.save.assert_called_once()

    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock")
    @patch("src.services.renderer_v2.load_a2_allowlists")
    @patch("src.services.renderer_v2.validate_manifest")
    def test_registry_load_failure_stops_render(
        self, mock_validate, mock_allowlists, mock_contracts, mock_registry,
    ):
        mock_registry.side_effect = RuntimeError("Registry file not found")

        tm = _make_template_manager()
        manifest = ProposalManifest(entries=[])
        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))

        assert result.success is False
        assert any("Registry load" in e for e in result.render_errors)

    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock")
    @patch("src.services.renderer_v2.load_a2_allowlists")
    @patch("src.services.renderer_v2.validate_manifest")
    def test_render_error_in_slide_recorded(
        self, mock_validate, mock_allowlists, mock_contracts, mock_registry,
    ):
        mock_registry.return_value = _make_registry("hash_A")
        mock_contracts.return_value = {}
        mock_allowlists.return_value = {}
        mock_validate.return_value = []

        tm = _make_template_manager("hash_A")
        tm.clone_a1.side_effect = RuntimeError("Clone failed")

        entry = _make_entry(entry_type="a1_clone", asset_id="bad_asset")
        manifest = ProposalManifest(entries=[entry])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))

        assert result.total_slides == 1
        assert result.records[0].error is not None
        assert "Clone failed" in result.records[0].error

    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock")
    @patch("src.services.renderer_v2.load_a2_allowlists")
    @patch("src.services.renderer_v2.validate_manifest")
    def test_template_hash_stored_in_result(
        self, mock_validate, mock_allowlists, mock_contracts, mock_registry,
    ):
        mock_registry.return_value = _make_registry("hash_XYZ")
        mock_contracts.return_value = {}
        mock_allowlists.return_value = {}
        mock_validate.return_value = []

        tm = _make_template_manager("hash_XYZ")
        manifest = ProposalManifest(entries=[])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))
        assert result.template_hash == "hash_XYZ"


# ── Semantic-ID-only resolution ────────────────────────────────────────


class TestSemanticIDOnly:
    def test_record_uses_semantic_layout_id(self):
        r = SlideRenderRecord(
            manifest_index=0, entry_type="b_variable",
            asset_id="test", semantic_layout_id="methodology_detail",
            section_id="section_03",
        )
        assert r.semantic_layout_id == "methodology_detail"
        # No raw slide index on the record
        assert not hasattr(r, "slide_idx")

    def test_no_raw_indices_in_manifest_entry(self):
        entry = _make_entry(
            semantic_layout_id="content_heading_desc",
            section_id="section_01",
        )
        assert not hasattr(entry, "slide_idx")
        assert entry.semantic_layout_id == "content_heading_desc"


# ── Zero-legacy-imports guardrail ──────────────────────────────────────


class TestZeroLegacyImports:
    def test_no_import_from_renderer(self):
        """renderer_v2.py must not import from renderer.py."""
        source_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "services" / "renderer_v2.py"
        )
        source = source_path.read_text(encoding="utf-8")
        # Check for imports from legacy renderer
        assert "from src.services.renderer " not in source
        assert "import src.services.renderer" not in source

    def test_no_import_from_formatting(self):
        """renderer_v2.py must not import from formatting.py."""
        source_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "services" / "renderer_v2.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "from src.services.formatting" not in source
        assert "import src.services.formatting" not in source

    def test_no_import_from_design_tokens_geometry(self):
        """renderer_v2.py must not import design_tokens geometry."""
        source_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "services" / "renderer_v2.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "design_tokens" not in source


# ── Zero-shape-creation guardrail ──────────────────────────────────────


class TestZeroShapeCreation:
    def test_source_has_no_shape_creation_calls(self):
        """renderer_v2.py must never call shape creation methods."""
        source_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "services" / "renderer_v2.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert ".add_shape(" not in source
        assert ".add_textbox(" not in source
        assert ".add_table(" not in source
        assert ".add_picture(" not in source

    def test_all_v2_path_modules_no_shape_creation(self):
        """All v2-path modules must have zero shape creation calls."""
        base = Path(__file__).resolve().parent.parent.parent / "src" / "services"
        v2_modules = [
            "renderer_v2.py",
            "placeholder_injectors.py",
            "shell_sanitizer.py",
            "content_fitter.py",
        ]
        for mod_name in v2_modules:
            source = (base / mod_name).read_text(encoding="utf-8")
            for forbidden in [".add_shape(", ".add_textbox(", ".add_table(", ".add_picture("]:
                assert forbidden not in source, (
                    f"{mod_name} contains forbidden call: {forbidden}"
                )


# ── Import isolation via AST ───────────────────────────────────────────


class TestImportIsolation:
    def test_renderer_v2_imports_are_safe(self):
        """Verify renderer_v2 only imports from approved modules."""
        source_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "services" / "renderer_v2.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        forbidden_sources = {
            "src.services.renderer",
            "src.services.formatting",
            "src.services.design_tokens",
            "src.utils.formatting",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for forbidden in forbidden_sources:
                    assert not node.module.startswith(forbidden), (
                        f"renderer_v2.py imports from forbidden module: {node.module}"
                    )
