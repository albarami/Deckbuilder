"""Assembly Plan Agent — template-first assembly plan for a proposal.

LLM agent (Opus) that runs after retrieval is approved (Gate 2).
Reads the RFP context and produces the structured inputs needed by
the existing deterministic infrastructure:

1. HouseInclusionPolicy (geography, proposal_mode, sector)
2. MethodologyBlueprint (phases with activities/deliverables)
3. CaseStudySelectionResult (scored against RFP matching context)
4. TeamSelectionResult (scored against RFP matching context)
5. SlideBudget (exact slide counts per section)

The LLM decides the "what" (phases, scope, slide counts).
Everything else is deterministic scoring + budgeting.
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import Field

from src.config.models import MODEL_MAP
from src.models.common import DeckForgeBaseModel
from src.models.enums import PipelineStage
from src.models.methodology_blueprint import (
    MethodologyBlueprint,
    build_methodology_blueprint,
)
from src.models.proposal_manifest import (
    HouseInclusionPolicy,
    build_inclusion_policy,
)
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm
from src.services.selection_policies import (
    CaseStudySelectionResult,
    ServiceDividerSelectionResult,
    TeamSelectionResult,
    select_case_studies,
    select_service_divider,
    select_team_members,
)
from src.services.slide_budgeter import SlideBudget, compute_slide_budget

from . import prompts

logger = logging.getLogger(__name__)


# ── Pydantic models for LLM output ─────────────────────────────────────


class MethodologyPhaseSpec(DeckForgeBaseModel):
    """Specification for one methodology phase (LLM output)."""

    phase_name_en: str
    phase_name_ar: str = ""
    activities: list[str] = Field(default_factory=list, min_length=1)
    deliverables: list[str] = Field(default_factory=list, min_length=1)
    governance_tier: str = ""


class RFPMatchingContext(DeckForgeBaseModel):
    """Context for deterministic case study + team selection scoring."""

    sector: str = ""
    services: list[str] = Field(default_factory=list)
    geography: str = ""
    technology_keywords: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    language: str = "en"


class AssemblyPlanOutput(DeckForgeBaseModel):
    """LLM output that feeds the deterministic assembly pipeline."""

    # HouseInclusionPolicy inputs
    geography: str  # ksa | gcc | mena | international
    proposal_mode: str  # lite | standard | full
    sector: str

    # MethodologyBlueprint inputs
    methodology_phases: list[MethodologyPhaseSpec] = Field(
        min_length=3, max_length=5
    )
    methodology_timeline_span: str = "12 weeks"

    # Selection context for case studies and team
    rfp_matching_context: RFPMatchingContext

    # Variable slide counts
    understanding_slides: int = 3
    timeline_slides: int = 2
    governance_slides: int = 1

    # Strategic framing
    win_themes: list[str] = Field(default_factory=list)
    rfp_summary: str = ""
    client_name: str = ""


# ── Assembly result (stored on state) ──────────────────────────────────


class AssemblyPlanResult(DeckForgeBaseModel):
    """Complete assembly plan — stored on DeckForgeState."""

    llm_output: AssemblyPlanOutput
    inclusion_policy: HouseInclusionPolicy
    methodology_blueprint: MethodologyBlueprint
    case_study_result: CaseStudySelectionResult
    team_result: TeamSelectionResult
    slide_budget: SlideBudget
    service_divider_result: ServiceDividerSelectionResult | None = None


# ── Pool metadata loading ──────────────────────────────────────────────


def _load_catalog_lock(catalog_lock_path: Path | None = None) -> dict[str, Any]:
    """Load the catalog lock JSON."""
    if catalog_lock_path is None:
        catalog_lock_path = (
            Path(__file__).resolve().parents[2] / "data" / "catalog_lock_en.json"
        )
    if not catalog_lock_path.exists():
        logger.warning("Catalog lock not found at %s", catalog_lock_path)
        return {}
    with open(catalog_lock_path, encoding="utf-8") as f:
        return json.load(f)


def _load_case_study_candidates(
    catalog_lock: dict[str, Any],
    knowledge_graph_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Build case study candidate dicts from catalog lock + knowledge graph.

    Each candidate has an ``asset_id`` (the catalog semantic_id) plus
    metadata fields used by ``select_case_studies()``.
    """
    pool_raw = catalog_lock.get("case_study_pool", [])
    # The catalog lock stores case_study_pool as either:
    # - a dict with category keys (e.g. {"general": [...entries...]})
    # - a list of entries directly
    if isinstance(pool_raw, dict):
        pool: list[dict[str, Any]] = []
        for entries in pool_raw.values():
            if isinstance(entries, list):
                pool.extend(entries)
    elif isinstance(pool_raw, list):
        pool = pool_raw
    else:
        pool = []

    if not pool:
        return []

    # Try to load knowledge graph for project metadata enrichment
    kg_projects: list[dict[str, Any]] = []
    if knowledge_graph_path is None:
        knowledge_graph_path = Path("state/index/knowledge_graph.json")
    if knowledge_graph_path.exists():
        try:
            with open(knowledge_graph_path, encoding="utf-8") as f:
                kg = json.load(f)
            kg_projects = kg.get("projects", [])
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not load knowledge graph for enrichment")

    candidates: list[dict[str, Any]] = []
    for i, entry in enumerate(pool):
        asset_id = entry.get("semantic_id", f"case_study_{i}")

        # Base candidate with asset_id
        candidate: dict[str, Any] = {
            "asset_id": asset_id,
            "sector": "",
            "services": [],
            "geography": "",
            "technology_keywords": [],
            "capability_tags": [],
            "language": "en",
        }

        # Enrich from knowledge graph project if available (round-robin mapping)
        if kg_projects and i < len(kg_projects):
            proj = kg_projects[i]
            candidate["sector"] = (proj.get("sector") or "").lower()
            candidate["geography"] = _country_to_geography(
                proj.get("country", "")
            )
            candidate["technology_keywords"] = [
                t.lower() for t in proj.get("technologies", [])
            ]
            candidate["capability_tags"] = [
                t.lower() for t in proj.get("domain_tags", [])
            ]

        candidates.append(candidate)

    return candidates


def _load_team_candidates(
    catalog_lock: dict[str, Any],
    knowledge_graph_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Build team member candidate dicts from catalog lock + knowledge graph.

    Each candidate maps to a team bio pool slide.  Metadata comes from
    the knowledge graph person records matched by name.
    """
    pool = catalog_lock.get("team_bio_pool", [])
    if not pool:
        return []

    # Load knowledge graph for person metadata
    kg_people: list[dict[str, Any]] = []
    if knowledge_graph_path is None:
        knowledge_graph_path = Path("state/index/knowledge_graph.json")
    if knowledge_graph_path.exists():
        try:
            with open(knowledge_graph_path, encoding="utf-8") as f:
                kg = json.load(f)
            kg_people = kg.get("people", [])
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not load knowledge graph for team enrichment")

    # Build name → person lookup
    people_by_name: dict[str, dict[str, Any]] = {}
    for person in kg_people:
        name = (person.get("name") or "").strip().lower()
        if name:
            people_by_name[name] = person

    candidates: list[dict[str, Any]] = []
    for entry in pool:
        asset_id = entry.get("semantic_id", "")
        member_names = entry.get("member_names", [])

        # Extract actual names (skip experience strings, roles, departments)
        actual_names = _extract_person_names(member_names)

        # Build candidate from matched knowledge graph people
        candidate: dict[str, Any] = {
            "asset_id": asset_id,
            "sector_experience": [],
            "services": [],
            "role": "",
            "geography_experience": [],
            "technology_keywords": [],
            "languages": [],
        }

        for name in actual_names:
            person = people_by_name.get(name.lower(), {})
            if person:
                # Aggregate expertise from matched person
                for expertise in person.get("domain_expertise", []):
                    candidate["technology_keywords"].append(expertise.lower())
                for lang in person.get("languages", []):
                    candidate["languages"].append(lang.lower())
                role = person.get("current_role", "")
                if role and not candidate["role"]:
                    candidate["role"] = role.lower()

        candidates.append(candidate)

    return candidates


def _extract_person_names(member_names: list[str]) -> list[str]:
    """Extract actual person names from catalog lock member_names list.

    The member_names list mixes names, roles, experience strings, and
    department names.  Names are typically ALL CAPS with 2-3 words.
    """
    names: list[str] = []
    skip_patterns = {
        "years of experience", "partner", "managing", "senior",
        "associate", "director", "consultant", "lead", "head",
        "strategy", "marketing", "digital", "cloud", "transformation",
        "organizational", "excellence", "people", "advisory",
        "deals", "research",
    }
    for entry in member_names:
        entry_lower = entry.lower().strip()
        # Skip obvious non-name entries
        if any(pat in entry_lower for pat in skip_patterns):
            continue
        # Names are typically 2+ words, all caps in template
        words = entry.strip().split()
        if len(words) >= 2 and all(w[0].isupper() for w in words if w):
            names.append(entry.strip())
    return names


def _country_to_geography(country: str | None) -> str:
    """Map a country name to geography code."""
    if not country:
        return "international"
    country_lower = country.lower()
    ksa_indicators = [
        "saudi", "المملكة العربية السعودية", "ksa",
        "kingdom of saudi arabia",
    ]
    gcc_indicators = [
        "uae", "bahrain", "kuwait", "qatar", "oman",
        "الإمارات", "البحرين", "الكويت", "قطر", "عمان",
    ]
    mena_indicators = [
        "egypt", "jordan", "lebanon", "morocco", "tunisia",
        "مصر", "الأردن", "لبنان", "المغرب", "تونس",
    ]

    for indicator in ksa_indicators:
        if indicator in country_lower:
            return "ksa"
    for indicator in gcc_indicators:
        if indicator in country_lower:
            return "gcc"
    for indicator in mena_indicators:
        if indicator in country_lower:
            return "mena"
    return "international"


# ── Main agent ─────────────────────────────────────────────────────────


async def run(
    state: DeckForgeState,
    *,
    catalog_lock_path: Path | None = None,
    knowledge_graph_path: Path | None = None,
) -> dict[str, Any]:
    """Run the Assembly Plan Agent.

    Reads from state:
      - rfp_context — parsed RFP
      - output_language — target language
      - proposal_mode, sector, geography — if pre-set by user

    Writes to state (as dict for LangGraph):
      - assembly_plan — full AssemblyPlanResult
      - methodology_blueprint — for downstream section fillers
      - slide_budget — for downstream section fillers
      - proposal_manifest — None (built later by render node)
      - current_stage — updated on success/error
    """
    # ── Step 1: Build LLM input ────────────────────────────────────────
    user_data: dict[str, Any] = {
        "output_language": str(state.output_language),
    }

    if state.rfp_context:
        user_data["rfp_context"] = state.rfp_context.model_dump(mode="json")

    if state.proposal_mode:
        user_data["pre_set_proposal_mode"] = state.proposal_mode
    if state.sector:
        user_data["pre_set_sector"] = state.sector
    if state.geography:
        user_data["pre_set_geography"] = state.geography

    # Include approved source summaries (not full text — that's for fillers)
    if state.retrieved_sources:
        user_data["retrieved_source_summaries"] = [
            {
                "doc_id": s.doc_id,
                "title": s.title,
                "summary": s.summary,
            }
            for s in state.retrieved_sources
            if s.recommendation == "include"
        ]

    # Include methodology approach from Proposal Strategy (Phase 4)
    if state.proposal_strategy and state.proposal_strategy.recommended_methodology_approach:
        user_data["recommended_methodology_approach"] = (
            state.proposal_strategy.recommended_methodology_approach
        )

    user_message = json.dumps(user_data, ensure_ascii=False)

    # ── Step 2: Call LLM ───────────────────────────────────────────────
    try:
        result = await call_llm(
            model=MODEL_MAP.get("assembly_plan_agent", MODEL_MAP["analysis_agent"]),
            system_prompt=prompts.SYSTEM_PROMPT,
            user_message=user_message,
            response_model=AssemblyPlanOutput,
            max_tokens=8000,
        )
        llm_output = result.parsed

    except LLMError as e:
        error = ErrorInfo(
            agent="assembly_plan",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        )
        return {
            "current_stage": PipelineStage.ERROR,
            "errors": state.errors + [error],
            "last_error": error,
        }

    # ── Step 3: Deterministic pipeline (all existing code) ─────────────

    # 3a. HouseInclusionPolicy
    try:
        inclusion_policy = build_inclusion_policy(
            proposal_mode=llm_output.proposal_mode,
            geography=llm_output.geography,
            sector=llm_output.sector,
        )
    except Exception as e:
        error = ErrorInfo(
            agent="assembly_plan",
            error_type="InclusionPolicyError",
            message=f"Failed to build inclusion policy: {e}",
        )
        return {
            "current_stage": PipelineStage.ERROR,
            "errors": state.errors + [error],
            "last_error": error,
        }

    # 3b. MethodologyBlueprint
    try:
        phase_defs = [
            {
                "phase_name_en": p.phase_name_en,
                "phase_name_ar": p.phase_name_ar,
                "activities": p.activities,
                "deliverables": p.deliverables,
                "governance_tier": p.governance_tier,
            }
            for p in llm_output.methodology_phases
        ]
        methodology_blueprint = build_methodology_blueprint(
            phase_count=len(llm_output.methodology_phases),
            phases=phase_defs,
            timeline_span=llm_output.methodology_timeline_span,
        )
    except Exception as e:
        error = ErrorInfo(
            agent="assembly_plan",
            error_type="MethodologyBlueprintError",
            message=f"Failed to build methodology blueprint: {e}",
        )
        return {
            "current_stage": PipelineStage.ERROR,
            "errors": state.errors + [error],
            "last_error": error,
        }

    # 3c. Load pool candidates and run deterministic selection
    catalog_lock = _load_catalog_lock(catalog_lock_path)

    matching_context = llm_output.rfp_matching_context.model_dump()

    # Case study selection
    cs_candidates = _load_case_study_candidates(catalog_lock, knowledge_graph_path)
    case_study_result = select_case_studies(
        candidates=cs_candidates,
        rfp_context=matching_context,
        min_count=inclusion_policy.case_study_count[0],
        max_count=inclusion_policy.case_study_count[1],
    )

    # Team selection
    team_candidates = _load_team_candidates(catalog_lock, knowledge_graph_path)
    team_result = select_team_members(
        candidates=team_candidates,
        rfp_context=matching_context,
        min_count=inclusion_policy.team_bio_count[0],
        max_count=inclusion_policy.team_bio_count[1],
    )

    # 3d. Compute slide budget
    try:
        slide_budget = compute_slide_budget(
            inclusion_policy=inclusion_policy,
            methodology_blueprint=methodology_blueprint,
            case_study_result=case_study_result,
            team_result=team_result,
            understanding_slides=llm_output.understanding_slides,
            timeline_slides=llm_output.timeline_slides,
            governance_slides=llm_output.governance_slides,
        )
    except Exception as e:
        error = ErrorInfo(
            agent="assembly_plan",
            error_type="BudgetError",
            message=f"Failed to compute slide budget: {e}",
        )
        return {
            "current_stage": PipelineStage.ERROR,
            "errors": state.errors + [error],
            "last_error": error,
        }

    # 3e. Select service divider
    catalog_data = _load_catalog_lock(catalog_lock_path)
    service_divider_pool = catalog_data.get("service_divider_pool", [])
    service_divider_result = select_service_divider(
        rfp_context=matching_context,
        service_divider_pool=service_divider_pool,
    )
    logger.info(
        "Service divider selected: %s (score=%.1f, reason=%s)",
        service_divider_result.selected_service_divider,
        service_divider_result.score,
        service_divider_result.reason,
    )

    # ── Step 4: Build assembly plan result ─────────────────────────────
    assembly_plan = AssemblyPlanResult(
        llm_output=llm_output,
        inclusion_policy=inclusion_policy,
        methodology_blueprint=methodology_blueprint,
        case_study_result=case_study_result,
        team_result=team_result,
        slide_budget=slide_budget,
        service_divider_result=service_divider_result,
    )

    # ── Step 5: Build ProposalManifest from assembly plan ────────────
    from src.services.manifest_builder import build_manifest_from_assembly_plan

    language = state.output_language
    lang_val = language.value if hasattr(language, "value") else str(language)
    lang_suffix = "ar" if lang_val == "ar" else "en"

    # Resolve catalog_lock_path so manifest builder can do slide_idx lookups
    resolved_lock = catalog_lock_path
    if resolved_lock is None:
        resolved_lock = (
            Path(__file__).resolve().parents[2]
            / "data"
            / f"catalog_lock_{lang_suffix}.json"
        )

    manifest = build_manifest_from_assembly_plan(
        assembly_plan=assembly_plan,
        catalog_lock_path=resolved_lock,
        language=lang_suffix,
    )

    # Update token counts
    input_tokens = result.input_tokens
    output_tokens = result.output_tokens

    logger.info(
        "Assembly Plan complete: %s mode, %s geography, %d methodology phases, "
        "%d case studies selected, %d team bios selected, %d total slides, "
        "%d manifest entries",
        llm_output.proposal_mode,
        llm_output.geography,
        len(llm_output.methodology_phases),
        len(case_study_result.selected),
        len(team_result.selected),
        slide_budget.total_slides,
        manifest.total_slides,
    )

    return {
        "assembly_plan": assembly_plan,
        "methodology_blueprint": methodology_blueprint,
        "slide_budget": slide_budget,
        "proposal_manifest": manifest,
        "selected_service_divider": (
            service_divider_result.selected_service_divider
        ),
        "sector": llm_output.sector,
        "geography": llm_output.geography,
        "proposal_mode": llm_output.proposal_mode,
        "current_stage": PipelineStage.ANALYSIS,
        "session": _updated_session(
            state.session, input_tokens, output_tokens
        ),
    }


def _updated_session(
    session: Any,
    input_tokens: int,
    output_tokens: int,
) -> Any:
    """Return session with updated token counts."""
    session.total_input_tokens += input_tokens
    session.total_output_tokens += output_tokens
    session.total_llm_calls += 1
    return session
