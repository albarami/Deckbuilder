"""Draft Agent — Turn 1: Opus drafts 18-22 SlideText from approved report."""

import json
from pathlib import Path

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.iterative import DeckDraft
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import GENERAL_PROMPT, STRICT_PROMPT

_KG_PATH = Path("state/index/knowledge_graph.json")


def _load_company_context() -> dict:
    """Load knowledge graph and build a company context summary."""
    if not _KG_PATH.exists():
        return {}

    with open(_KG_PATH, encoding="utf-8") as f:
        kg = json.load(f)

    people = kg.get("people", [])
    projects = kg.get("projects", [])
    clients = kg.get("clients", [])

    # Build compact summaries
    team_summary = []
    for p in people[:30]:  # Cap to avoid prompt overflow
        entry = {
            "name": p.get("name", ""),
            "role": p.get("current_role", ""),
            "certifications": p.get("certifications", []),
            "expertise": p.get("domain_expertise", []),
            "years_experience": p.get("years_experience"),
        }
        team_summary.append(entry)

    project_summary = []
    for proj in projects[:40]:  # Most relevant projects
        entry = {
            "name": proj.get("project_name", ""),
            "client": proj.get("client", ""),
            "sector": proj.get("sector", ""),
            "scope": proj.get("domain_tags", []),
            "start_date": proj.get("start_date"),
            "end_date": proj.get("end_date"),
            "team_size": proj.get("team_size"),
            "outcomes": proj.get("outcomes", []),
        }
        project_summary.append(entry)

    client_summary = []
    for c in clients[:30]:
        entry = {
            "name": c.get("name", ""),
            "sector": c.get("sector", ""),
            "type": c.get("client_type", ""),
        }
        client_summary.append(entry)

    return {
        "total_team_members": len(people),
        "total_projects": len(projects),
        "total_clients": len(clients),
        "team_members": team_summary,
        "projects": project_summary,
        "clients": client_summary,
    }


async def run(state: DeckForgeState) -> DeckForgeState:
    """Draft Agent — Turn 1 of 5-turn iterative slide builder.

    Reads the approved report and RFP context, produces an initial
    DeckDraft with 18-22 SlideText objects. Uses Strict or General
    prompt based on state.evidence_mode.
    """
    is_general = state.evidence_mode == "general"
    system_prompt = GENERAL_PROMPT if is_general else STRICT_PROMPT

    # Build user message
    user_data: dict = {
        "approved_report": state.report_markdown,
        "rfp_context": state.rfp_context.model_dump(mode="json") if state.rfp_context else None,
        "output_language": state.output_language,
        "evidence_mode": state.evidence_mode,
    }

    # In general mode, include knowledge graph company context
    if is_general:
        user_data["company_context"] = _load_company_context()

    # In strict mode, include reference index if available
    if not is_general and state.reference_index:
        user_data["reference_index"] = state.reference_index.model_dump(mode="json")

    user_message = json.dumps(user_data, ensure_ascii=False)

    try:
        result = await call_llm(
            model=MODEL_MAP["research_agent"],
            system_prompt=system_prompt,
            user_message=user_message,
            response_model=DeckDraft,
            max_tokens=16000,
        )
        state.deck_drafts.append(result.parsed.model_dump(mode="json"))
        state.current_stage = PipelineStage.SLIDE_BUILDING
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="draft_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
