"""Knowledge Graph models — People, Projects, Clients.

These models power the entity extraction pipeline. The Knowledge Graph
stores WHO did WHAT for WHOM across all indexed documents, enabling
team slide population, project experience lookup by client, and
certification-to-person matching.
"""

from datetime import UTC, datetime

from pydantic import Field

from .common import DeckForgeBaseModel


class PersonProfile(DeckForgeBaseModel):
    """A person extracted from knowledge-base documents."""

    person_id: str  # PER-001
    name: str
    name_ar: str | None = None
    email: str | None = None
    phone: str | None = None
    current_role: str | None = None
    company: str | None = None
    nationality: str | None = None
    years_experience: int | None = None
    certifications: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    domain_expertise: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    source_documents: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)  # PRJ-NNN refs
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProjectRecord(DeckForgeBaseModel):
    """A project extracted from knowledge-base documents."""

    project_id: str  # PRJ-001
    project_name: str
    project_name_ar: str | None = None
    client: str
    client_type: str | None = None
    country: str | None = None
    city: str | None = None
    sector: str | None = None
    domain_tags: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None
    contract_value: str | None = None
    team_size: int | None = None
    team_members: list[str] = Field(default_factory=list)  # PER-NNN refs
    outcomes: list[str] = Field(default_factory=list)
    methodologies: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    source_documents: list[str] = Field(default_factory=list)


class ClientRecord(DeckForgeBaseModel):
    """A client/organization extracted from knowledge-base documents."""

    client_id: str  # CLI-001
    name: str
    name_ar: str | None = None
    client_type: str | None = None  # government, private, semi-government
    sector: str | None = None
    country: str | None = None
    projects: list[str] = Field(default_factory=list)  # PRJ-NNN refs
    source_documents: list[str] = Field(default_factory=list)


class KnowledgeGraph(DeckForgeBaseModel):
    """Top-level knowledge graph holding all entities and relationships."""

    people: list[PersonProfile] = Field(default_factory=list)
    projects: list[ProjectRecord] = Field(default_factory=list)
    clients: list[ClientRecord] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
    document_count: int = 0
