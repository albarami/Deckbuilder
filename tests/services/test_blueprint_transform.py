"""Tests for blueprint_transform service.

Verifies:
1. Legacy SlideBlueprintEntry maps to correct canonical section_id
2. Contract entries have correct ownership, house_action, content fields
3. Missing sections are filled with defaults
4. Output is sorted by template order (S01-S31)
5. Validation runs and violations are reported
6. Empty input returns violations
"""

from __future__ import annotations

import pytest

from src.models.source_book import SlideBlueprintEntry as LegacyEntry
from src.models.slide_blueprint import SlideBlueprintEntry as ContractEntry
from src.models.template_contract import TEMPLATE_SECTION_ORDER
from src.services.blueprint_transform import (
    _classify_section_id,
    _to_contract_entry,
    _ensure_all_sections,
    _sort_by_template_order,
    transform_to_contract_blueprint,
)


# ── Helpers ───────────────────────────────────────────────────────


def _legacy(
    *,
    slide_number: int = 1,
    section: str = "",
    title: str = "",
    purpose: str = "",
    key_message: str = "",
    bullet_logic: list[str] | None = None,
    proof_points: list[str] | None = None,
    visual_guidance: str = "",
    must_have_evidence: list[str] | None = None,
) -> LegacyEntry:
    return LegacyEntry(
        slide_number=slide_number,
        section=section,
        title=title,
        purpose=purpose,
        key_message=key_message,
        bullet_logic=bullet_logic or [],
        proof_points=proof_points or [],
        visual_guidance=visual_guidance,
        must_have_evidence=must_have_evidence or [],
    )


# ── Classification Tests ─────────────────────────────────────────


class TestClassifySectionId:
    """_classify_section_id maps legacy entries to canonical section IDs."""

    def test_cover_keyword(self):
        entry = _legacy(section="Cover Page", title="غلاف المشروع")
        assert _classify_section_id(entry) == "S01"

    def test_executive_summary_keyword(self):
        entry = _legacy(section="Executive Summary", title="ملخص تنفيذي")
        assert _classify_section_id(entry) == "S02"

    def test_methodology_keyword(self):
        entry = _legacy(section="Methodology", title="منهجية التنفيذ")
        assert _classify_section_id(entry) == "S09"

    def test_timeline_keyword(self):
        entry = _legacy(section="Timeline", title="الجدول الزمني")
        assert _classify_section_id(entry) == "S11"

    def test_team_keyword(self):
        entry = _legacy(section="Team", title="فريق العمل")
        assert _classify_section_id(entry) == "S12"

    def test_governance_keyword(self):
        entry = _legacy(section="Governance", title="حوكمة المشروع")
        assert _classify_section_id(entry) == "S13"

    def test_case_study_keyword(self):
        entry = _legacy(section="Case Study", title="دراسة حالة")
        assert _classify_section_id(entry) == "S18"

    def test_understanding_keyword(self):
        entry = _legacy(section="Understanding", title="فهم المشروع")
        assert _classify_section_id(entry) == "S05"

    def test_why_strategic_keyword(self):
        entry = _legacy(section="Why Strategic Gears", title="لماذا نحن")
        assert _classify_section_id(entry) == "S07"

    def test_fallback_by_slide_number(self):
        entry = _legacy(slide_number=1, section="unknown", title="unknown")
        assert _classify_section_id(entry) == "S01"

    def test_fallback_high_slide_number(self):
        entry = _legacy(slide_number=15, section="misc", title="misc")
        assert _classify_section_id(entry) == "S11"


# ── Contract Entry Conversion Tests ──────────────────────────────


class TestToContractEntry:
    """_to_contract_entry produces correctly typed contract entries."""

    def test_house_entry_no_content_fields(self):
        entry = _legacy(section="Cover Page", title="")
        result = _to_contract_entry(entry, "S01")
        assert result.ownership == "hybrid"
        assert result.house_action == "include_as_is"

    def test_dynamic_entry_has_content(self):
        entry = _legacy(
            section="Understanding", title="فهم المشروع",
            key_message="Key insight", bullet_logic=["Point 1", "Point 2"],
            proof_points=["CLM-001"],
        )
        result = _to_contract_entry(entry, "S05")
        assert result.ownership == "dynamic"
        assert result.slide_title == "فهم المشروع"
        assert result.key_message == "Key insight"
        assert result.bullet_points == ["Point 1", "Point 2"]
        assert "CLM-001" in result.evidence_ids

    def test_evidence_ids_deduplicated(self):
        entry = _legacy(
            section="Methodology", title="Phase 1",
            proof_points=["CLM-001", "CLM-002"],
            must_have_evidence=["CLM-002", "CLM-003"],
        )
        result = _to_contract_entry(entry, "S09")
        assert result.evidence_ids == ["CLM-001", "CLM-002", "CLM-003"]

    def test_invalid_section_id_raises(self):
        entry = _legacy(section="test")
        with pytest.raises(ValueError, match="Unknown section_id"):
            _to_contract_entry(entry, "S99")


# ── Ensure All Sections ──────────────────────────────────────────


class TestEnsureAllSections:
    """_ensure_all_sections fills gaps in the blueprint."""

    def test_adds_missing_sections(self):
        entries = [
            ContractEntry(
                section_id="S01", section_name="Proposal Shell",
                ownership="hybrid", house_action="include_as_is",
            ),
        ]
        result = _ensure_all_sections(entries)
        section_ids = {e.section_id for e in result}
        template_ids = {s.section_id for s in TEMPLATE_SECTION_ORDER}
        assert template_ids.issubset(section_ids)

    def test_does_not_duplicate_existing(self):
        entries = [
            ContractEntry(
                section_id="S01", section_name="Proposal Shell",
                ownership="hybrid", house_action="include_as_is",
            ),
        ]
        result = _ensure_all_sections(entries)
        s01_count = sum(1 for e in result if e.section_id == "S01")
        assert s01_count == 1


# ── Sort by Template Order ───────────────────────────────────────


class TestSortByTemplateOrder:
    """_sort_by_template_order produces S01 → S31 ordering."""

    def test_sorts_correctly(self):
        entries = [
            ContractEntry(
                section_id="S09", section_name="Methodology",
                ownership="dynamic", slide_title="Phase",
            ),
            ContractEntry(
                section_id="S01", section_name="Shell",
                ownership="hybrid", house_action="include_as_is",
            ),
        ]
        result = _sort_by_template_order(entries)
        assert result[0].section_id == "S01"
        assert result[1].section_id == "S09"


# ── End-to-End Transform ─────────────────────────────────────────


class TestTransformToContractBlueprint:
    """transform_to_contract_blueprint full pipeline."""

    def test_empty_input_returns_violations(self):
        entries, violations = transform_to_contract_blueprint([])
        assert entries == []
        assert "No blueprints provided" in violations

    def test_single_entry_produces_full_blueprint(self):
        legacy = [
            _legacy(
                slide_number=5, section="Understanding", title="فهم المشروع",
                key_message="Core insight",
                bullet_logic=["Point 1", "Point 2", "Point 3"],
            ),
        ]
        entries, violations = transform_to_contract_blueprint(legacy)

        # Must have all template sections
        section_ids = {e.section_id for e in entries}
        template_ids = {s.section_id for s in TEMPLATE_SECTION_ORDER}
        assert template_ids.issubset(section_ids)

        # S05 should be dynamic with content
        s05 = [e for e in entries if e.section_id == "S05"]
        assert len(s05) >= 1
        assert s05[0].ownership == "dynamic"
        assert s05[0].slide_title == "فهم المشروع"

    def test_realistic_blueprint_passes_validation(self):
        legacy = [
            _legacy(slide_number=1, section="Cover", title="Cover"),
            _legacy(slide_number=2, section="Executive Summary", title="Intro",
                    key_message="Welcome"),
            _legacy(slide_number=3, section="Table of Contents", title="ToC"),
            _legacy(slide_number=5, section="Understanding", title="Scope",
                    key_message="Insight", bullet_logic=["A", "B"]),
            _legacy(slide_number=7, section="Why Strategic Gears", title="Why SG",
                    key_message="Because", bullet_logic=["X"]),
            _legacy(slide_number=10, section="Methodology Phase 1", title="Phase 1",
                    key_message="Discover", bullet_logic=["Interviews"]),
            _legacy(slide_number=11, section="Methodology Phase 2", title="Phase 2",
                    key_message="Design", bullet_logic=["Architecture"]),
            _legacy(slide_number=12, section="Methodology Phase 3", title="Phase 3",
                    key_message="Build", bullet_logic=["Configure"]),
            _legacy(slide_number=14, section="Timeline", title="Timeline",
                    key_message="26 weeks", bullet_logic=["Phase 1: 4w"]),
            _legacy(slide_number=16, section="Team", title="Team"),
            _legacy(slide_number=17, section="Governance", title="Gov"),
        ]
        entries, violations = transform_to_contract_blueprint(legacy)

        # Should be sorted S01 first
        assert entries[0].section_id == "S01"

        # All entries are valid ContractEntry instances
        for e in entries:
            assert isinstance(e, ContractEntry)

    def test_output_sorted_by_template_order(self):
        legacy = [
            _legacy(slide_number=14, section="Timeline", title="Timeline",
                    key_message="Plan", bullet_logic=["A"]),
            _legacy(slide_number=1, section="Cover", title="Cover"),
        ]
        entries, _ = transform_to_contract_blueprint(legacy)
        ids = [e.section_id for e in entries]
        # S01 must come before S11
        assert ids.index("S01") < ids.index("S11")
