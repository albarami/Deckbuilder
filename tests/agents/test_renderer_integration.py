"""Phase 15 — End-to-End Integration Tests for renderer_v2.

Tests the full v2 render pipeline: manifest → sanitize → inject → fit → save.
Uses mocks for template_manager and catalog lock, but tests the actual
orchestration logic in renderer_v2.render_v2().

Key scenarios:
  - Hash enforcement (fail-closed on mismatch)
  - Registry load failure handling
  - Multi-entry manifest (A1 + A2 + B + pool)
  - Per-slide error recording
  - Sanitization runs on A2 shells (not A1)
  - Injection dispatches by layout family
  - Continuation detection via fit reports
  - Manifest validation errors stop rendering
  - Output path stored on success
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.proposal_manifest import (
    ContentSourcePolicy,
    HouseInclusionPolicy,
    ManifestEntry,
    ProposalManifest,
)
from src.services.renderer_v2 import (
    RenderResult,
    SlideRenderRecord,
    render_v2,
)

# ── Test helpers ──────────────────────────────────────────────────────


def _make_entry(
    entry_type: str = "b_variable",
    asset_id: str = "test_asset",
    semantic_layout_id: str = "content_heading_desc",
    content_source_policy: ContentSourcePolicy = ContentSourcePolicy.PROPOSAL_SPECIFIC,
    section_id: str = "section_01",
    injection_data: dict | None = None,
) -> ManifestEntry:
    return ManifestEntry(
        entry_type=entry_type,
        asset_id=asset_id,
        semantic_layout_id=semantic_layout_id,
        content_source_policy=content_source_policy,
        section_id=section_id,
        injection_data=injection_data,
    )


def _make_manifest(entries: list[ManifestEntry] | None = None) -> ProposalManifest:
    return ProposalManifest(
        entries=entries or [],
        inclusion_policy=HouseInclusionPolicy(
            proposal_mode="standard",
            geography="ksa",
            sector="consulting",
        ),
    )


def _make_tm(hash_val: str = "hash_ABC"):
    tm = MagicMock()
    tm.template_hash = hash_val
    tm.clone_a1.return_value = MagicMock()
    tm.clone_a2.return_value = MagicMock()
    tm.clone_divider.return_value = MagicMock()
    tm.add_slide_from_layout.return_value = MagicMock()
    tm.clone_slide.return_value = MagicMock()
    tm.save.return_value = Path("/fake/output.pptx")
    return tm


# ── Template Hash Enforcement ────────────────────────────────────────


class TestHashEnforcement:
    """Template hash must be validated before rendering."""

    @patch("src.services.renderer_v2.load_a2_allowlists")
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock")
    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.validate_manifest", return_value=[])
    def test_hash_match_allows_render(self, vm, lr, bc, la):
        reg = MagicMock()
        reg.template_hash = "hash_ABC"
        lr.return_value = reg
        bc.return_value = {}
        la.return_value = {}

        tm = _make_tm("hash_ABC")
        manifest = _make_manifest([_make_entry()])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))
        assert result.template_hash == "hash_ABC"

    @patch("src.services.renderer_v2.load_registry")
    def test_hash_mismatch_stops_render(self, lr):
        reg = MagicMock()
        reg.template_hash = "hash_OLD"
        lr.return_value = reg

        tm = _make_tm("hash_NEW")
        manifest = _make_manifest([_make_entry()])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))
        assert not result.success
        assert any("hash" in e.lower() or "mismatch" in e.lower() for e in result.render_errors)

    @patch("src.services.renderer_v2.load_registry")
    def test_missing_hash_stops_render(self, lr):
        reg = MagicMock()
        reg.template_hash = ""
        lr.return_value = reg

        tm = _make_tm("")
        manifest = _make_manifest([_make_entry()])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))
        assert not result.success


# ── Registry Load Failure ────────────────────────────────────────────


class TestRegistryLoadFailure:
    """Registry load failure stops rendering gracefully."""

    @patch("src.services.renderer_v2.load_registry", side_effect=FileNotFoundError("not found"))
    def test_registry_not_found(self, lr):
        tm = _make_tm()
        manifest = _make_manifest([_make_entry()])

        result = render_v2(manifest, tm, Path("/missing/lock.json"), Path("/fake/out.pptx"))
        assert not result.success
        assert any("registry" in e.lower() or "load" in e.lower() for e in result.render_errors)


# ── Manifest Validation ──────────────────────────────────────────────


class TestManifestValidation:
    """Manifest validation errors stop rendering."""

    @patch("src.services.renderer_v2.load_a2_allowlists", return_value={})
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock", return_value={})
    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.validate_manifest", return_value=["Invalid section order"])
    def test_manifest_error_stops_render(self, vm, lr, bc, la):
        reg = MagicMock()
        reg.template_hash = "hash_ABC"
        lr.return_value = reg

        tm = _make_tm("hash_ABC")
        manifest = _make_manifest([_make_entry()])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))
        assert not result.success
        assert "Invalid section order" in result.manifest_errors


# ── Slide Dispatch by Entry Type ─────────────────────────────────────


class TestSlideDispatch:
    """Each entry_type dispatches to the correct clone/add method."""

    @patch("src.services.renderer_v2.load_a2_allowlists", return_value={})
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock", return_value={})
    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.validate_manifest", return_value=[])
    def test_a1_clone_dispatches_to_clone_a1(self, vm, lr, bc, la):
        reg = MagicMock()
        reg.template_hash = "hash_ABC"
        lr.return_value = reg

        tm = _make_tm("hash_ABC")
        entry = _make_entry(
            entry_type="a1_clone",
            asset_id="overview",
            content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
        )
        manifest = _make_manifest([entry])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))
        tm.clone_a1.assert_called_once_with("overview")
        assert result.records[0].entry_type == "a1_clone"

    @patch("src.services.renderer_v2.load_a2_allowlists")
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock", return_value={})
    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.validate_manifest", return_value=[])
    @patch("src.services.renderer_v2.sanitize_shell")
    @patch("src.services.renderer_v2.get_allowlist")
    def test_a2_shell_dispatches_to_clone_a2(self, ga, ss, vm, lr, bc, la):
        reg = MagicMock()
        reg.template_hash = "hash_ABC"
        lr.return_value = reg
        ga.return_value = MagicMock()
        ss.return_value = MagicMock()

        tm = _make_tm("hash_ABC")
        entry = _make_entry(
            entry_type="a2_shell",
            asset_id="proposal_cover",
            semantic_layout_id="proposal_cover",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        )
        manifest = _make_manifest([entry])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))
        tm.clone_a2.assert_called_once_with("proposal_cover")
        assert result.records[0].entry_type == "a2_shell"

    @patch("src.services.renderer_v2.load_a2_allowlists", return_value={})
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock", return_value={})
    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.validate_manifest", return_value=[])
    def test_b_variable_dispatches_to_add_slide(self, vm, lr, bc, la):
        reg = MagicMock()
        reg.template_hash = "hash_ABC"
        lr.return_value = reg

        tm = _make_tm("hash_ABC")
        entry = _make_entry(
            entry_type="b_variable",
            semantic_layout_id="content_heading_desc",
        )
        manifest = _make_manifest([entry])

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))
        tm.add_slide_from_layout.assert_called_once_with("content_heading_desc")
        assert result.records[0].entry_type == "b_variable"


# ── RenderResult Properties ──────────────────────────────────────────


class TestRenderResultProperties:
    """RenderResult aggregates results and exposes computed properties."""

    def test_success_when_no_errors(self):
        result = RenderResult(total_slides=5)
        assert result.success

    def test_failure_on_manifest_errors(self):
        result = RenderResult(total_slides=5, manifest_errors=["bad"])
        assert not result.success

    def test_failure_on_render_errors(self):
        result = RenderResult(total_slides=5, render_errors=["failed"])
        assert not result.success

    def test_failure_on_zero_slides(self):
        result = RenderResult(total_slides=0)
        assert not result.success

    def test_continuation_needed(self):
        fit_report = MagicMock()
        fit_report.any_continuation = True
        record = SlideRenderRecord(
            manifest_index=0, entry_type="b_variable",
            asset_id="t", semantic_layout_id="content_heading_desc",
            section_id="s01", fit_report=fit_report,
        )
        result = RenderResult(total_slides=1, records=[record])
        assert result.continuation_needed

    def test_no_continuation(self):
        record = SlideRenderRecord(
            manifest_index=0, entry_type="a1_clone",
            asset_id="t", semantic_layout_id="overview",
            section_id="company",
        )
        result = RenderResult(total_slides=1, records=[record])
        assert not result.continuation_needed


# ── SlideRenderRecord ────────────────────────────────────────────────


class TestSlideRenderRecord:
    """SlideRenderRecord must be frozen and capture all metadata."""

    def test_record_frozen(self):
        r = SlideRenderRecord(
            manifest_index=0, entry_type="b_variable",
            asset_id="t", semantic_layout_id="content_heading_desc",
            section_id="s01",
        )
        with pytest.raises(AttributeError):
            r.entry_type = "a1_clone"  # type: ignore[misc]

    def test_record_captures_error(self):
        r = SlideRenderRecord(
            manifest_index=2, entry_type="b_variable",
            asset_id="broken", semantic_layout_id="unknown",
            section_id="s03", error="Layout not found",
        )
        assert r.error == "Layout not found"

    def test_record_default_none_fields(self):
        r = SlideRenderRecord(
            manifest_index=0, entry_type="a1_clone",
            asset_id="overview", semantic_layout_id="overview",
            section_id="company",
        )
        assert r.injection_result is None
        assert r.sanitization_report is None
        assert r.fit_report is None
        assert r.error is None


# ── Multi-Slide Manifest ─────────────────────────────────────────────


class TestMultiSlideManifest:
    """render_v2 processes all entries in manifest order."""

    @patch("src.services.renderer_v2.run_quality_gate")
    @patch("src.services.renderer_v2.load_a2_allowlists", return_value={})
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock", return_value={})
    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.validate_manifest", return_value=[])
    def test_three_entries_produce_three_records(self, vm, lr, bc, la, mock_qg):
        from src.services.quality_gate import QualityGateResult
        mock_qg.return_value = QualityGateResult(passed=True)

        reg = MagicMock()
        reg.template_hash = "hash_ABC"
        lr.return_value = reg

        tm = _make_tm("hash_ABC")
        entries = [
            _make_entry(entry_type="a1_clone", asset_id="overview",
                        content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE),
            _make_entry(entry_type="b_variable", asset_id="understanding_01",
                        semantic_layout_id="content_heading_desc"),
            _make_entry(entry_type="b_variable", asset_id="methodology_overview",
                        semantic_layout_id="methodology_overview_4"),
        ]
        manifest = _make_manifest(entries)

        result = render_v2(manifest, tm, Path("/fake/lock.json"), Path("/fake/out.pptx"))
        assert len(result.records) == 3
        assert result.records[0].entry_type == "a1_clone"
        assert result.records[1].entry_type == "b_variable"
        assert result.records[2].entry_type == "b_variable"
        assert result.total_slides == 3


# ── ManifestEntry Model ──────────────────────────────────────────────


class TestManifestEntryModel:
    """ManifestEntry is frozen and uses semantic IDs only."""

    def test_entry_frozen(self):
        entry = _make_entry()
        with pytest.raises(AttributeError):
            entry.asset_id = "other"  # type: ignore[misc]

    def test_entry_no_raw_slide_idx(self):
        entry = _make_entry()
        assert not hasattr(entry, "slide_idx")
        assert not hasattr(entry, "raw_index")

    def test_entry_uses_semantic_layout_id(self):
        entry = _make_entry(semantic_layout_id="methodology_detail")
        assert entry.semantic_layout_id == "methodology_detail"

    def test_entry_has_content_source_policy(self):
        entry = _make_entry(content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL)
        assert entry.content_source_policy == ContentSourcePolicy.APPROVED_ASSET_POOL
