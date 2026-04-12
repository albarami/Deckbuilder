"""Regression test: Arabic presentation-form normalization.

The Etimad platform produces HTML-to-PDF renders that use Unicode Arabic
Presentation Forms (FB50-FDFF, FE70-FEFF) instead of standard Arabic (0600-06FF).
Without NFKC normalization, the context agent fails to extract:
- evaluation model (misclassifies as weighted instead of pass/fail)
- contract duration (returns None instead of 12 months)
- phase structure (returns None instead of 5 named phases)
- deliverables (returns empty instead of 17 items)

This test uses raw text fixtures from the NCNP RFP to prove that normalization
recovers all critical procurement facts.
"""

import json
from pathlib import Path

import pytest

from src.utils.extractors import _normalize_arabic_text

FIXTURES_PATH = Path(__file__).parent.parent / "fixtures" / "ncnp_arabic_raw_lines.json"


@pytest.fixture
def raw_lines():
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_award_clause_recovers_lowest_price(raw_lines):
    """The award clause must contain 'الأقل' and 'الترسية' after normalization."""
    normalized = _normalize_arabic_text(raw_lines["award_clause_raw"])
    assert "الأقل" in normalized, f"'الأقل' (lowest) not found in: {normalized[:200]}"
    assert "الترسية" in normalized, f"'الترسية' (award) not found in: {normalized[:200]}"
    # Must NOT contain weighted-scoring keywords
    assert "70%" not in normalized
    assert "30%" not in normalized


def test_duration_recovers_12_months(raw_lines):
    """The duration line must contain '12' and 'شهر' after normalization."""
    normalized = _normalize_arabic_text(raw_lines["duration_raw"])
    assert "12" in normalized, f"'12' not found in: {normalized[:200]}"
    assert "شهر" in normalized, f"'شهر' (month) not found in: {normalized[:200]}"
    assert "العقد" in normalized, f"'العقد' (contract) not found in: {normalized[:200]}"


def test_phases_recover_all_five(raw_lines):
    """All 5 phase lines must contain 'مرحلة' (phase) after normalization."""
    for key in ["phase1_raw", "phase2_raw", "phase3_raw", "phase4_raw", "phase5_raw"]:
        normalized = _normalize_arabic_text(raw_lines[key])
        assert "مرحلة" in normalized, f"'مرحلة' (phase) not found in {key}: {normalized[:200]}"


def test_phase_ordinals_present(raw_lines):
    """Phase ordinals (أولًا through خامسًا) must survive normalization."""
    ordinals = {
        "phase1_raw": "أول",
        "phase2_raw": "ثاني",
        "phase3_raw": "ثالث",
        "phase4_raw": "رابع",
        "phase5_raw": "خامس",
    }
    for key, ordinal_root in ordinals.items():
        normalized = _normalize_arabic_text(raw_lines[key])
        assert ordinal_root in normalized, (
            f"Ordinal root '{ordinal_root}' not found in {key}: {normalized[:200]}"
        )


def test_deliverable_header_recovers(raw_lines):
    """The deliverable header must contain 'المخرجات' after normalization."""
    normalized = _normalize_arabic_text(raw_lines["deliverable_header_raw"])
    assert "المخرجات" in normalized, f"'المخرجات' (outputs) not found in: {normalized[:200]}"


def test_presentation_forms_removed(raw_lines):
    """After normalization, no Arabic presentation form characters should remain."""
    for key, raw_text in raw_lines.items():
        if key == "total_raw_length":
            continue
        normalized = _normalize_arabic_text(raw_text)
        for char in normalized:
            code = ord(char)
            assert not (0xFB50 <= code <= 0xFDFF), (
                f"Presentation Form-A char U+{code:04X} in {key}"
            )
            assert not (0xFE70 <= code <= 0xFEFF), (
                f"Presentation Form-B char U+{code:04X} in {key}"
            )


def test_double_spaces_collapsed(raw_lines):
    """Double spaces from Etimad formatting must be collapsed to single."""
    for key, raw_text in raw_lines.items():
        if key == "total_raw_length":
            continue
        normalized = _normalize_arabic_text(raw_text)
        assert "  " not in normalized, f"Double space found in {key}: {normalized[:200]}"


def test_normalize_empty_and_none():
    """Normalization must handle empty string and None-ish input."""
    assert _normalize_arabic_text("") == ""
    assert _normalize_arabic_text("   ") == ""
