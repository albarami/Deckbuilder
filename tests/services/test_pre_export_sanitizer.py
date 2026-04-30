"""Tests for pre-export forbidden leakage sanitizer.

The sanitizer removes forbidden content from client-facing SourceBook
sections BEFORE DOCX export. Each removal is reported as a gate finding
so the conformance validator can enforce fail-closed behavior.
"""

from __future__ import annotations

import pytest

from src.services.pre_export_sanitizer import (
    SanitizationResult,
    sanitize_source_book_sections,
)


def test_engine2_removed_from_certifications():
    """ENGINE 2 REQUIRED must be removed from certifications list."""
    sections = {
        "why_strategic_gears": {
            "certifications_and_compliance": [
                "ISO 27001 — certified",
                "ISMS audit — ENGINE 2 REQUIRED",
                "PMP certification — valid",
            ],
        },
    }
    result = sanitize_source_book_sections(sections)
    certs = result.sanitized["why_strategic_gears"]["certifications_and_compliance"]
    assert not any("ENGINE 2" in c for c in certs)
    assert len(result.removals) >= 1
    assert any("ENGINE 2 REQUIRED" in r.matched_text for r in result.removals)


def test_prj_id_removed_from_client_body():
    """PRJ-001 must be removed from client-facing body text."""
    sections = {
        "why_strategic_gears": {
            "capability_mapping_text": "خبرة سابقة [PRJ-001] في مشاريع مماثلة",
        },
    }
    result = sanitize_source_book_sections(sections)
    text = result.sanitized["why_strategic_gears"]["capability_mapping_text"]
    assert "PRJ-001" not in text
    assert len(result.removals) >= 1


def test_internal_placeholder_removed():
    """INTERNAL_PROOF_PLACEHOLDER must be removed."""
    sections = {
        "rfp_interpretation": {
            "key_compliance": ["requirement 1", "INTERNAL_PROOF_PLACEHOLDER item"],
        },
    }
    result = sanitize_source_book_sections(sections)
    items = result.sanitized["rfp_interpretation"]["key_compliance"]
    assert not any("INTERNAL_PROOF_PLACEHOLDER" in i for i in items)


def test_clean_content_unchanged():
    """Content without forbidden patterns passes through unchanged."""
    sections = {
        "rfp_interpretation": {
            "objective_and_scope": "تقييم الوضع الراهن لأخلاقيات الذكاء الاصطناعي",
        },
    }
    result = sanitize_source_book_sections(sections)
    assert result.sanitized == sections
    assert result.removals == []


def test_removals_reported_with_location():
    """Each removal must include the section path and matched text."""
    sections = {
        "proposed_solution": {
            "methodology_overview": "نطبق منهجية ENGINE 2 REQUIRED للتحقق",
        },
    }
    result = sanitize_source_book_sections(sections)
    assert len(result.removals) >= 1
    r = result.removals[0]
    assert r.section_path == "proposed_solution/methodology_overview"
    assert "ENGINE 2 REQUIRED" in r.matched_text


def test_removal_leaves_conformance_finding():
    """Removals must be flagged as conformance findings for fail-closed gate."""
    sections = {
        "why_strategic_gears": {
            "certifications_and_compliance": [
                "ENGINE 2 REQUIRED: ISO 27001",
                "ENGINE 2 REQUIRED: PMP",
            ],
        },
    }
    result = sanitize_source_book_sections(sections)
    assert result.total_removals >= 2
    # The gate should treat these removals as evidence that the section
    # had unsupported proof — conformance should flag it


def test_semantic_phrase_sdaia_removed():
    """Semantic phrase 'خبرة موثقة في العمل مع سدايا' must be removed."""
    sections = {
        "why_strategic_gears": {
            "experience_text": "خبرة موثقة في العمل مع سدايا في مشاريع مماثلة",
        },
    }
    result = sanitize_source_book_sections(sections)
    text = result.sanitized["why_strategic_gears"]["experience_text"]
    assert "خبرة موثقة في العمل مع سدايا" not in text
    assert len(result.removals) >= 1
    assert any("semantic:" in r.pattern for r in result.removals)


def test_semantic_phrase_unesco_removed():
    """Semantic phrase 'documented collaboration with UNESCO' must be removed."""
    sections = {
        "why_strategic_gears": {
            "partnerships": "documented collaboration with UNESCO on AI ethics",
        },
    }
    result = sanitize_source_book_sections(sections)
    text = result.sanitized["why_strategic_gears"]["partnerships"]
    assert "documented collaboration with UNESCO" not in text


def test_internal_field_not_sanitized():
    """Internal-only fields must not be sanitized."""
    sections = {
        "internal_gap_appendix": {
            "notes": "PRJ-001 ENGINE 2 REQUIRED خبرة موثقة في العمل مع سدايا",
        },
    }
    result = sanitize_source_book_sections(sections)
    text = result.sanitized["internal_gap_appendix"]["notes"]
    assert "PRJ-001" in text
    assert "ENGINE 2 REQUIRED" in text
    assert result.removals == []
