"""Tests for post-render zero-placeholder verification.

Proves that verify_zero_placeholders:
  1. Detects unfilled placeholders on b_variable slides
  2. Detects remaining template syntax in injected content
  3. Returns clean when all placeholders are filled
  4. Is wired into the live render_v2() path (fail-closed)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.placeholder_injectors import InjectedPlaceholder, InjectionResult
from src.services.renderer_v2 import (
    RenderResult,
    SlideRenderRecord,
    render_v2,
    verify_zero_placeholders,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _make_record(
    *,
    entry_type: str = "b_variable",
    asset_id: str = "slide_01",
    idx: int = 0,
    injected: tuple[InjectedPlaceholder, ...] = (),
    skipped: tuple[int, ...] = (),
    skipped_types: tuple[str, ...] = (),
    error: str | None = None,
) -> SlideRenderRecord:
    return SlideRenderRecord(
        manifest_index=idx,
        entry_type=entry_type,
        asset_id=asset_id,
        semantic_layout_id="content_heading_desc",
        section_id="section_01",
        injection_result=InjectionResult(
            semantic_layout_id="content_heading_desc",
            injected=injected,
            skipped=skipped,
            skipped_types=skipped_types,
        ),
        error=error,
    )


def _injected(ph_idx: int, preview: str) -> InjectedPlaceholder:
    return InjectedPlaceholder(
        placeholder_idx=ph_idx,
        placeholder_type="BODY",
        content_preview=preview,
    )


# ── Tests ──────────────────────────────────────────────────────────────


class TestVerifyZeroPlaceholders:
    """Post-render zero-placeholder audit."""

    def test_clean_result(self):
        """All placeholders filled, no template syntax → clean."""
        record = _make_record(
            injected=(
                _injected(0, "Strategic Understanding"),
                _injected(13, "Our approach focuses on transformation"),
            ),
            skipped=(),
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert audit.clean
        assert audit.unfilled_placeholders == []
        assert audit.template_syntax_found == []

    def test_skipped_non_text_placeholders_informational(self):
        """Skipped OBJECT/TABLE on b_variable → informational, audit stays clean."""
        record = _make_record(
            entry_type="b_variable",
            injected=(_injected(0, "Title"),),
            skipped=(1, 2),
            skipped_types=("OBJECT", "TABLE"),
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert audit.clean  # non-text skipped = informational only
        assert len(audit.unfilled_non_text) == 2
        assert len(audit.unfilled_required) == 0

    def test_skipped_required_text_placeholder_fails_closed(self):
        """Skipped BODY on b_variable → unfilled_required, audit is dirty."""
        record = _make_record(
            entry_type="b_variable",
            injected=(_injected(0, "Title"),),
            skipped=(13,),
            skipped_types=("BODY",),
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert not audit.clean  # required text placeholder unfilled = hard fail
        assert len(audit.unfilled_required) == 1
        assert "BODY" in audit.unfilled_required[0]
        assert "idx 13" in audit.unfilled_required[0]

    def test_mixed_skipped_required_and_non_text(self):
        """Mix of required BODY + non-text OBJECT → dirty (BODY is required)."""
        record = _make_record(
            entry_type="b_variable",
            injected=(_injected(0, "Title"),),
            skipped=(13, 42),
            skipped_types=("BODY", "OBJECT"),
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert not audit.clean  # BODY unfilled = hard fail
        assert len(audit.unfilled_required) == 1
        assert len(audit.unfilled_non_text) == 1

    def test_skipped_placeholders_on_a1_clone_ignored(self):
        """Skipped placeholders on a1_clone → NOT flagged (template-owned)."""
        record = _make_record(
            entry_type="a1_clone",
            asset_id="company_overview",
            injected=(),
            skipped=(5, 6),
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert audit.clean

    def test_template_syntax_double_braces(self):
        """{{placeholder}} syntax in content → flagged."""
        record = _make_record(
            injected=(_injected(0, "Hello {{client_name}} world"),),
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert not audit.clean
        assert len(audit.template_syntax_found) == 1
        assert "{{client_name}}" in audit.template_syntax_found[0]

    def test_template_syntax_placeholder_bracket(self):
        """[PLACEHOLDER: ...] syntax in content → flagged."""
        record = _make_record(
            injected=(_injected(13, "Text with [PLACEHOLDER: add detail]"),),
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert not audit.clean
        assert len(audit.template_syntax_found) == 1

    def test_template_syntax_tbc(self):
        """[TBC] in content → flagged."""
        record = _make_record(
            injected=(_injected(0, "Timeline: [TBC]"),),
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert not audit.clean

    def test_template_syntax_insert(self):
        """[INSERT ...] in content → flagged."""
        record = _make_record(
            injected=(_injected(0, "[INSERT client requirements here]"),),
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert not audit.clean

    def test_no_injection_result_skipped(self):
        """Record with no injection_result → no crash."""
        record = SlideRenderRecord(
            manifest_index=0,
            entry_type="a1_clone",
            asset_id="cover",
            semantic_layout_id="proposal_cover",
            section_id="cover",
            injection_result=None,
        )
        result = RenderResult(records=[record], total_slides=1)
        audit = verify_zero_placeholders(result)
        assert audit.clean

    def test_multiple_issues_aggregated(self):
        """Multiple records with issues → all aggregated."""
        records = [
            _make_record(
                idx=0,
                asset_id="slide_01",
                injected=(_injected(0, "{{missing}}"),),
                skipped=(13,),
                skipped_types=("BODY",),
            ),
            _make_record(
                idx=1,
                asset_id="slide_02",
                injected=(_injected(0, "[TBD]"),),
            ),
        ]
        result = RenderResult(records=records, total_slides=2)
        audit = verify_zero_placeholders(result)
        assert not audit.clean
        # 1 unfilled required (BODY) + 2 template syntax
        assert len(audit.unfilled_required) == 1
        assert len(audit.template_syntax_found) == 2


# ── Integration tests — live render path ──────────────────────────────


def _make_dirty_record_template_syntax() -> SlideRenderRecord:
    """b_variable record with template syntax → dirty audit."""
    return SlideRenderRecord(
        manifest_index=0,
        entry_type="b_variable",
        asset_id="slide_01",
        semantic_layout_id="content_heading_desc",
        section_id="section_01",
        injection_result=InjectionResult(
            semantic_layout_id="content_heading_desc",
            injected=(
                InjectedPlaceholder(
                    placeholder_idx=0,
                    placeholder_type="BODY",
                    content_preview="Hello {{client_name}} world",
                ),
            ),
            skipped=(),
        ),
    )


def _make_dirty_record_unfilled_required() -> SlideRenderRecord:
    """b_variable record with unfilled required BODY placeholder → dirty."""
    return SlideRenderRecord(
        manifest_index=0,
        entry_type="b_variable",
        asset_id="slide_01",
        semantic_layout_id="content_heading_desc",
        section_id="section_01",
        injection_result=InjectionResult(
            semantic_layout_id="content_heading_desc",
            injected=(
                InjectedPlaceholder(
                    placeholder_idx=0,
                    placeholder_type="TITLE",
                    content_preview="Slide Title",
                ),
            ),
            skipped=(13,),
            skipped_types=("BODY",),
        ),
    )


def _make_clean_record_with_non_text_skipped() -> SlideRenderRecord:
    """b_variable record with OBJECT skipped (expected) → clean audit."""
    return SlideRenderRecord(
        manifest_index=0,
        entry_type="b_variable",
        asset_id="slide_01",
        semantic_layout_id="content_heading_desc",
        section_id="section_01",
        injection_result=InjectionResult(
            semantic_layout_id="content_heading_desc",
            injected=(
                InjectedPlaceholder(
                    placeholder_idx=0,
                    placeholder_type="BODY",
                    content_preview="Strategic transformation approach",
                ),
            ),
            skipped=(1, 2),
            skipped_types=("OBJECT", "TABLE"),
        ),
    )


def _make_clean_record() -> SlideRenderRecord:
    """b_variable record with real content → clean audit."""
    return SlideRenderRecord(
        manifest_index=0,
        entry_type="b_variable",
        asset_id="slide_01",
        semantic_layout_id="content_heading_desc",
        section_id="section_01",
        injection_result=InjectionResult(
            semantic_layout_id="content_heading_desc",
            injected=(
                InjectedPlaceholder(
                    placeholder_idx=0,
                    placeholder_type="BODY",
                    content_preview="Strategic transformation approach",
                ),
            ),
            skipped=(),
        ),
    )


def _render_v2_manifest():
    """Shared single-slide manifest for integration tests."""
    from src.models.proposal_manifest import (
        ContentSourcePolicy,
        ManifestEntry,
        ProposalManifest,
    )
    return ProposalManifest(entries=[
        ManifestEntry(
            entry_type="b_variable",
            asset_id="slide_01",
            semantic_layout_id="content_heading_desc",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
            section_id="section_01",
        ),
    ])


_RENDER_PATCHES = [
    "src.services.renderer_v2.validate_manifest",
    "src.services.renderer_v2.load_registry",
    "src.services.renderer_v2._enforce_template_hash",
    "src.services.renderer_v2.build_contracts_from_catalog_lock",
    "src.services.renderer_v2.load_a2_allowlists",
    "src.services.renderer_v2._render_entry",
    "src.services.renderer_v2.run_quality_gate",
]


class TestRenderV2ZeroPlaceholderIntegration:
    """Proves render_v2() calls verify_zero_placeholders and fails closed."""

    @patch(_RENDER_PATCHES[5])
    @patch(_RENDER_PATCHES[4], return_value={})
    @patch(_RENDER_PATCHES[3], return_value={})
    @patch(_RENDER_PATCHES[2])
    @patch(_RENDER_PATCHES[1])
    @patch(_RENDER_PATCHES[0], return_value=[])
    def test_template_syntax_blocks_render(
        self, _v, mock_reg, _h, _c, _a, mock_entry,
    ):
        """Template syntax in content → fail-closed, no save."""
        mock_reg.return_value = MagicMock(template_hash="abc123")
        mock_entry.return_value = _make_dirty_record_template_syntax()

        tm = MagicMock()
        result = render_v2(_render_v2_manifest(), tm, Path("f.json"), Path("o.pptx"))

        assert not result.success, "Template syntax must block render"
        assert "Zero-placeholder audit failed" in result.render_errors[0]
        assert "{{client_name}}" in result.render_errors[0]
        assert result.placeholder_audit is not None
        assert not result.placeholder_audit.clean
        tm.save.assert_not_called()
        tm.remove_original_slides.assert_not_called()

    @patch(_RENDER_PATCHES[5])
    @patch(_RENDER_PATCHES[4], return_value={})
    @patch(_RENDER_PATCHES[3], return_value={})
    @patch(_RENDER_PATCHES[2])
    @patch(_RENDER_PATCHES[1])
    @patch(_RENDER_PATCHES[0], return_value=[])
    def test_unfilled_required_body_blocks_render(
        self, _v, mock_reg, _h, _c, _a, mock_entry,
    ):
        """Unfilled required BODY placeholder on b_variable → fail-closed."""
        mock_reg.return_value = MagicMock(template_hash="abc123")
        mock_entry.return_value = _make_dirty_record_unfilled_required()

        tm = MagicMock()
        result = render_v2(_render_v2_manifest(), tm, Path("f.json"), Path("o.pptx"))

        assert not result.success, "Unfilled BODY must block render"
        assert "Zero-placeholder audit failed" in result.render_errors[0]
        assert "BODY" in result.render_errors[0]
        assert result.placeholder_audit is not None
        assert len(result.placeholder_audit.unfilled_required) == 1
        assert not result.placeholder_audit.clean
        tm.save.assert_not_called()
        tm.remove_original_slides.assert_not_called()

    @patch(_RENDER_PATCHES[6])
    @patch(_RENDER_PATCHES[5])
    @patch(_RENDER_PATCHES[4], return_value={})
    @patch(_RENDER_PATCHES[3], return_value={})
    @patch(_RENDER_PATCHES[2])
    @patch(_RENDER_PATCHES[1])
    @patch(_RENDER_PATCHES[0], return_value=[])
    def test_non_text_skipped_allows_render(
        self, _v, mock_reg, _h, _c, _a, mock_entry, mock_qg,
    ):
        """Skipped OBJECT/TABLE (non-text) on b_variable → render succeeds."""
        from src.services.quality_gate import QualityGateResult

        mock_reg.return_value = MagicMock(template_hash="abc123")
        mock_entry.return_value = _make_clean_record_with_non_text_skipped()
        mock_qg.return_value = QualityGateResult(passed=True)

        tm = MagicMock()
        tm.save.return_value = Path("o.pptx")
        result = render_v2(_render_v2_manifest(), tm, Path("f.json"), Path("o.pptx"))

        assert result.success, f"Non-text skipped must allow render: {result.render_errors}"
        assert result.placeholder_audit is not None
        assert result.placeholder_audit.clean
        assert len(result.placeholder_audit.unfilled_non_text) == 2
        tm.save.assert_called_once()
        tm.remove_original_slides.assert_called_once()

    @patch(_RENDER_PATCHES[6])
    @patch(_RENDER_PATCHES[5])
    @patch(_RENDER_PATCHES[4], return_value={})
    @patch(_RENDER_PATCHES[3], return_value={})
    @patch(_RENDER_PATCHES[2])
    @patch(_RENDER_PATCHES[1])
    @patch(_RENDER_PATCHES[0], return_value=[])
    def test_clean_audit_allows_render(
        self, _v, mock_reg, _h, _c, _a, mock_entry, mock_qg,
    ):
        """Clean zero-placeholder audit → render proceeds to save."""
        from src.services.quality_gate import QualityGateResult

        mock_reg.return_value = MagicMock(template_hash="abc123")
        mock_entry.return_value = _make_clean_record()
        mock_qg.return_value = QualityGateResult(passed=True)

        tm = MagicMock()
        tm.save.return_value = Path("o.pptx")
        result = render_v2(_render_v2_manifest(), tm, Path("f.json"), Path("o.pptx"))

        assert result.success, f"Clean audit must allow render: {result.render_errors}"
        assert result.placeholder_audit is not None
        assert result.placeholder_audit.clean
        assert len(result.render_errors) == 0
        tm.remove_original_slides.assert_called_once()
        tm.save.assert_called_once()
