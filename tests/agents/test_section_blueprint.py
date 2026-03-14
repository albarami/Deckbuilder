"""Tests for Phase 3a — section_blueprint.py.

Tests section blueprint construction, mandatory ordering, divider mapping,
and semantic layout ID usage (never raw display names).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.section_blueprint import (
    MANDATORY_SECTION_ORDER,
    SectionBlueprint,
    build_section_blueprints,
    get_section_for_divider,
    validate_section_order,
)

GRAMMAR_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "data" / "template_grammar"


# ── Mandatory section order ──────────────────────────────────────────────


class TestMandatorySectionOrder:
    def test_order_starts_with_cover(self):
        assert MANDATORY_SECTION_ORDER[0] == "cover"

    def test_order_ends_with_closing(self):
        assert MANDATORY_SECTION_ORDER[-1] == "closing"

    def test_sections_01_through_06_present(self):
        for i in range(1, 7):
            assert f"section_{i:02d}" in MANDATORY_SECTION_ORDER

    def test_company_profile_after_section_06(self):
        idx_06 = MANDATORY_SECTION_ORDER.index("section_06")
        idx_cp = MANDATORY_SECTION_ORDER.index("company_profile")
        assert idx_cp > idx_06

    def test_order_has_9_sections(self):
        assert len(MANDATORY_SECTION_ORDER) == 9


# ── Blueprint construction ───────────────────────────────────────────────


class TestBuildSectionBlueprints:
    def test_returns_all_sections(self):
        blueprints = build_section_blueprints()
        assert set(blueprints.keys()) == set(MANDATORY_SECTION_ORDER)

    def test_all_blueprints_are_frozen(self):
        blueprints = build_section_blueprints()
        for bp in blueprints.values():
            assert isinstance(bp, SectionBlueprint)
            with pytest.raises(AttributeError):
                bp.section_id = "hacked"  # type: ignore[misc]

    def test_section_numbers_match_dividers(self):
        blueprints = build_section_blueprints()
        for i in range(1, 7):
            sid = f"section_{i:02d}"
            assert blueprints[sid].section_number == i

    def test_non_divider_sections_have_number_zero(self):
        blueprints = build_section_blueprints()
        for sid in ("cover", "company_profile", "closing"):
            assert blueprints[sid].section_number == 0

    def test_section_03_expects_methodology(self):
        blueprints = build_section_blueprints()
        assert blueprints["section_03"].expects_methodology is True
        assert blueprints["section_01"].expects_methodology is False

    def test_section_05_expects_team(self):
        blueprints = build_section_blueprints()
        assert blueprints["section_05"].expects_team is True

    def test_section_06_expects_governance(self):
        blueprints = build_section_blueprints()
        assert blueprints["section_06"].expects_governance is True

    def test_section_02_expects_case_studies(self):
        blueprints = build_section_blueprints()
        assert blueprints["section_02"].expects_case_studies is True

    def test_section_04_expects_timeline(self):
        blueprints = build_section_blueprints()
        assert blueprints["section_04"].expects_timeline is True

    def test_section_01_expects_proof(self):
        blueprints = build_section_blueprints()
        assert blueprints["section_01"].expects_proof is True


# ── Recommended layouts use semantic IDs ──────────────────────────────────


class TestRecommendedLayouts:
    def test_methodology_layouts_are_semantic_ids(self):
        blueprints = build_section_blueprints()
        for layout_id in blueprints["section_03"].recommended_layouts:
            assert layout_id.startswith("methodology_")

    def test_team_section_uses_semantic_layout(self):
        blueprints = build_section_blueprints()
        assert "team_two_members" in blueprints["section_05"].recommended_layouts

    def test_case_study_section_uses_semantic_layout(self):
        blueprints = build_section_blueprints()
        layouts = blueprints["section_02"].recommended_layouts
        assert "case_study_cases" in layouts or "case_study_detailed" in layouts

    def test_a1_sections_have_no_recommended_layouts(self):
        """A1 clone sections don't need layout routing."""
        blueprints = build_section_blueprints()
        assert blueprints["company_profile"].recommended_layouts == []
        assert blueprints["closing"].recommended_layouts == []

    def test_no_raw_display_names_in_layouts(self):
        """Recommended layouts must never contain raw display names."""
        raw_display_names = {
            "Methodology -4- Overview of Phases",
            "Methdology -4- Focused Phase",
            "two team members",
            "Services - Cases",
            "ToC / Agenda",
        }
        blueprints = build_section_blueprints()
        for bp in blueprints.values():
            for layout_id in bp.recommended_layouts:
                assert layout_id not in raw_display_names, (
                    f"Raw display name '{layout_id}' found in "
                    f"{bp.section_id}.recommended_layouts"
                )


# ── Grammar enrichment ───────────────────────────────────────────────────


class TestGrammarEnrichment:
    @pytest.mark.skipif(
        not GRAMMAR_DIR.exists(),
        reason="Template grammar directory not available",
    )
    def test_framing_language_loaded_from_grammar(self):
        blueprints = build_section_blueprints(grammar_dir=GRAMMAR_DIR)
        # Section 01 should have framing from section_naming_grammar
        bp = blueprints["section_01"]
        assert len(bp.template_framing_language) > 0

    def test_no_grammar_dir_yields_empty_framing(self):
        blueprints = build_section_blueprints(grammar_dir=None)
        for bp in blueprints.values():
            assert bp.template_framing_language == []

    def test_nonexistent_grammar_dir_yields_empty_framing(self, tmp_path):
        blueprints = build_section_blueprints(
            grammar_dir=tmp_path / "nonexistent",
        )
        for bp in blueprints.values():
            assert bp.template_framing_language == []


# ── Divider mapping ──────────────────────────────────────────────────────


class TestDividerMapping:
    @pytest.mark.parametrize("num,expected", [
        (1, "section_01"),
        (2, "section_02"),
        (3, "section_03"),
        (4, "section_04"),
        (5, "section_05"),
        (6, "section_06"),
    ])
    def test_valid_divider_numbers(self, num, expected):
        assert get_section_for_divider(num) == expected

    def test_divider_0_raises(self):
        with pytest.raises(ValueError, match="1-6"):
            get_section_for_divider(0)

    def test_divider_7_raises(self):
        with pytest.raises(ValueError, match="1-6"):
            get_section_for_divider(7)


# ── Order validation ─────────────────────────────────────────────────────


class TestValidateSectionOrder:
    def test_correct_order_no_errors(self):
        errors = validate_section_order(list(MANDATORY_SECTION_ORDER))
        assert errors == []

    def test_subset_in_correct_order(self):
        errors = validate_section_order([
            "cover", "section_01", "section_03", "closing",
        ])
        assert errors == []

    def test_reversed_order_has_errors(self):
        errors = validate_section_order([
            "closing", "section_06", "section_01", "cover",
        ])
        assert len(errors) > 0

    def test_unknown_section_id_flagged(self):
        errors = validate_section_order(["cover", "phantom_section"])
        assert any("Unknown" in e for e in errors)

    def test_duplicate_section_flagged(self):
        errors = validate_section_order([
            "cover", "section_01", "cover",
        ])
        assert len(errors) > 0
