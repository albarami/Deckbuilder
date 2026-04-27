"""Tests for forbidden internal-claim leakage scanner."""
import pytest

from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.services.artifact_gates import ArtifactSection, scan_for_forbidden_leakage


def test_prj_id_rejected_in_client_body():
    section = ArtifactSection(
        section_path="why_sg/capability_mapping",
        section_type="client_facing_body",
        text="خبرة موثقة في العمل مع سدايا [PRJ-001]",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1
    assert any("PRJ-001" in v.matched_text for v in violations)


def test_prj_id_allowed_in_internal_gap_appendix():
    section = ArtifactSection(
        section_path="appendix/engine2_requirements",
        section_type="internal_gap_appendix",
        text="PRJ-001: requires verification",
    )
    violations = scan_for_forbidden_leakage(section)
    assert violations == []


def test_cli_id_rejected_in_slide_body():
    section = ArtifactSection(
        section_path="slide_8/body",
        section_type="slide_body",
        text="CLI-002 confirmed partnership",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1


def test_clm_id_rejected_in_proof_column():
    section = ArtifactSection(
        section_path="section_3/proof",
        section_type="proof_column",
        text="Evidence: CLM-0012",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1


def test_engine2_required_rejected():
    section = ArtifactSection(
        section_path="section_3/capabilities",
        section_type="proof_column",
        text="Team assignment ENGINE 2 REQUIRED",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1


def test_arabic_internal_marker_rejected():
    section = ArtifactSection(
        section_path="section_3/body",
        section_type="client_facing_body",
        text="هذا البند إثبات داخلي مطلوب من السجلات",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1


def test_semantic_phrase_rejected():
    section = ArtifactSection(
        section_path="why_sg/experience",
        section_type="client_facing_body",
        text="خبرة موثقة في العمل مع سدايا واليونسكو",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1


def test_semantic_phrase_allowed_if_verified_in_registry():
    registry = ClaimRegistry()
    registry.register(ClaimProvenance(
        claim_id="BIDDER-001",
        text="خبرة موثقة في العمل مع سدايا",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_verified",
        requires_client_naming_permission=True,
        client_naming_permission=True,
        scope_summary_allowed_for_proposal=True,
    ))
    section = ArtifactSection(
        section_path="why_sg/experience",
        section_type="client_facing_body",
        text="خبرة موثقة في العمل مع سدايا",
    )
    violations = scan_for_forbidden_leakage(section, registry)
    assert violations == []


def test_internal_placeholder_rejected():
    section = ArtifactSection(
        section_path="slide_5/key_message",
        section_type="slide_body",
        text="Our team has INTERNAL_PROOF_PLACEHOLDER experience",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1


def test_allowed_in_drafting_notes():
    section = ArtifactSection(
        section_path="drafting/notes",
        section_type="drafting_notes",
        text="PRJ-001 CLI-002 ENGINE 2 REQUIRED",
    )
    violations = scan_for_forbidden_leakage(section)
    assert violations == []


def test_allowed_in_evidence_ledger():
    section = ArtifactSection(
        section_path="evidence/ledger",
        section_type="evidence_ledger",
        text="PRJ-001 internal reference",
    )
    violations = scan_for_forbidden_leakage(section)
    assert violations == []
