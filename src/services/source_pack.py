"""Source Pack — deterministic assembly of evidence from knowledge graph.

Reads the knowledge graph directly and extracts structured evidence:
- Company aggregate stats (people, projects, clients)
- People with roles, expertise, certifications
- Projects with clients, scope, outcomes
- Client list with sectors
- Full document content from approved sources (NOT truncated)

This replaces the Analysis Agent's truncated claim extraction.
Section fillers consume the SourcePack as their evidence base.

**Content contract:** SourcePack carries FULL source document content.
The ``content_text`` field on ``DocumentEvidence`` is the complete document
text (up to the analysis agent's MAX_CHARS_PER_DOC limit of 50,000 chars).
Downstream section fillers receive full evidence — no silent truncation.

NO LLM calls.  Pure deterministic extraction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.models.knowledge import (
    ClientRecord,
    KnowledgeGraph,
    PersonProfile,
    ProjectRecord,
)

logger = logging.getLogger(__name__)


# ── Source Pack models ────────────────────────────────────────────────


@dataclass(frozen=True)
class PersonSummary:
    """Compact person summary for section fillers."""

    person_id: str
    name: str
    current_role: str
    company: str
    years_experience: int | None
    certifications: list[str]
    domain_expertise: list[str]
    project_ids: list[str]


@dataclass(frozen=True)
class ProjectSummary:
    """Compact project summary for section fillers."""

    project_id: str
    project_name: str
    client: str
    sector: str | None
    country: str | None
    outcomes: list[str]
    methodologies: list[str]
    technologies: list[str]
    team_size: int | None
    duration_months: int | None


@dataclass(frozen=True)
class ClientSummary:
    """Compact client summary for section fillers."""

    client_id: str
    name: str
    client_type: str | None
    sector: str | None
    country: str | None
    project_count: int


@dataclass(frozen=True)
class DocumentEvidence:
    """Full-content evidence document for section fillers.

    **Contract:** ``content_text`` is the FULL document content, not a
    preview or truncated excerpt.  The analysis agent's upstream limit
    (MAX_CHARS_PER_DOC = 50,000) is the only cap — SourcePack does NOT
    apply any additional truncation.
    """

    doc_id: str
    title: str
    content_text: str  # FULL content — not truncated by SourcePack
    char_count: int


@dataclass
class SourcePack:
    """Complete evidence pack assembled from knowledge graph + documents.

    **Content contract:** This pack carries FULL source content.
    ``documents`` contains ``DocumentEvidence`` objects with complete
    ``content_text``.  Section fillers receive full evidence text.
    No silent truncation occurs in this layer.

    All fields are deterministically derived — no LLM.
    """

    # Aggregate stats
    total_people: int = 0
    total_projects: int = 0
    total_clients: int = 0

    # Detailed records
    people: list[PersonSummary] = field(default_factory=list)
    projects: list[ProjectSummary] = field(default_factory=list)
    clients: list[ClientSummary] = field(default_factory=list)
    documents: list[DocumentEvidence] = field(default_factory=list)

    # Sector-level aggregates
    sectors: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)


# ── Builder ───────────────────────────────────────────────────────────


def _person_to_summary(person: PersonProfile) -> PersonSummary:
    return PersonSummary(
        person_id=person.person_id,
        name=person.name,
        current_role=person.current_role or "",
        company=person.company or "",
        years_experience=person.years_experience,
        certifications=list(person.certifications),
        domain_expertise=list(person.domain_expertise),
        project_ids=list(person.projects),
    )


def _project_to_summary(project: ProjectRecord) -> ProjectSummary:
    return ProjectSummary(
        project_id=project.project_id,
        project_name=project.project_name,
        client=project.client,
        sector=project.sector,
        country=project.country,
        outcomes=list(project.outcomes),
        methodologies=list(project.methodologies),
        technologies=list(project.technologies),
        team_size=project.team_size,
        duration_months=project.duration_months,
    )


def _client_to_summary(client: ClientRecord, kg: KnowledgeGraph) -> ClientSummary:
    project_count = sum(
        1 for p in kg.projects if p.client == client.name
    )
    return ClientSummary(
        client_id=client.client_id,
        name=client.name,
        client_type=client.client_type,
        sector=client.sector,
        country=client.country,
        project_count=project_count,
    )


def build_source_pack(
    knowledge_graph: KnowledgeGraph | None = None,
    approved_sources: list[dict] | None = None,
) -> SourcePack:
    """Build a SourcePack from the knowledge graph and approved sources.

    **Content contract:** Approved source content is stored in FULL.
    No truncation is applied by this function.  The upstream analysis
    agent's MAX_CHARS_PER_DOC (50,000) is the only content limit.

    Parameters
    ----------
    knowledge_graph : KnowledgeGraph, optional
        Extracted entity graph from indexed documents.
    approved_sources : list[dict], optional
        Approved source documents with full ``content_text``.

    Returns
    -------
    SourcePack
        Complete evidence pack for section fillers.
    """
    pack = SourcePack()

    if knowledge_graph is not None:
        kg = knowledge_graph
        pack.total_people = len(kg.people)
        pack.total_projects = len(kg.projects)
        pack.total_clients = len(kg.clients)

        pack.people = [_person_to_summary(p) for p in kg.people]
        pack.projects = [_project_to_summary(p) for p in kg.projects]
        pack.clients = [_client_to_summary(c, kg) for c in kg.clients]

        # Aggregate unique sectors and countries
        pack.sectors = sorted({
            p.sector for p in kg.projects if p.sector
        })
        pack.countries = sorted({
            p.country for p in kg.projects if p.country
        })

    if approved_sources:
        for doc in approved_sources:
            content = str(doc.get("content_text", ""))
            pack.documents.append(DocumentEvidence(
                doc_id=str(doc.get("doc_id", "")),
                title=str(doc.get("title", "")),
                content_text=content,  # FULL content — no truncation
                char_count=len(content),
            ))

    logger.info(
        "SourcePack built: people=%d, projects=%d, clients=%d, docs=%d, "
        "total_doc_chars=%d",
        pack.total_people, pack.total_projects,
        pack.total_clients, len(pack.documents),
        sum(d.char_count for d in pack.documents),
    )
    return pack
