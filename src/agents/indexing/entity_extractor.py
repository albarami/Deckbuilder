"""Entity Extractor — extracts People, Projects, Clients from documents.

Uses GPT-5.4 to identify WHO did WHAT for WHOM across all indexed documents.
Produces a KnowledgeGraph with deduplicated entities and cross-references.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import Field

from src.config.models import MODEL_MAP
from src.models.common import DeckForgeBaseModel
from src.models.extraction import ExtractedDocument
from src.models.knowledge import (
    ClientRecord,
    KnowledgeGraph,
    PersonProfile,
    ProjectRecord,
)
from src.services.llm import LLMError, call_llm

logger = logging.getLogger(__name__)

# Max content sent to GPT-5.4 for entity extraction
_MAX_CONTENT_CHARS = 30000

# Concurrency limit for parallel extraction
_MAX_CONCURRENT = 5

# Fuzzy match thresholds
_PERSON_NAME_THRESHOLD = 0.80
_PROJECT_NAME_THRESHOLD = 0.80
_CLIENT_NAME_THRESHOLD = 0.85


# ──────────────────────────────────────────────────────────────
# LLM Response Model
# ──────────────────────────────────────────────────────────────


class EntityExtractionResult(DeckForgeBaseModel):
    """Structured output from GPT-5.4 entity extraction.

    Each list contains dicts with flexible fields — the merge step
    normalizes these into typed PersonProfile / ProjectRecord / ClientRecord.
    """

    people: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    clients: list[dict] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────────────────────

ENTITY_EXTRACTION_PROMPT = """From this document, extract ALL mentions of:

1. PEOPLE — full name, role/title, qualifications, certifications, years of experience,
   nationality, email, phone. If a person appears multiple times, merge into one entry.

2. PROJECTS — project name, client name, dates, scope, outcomes, team size, contract value,
   technologies used, methodologies applied. Extract from case studies, past experience
   sections, project summaries.

3. CLIENTS/ENTITIES — organization names, type (government/private/semi-government),
   sector, country.

4. RELATIONSHIPS — who worked on which project, for which client, in what role.

Extract ONLY what is explicitly stated. Do NOT guess or infer.
If a name is mentioned without a role, extract the name and set role to null.
Output ONLY valid JSON matching the schema.

For each person, include these fields where available:
- name (required), name_ar, email, phone, current_role, company, nationality,
  years_experience (int), certifications (list), education (list),
  domain_expertise (list), languages (list)

For each project, include these fields where available:
- project_name (required), project_name_ar, client (required), client_type,
  country, city, sector, domain_tags (list), start_date, end_date,
  duration_months (int), contract_value, team_size (int), team_members (list of names),
  outcomes (list), methodologies (list), technologies (list)

For each client, include these fields where available:
- name (required), name_ar, client_type, sector, country"""


# ──────────────────────────────────────────────────────────────
# Extraction Functions
# ──────────────────────────────────────────────────────────────


async def extract_entities(
    doc: ExtractedDocument,
    doc_id: str,
) -> EntityExtractionResult:
    """Extract people, projects, clients from a single document using GPT-5.4."""
    content_text = doc.full_text[:_MAX_CONTENT_CHARS] if doc.full_text else ""
    if not content_text.strip():
        return EntityExtractionResult()

    user_message = (
        f"Document ID: {doc_id}\n"
        f"Filename: {doc.filename}\n"
        f"Content Type: {doc.file_type}\n"
        f"\n--- CONTENT ---\n\n"
        f"{content_text}"
    )

    try:
        response = await call_llm(
            model=MODEL_MAP["indexing_classifier"],
            system_prompt=ENTITY_EXTRACTION_PROMPT,
            user_message=user_message,
            response_model=EntityExtractionResult,
            temperature=0.0,
            max_tokens=8000,
        )
        result = response.parsed
        logger.info(
            "Extracted from %s (%s): %d people, %d projects, %d clients",
            doc_id, doc.filename,
            len(result.people), len(result.projects), len(result.clients),
        )
        return result

    except LLMError as e:
        logger.warning(
            "Entity extraction failed for %s (%s): %s",
            doc_id, doc.filename, e,
        )
        return EntityExtractionResult()


async def extract_entities_batch(
    docs: list[tuple[ExtractedDocument, str]],
) -> list[EntityExtractionResult]:
    """Extract entities from multiple docs with concurrency limit."""
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    results: list[EntityExtractionResult] = []

    async def _extract_one(
        doc: ExtractedDocument, doc_id: str,
    ) -> EntityExtractionResult:
        async with semaphore:
            return await extract_entities(doc, doc_id)

    tasks = [_extract_one(doc, doc_id) for doc, doc_id in docs]
    completed = await asyncio.gather(*tasks)
    results.extend(completed)
    return results


# ──────────────────────────────────────────────────────────────
# Fuzzy Matching Utilities
# ──────────────────────────────────────────────────────────────


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip, remove hyphens."""
    return name.lower().strip().replace("-", " ").replace("  ", " ")


def _name_similarity(a: str, b: str) -> float:
    """Compute fuzzy similarity between two names using SequenceMatcher."""
    return SequenceMatcher(None, _normalize_name(a), _normalize_name(b)).ratio()


def _find_matching_person(
    people: list[PersonProfile], name: str,
) -> PersonProfile | None:
    """Find a person in the list by fuzzy name match."""
    for person in people:
        if _name_similarity(person.name, name) >= _PERSON_NAME_THRESHOLD:
            return person
    return None


def _find_matching_project(
    projects: list[ProjectRecord], name: str, client: str,
) -> ProjectRecord | None:
    """Find a project by fuzzy name + client match."""
    for proj in projects:
        name_sim = _name_similarity(proj.project_name, name)
        client_sim = _name_similarity(proj.client, client) if client else 0.0
        # Match if name is similar AND client matches
        if name_sim >= _PROJECT_NAME_THRESHOLD and client_sim >= _CLIENT_NAME_THRESHOLD:
            return proj
    return None


def _find_matching_client(
    clients: list[ClientRecord], name: str,
) -> ClientRecord | None:
    """Find a client by fuzzy name match."""
    for client in clients:
        if _name_similarity(client.name, name) >= _CLIENT_NAME_THRESHOLD:
            return client
    return None


# ──────────────────────────────────────────────────────────────
# Merge Logic
# ──────────────────────────────────────────────────────────────


def _merge_list_field(existing: list, new_items: list) -> list:
    """Merge two lists, deduplicating by lowercase string comparison."""
    existing_lower = {str(item).lower() for item in existing}
    merged = list(existing)
    for item in new_items:
        if str(item).lower() not in existing_lower:
            merged.append(item)
            existing_lower.add(str(item).lower())
    return merged


def _merge_person(existing: PersonProfile, data: dict, doc_id: str) -> PersonProfile:
    """Merge new person data into existing PersonProfile."""
    # Update scalar fields only if currently None
    if existing.name_ar is None and data.get("name_ar"):
        existing.name_ar = data["name_ar"]
    if existing.email is None and data.get("email"):
        existing.email = data["email"]
    if existing.phone is None and data.get("phone"):
        existing.phone = data["phone"]
    if existing.current_role is None and data.get("current_role"):
        existing.current_role = data["current_role"]
    if existing.company is None and data.get("company"):
        existing.company = data["company"]
    if existing.nationality is None and data.get("nationality"):
        existing.nationality = data["nationality"]
    if existing.years_experience is None and data.get("years_experience"):
        existing.years_experience = data["years_experience"]

    # Merge list fields
    existing.certifications = _merge_list_field(
        existing.certifications, data.get("certifications", [])
    )
    existing.education = _merge_list_field(
        existing.education, data.get("education", [])
    )
    existing.domain_expertise = _merge_list_field(
        existing.domain_expertise, data.get("domain_expertise", [])
    )
    existing.languages = _merge_list_field(
        existing.languages, data.get("languages", [])
    )

    # Track source document
    if doc_id not in existing.source_documents:
        existing.source_documents.append(doc_id)

    existing.last_updated = datetime.now(UTC)
    return existing


def _merge_project(
    existing: ProjectRecord, data: dict, doc_id: str,
) -> ProjectRecord:
    """Merge new project data into existing ProjectRecord."""
    if existing.project_name_ar is None and data.get("project_name_ar"):
        existing.project_name_ar = data["project_name_ar"]
    if existing.client_type is None and data.get("client_type"):
        existing.client_type = data["client_type"]
    if existing.country is None and data.get("country"):
        existing.country = data["country"]
    if existing.city is None and data.get("city"):
        existing.city = data["city"]
    if existing.sector is None and data.get("sector"):
        existing.sector = data["sector"]
    if existing.start_date is None and data.get("start_date"):
        existing.start_date = data["start_date"]
    if existing.end_date is None and data.get("end_date"):
        existing.end_date = data["end_date"]
    if existing.duration_months is None and data.get("duration_months"):
        existing.duration_months = data["duration_months"]
    if existing.contract_value is None and data.get("contract_value"):
        existing.contract_value = data["contract_value"]
    if existing.team_size is None and data.get("team_size"):
        existing.team_size = data["team_size"]

    existing.domain_tags = _merge_list_field(
        existing.domain_tags, data.get("domain_tags", [])
    )
    existing.team_members = _merge_list_field(
        existing.team_members, data.get("team_members", [])
    )
    existing.outcomes = _merge_list_field(
        existing.outcomes, data.get("outcomes", [])
    )
    existing.methodologies = _merge_list_field(
        existing.methodologies, data.get("methodologies", [])
    )
    existing.technologies = _merge_list_field(
        existing.technologies, data.get("technologies", [])
    )

    if doc_id not in existing.source_documents:
        existing.source_documents.append(doc_id)

    return existing


def _merge_client(
    existing: ClientRecord, data: dict, doc_id: str,
) -> ClientRecord:
    """Merge new client data into existing ClientRecord."""
    if existing.name_ar is None and data.get("name_ar"):
        existing.name_ar = data["name_ar"]
    if existing.client_type is None and data.get("client_type"):
        existing.client_type = data["client_type"]
    if existing.sector is None and data.get("sector"):
        existing.sector = data["sector"]
    if existing.country is None and data.get("country"):
        existing.country = data["country"]

    if doc_id not in existing.source_documents:
        existing.source_documents.append(doc_id)

    return existing


async def merge_into_knowledge_graph(
    existing: KnowledgeGraph,
    new_results: list[EntityExtractionResult],
    doc_ids: list[str],
) -> KnowledgeGraph:
    """Merge new entity extraction results into the knowledge graph.

    Deduplicates by fuzzy name matching:
    - Same person name (>80% similarity) → merge into one PersonProfile
    - Same project name + client → merge into one ProjectRecord
    - Same client name (>85% similarity) → merge into one ClientRecord
    """
    # Counters for new IDs
    person_counter = len(existing.people)
    project_counter = len(existing.projects)
    client_counter = len(existing.clients)

    for result, doc_id in zip(new_results, doc_ids):
        # Merge people
        for person_data in result.people:
            name = person_data.get("name", "")
            if not name:
                continue

            match = _find_matching_person(existing.people, name)
            if match:
                _merge_person(match, person_data, doc_id)
            else:
                person_counter += 1
                new_person = PersonProfile(
                    person_id=f"PER-{person_counter:03d}",
                    name=name,
                    name_ar=person_data.get("name_ar"),
                    email=person_data.get("email"),
                    phone=person_data.get("phone"),
                    current_role=person_data.get("current_role"),
                    company=person_data.get("company"),
                    nationality=person_data.get("nationality"),
                    years_experience=person_data.get("years_experience"),
                    certifications=person_data.get("certifications", []),
                    education=person_data.get("education", []),
                    domain_expertise=person_data.get("domain_expertise", []),
                    languages=person_data.get("languages", []),
                    source_documents=[doc_id],
                    projects=person_data.get("projects", []),
                )
                existing.people.append(new_person)

        # Merge projects
        for project_data in result.projects:
            proj_name = project_data.get("project_name", "")
            proj_client = project_data.get("client", "")
            if not proj_name:
                continue

            match = _find_matching_project(
                existing.projects, proj_name, proj_client,
            )
            if match:
                _merge_project(match, project_data, doc_id)
            else:
                project_counter += 1
                new_project = ProjectRecord(
                    project_id=f"PRJ-{project_counter:03d}",
                    project_name=proj_name,
                    project_name_ar=project_data.get("project_name_ar"),
                    client=proj_client,
                    client_type=project_data.get("client_type"),
                    country=project_data.get("country"),
                    city=project_data.get("city"),
                    sector=project_data.get("sector"),
                    domain_tags=project_data.get("domain_tags", []),
                    start_date=project_data.get("start_date"),
                    end_date=project_data.get("end_date"),
                    duration_months=project_data.get("duration_months"),
                    contract_value=project_data.get("contract_value"),
                    team_size=project_data.get("team_size"),
                    team_members=project_data.get("team_members", []),
                    outcomes=project_data.get("outcomes", []),
                    methodologies=project_data.get("methodologies", []),
                    technologies=project_data.get("technologies", []),
                    source_documents=[doc_id],
                )
                existing.projects.append(new_project)

        # Merge clients
        for client_data in result.clients:
            client_name = client_data.get("name", "")
            if not client_name:
                continue

            match = _find_matching_client(existing.clients, client_name)
            if match:
                _merge_client(match, client_data, doc_id)
            else:
                client_counter += 1
                new_client = ClientRecord(
                    client_id=f"CLI-{client_counter:03d}",
                    name=client_name,
                    name_ar=client_data.get("name_ar"),
                    client_type=client_data.get("client_type"),
                    sector=client_data.get("sector"),
                    country=client_data.get("country"),
                    source_documents=[doc_id],
                )
                existing.clients.append(new_client)

    existing.last_updated = datetime.now(UTC)
    existing.document_count += len(doc_ids)
    return existing


# ──────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────


def save_knowledge_graph(kg: KnowledgeGraph, path: str) -> None:
    """Save knowledge graph to JSON file."""
    filepath = Path(path)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            kg.model_dump(mode="json"),
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    logger.info(
        "Saved knowledge graph: %d people, %d projects, %d clients → %s",
        len(kg.people), len(kg.projects), len(kg.clients), path,
    )


def load_knowledge_graph(path: str) -> KnowledgeGraph:
    """Load knowledge graph from JSON file."""
    filepath = Path(path)
    if not filepath.exists():
        return KnowledgeGraph()
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    return KnowledgeGraph.model_validate(data)
