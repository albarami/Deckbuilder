"""Tests for Phase 9 — placeholder_contracts.py.

Tests PlaceholderContract construction from catalog lock, fail-closed
validation, missing/wrong-type placeholder detection, unknown layout
handling, and semantic-ID-only resolution.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.placeholder_contracts import (
    ContractValidationResult,
    ContractViolationError,
    PlaceholderContract,
    PlaceholderContractViolation,
    build_contracts_from_catalog_lock,
    get_contract,
    validate_placeholders,
    validate_slide_against_catalog,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "data"
CATALOG_LOCK_EN = DATA_DIR / "catalog_lock_en.json"

pytestmark = pytest.mark.skipif(
    not CATALOG_LOCK_EN.exists(),
    reason="Catalog lock not available",
)


# ── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def contracts() -> dict[str, PlaceholderContract]:
    return build_contracts_from_catalog_lock(CATALOG_LOCK_EN)


def _write_lock(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── PlaceholderContract ─────────────────────────────────────────────────


class TestPlaceholderContract:
    def test_frozen(self):
        c = PlaceholderContract(
            semantic_layout_id="test",
            required_placeholders={0: "TITLE"},
        )
        with pytest.raises(AttributeError):
            c.semantic_layout_id = "hacked"  # type: ignore[misc]

    def test_default_optional_empty(self):
        c = PlaceholderContract(
            semantic_layout_id="test",
            required_placeholders={0: "TITLE"},
        )
        assert c.optional_placeholders == {}
        assert c.table_requirements is None

    def test_table_requirements(self):
        c = PlaceholderContract(
            semantic_layout_id="toc_table",
            required_placeholders={0: "TITLE", 10: "TABLE"},
            table_requirements={10: (5, 3)},
        )
        assert c.table_requirements[10] == (5, 3)


# ── PlaceholderContractViolation ────────────────────────────────────────


class TestViolation:
    def test_frozen(self):
        v = PlaceholderContractViolation(
            semantic_layout_id="test",
            violation_type="missing_required",
            detail="test detail",
        )
        with pytest.raises(AttributeError):
            v.detail = "hacked"  # type: ignore[misc]

    def test_fields(self):
        v = PlaceholderContractViolation(
            semantic_layout_id="content_heading_desc",
            violation_type="missing_required",
            detail="Required placeholder idx=0 (TITLE) missing",
            placeholder_idx=0,
        )
        assert v.semantic_layout_id == "content_heading_desc"
        assert v.violation_type == "missing_required"
        assert v.placeholder_idx == 0


# ── build_contracts_from_catalog_lock ───────────────────────────────────


class TestBuildContracts:
    def test_loads_from_catalog_lock(self, contracts):
        assert len(contracts) > 0

    def test_known_layouts_present(self, contracts):
        expected = {
            "content_heading_desc", "methodology_overview_4",
            "proposal_cover", "team_two_members", "toc_table",
            "section_divider_01", "case_study_detailed",
        }
        for lid in expected:
            assert lid in contracts, f"Missing contract for '{lid}'"

    def test_content_heading_desc_contract(self, contracts):
        c = contracts["content_heading_desc"]
        assert c.semantic_layout_id == "content_heading_desc"
        assert 0 in c.required_placeholders
        assert c.required_placeholders[0] == "TITLE"
        assert 13 in c.required_placeholders
        assert c.required_placeholders[13] == "BODY"

    def test_proposal_cover_contract(self, contracts):
        c = contracts["proposal_cover"]
        assert 1 in c.required_placeholders
        assert c.required_placeholders[1] == "SUBTITLE"
        assert 12 in c.required_placeholders
        assert c.required_placeholders[12] == "PICTURE"

    def test_toc_table_has_table_placeholder(self, contracts):
        c = contracts["toc_table"]
        assert 10 in c.required_placeholders
        assert c.required_placeholders[10] == "TABLE"

    def test_methodology_overview_4_has_many_placeholders(self, contracts):
        c = contracts["methodology_overview_4"]
        assert len(c.required_placeholders) == 13

    def test_team_two_members_has_pictures(self, contracts):
        c = contracts["team_two_members"]
        picture_indices = [
            idx for idx, t in c.required_placeholders.items() if t == "PICTURE"
        ]
        assert len(picture_indices) == 2

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ContractViolationError, match="not found"):
            build_contracts_from_catalog_lock(tmp_path / "nonexistent.json")

    def test_empty_layouts_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        _write_lock(bad, {"layouts": {}})
        with pytest.raises(ContractViolationError, match="no 'layouts'"):
            build_contracts_from_catalog_lock(bad)

    def test_no_layouts_key_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        _write_lock(bad, {"template_hash": "x"})
        with pytest.raises(ContractViolationError, match="no 'layouts'"):
            build_contracts_from_catalog_lock(bad)

    def test_all_contracts_have_semantic_ids(self, contracts):
        """No contract should use a raw display name as its key."""
        raw_names = {
            "Heading and description",
            "Methodology -4- Overview of Phases",
            "Proposal Cover",
            "two team members",
        }
        for lid in contracts:
            assert lid not in raw_names
            assert lid == lid.lower() or "_" in lid


# ── get_contract ────────────────────────────────────────────────────────


class TestGetContract:
    def test_lookup_existing(self, contracts):
        c = get_contract(contracts, "content_heading_desc")
        assert c.semantic_layout_id == "content_heading_desc"

    def test_lookup_missing_raises(self, contracts):
        with pytest.raises(ContractViolationError, match="phantom"):
            get_contract(contracts, "phantom")

    def test_lookup_by_display_name_raises(self, contracts):
        """Cannot look up by raw display name."""
        with pytest.raises(ContractViolationError):
            get_contract(contracts, "Heading and description")


# ── validate_placeholders ───────────────────────────────────────────────


class TestValidatePlaceholders:
    def test_valid_slide_passes(self, contracts):
        c = contracts["content_heading_desc"]
        actual = {0: "TITLE", 13: "BODY"}
        result = validate_placeholders(c, actual)
        assert isinstance(result, ContractValidationResult)
        assert result.is_valid is True
        assert len(result.violations) == 0

    def test_missing_placeholder_flagged(self, contracts):
        c = contracts["content_heading_desc"]
        actual = {0: "TITLE"}  # missing idx 13 BODY
        result = validate_placeholders(c, actual)
        assert result.is_valid is False
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == "missing_required"
        assert result.violations[0].placeholder_idx == 13

    def test_wrong_type_flagged(self, contracts):
        c = contracts["content_heading_desc"]
        actual = {0: "TITLE", 13: "TABLE"}  # BODY expected, got TABLE
        result = validate_placeholders(c, actual)
        assert result.is_valid is False
        assert any(v.violation_type == "wrong_type" for v in result.violations)

    def test_extra_placeholders_not_flagged(self, contracts):
        """Extra placeholders beyond the contract are OK."""
        c = contracts["content_heading_desc"]
        actual = {0: "TITLE", 13: "BODY", 99: "PICTURE"}
        result = validate_placeholders(c, actual)
        assert result.is_valid is True

    def test_multiple_missing_flagged(self):
        c = PlaceholderContract(
            semantic_layout_id="test",
            required_placeholders={0: "TITLE", 1: "BODY", 2: "TABLE"},
        )
        actual = {}  # all missing
        result = validate_placeholders(c, actual)
        assert result.is_valid is False
        assert len(result.violations) == 3

    def test_violations_are_frozen_tuple(self, contracts):
        c = contracts["content_heading_desc"]
        actual = {0: "TITLE"}
        result = validate_placeholders(c, actual)
        assert isinstance(result.violations, tuple)

    def test_result_frozen(self, contracts):
        c = contracts["content_heading_desc"]
        result = validate_placeholders(c, {0: "TITLE", 13: "BODY"})
        with pytest.raises(AttributeError):
            result.is_valid = False  # type: ignore[misc]

    def test_violation_detail_has_useful_info(self, contracts):
        c = contracts["content_heading_desc"]
        actual = {0: "TITLE"}  # missing 13
        result = validate_placeholders(c, actual)
        detail = result.violations[0].detail
        assert "idx=13" in detail
        assert "BODY" in detail


# ── validate_slide_against_catalog ──────────────────────────────────────


class TestValidateSlideAgainstCatalog:
    def test_valid_slide(self, contracts):
        result = validate_slide_against_catalog(
            "content_heading_desc",
            {0: "TITLE", 13: "BODY"},
            contracts,
        )
        assert result.is_valid is True
        assert result.semantic_layout_id == "content_heading_desc"

    def test_unknown_layout(self, contracts):
        result = validate_slide_against_catalog(
            "phantom_layout",
            {0: "TITLE"},
            contracts,
        )
        assert result.is_valid is False
        assert result.violations[0].violation_type == "unknown_layout"

    def test_missing_placeholder_via_convenience(self, contracts):
        result = validate_slide_against_catalog(
            "content_heading_desc",
            {0: "TITLE"},  # missing 13
            contracts,
        )
        assert result.is_valid is False

    def test_section_divider_contract(self, contracts):
        """Section dividers have TITLE + BODY."""
        result = validate_slide_against_catalog(
            "section_divider_01",
            {0: "TITLE", 10: "BODY"},
            contracts,
        )
        assert result.is_valid is True

    def test_methodology_overview_full_match(self, contracts):
        """methodology_overview_4 has 13 placeholders — all must match."""
        c = contracts["methodology_overview_4"]
        actual = dict(c.required_placeholders)  # perfect match
        result = validate_slide_against_catalog(
            "methodology_overview_4",
            actual,
            contracts,
        )
        assert result.is_valid is True


# ── Cross-cutting: catalog lock coverage ────────────────────────────────


class TestCatalogLockCoverage:
    def test_all_layouts_have_contracts(self, contracts):
        """Every layout in the catalog lock has a contract."""
        with open(CATALOG_LOCK_EN, encoding="utf-8") as f:
            lock = json.load(f)
        for lid in lock.get("layouts", {}):
            assert lid in contracts, f"No contract for layout '{lid}'"

    def test_key_layouts_have_placeholders(self, contracts):
        """Key content layouts must have at least one placeholder.
        Many A1 house slides have zero formal placeholders (they are
        immutable visual assets), which is correct."""
        must_have = [
            "content_heading_desc", "proposal_cover", "toc_table",
            "section_divider_01", "case_study_detailed", "team_two_members",
            "methodology_overview_4", "intro_message",
        ]
        for lid in must_have:
            if lid in contracts:
                assert len(contracts[lid].required_placeholders) >= 1, (
                    f"Contract '{lid}' must have at least one placeholder"
                )

    def test_placeholder_indices_are_integers(self, contracts):
        for lid, c in contracts.items():
            for idx in c.required_placeholders:
                assert isinstance(idx, int), (
                    f"Contract '{lid}' has non-int placeholder idx: {idx}"
                )

    def test_placeholder_types_are_strings(self, contracts):
        known_types = {
            "TITLE", "SUBTITLE", "CENTER_TITLE",
            "BODY", "TABLE", "PICTURE", "OBJECT",
        }
        for lid, c in contracts.items():
            for idx, ptype in c.required_placeholders.items():
                assert ptype in known_types, (
                    f"Contract '{lid}' idx={idx} has unknown type '{ptype}'"
                )
