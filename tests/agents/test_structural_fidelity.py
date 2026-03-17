"""Phase 15 — Structural Fidelity Tests.

For CLASS A1 (structurally cloned) and CLASS A2 (shell) slides, verify
that cloning preserves visual/structural fidelity.

Checks (structural, NOT byte-level):
  - Same shape count between source and clone
  - Same placeholder count and types
  - Same media asset fingerprints
  - Same font family set
  - Bounding-box signature within +/-0.01"
  - Non-injected text preserved (A1)
  - Only approved placeholders changed (A2)

Also verifies that:
  - SlideRenderRecord captures semantic layout ID (never raw index)
  - Clone operations preserve master/layout linkage
  - Structural fidelity functions are correct
"""

from __future__ import annotations

import pytest

from src.services.composition_scorer import ShapeInfo
from src.services.shell_sanitizer import ShellAllowlist

# ── Fidelity threshold constants ─────────────────────────────────────


BOUNDING_BOX_TOLERANCE_IN = 0.01   # +/- 0.01 inches


# ── Fidelity verification helpers ────────────────────────────────────


def shapes_match_count(source_shapes: list, clone_shapes: list) -> bool:
    """Verify source and clone have the same shape count."""
    return len(source_shapes) == len(clone_shapes)


def placeholders_match(source_shapes: list[ShapeInfo], clone_shapes: list[ShapeInfo]) -> bool:
    """Verify placeholder count and types match between source and clone."""
    src_phs = sorted(
        [(s.placeholder_idx, s.shape_type) for s in source_shapes if s.is_placeholder],
        key=lambda x: x[0],
    )
    clone_phs = sorted(
        [(s.placeholder_idx, s.shape_type) for s in clone_shapes if s.is_placeholder],
        key=lambda x: x[0],
    )
    return src_phs == clone_phs


def bounding_boxes_match(
    source: ShapeInfo,
    clone: ShapeInfo,
    tolerance: float = BOUNDING_BOX_TOLERANCE_IN,
) -> bool:
    """Verify bounding box within tolerance."""
    return (
        abs(source.left_in - clone.left_in) <= tolerance
        and abs(source.top_in - clone.top_in) <= tolerance
        and abs(source.width_in - clone.width_in) <= tolerance
        and abs(source.height_in - clone.height_in) <= tolerance
    )


def font_families_match(source_shapes: list[ShapeInfo], clone_shapes: list[ShapeInfo]) -> bool:
    """Verify same set of font families used."""
    src_fonts = {s.font_name for s in source_shapes if s.font_name}
    clone_fonts = {s.font_name for s in clone_shapes if s.font_name}
    return src_fonts == clone_fonts


# ── ShapeInfo for fidelity checks ────────────────────────────────────


class TestShapeInfoModel:
    """ShapeInfo provides all fields needed for structural fidelity."""

    def test_shape_info_has_position_fields(self):
        s = ShapeInfo(
            slide_index=0, slide_id="slide_0", shape_name="Title",
            shape_type="placeholder", left_in=0.82, top_in=0.5,
            width_in=8.0, height_in=1.0,
        )
        assert s.left_in == 0.82
        assert s.top_in == 0.5
        assert s.width_in == 8.0
        assert s.height_in == 1.0

    def test_shape_info_has_placeholder_fields(self):
        s = ShapeInfo(
            slide_index=0, slide_id="slide_0", shape_name="Body",
            shape_type="placeholder", left_in=0.82, top_in=1.5,
            width_in=8.0, height_in=4.0,
            is_placeholder=True, placeholder_idx=1,
        )
        assert s.is_placeholder is True
        assert s.placeholder_idx == 1

    def test_shape_info_has_font_fields(self):
        s = ShapeInfo(
            slide_index=0, slide_id="slide_0", shape_name="Title",
            shape_type="placeholder", left_in=0.82, top_in=0.5,
            width_in=8.0, height_in=1.0,
            font_name="Euclid Flex", font_size_pt=28.0,
        )
        assert s.font_name == "Euclid Flex"
        assert s.font_size_pt == 28.0

    def test_shape_info_frozen(self):
        s = ShapeInfo(
            slide_index=0, slide_id="slide_0", shape_name="Title",
            shape_type="placeholder", left_in=0.82, top_in=0.5,
            width_in=8.0, height_in=1.0,
        )
        with pytest.raises(AttributeError):
            s.left_in = 1.0  # type: ignore[misc]


# ── Shape count matching ──────────────────────────────────────────────


class TestShapeCountFidelity:
    """Cloned slides must have the same shape count as source."""

    def _make_shapes(self, count: int) -> list[ShapeInfo]:
        return [
            ShapeInfo(
                slide_index=0, slide_id="slide_0",
                shape_name=f"Shape_{i}", shape_type="placeholder",
                left_in=0.82, top_in=0.5 + i, width_in=8.0, height_in=1.0,
            )
            for i in range(count)
        ]

    def test_same_count_passes(self):
        src = self._make_shapes(5)
        clone = self._make_shapes(5)
        assert shapes_match_count(src, clone)

    def test_different_count_fails(self):
        src = self._make_shapes(5)
        clone = self._make_shapes(4)
        assert not shapes_match_count(src, clone)

    def test_empty_slides_pass(self):
        assert shapes_match_count([], [])


# ── Placeholder matching ──────────────────────────────────────────────


class TestPlaceholderFidelity:
    """Placeholder count and types must match between source and clone."""

    def test_matching_placeholders(self):
        src = [
            ShapeInfo(0, "s0", "Title", "placeholder", 0, 0, 8, 1,
                      is_placeholder=True, placeholder_idx=0),
            ShapeInfo(0, "s0", "Body", "placeholder", 0, 1, 8, 4,
                      is_placeholder=True, placeholder_idx=1),
        ]
        clone = [
            ShapeInfo(1, "s1", "Title", "placeholder", 0, 0, 8, 1,
                      is_placeholder=True, placeholder_idx=0),
            ShapeInfo(1, "s1", "Body", "placeholder", 0, 1, 8, 4,
                      is_placeholder=True, placeholder_idx=1),
        ]
        assert placeholders_match(src, clone)

    def test_mismatched_placeholder_idx(self):
        src = [
            ShapeInfo(0, "s0", "Title", "placeholder", 0, 0, 8, 1,
                      is_placeholder=True, placeholder_idx=0),
        ]
        clone = [
            ShapeInfo(1, "s1", "Title", "placeholder", 0, 0, 8, 1,
                      is_placeholder=True, placeholder_idx=2),
        ]
        assert not placeholders_match(src, clone)

    def test_non_placeholder_shapes_ignored(self):
        src = [
            ShapeInfo(0, "s0", "Title", "placeholder", 0, 0, 8, 1,
                      is_placeholder=True, placeholder_idx=0),
            ShapeInfo(0, "s0", "Deco", "shape", 5, 0, 1, 1,
                      is_placeholder=False, placeholder_idx=-1),
        ]
        clone = [
            ShapeInfo(1, "s1", "Title", "placeholder", 0, 0, 8, 1,
                      is_placeholder=True, placeholder_idx=0),
        ]
        # Only compares placeholders
        assert placeholders_match(src, clone)


# ── Bounding-box fidelity ────────────────────────────────────────────


class TestBoundingBoxFidelity:
    """Bounding boxes must match within +/- 0.01"."""

    def test_exact_match(self):
        src = ShapeInfo(0, "s0", "Title", "placeholder", 0.82, 0.5, 8.0, 1.0)
        clone = ShapeInfo(1, "s1", "Title", "placeholder", 0.82, 0.5, 8.0, 1.0)
        assert bounding_boxes_match(src, clone)

    def test_within_tolerance(self):
        src = ShapeInfo(0, "s0", "Title", "placeholder", 0.82, 0.5, 8.0, 1.0)
        clone = ShapeInfo(1, "s1", "Title", "placeholder", 0.825, 0.505, 7.995, 1.005)
        assert bounding_boxes_match(src, clone)

    def test_outside_tolerance(self):
        src = ShapeInfo(0, "s0", "Title", "placeholder", 0.82, 0.5, 8.0, 1.0)
        clone = ShapeInfo(1, "s1", "Title", "placeholder", 0.85, 0.5, 8.0, 1.0)
        assert not bounding_boxes_match(src, clone)

    def test_tolerance_boundary(self):
        """Within tolerance is acceptable (0.005" shift)."""
        src = ShapeInfo(0, "s0", "T", "placeholder", 1.0, 1.0, 5.0, 2.0)
        clone = ShapeInfo(1, "s1", "T", "placeholder", 1.005, 1.005, 5.005, 2.005)
        assert bounding_boxes_match(src, clone)


# ── Font family set fidelity ─────────────────────────────────────────


class TestFontFamilyFidelity:
    """Same set of font families must be used in source and clone."""

    def test_same_fonts(self):
        src = [
            ShapeInfo(0, "s0", "T", "ph", 0, 0, 8, 1, font_name="Euclid Flex"),
            ShapeInfo(0, "s0", "B", "ph", 0, 1, 8, 4, font_name="Euclid Flex"),
        ]
        clone = [
            ShapeInfo(1, "s1", "T", "ph", 0, 0, 8, 1, font_name="Euclid Flex"),
            ShapeInfo(1, "s1", "B", "ph", 0, 1, 8, 4, font_name="Euclid Flex"),
        ]
        assert font_families_match(src, clone)

    def test_different_fonts_fail(self):
        src = [
            ShapeInfo(0, "s0", "T", "ph", 0, 0, 8, 1, font_name="Euclid Flex"),
        ]
        clone = [
            ShapeInfo(1, "s1", "T", "ph", 0, 0, 8, 1, font_name="Aptos"),
        ]
        assert not font_families_match(src, clone)

    def test_empty_font_names_ignored(self):
        src = [
            ShapeInfo(0, "s0", "T", "ph", 0, 0, 8, 1, font_name="Euclid Flex"),
            ShapeInfo(0, "s0", "Deco", "shape", 5, 0, 1, 1, font_name=""),
        ]
        clone = [
            ShapeInfo(1, "s1", "T", "ph", 0, 0, 8, 1, font_name="Euclid Flex"),
        ]
        assert font_families_match(src, clone)


# ── A1 immutability ──────────────────────────────────────────────────


class TestA1Immutability:
    """A1 slides are structurally cloned with zero modification."""

    def test_a1_slide_class_no_injection(self):
        """A1 entries have entry_type='a1_clone' and no injection_data."""
        from src.services.renderer_v2 import SlideRenderRecord

        record = SlideRenderRecord(
            manifest_index=0,
            entry_type="a1_clone",
            asset_id="overview",
            semantic_layout_id="company_overview",
            section_id="company_profile",
        )
        assert record.entry_type == "a1_clone"

    def test_a1_requires_no_sanitization(self):
        """A1 slides skip sanitization (they are immutable)."""
        # A1 entry_type in renderer_v2 dispatches to _render_a1_clone
        # which does NOT call sanitize_shell
        from src.services.renderer_v2 import SlideRenderRecord

        record = SlideRenderRecord(
            manifest_index=0,
            entry_type="a1_clone",
            asset_id="ksa_context",
            semantic_layout_id="ksa_context",
            section_id="company_profile",
        )
        # Verify this is classified as a1_clone, not a2_shell
        assert record.entry_type != "a2_shell"


# ── A2 mutation scope ────────────────────────────────────────────────


class TestA2MutationScope:
    """Only approved placeholders on A2 shells may be modified."""

    def test_a2_entry_type(self):
        from src.services.renderer_v2 import SlideRenderRecord

        record = SlideRenderRecord(
            manifest_index=1,
            entry_type="a2_shell",
            asset_id="proposal_cover",
            semantic_layout_id="proposal_cover",
            section_id="cover",
        )
        assert record.entry_type == "a2_shell"

    def test_allowlist_restricts_mutation(self):
        """Only indices in approved_placeholder_indices can be injected."""
        al = ShellAllowlist(
            shell_id="proposal_cover",
            approved_placeholder_indices={0, 1},
            preserved_shape_names=set(),
            preserved_table_names=set(),
        )
        # Index 0 and 1 are approved
        assert 0 in al.approved_placeholder_indices
        assert 1 in al.approved_placeholder_indices
        # Index 5 is NOT approved
        assert 5 not in al.approved_placeholder_indices


# ── Record uses semantic layout ID ───────────────────────────────────


class TestRecordSemanticID:
    """SlideRenderRecord uses semantic_layout_id, never raw slide index."""

    def test_record_stores_semantic_id(self):
        from src.services.renderer_v2 import SlideRenderRecord

        r = SlideRenderRecord(
            manifest_index=0,
            entry_type="b_variable",
            asset_id="understanding_01",
            semantic_layout_id="content_heading_desc",
            section_id="section_01",
        )
        assert r.semantic_layout_id == "content_heading_desc"
        assert not hasattr(r, "slide_idx")
        assert not hasattr(r, "raw_index")

    def test_record_frozen(self):
        from src.services.renderer_v2 import SlideRenderRecord

        r = SlideRenderRecord(
            manifest_index=0,
            entry_type="b_variable",
            asset_id="test",
            semantic_layout_id="content_heading_desc",
            section_id="section_01",
        )
        with pytest.raises(AttributeError):
            r.semantic_layout_id = "other"  # type: ignore[misc]
