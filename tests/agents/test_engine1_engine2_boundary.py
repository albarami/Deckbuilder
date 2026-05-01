"""Tests for Engine 1 / Engine 2 boundary enforcement.

The Source Book is an internal/full intelligence artifact. It SHOULD
contain Engine 2 candidate names/projects — labelled as internal
evidence candidates with verification status.

Engine 1 produces role requirements and proof archetypes.
Engine 2 searches the internal evidence corpus for matches.

The Source Book shows both:
A. Engine 1 role/proof requirements
B. Engine 2 candidate matches (labelled, not treated as verified proof)

Named people/projects may appear in the final client-facing proposal
ONLY after Engine 2 verification + disclosure permission.
"""

from __future__ import annotations

import pytest

from src.models.knowledge import KnowledgeGraph, PersonProfile, ProjectRecord
from src.models.source_book import (
    ConsultantProfile,
    ProjectExperience,
    SourceBook,
    WhyStrategicGears,
)
from src.models.state import DeckForgeState


def _state_with_kg() -> DeckForgeState:
    """State with a knowledge graph containing real people/projects."""
    state = DeckForgeState()
    state.knowledge_graph = KnowledgeGraph(
        people=[
            PersonProfile(
                person_id="P001",
                name="Nagaraj Padmanabhan",
                person_type="internal_team",
                current_role="Director",
                company="Strategic Gears",
            ),
            PersonProfile(
                person_id="P002",
                name="Ahmed Essam",
                person_type="internal_team",
                current_role="Senior Consultant",
                company="Strategic Gears",
            ),
        ],
        projects=[
            ProjectRecord(
                project_id="PRJ-001",
                project_name="Qatar Museums AI Tour",
                client="Qatar Museums",
                sector="Culture",
            ),
            ProjectRecord(
                project_id="PRJ-002",
                project_name="SDAIA Strategy Support",
                client="SDAIA",
                sector="Government",
            ),
        ],
        clients=[],
    )
    return state


def _source_book_with_names() -> SourceBook:
    """Source Book where the writer placed KG names in fields."""
    sb = SourceBook(
        client_name="Test", rfp_name="Test RFP", language="en",
    )
    sb.why_strategic_gears = WhyStrategicGears(
        named_consultants=[
            ConsultantProfile(
                name="Nagaraj Padmanabhan",
                role="Lead Consultant",
                staffing_status="recommended_candidate",
                relevance="AI governance expertise",
            ),
            ConsultantProfile(
                name="Fabricated Person",
                role="Data Scientist",
                staffing_status="recommended_candidate",
                relevance="Made up",
            ),
            ConsultantProfile(
                name="",
                role="Project Manager",
                staffing_status="open_role_profile",
                relevance="Already open",
            ),
        ],
        project_experience=[
            ProjectExperience(
                project_name="Qatar Museums AI Tour",
                client="Qatar Museums",
                sector="Culture",
                outcomes="AI-powered tour guides",
            ),
            ProjectExperience(
                project_name="Fabricated Project XYZ",
                client="Nobody",
                sector="N/A",
                outcomes="Made up",
            ),
        ],
    )
    return sb


# ── Source Book internal mode: KG candidates KEPT ────────────────


def test_kg_matched_consultant_kept_in_source_book():
    """KG-matched consultant STAYS in Source Book with exact name preserved."""
    from src.agents.source_book.writer import _engine1_guard

    state = _state_with_kg()
    sb = _source_book_with_names()

    _engine1_guard(sb, state)

    lead = next(
        nc for nc in sb.why_strategic_gears.named_consultants
        if nc.role == "Lead Consultant"
    )
    # Name is PRESERVED in internal Source Book — not stripped
    assert lead.name == "Nagaraj Padmanabhan"
    # Must NOT be recommended_candidate (old label implying proposal-ready)
    assert lead.staffing_status != "recommended_candidate"


def test_kg_matched_consultant_labelled_as_candidate():
    """KG-matched consultant must be labelled candidate_pending_verification."""
    from src.agents.source_book.writer import _engine1_guard

    state = _state_with_kg()
    sb = _source_book_with_names()

    _engine1_guard(sb, state)

    lead = next(
        nc for nc in sb.why_strategic_gears.named_consultants
        if nc.role == "Lead Consultant"
    )
    assert lead.name == "Nagaraj Padmanabhan"
    assert lead.staffing_status == "candidate_pending_verification"
    assert "internal_evidence_candidate" in (lead.source_of_recommendation or "")
    assert "verification" in (lead.source_of_recommendation or "").lower()
    assert "disclosure" in (lead.source_of_recommendation or "").lower()
    assert "client-facing" in (lead.source_of_recommendation or "").lower()


def test_fabricated_consultant_stripped():
    """Fabricated consultant (not in KG) must be stripped."""
    from src.agents.source_book.writer import _engine1_guard

    state = _state_with_kg()
    sb = _source_book_with_names()

    _engine1_guard(sb, state)

    ds = next(
        nc for nc in sb.why_strategic_gears.named_consultants
        if nc.role == "Data Scientist"
    )
    assert ds.name == ""
    assert ds.staffing_status == "open_role_profile"


def test_open_role_profile_preserved():
    """Already-open role profiles should remain unchanged."""
    from src.agents.source_book.writer import _engine1_guard

    state = _state_with_kg()
    sb = _source_book_with_names()

    _engine1_guard(sb, state)

    pm = next(
        nc for nc in sb.why_strategic_gears.named_consultants
        if nc.role == "Project Manager"
    )
    assert pm.staffing_status == "open_role_profile"
    assert pm.name == ""


def test_kg_matched_project_kept_in_source_book():
    """KG-matched project STAYS in Source Book project_experience."""
    from src.agents.source_book.writer import _engine1_guard

    state = _state_with_kg()
    sb = _source_book_with_names()

    _engine1_guard(sb, state)

    project_names = [pe.project_name for pe in sb.why_strategic_gears.project_experience]
    assert "Qatar Museums AI Tour" in project_names


def test_kg_matched_project_labelled_as_candidate():
    """KG-matched project must carry verification_status and evidence_source."""
    from src.agents.source_book.writer import _engine1_guard

    state = _state_with_kg()
    sb = _source_book_with_names()

    _engine1_guard(sb, state)

    qatar = next(
        pe for pe in sb.why_strategic_gears.project_experience
        if "Qatar" in pe.project_name
    )
    assert qatar.verification_status == "candidate_pending_verification"
    assert qatar.evidence_source == "internal_kg"


def test_fabricated_project_stripped():
    """Fabricated project (not in KG) must be stripped."""
    from src.agents.source_book.writer import _engine1_guard

    state = _state_with_kg()
    sb = _source_book_with_names()

    _engine1_guard(sb, state)

    project_names = [pe.project_name for pe in sb.why_strategic_gears.project_experience]
    assert "Fabricated Project XYZ" not in project_names


def test_guard_with_empty_kg():
    """With no KG, all named consultants become open_role_profile."""
    from src.agents.source_book.writer import _engine1_guard

    state = DeckForgeState()  # No KG
    sb = _source_book_with_names()

    _engine1_guard(sb, state)

    for nc in sb.why_strategic_gears.named_consultants:
        assert nc.staffing_status == "open_role_profile"
        assert nc.name == ""

    # No projects either
    assert sb.why_strategic_gears.project_experience == []


def test_source_book_distinguishes_requirements_from_candidates():
    """Source Book should contain both open role profiles AND KG candidates."""
    from src.agents.source_book.writer import _engine1_guard

    state = _state_with_kg()
    sb = _source_book_with_names()

    _engine1_guard(sb, state)

    statuses = {nc.staffing_status for nc in sb.why_strategic_gears.named_consultants}
    # Should have both: open roles (from fabricated/already-open) AND candidates (from KG)
    assert "open_role_profile" in statuses
    assert "candidate_pending_verification" in statuses


# ── Prompt regression: no old language implying KG = proposal-ready ──


def test_prompt_does_not_instruct_recommended_candidate_for_kg():
    """Section 3.2 prompt must NOT instruct writer to USE recommended_candidate
    as the status for KG-matched people (old language implying proposal-ready)."""
    from src.agents.source_book.prompts import STAGE1B_SECTION3_PROMPT

    section_32 = STAGE1B_SECTION3_PROMPT.split("3.2")[1].split("3.3")[0]
    # The prompt may MENTION recommended_candidate in a "NEVER use" context,
    # but must NOT instruct the writer to set it as the staffing_status.
    # Old bad instruction: 'Use "recommended_candidate" for KG-sourced names'
    assert 'Use "recommended_candidate"' not in section_32
    assert 'staffing_status="recommended_candidate"' not in section_32


def test_prompt_uses_candidate_pending_verification():
    """Section 3 prompt must instruct writer to use candidate_pending_verification."""
    from src.agents.source_book.prompts import STAGE1B_SECTION3_PROMPT

    section_32 = STAGE1B_SECTION3_PROMPT.split("3.2")[1].split("3.3")[0]
    assert "candidate_pending_verification" in section_32


def test_prompt_labels_kg_as_internal_evidence():
    """Section 3 prompt must describe KG data as internal evidence candidates."""
    from src.agents.source_book.prompts import STAGE1B_SECTION3_PROMPT

    section_32 = STAGE1B_SECTION3_PROMPT.split("3.2")[1].split("3.3")[0]
    assert "internal" in section_32.lower()
    assert "evidence candidate" in section_32.lower() or "internal_evidence_candidate" in section_32


def test_prompt_section33_labels_projects_as_candidates():
    """Section 3.3 prompt must label KG projects as candidates, not verified."""
    from src.agents.source_book.prompts import STAGE1B_SECTION3_PROMPT

    section_33 = STAGE1B_SECTION3_PROMPT.split("3.3")[1].split("3.4")[0]
    assert "candidate_pending_verification" in section_33
    assert "internal_kg" in section_33
    # Must NOT positively describe KG projects as verified case studies.
    # Negative instructions ("Do NOT describe as verified") are allowed.
    # Check: no line that says KG projects ARE verified case studies.
    for line in section_33.split("\n"):
        line_lower = line.lower().strip()
        if "verified case stud" in line_lower:
            # Allowed if it's a negative instruction
            assert "not" in line_lower or "never" in line_lower, (
                f"Line positively describes KG as verified case study: {line}"
            )
