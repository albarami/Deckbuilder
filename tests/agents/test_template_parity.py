"""Tests for Phase 2 — template_parity.py.

Tests catalog-lock-level EN/AR parity checks: semantic ID sets,
placeholder indices, pool structures, allowlist shapes.
Fail-closed enforcement verified via ParityError on critical mismatch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.template_parity import (
    ParityCheck,
    ParityError,
    ParityReport,
    run_parity_check,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "data"
CATALOG_LOCK_EN = DATA_DIR / "catalog_lock_en.json"
CATALOG_LOCK_AR = DATA_DIR / "catalog_lock_ar.json"

# Skip all tests if catalog lock files are not available
pytestmark = pytest.mark.skipif(
    not CATALOG_LOCK_EN.exists() or not CATALOG_LOCK_AR.exists(),
    reason="Catalog lock files not available",
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _make_lock_pair(tmp_path, *, en_mods=None, ar_mods=None):
    """Create modified EN/AR lock pair in tmp_path."""
    en = _load(CATALOG_LOCK_EN)
    ar = _load(CATALOG_LOCK_AR)
    if en_mods:
        en_mods(en)
    if ar_mods:
        ar_mods(ar)
    en_path = tmp_path / "lock_en.json"
    ar_path = tmp_path / "lock_ar.json"
    _write(en_path, en)
    _write(ar_path, ar)
    return en_path, ar_path


# ── ParityCheck / ParityReport unit tests ─────────────────────────────────


class TestParityReport:
    def test_passing_check(self):
        report = ParityReport()
        report.add(ParityCheck("test", "critical", True, "a", "a"))
        assert report.overall_pass is True
        assert report.critical_failures == 0

    def test_critical_failure(self):
        report = ParityReport()
        report.add(ParityCheck("test", "critical", False, "a", "b"))
        assert report.overall_pass is False
        assert report.critical_failures == 1

    def test_warning_does_not_block(self):
        report = ParityReport()
        report.add(ParityCheck("test", "warning", False, 5, 6))
        assert report.overall_pass is True
        assert report.warnings == 1

    def test_to_dict(self):
        report = ParityReport()
        report.add(ParityCheck("x", "critical", True, 1, 1, "ok"))
        d = report.to_dict()
        assert d["overall_pass"] is True
        assert len(d["checks"]) == 1
        assert d["checks"][0]["detail"] == "ok"

    def test_to_dict_no_detail(self):
        report = ParityReport()
        report.add(ParityCheck("x", "critical", True, 1, 1))
        d = report.to_dict()
        assert "detail" not in d["checks"][0]


# ── Production catalog lock parity (happy path) ──────────────────────────


class TestProductionParity:
    def test_production_locks_pass(self):
        """EN and AR production catalog locks must be in full parity."""
        report = run_parity_check(CATALOG_LOCK_EN, CATALOG_LOCK_AR)
        assert report.overall_pass is True
        assert report.critical_failures == 0

    def test_all_checks_present(self):
        """Report should contain all expected check categories."""
        report = run_parity_check(CATALOG_LOCK_EN, CATALOG_LOCK_AR)
        names = {c.name for c in report.checks}
        assert "language_labels" in names
        assert "a1_immutable_ids" in names
        assert "a2_shell_ids" in names
        assert "section_divider_numbers" in names
        assert "layout_semantic_ids" in names
        assert "case_study_categories" in names
        assert "team_bio_pool_count" in names
        assert "service_divider_ids" in names

    def test_a2_placeholder_checks_present(self):
        """Each A2 shell should get a placeholder parity check."""
        report = run_parity_check(CATALOG_LOCK_EN, CATALOG_LOCK_AR)
        en = _load(CATALOG_LOCK_EN)
        a2_names = {
            f"a2_placeholder_parity:{sid}" for sid in en["a2_shells"]
        }
        check_names = {c.name for c in report.checks}
        assert a2_names.issubset(check_names)

    def test_report_serializable(self):
        """Report.to_dict() must produce valid JSON."""
        report = run_parity_check(CATALOG_LOCK_EN, CATALOG_LOCK_AR)
        d = report.to_dict()
        roundtrip = json.loads(json.dumps(d))
        assert roundtrip["overall_pass"] is True


# ── Fail-closed: critical mismatches raise ParityError ────────────────────


class TestFailClosed:
    def test_missing_lock_file(self, tmp_path):
        with pytest.raises(ParityError, match="not found"):
            run_parity_check(
                tmp_path / "nonexistent.json",
                CATALOG_LOCK_AR,
            )

    def test_incomplete_lock(self, tmp_path):
        bad = tmp_path / "bad.json"
        _write(bad, {"template_hash": "x", "language": "en"})
        with pytest.raises(ParityError, match="missing fields"):
            run_parity_check(bad, CATALOG_LOCK_AR)

    def test_a1_id_mismatch_raises(self, tmp_path):
        """Extra A1 slide in EN raises ParityError."""
        def add_fake_a1(en):
            en["a1_immutable"]["fake_slide_xyz"] = {
                "slide_idx": 999,
                "semantic_layout_id": "fake_slide_xyz",
                "display_name": "Fake",
                "shape_count": 0,
                "media_count": 0,
            }
        en_path, ar_path = _make_lock_pair(tmp_path, en_mods=add_fake_a1)
        with pytest.raises(ParityError, match="a1_immutable_ids"):
            run_parity_check(en_path, ar_path)

    def test_a2_id_mismatch_raises(self, tmp_path):
        """Missing A2 shell in AR raises ParityError."""
        def remove_a2(ar):
            first_key = next(iter(ar["a2_shells"]))
            del ar["a2_shells"][first_key]
        en_path, ar_path = _make_lock_pair(tmp_path, ar_mods=remove_a2)
        with pytest.raises(ParityError, match="a2_shell_ids"):
            run_parity_check(en_path, ar_path)

    def test_section_divider_mismatch_raises(self, tmp_path):
        """Extra divider in EN raises ParityError."""
        def add_divider(en):
            en["section_dividers"]["99"] = {
                "slide_idx": 999,
                "semantic_layout_id": "section_99",
                "display_name": "Section 99",
            }
        en_path, ar_path = _make_lock_pair(tmp_path, en_mods=add_divider)
        with pytest.raises(ParityError, match="section_divider_numbers"):
            run_parity_check(en_path, ar_path)

    def test_layout_id_mismatch_raises(self, tmp_path):
        """Extra layout in EN raises ParityError."""
        def add_layout(en):
            en["layouts"]["phantom_layout_xyz"] = {
                "display_name": "Phantom",
                "master_idx": 0,
                "placeholder_count": 0,
                "placeholders": {},
            }
        en_path, ar_path = _make_lock_pair(tmp_path, en_mods=add_layout)
        with pytest.raises(ParityError, match="layout_semantic_ids"):
            run_parity_check(en_path, ar_path)

    def test_a2_placeholder_mismatch_raises(self, tmp_path):
        """Divergent A2 allowlist placeholder indices raise ParityError."""
        def break_allowlist(en):
            first_key = next(iter(en["a2_shells"]))
            al = en["a2_shells"][first_key].setdefault("allowlist", {})
            phs = al.setdefault("approved_injection_placeholders", {})
            phs["999"] = "ph_999"
        en_path, ar_path = _make_lock_pair(tmp_path, en_mods=break_allowlist)
        with pytest.raises(ParityError, match="a2_placeholder_parity"):
            run_parity_check(en_path, ar_path)

    def test_service_divider_id_mismatch_raises(self, tmp_path):
        """Divergent service divider semantic IDs raise ParityError."""
        def add_svc_div(en):
            en["service_divider_pool"].append({
                "slide_idx": 999,
                "semantic_id": "svc_divider_phantom",
                "service_category": "phantom",
            })
        en_path, ar_path = _make_lock_pair(tmp_path, en_mods=add_svc_div)
        with pytest.raises(ParityError, match="service_divider_ids"):
            run_parity_check(en_path, ar_path)

    def test_case_study_category_mismatch_raises(self, tmp_path):
        """Divergent case study categories raise ParityError."""
        def add_cat(en):
            en["case_study_pool"]["phantom_category"] = []
        en_path, ar_path = _make_lock_pair(tmp_path, en_mods=add_cat)
        with pytest.raises(ParityError, match="case_study_categories"):
            run_parity_check(en_path, ar_path)

    def test_language_label_mismatch_raises(self, tmp_path):
        """Swapped language labels raise ParityError."""
        def swap_lang(en):
            en["language"] = "ar"
        en_path, ar_path = _make_lock_pair(tmp_path, en_mods=swap_lang)
        with pytest.raises(ParityError, match="language_labels"):
            run_parity_check(en_path, ar_path)


# ── Suppressed fail-closed mode ──────────────────────────────────────────


class TestSuppressedFailClosed:
    def test_fail_on_critical_false_returns_report(self, tmp_path):
        """With fail_on_critical=False, report is returned even on failure."""
        def add_fake_a1(en):
            en["a1_immutable"]["fake_slide_xyz"] = {
                "slide_idx": 999,
                "semantic_layout_id": "fake_slide_xyz",
                "display_name": "Fake",
                "shape_count": 0,
                "media_count": 0,
            }
        en_path, ar_path = _make_lock_pair(tmp_path, en_mods=add_fake_a1)
        report = run_parity_check(en_path, ar_path, fail_on_critical=False)
        assert report.overall_pass is False
        assert report.critical_failures >= 1


# ── Warning-only checks ──────────────────────────────────────────────────


class TestWarnings:
    def test_team_count_mismatch_is_warning(self, tmp_path):
        """Team bio pool count mismatch is a warning, not critical."""
        def add_team(en):
            en["team_bio_pool"].append({
                "slide_idx": 999,
                "semantic_layout_id": "team_extra",
                "display_name": "Extra",
                "team_family": "team_variant",
            })
        en_path, ar_path = _make_lock_pair(tmp_path, en_mods=add_team)
        report = run_parity_check(en_path, ar_path, fail_on_critical=False)
        team_check = next(
            c for c in report.checks if c.name == "team_bio_pool_count"
        )
        assert team_check.match is False
        assert team_check.severity == "warning"

    def test_service_divider_count_mismatch_is_warning(self, tmp_path):
        """Service divider pool count mismatch is warning (IDs are critical)."""
        # Add to both EN and AR so IDs still match, but count differs
        def add_both_svc(en):
            en["service_divider_pool"].append({
                "slide_idx": 999,
                "semantic_id": "svc_divider_extra",
                "service_category": "extra",
            })
        def add_both_svc_ar(ar):
            ar["service_divider_pool"].append({
                "slide_idx": 999,
                "semantic_id": "svc_divider_extra",
                "service_category": "extra",
            })
            ar["service_divider_pool"].append({
                "slide_idx": 998,
                "semantic_id": "svc_divider_extra2",
                "service_category": "extra2",
            })
        en_path, ar_path = _make_lock_pair(
            tmp_path, en_mods=add_both_svc, ar_mods=add_both_svc_ar,
        )
        # IDs diverge so this will hit critical on service_divider_ids
        report = run_parity_check(en_path, ar_path, fail_on_critical=False)
        count_check = next(
            c for c in report.checks if c.name == "service_divider_pool_count"
        )
        assert count_check.severity == "warning"
