"""Tests for src/services/source_pack.py — SourcePack builder.

Verifies the SourcePack content contract: full document content is
preserved (no truncation), knowledge graph entities are correctly
extracted, and aggregate stats are computed.
"""

from src.models.knowledge import (
    ClientRecord,
    KnowledgeGraph,
    PersonProfile,
    ProjectRecord,
)
from src.services.source_pack import (
    DocumentEvidence,
    SourcePack,
    build_source_pack,
)


def _make_kg() -> KnowledgeGraph:
    return KnowledgeGraph(
        people=[
            PersonProfile(
                person_id="PER-001",
                name="Alice Smith",
                current_role="Principal Consultant",
                company="Strategic Gears",
                years_experience=15,
                certifications=["PMP", "TOGAF"],
                domain_expertise=["strategy", "digital transformation"],
                projects=["PRJ-001"],
            ),
            PersonProfile(
                person_id="PER-002",
                name="Bob Jones",
                current_role="Senior Manager",
                company="Strategic Gears",
                years_experience=10,
                certifications=["PRINCE2"],
                domain_expertise=["governance"],
                projects=["PRJ-001", "PRJ-002"],
            ),
        ],
        projects=[
            ProjectRecord(
                project_id="PRJ-001",
                project_name="Digital Transformation",
                client="Ministry of Finance",
                sector="government",
                country="KSA",
                outcomes=["Cost reduction 30%"],
                methodologies=["Agile"],
                technologies=["SAP"],
                team_size=12,
                duration_months=18,
            ),
            ProjectRecord(
                project_id="PRJ-002",
                project_name="IT Strategy",
                client="ARAMCO",
                sector="energy",
                country="KSA",
                outcomes=["IT roadmap delivered"],
            ),
        ],
        clients=[
            ClientRecord(
                client_id="CLI-001",
                name="Ministry of Finance",
                client_type="government",
                sector="government",
                country="KSA",
            ),
            ClientRecord(
                client_id="CLI-002",
                name="ARAMCO",
                client_type="semi-government",
                sector="energy",
                country="KSA",
            ),
        ],
    )


class TestBuildSourcePack:
    def test_empty_inputs(self):
        pack = build_source_pack()
        assert isinstance(pack, SourcePack)
        assert pack.total_people == 0
        assert pack.total_projects == 0
        assert pack.total_clients == 0

    def test_from_knowledge_graph(self):
        kg = _make_kg()
        pack = build_source_pack(knowledge_graph=kg)
        assert pack.total_people == 2
        assert pack.total_projects == 2
        assert pack.total_clients == 2
        assert len(pack.people) == 2
        assert len(pack.projects) == 2
        assert len(pack.clients) == 2

    def test_person_summary_fields(self):
        kg = _make_kg()
        pack = build_source_pack(knowledge_graph=kg)
        alice = pack.people[0]
        assert alice.person_id == "PER-001"
        assert alice.name == "Alice Smith"
        assert alice.current_role == "Principal Consultant"
        assert "PMP" in alice.certifications
        assert "strategy" in alice.domain_expertise

    def test_project_summary_fields(self):
        kg = _make_kg()
        pack = build_source_pack(knowledge_graph=kg)
        proj = pack.projects[0]
        assert proj.project_id == "PRJ-001"
        assert proj.client == "Ministry of Finance"
        assert proj.sector == "government"
        assert "Cost reduction 30%" in proj.outcomes

    def test_client_project_count(self):
        kg = _make_kg()
        pack = build_source_pack(knowledge_graph=kg)
        mof = next(c for c in pack.clients if c.name == "Ministry of Finance")
        assert mof.project_count == 1
        aramco = next(c for c in pack.clients if c.name == "ARAMCO")
        assert aramco.project_count == 1

    def test_sector_and_country_aggregates(self):
        kg = _make_kg()
        pack = build_source_pack(knowledge_graph=kg)
        assert "government" in pack.sectors
        assert "energy" in pack.sectors
        assert "KSA" in pack.countries


class TestFullContentContract:
    """Verify SourcePack carries FULL document content — no truncation."""

    def test_full_content_preserved(self):
        """Content larger than old DOCUMENT_PREVIEW_CHARS is NOT truncated."""
        big_content = "A" * 50_000  # Full 50k chars
        sources = [
            {"doc_id": "DOC-001", "title": "Big Doc", "content_text": big_content},
        ]
        pack = build_source_pack(approved_sources=sources)
        doc = pack.documents[0]
        assert isinstance(doc, DocumentEvidence)
        assert doc.content_text == big_content  # FULL — not truncated
        assert len(doc.content_text) == 50_000
        assert doc.char_count == 50_000

    def test_small_content_preserved(self):
        sources = [
            {"doc_id": "DOC-002", "title": "Small", "content_text": "short"},
        ]
        pack = build_source_pack(approved_sources=sources)
        assert pack.documents[0].content_text == "short"
        assert pack.documents[0].char_count == 5

    def test_multiple_docs_all_full(self):
        sources = [
            {"doc_id": f"DOC-{i}", "title": f"Doc {i}", "content_text": "x" * (i * 1000)}
            for i in range(1, 6)
        ]
        pack = build_source_pack(approved_sources=sources)
        assert len(pack.documents) == 5
        for i, doc in enumerate(pack.documents):
            expected_len = (i + 1) * 1000
            assert len(doc.content_text) == expected_len
            assert doc.char_count == expected_len

    def test_combined_kg_and_full_sources(self):
        kg = _make_kg()
        sources = [
            {"doc_id": "DOC-001", "title": "RFP", "content_text": "Z" * 10_000},
        ]
        pack = build_source_pack(knowledge_graph=kg, approved_sources=sources)
        assert pack.total_people == 2
        assert len(pack.documents) == 1
        assert len(pack.documents[0].content_text) == 10_000  # FULL
