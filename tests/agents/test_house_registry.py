"""Tests for Phase 4 — house_registry.py.

Tests HouseAssetRegistry loading from catalog lock, semantic ID
resolution (both asset and layout), fail-closed on missing IDs,
and structural integrity of all pools.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.models.house_registry import (
    HouseAssetRegistry,
    RegistryLoadError,
    SemanticIDMissing,
    load_registry,
)
from src.services.template_manager import AssetLocation, ShellDef

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "data"
CATALOG_LOCK_EN = DATA_DIR / "catalog_lock_en.json"
CATALOG_LOCK_AR = DATA_DIR / "catalog_lock_ar.json"

pytestmark = pytest.mark.skipif(
    not CATALOG_LOCK_EN.exists(),
    reason="Catalog lock not available",
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _load_lock(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_lock(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _make_modified_lock(tmp_path, modifier):
    """Create a modified catalog lock in tmp_path."""
    lock = _load_lock(CATALOG_LOCK_EN)
    modifier(lock)
    out = tmp_path / "modified_lock.json"
    _write_lock(out, lock)
    return out


@pytest.fixture(scope="module")
def registry():
    """Shared registry loaded from EN catalog lock."""
    return load_registry(CATALOG_LOCK_EN)


# ── Loading ──────────────────────────────────────────────────────────────


class TestRegistryLoading:
    def test_load_en_succeeds(self, registry):
        assert isinstance(registry, HouseAssetRegistry)

    def test_load_ar_succeeds(self):
        if not CATALOG_LOCK_AR.exists():
            pytest.skip("AR catalog lock not available")
        reg = load_registry(CATALOG_LOCK_AR)
        assert isinstance(reg, HouseAssetRegistry)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(RegistryLoadError, match="not found"):
            load_registry(tmp_path / "nonexistent.json")

    def test_missing_keys_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        _write_lock(bad, {"template_hash": "x"})
        with pytest.raises(RegistryLoadError, match="missing required keys"):
            load_registry(bad)

    def test_registry_is_frozen(self, registry):
        with pytest.raises(AttributeError):
            registry.template_hash = "hacked"  # type: ignore[misc]


# ── A1 immutable slides ─────────────────────────────────────────────────


class TestA1Slides:
    def test_a1_count(self, registry):
        assert len(registry.house_slides_a1) == 21

    def test_a1_known_ids_present(self, registry):
        expected = {
            "ksa_context", "vision_pillars", "vision_programs_numbers",
            "vision_programs", "main_cover", "overview", "what_drives_us",
            "at_a_glance", "why_sg", "deep_experience_1", "deep_experience_2",
            "deep_experience_3", "deep_experience_4", "expertise",
            "vast_network", "purpose_1", "purpose_2", "services_overview",
            "our_leadership", "know_more", "contact",
        }
        assert set(registry.a1_ids) == expected

    def test_a1_returns_asset_location(self, registry):
        loc = registry.get_a1("overview")
        assert isinstance(loc, AssetLocation)
        assert loc.semantic_layout_id == "overview"

    def test_a1_missing_id_raises(self, registry):
        with pytest.raises(SemanticIDMissing, match="phantom"):
            registry.get_a1("phantom")


# ── A2 shells ────────────────────────────────────────────────────────────


class TestA2Shells:
    def test_a2_count(self, registry):
        assert len(registry.house_slides_a2) == 3

    def test_a2_known_ids(self, registry):
        assert set(registry.a2_ids) == {
            "proposal_cover", "intro_message", "toc_agenda",
        }

    def test_a2_returns_shell_def(self, registry):
        shell = registry.get_a2("proposal_cover")
        assert isinstance(shell, ShellDef)
        assert shell.semantic_layout_id == "proposal_cover"

    def test_a2_has_allowlist(self, registry):
        shell = registry.get_a2("proposal_cover")
        assert "approved_injection_placeholders" in shell.allowlist

    def test_a2_missing_id_raises(self, registry):
        with pytest.raises(SemanticIDMissing, match="phantom"):
            registry.get_a2("phantom")


# ── Section dividers ─────────────────────────────────────────────────────


class TestSectionDividers:
    def test_divider_count(self, registry):
        assert len(registry.section_dividers) == 6

    def test_divider_numbers(self, registry):
        assert registry.divider_numbers == [1, 2, 3, 4, 5, 6]

    def test_divider_returns_shell_def(self, registry):
        div = registry.get_divider(1)
        assert isinstance(div, ShellDef)
        assert "section_divider" in div.semantic_layout_id

    def test_divider_has_allowlist(self, registry):
        div = registry.get_divider(1)
        assert "approved_injection_placeholders" in div.allowlist

    def test_divider_missing_raises(self, registry):
        with pytest.raises(SemanticIDMissing, match="7"):
            registry.get_divider(7)


# ── Case study pool ─────────────────────────────────────────────────────


class TestCaseStudyPool:
    def test_pool_has_categories(self, registry):
        assert len(registry.case_study_pool) >= 1

    def test_general_category_present(self, registry):
        assert "general" in registry.case_study_pool

    def test_entries_are_asset_locations(self, registry):
        for entries in registry.case_study_pool.values():
            for entry in entries:
                assert isinstance(entry, AssetLocation)

    def test_case_studies_use_semantic_layout_ids(self, registry):
        for entries in registry.case_study_pool.values():
            for entry in entries:
                assert entry.semantic_layout_id in (
                    "case_study_cases", "case_study_detailed",
                )


# ── Team bio pool ────────────────────────────────────────────────────────


class TestTeamBioPool:
    def test_pool_count(self, registry):
        assert len(registry.team_bio_pool) == 9

    def test_entries_are_asset_locations(self, registry):
        for entry in registry.team_bio_pool:
            assert isinstance(entry, AssetLocation)

    def test_team_uses_semantic_layout_id(self, registry):
        for entry in registry.team_bio_pool:
            assert entry.semantic_layout_id == "team_two_members"


# ── Service dividers ─────────────────────────────────────────────────────


class TestServiceDividers:
    def test_pool_count(self, registry):
        assert len(registry.service_dividers) == 7

    def test_entries_are_asset_locations(self, registry):
        for entry in registry.service_dividers:
            assert isinstance(entry, AssetLocation)

    def test_service_dividers_use_semantic_ids(self, registry):
        for entry in registry.service_dividers:
            assert entry.semantic_layout_id.startswith("svc_")


# ── Methodology layouts ──────────────────────────────────────────────────


class TestMethodologyLayouts:
    def test_all_five_present(self, registry):
        expected = {
            "methodology_overview_4", "methodology_overview_3",
            "methodology_focused_4", "methodology_focused_3",
            "methodology_detail",
        }
        assert set(registry.methodology_layouts.keys()) == expected

    def test_lookup_returns_same_id(self, registry):
        result = registry.get_methodology_layout("methodology_overview_4")
        assert result == "methodology_overview_4"

    def test_missing_layout_raises(self, registry):
        with pytest.raises(SemanticIDMissing, match="phantom"):
            registry.get_methodology_layout("phantom")


# ── Template hash ────────────────────────────────────────────────────────


class TestTemplateHash:
    def test_hash_present(self, registry):
        assert registry.template_hash.startswith("sha256:")

    def test_hash_matches_catalog_lock(self, registry):
        lock = _load_lock(CATALOG_LOCK_EN)
        assert registry.template_hash == lock["template_hash"]


# ── Fail-closed: structural integrity ────────────────────────────────────


class TestFailClosed:
    def test_missing_methodology_layout_raises(self, tmp_path):
        """Missing methodology layout in catalog lock = RegistryLoadError."""
        def remove_meth(lock):
            del lock["layouts"]["methodology_detail"]
        path = _make_modified_lock(tmp_path, remove_meth)
        with pytest.raises(RegistryLoadError, match="methodology_detail"):
            load_registry(path)

    def test_bad_case_study_pool_type_raises(self, tmp_path):
        """case_study_pool must be a dict."""
        def break_pool(lock):
            lock["case_study_pool"] = []
        path = _make_modified_lock(tmp_path, break_pool)
        with pytest.raises(RegistryLoadError, match="case_study_pool"):
            load_registry(path)

    def test_missing_a1_section_loads_without_it(self, tmp_path):
        """Registry loads whatever A1 entries exist — missing ones
        are caught at lookup time via get_a1() fail-closed."""
        def remove_a1(lock):
            del lock["a1_immutable"]["ksa_context"]
        path = _make_modified_lock(tmp_path, remove_a1)
        reg = load_registry(path)
        assert "ksa_context" not in reg.house_slides_a1
        with pytest.raises(SemanticIDMissing):
            reg.get_a1("ksa_context")


# ── No raw display names or indices in API ───────────────────────────────


class TestNoRawValues:
    def test_a1_lookup_by_semantic_id_only(self, registry):
        """Cannot look up A1 by display name."""
        with pytest.raises(SemanticIDMissing):
            registry.get_a1("Overview")  # display name, not semantic ID

    def test_a2_lookup_by_semantic_id_only(self, registry):
        """Cannot look up A2 by display name."""
        with pytest.raises(SemanticIDMissing):
            registry.get_a2("Proposal Cover")  # display name

    def test_methodology_lookup_by_semantic_id_only(self, registry):
        """Cannot look up methodology layout by display name."""
        with pytest.raises(SemanticIDMissing):
            registry.get_methodology_layout(
                "Methodology -4- Overview of Phases"
            )
