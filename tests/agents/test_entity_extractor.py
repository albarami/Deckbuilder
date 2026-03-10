"""Tests for entity extraction — people, projects, clients from documents.

TDD: Write tests first, then implement src/agents/indexing/entity_extractor.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.extraction import ExtractedDocument
from src.models.knowledge import (
    ClientRecord,
    KnowledgeGraph,
    PersonProfile,
    ProjectRecord,
)

# ── Fixtures ──────────────────────────────────────────────────────────


def _make_doc(filename: str, text: str) -> ExtractedDocument:
    """Create a minimal ExtractedDocument for testing."""
    return ExtractedDocument(
        filepath=f"/fake/{filename}",
        filename=filename,
        file_type=filename.rsplit(".", 1)[-1],
        full_text=text,
    )


def _mock_llm_response(parsed: object) -> MagicMock:
    """Create a mock LLMResponse with a .parsed attribute."""
    resp = MagicMock()
    resp.parsed = parsed
    resp.input_tokens = 100
    resp.output_tokens = 200
    resp.model = "gpt-5.4"
    resp.latency_ms = 500.0
    return resp


# ── Test 1: Extract entities finds people ─────────────────────────────


@pytest.mark.asyncio
async def test_extract_entities_finds_people() -> None:
    """Mock LLM returns people from a team slide document."""
    from src.agents.indexing.entity_extractor import (
        EntityExtractionResult,
        extract_entities,
    )

    mock_result = EntityExtractionResult(
        people=[
            {
                "name": "Hattan Saaty",
                "current_role": "CEO",
                "company": "Strategic Gears",
                "certifications": ["PMP"],
                "domain_expertise": ["Digital Transformation", "Strategy"],
            },
            {
                "name": "Laith Abdin",
                "current_role": "COO",
                "company": "Strategic Gears",
            },
        ],
        projects=[],
        clients=[],
    )

    with patch(
        "src.agents.indexing.entity_extractor.call_llm",
        new_callable=AsyncMock,
        return_value=_mock_llm_response(mock_result),
    ):
        doc = _make_doc("team_slide.pptx", "Hattan Saaty, CEO\nLaith Abdin, COO")
        result = await extract_entities(doc, "DOC-001")

    assert len(result.people) == 2
    assert result.people[0]["name"] == "Hattan Saaty"
    assert result.people[0]["current_role"] == "CEO"
    assert result.people[1]["name"] == "Laith Abdin"


# ── Test 2: Extract entities finds projects ───────────────────────────


@pytest.mark.asyncio
async def test_extract_entities_finds_projects() -> None:
    """Mock LLM returns projects from a case study document."""
    from src.agents.indexing.entity_extractor import (
        EntityExtractionResult,
        extract_entities,
    )

    mock_result = EntityExtractionResult(
        people=[],
        projects=[
            {
                "project_name": "Saudi Water Authority Digital Transformation",
                "client": "Saudi Water Authority",
                "country": "Saudi Arabia",
                "sector": "Water & Utilities",
                "outcomes": ["Reduced processing time by 40%"],
                "technologies": ["SAP S/4HANA", "Power BI"],
            },
        ],
        clients=[],
    )

    with patch(
        "src.agents.indexing.entity_extractor.call_llm",
        new_callable=AsyncMock,
        return_value=_mock_llm_response(mock_result),
    ):
        doc = _make_doc("swa_case_study.pdf", "Saudi Water Authority project...")
        result = await extract_entities(doc, "DOC-002")

    assert len(result.projects) == 1
    assert result.projects[0]["client"] == "Saudi Water Authority"
    assert "SAP S/4HANA" in result.projects[0]["technologies"]


# ── Test 3: Extract entities finds clients ────────────────────────────


@pytest.mark.asyncio
async def test_extract_entities_finds_clients() -> None:
    """Mock LLM returns client organizations."""
    from src.agents.indexing.entity_extractor import (
        EntityExtractionResult,
        extract_entities,
    )

    mock_result = EntityExtractionResult(
        people=[],
        projects=[],
        clients=[
            {
                "name": "Ministry of Labor",
                "client_type": "government",
                "sector": "Public Sector",
                "country": "Qatar",
            },
        ],
    )

    with patch(
        "src.agents.indexing.entity_extractor.call_llm",
        new_callable=AsyncMock,
        return_value=_mock_llm_response(mock_result),
    ):
        doc = _make_doc("mol_proposal.docx", "Ministry of Labor, Qatar...")
        result = await extract_entities(doc, "DOC-003")

    assert len(result.clients) == 1
    assert result.clients[0]["name"] == "Ministry of Labor"
    assert result.clients[0]["country"] == "Qatar"


# ── Test 4: Merge deduplicates same person from two docs ──────────────


@pytest.mark.asyncio
async def test_merge_deduplicates_same_person() -> None:
    """Same person from two documents gets merged into one PersonProfile."""
    from src.agents.indexing.entity_extractor import (
        EntityExtractionResult,
        merge_into_knowledge_graph,
    )

    existing = KnowledgeGraph()

    # First doc: person with PMP cert
    result1 = EntityExtractionResult(
        people=[
            {
                "name": "Ahmad Al Omary",
                "current_role": "Senior Consultant",
                "certifications": ["PMP"],
                "domain_expertise": ["ERP"],
            },
        ],
        projects=[],
        clients=[],
    )

    # Second doc: same person with different spelling + extra certs
    result2 = EntityExtractionResult(
        people=[
            {
                "name": "Ahmed Al-Omary",
                "current_role": "Senior Consultant",
                "certifications": ["ITIL", "TOGAF"],
                "domain_expertise": ["Cloud"],
            },
        ],
        projects=[],
        clients=[],
    )

    kg = await merge_into_knowledge_graph(
        existing, [result1, result2], ["DOC-001", "DOC-002"]
    )

    # Should be merged into ONE person, not two
    assert len(kg.people) == 1
    person = kg.people[0]
    assert "PMP" in person.certifications
    assert "ITIL" in person.certifications
    assert "TOGAF" in person.certifications
    assert "DOC-001" in person.source_documents
    assert "DOC-002" in person.source_documents


# ── Test 5: Merge deduplicates same project from two docs ─────────────


@pytest.mark.asyncio
async def test_merge_deduplicates_same_project() -> None:
    """Same project from two documents gets merged."""
    from src.agents.indexing.entity_extractor import (
        EntityExtractionResult,
        merge_into_knowledge_graph,
    )

    existing = KnowledgeGraph()

    result1 = EntityExtractionResult(
        people=[],
        projects=[
            {
                "project_name": "SWA Digital Transformation",
                "client": "Saudi Water Authority",
                "country": "Saudi Arabia",
                "technologies": ["SAP"],
            },
        ],
        clients=[],
    )

    result2 = EntityExtractionResult(
        people=[],
        projects=[
            {
                "project_name": "SWA Digital Transformation Phase 2",
                "client": "Saudi Water Authority",
                "technologies": ["Power BI"],
            },
        ],
        clients=[],
    )

    kg = await merge_into_knowledge_graph(
        existing, [result1, result2], ["DOC-001", "DOC-002"]
    )

    # These are different enough that they should NOT merge (similarity < threshold)
    # "SWA Digital Transformation" vs "SWA Digital Transformation Phase 2" + same client
    # depends on threshold — if same client AND name similarity > 0.8, merge
    # In this case they should merge because client is same and name is very similar
    assert len(kg.projects) == 1
    proj = kg.projects[0]
    assert "SAP" in proj.technologies
    assert "Power BI" in proj.technologies


# ── Test 6: Knowledge graph saves and loads JSON ──────────────────────


@pytest.mark.asyncio
async def test_knowledge_graph_saves_and_loads(tmp_path: Path) -> None:
    """KnowledgeGraph JSON round-trip persistence."""
    from src.agents.indexing.entity_extractor import (
        load_knowledge_graph,
        save_knowledge_graph,
    )

    now = datetime.now(UTC)
    kg = KnowledgeGraph(
        people=[
            PersonProfile(
                person_id="PER-001",
                name="Test Person",
                current_role="Tester",
                last_updated=now,
            ),
        ],
        projects=[
            ProjectRecord(
                project_id="PRJ-001",
                project_name="Test Project",
                client="Test Client",
            ),
        ],
        clients=[
            ClientRecord(
                client_id="CLI-001",
                name="Test Client",
            ),
        ],
        last_updated=now,
        document_count=5,
    )

    path = str(tmp_path / "knowledge_graph.json")
    save_knowledge_graph(kg, path)

    # Verify file exists
    assert Path(path).exists()

    # Reload and verify
    loaded = load_knowledge_graph(path)
    assert len(loaded.people) == 1
    assert loaded.people[0].name == "Test Person"
    assert len(loaded.projects) == 1
    assert loaded.projects[0].project_name == "Test Project"
    assert len(loaded.clients) == 1
    assert loaded.clients[0].name == "Test Client"
    assert loaded.document_count == 5


# ── Test 7: Entity extractor uses MODEL_MAP ───────────────────────────


@pytest.mark.asyncio
async def test_entity_extractor_uses_model_map() -> None:
    """Entity extractor calls LLM with MODEL_MAP['indexing_classifier']."""
    from src.agents.indexing.entity_extractor import (
        EntityExtractionResult,
        extract_entities,
    )

    mock_result = EntityExtractionResult(people=[], projects=[], clients=[])

    with patch(
        "src.agents.indexing.entity_extractor.call_llm",
        new_callable=AsyncMock,
        return_value=_mock_llm_response(mock_result),
    ) as mock_llm:
        doc = _make_doc("test.pdf", "Some content")
        await extract_entities(doc, "DOC-001")

    call_kwargs = mock_llm.call_args
    from src.config.models import MODEL_MAP

    assert call_kwargs.kwargs["model"] == MODEL_MAP["indexing_classifier"]


# ── Test 8: Entity extractor handles LLM error gracefully ────────────


@pytest.mark.asyncio
async def test_entity_extractor_handles_llm_error() -> None:
    """LLM failure returns empty EntityExtractionResult."""
    from src.agents.indexing.entity_extractor import extract_entities
    from src.services.llm import LLMError

    with patch(
        "src.agents.indexing.entity_extractor.call_llm",
        new_callable=AsyncMock,
        side_effect=LLMError(
            model="gpt-5.4", attempts=4, last_error=Exception("timeout")
        ),
    ):
        doc = _make_doc("bad.pdf", "Some content")
        result = await extract_entities(doc, "DOC-001")

    # Should return empty, not raise
    assert len(result.people) == 0
    assert len(result.projects) == 0
    assert len(result.clients) == 0
