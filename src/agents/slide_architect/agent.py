"""Slide Architect agent — converts Source Book into per-slide blueprint.

Reads the approved Source Book (with its 7-section structure and evidence
ledger) plus the assembly plan (methodology, slide budget) and produces
a SlideBlueprint with one SlideBlueprintEntry per variable slide.

Model: Claude Opus via MODEL_MAP["slide_architect"]
"""

import json
import logging

from src.config.models import MODEL_MAP
from src.models.slide_blueprint import SlideBlueprint
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import call_llm

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _build_user_message(state: DeckForgeState) -> str:
    """Serialize state context for the Slide Architect LLM call.

    Includes:
    - Source Book content (serialized)
    - Assembly plan metadata (methodology, slide budget, sector/geography)
    - RFP context (mandate, evaluation criteria)
    - Proposal manifest section summary (which sections need variable slides)
    """
    payload: dict = {}

    # Source Book — the primary input
    if state.source_book:
        payload["source_book"] = state.source_book.model_dump(mode="json")

    # Assembly plan — slide budget and methodology
    if state.assembly_plan:
        payload["assembly_plan"] = state.assembly_plan

    # Slide budget details
    if state.slide_budget:
        payload["slide_budget"] = state.slide_budget

    # Methodology blueprint (frozen dataclass — use dataclasses.asdict)
    if state.methodology_blueprint:
        from dataclasses import asdict
        payload["methodology_blueprint"] = asdict(state.methodology_blueprint)

    # Sector and geography
    if state.sector:
        payload["sector"] = state.sector
    if state.geography:
        payload["geography"] = state.geography

    # RFP context — mandate, evaluation criteria
    if state.rfp_context:
        rfp_dump = state.rfp_context.model_dump(mode="json")
        # Keep it focused — just the key fields
        payload["rfp_context"] = {
            k: rfp_dump[k]
            for k in (
                "rfp_name", "mandate", "evaluation_criteria",
                "scope_items", "deliverables",
            )
            if k in rfp_dump and rfp_dump[k]
        }

    # Proposal manifest — which sections need variable slides
    if state.proposal_manifest:
        sections_summary = {}
        for entry in state.proposal_manifest.entries:
            if entry.entry_type == "b_variable":
                sid = entry.section_id
                sections_summary.setdefault(sid, 0)
                sections_summary[sid] += 1
        payload["variable_slide_budget_by_section"] = sections_summary

    # Evidence ledger from Source Book (for cross-referencing)
    if state.source_book and state.source_book.evidence_ledger:
        ledger = state.source_book.evidence_ledger
        if hasattr(ledger, "entries") and ledger.entries:
            payload["evidence_ledger"] = [
                e.model_dump(mode="json")
                for e in ledger.entries
            ]

    return json.dumps(payload, ensure_ascii=False, default=str)


async def run(state: DeckForgeState) -> dict:
    """Run the Slide Architect agent.

    Returns a dict with keys matching DeckForgeState fields to update.
    """
    user_message = _build_user_message(state)

    logger.info(
        "Slide Architect payload: chars=%d, has_source_book=%s, "
        "has_assembly_plan=%s",
        len(user_message),
        state.source_book is not None,
        state.assembly_plan is not None,
    )

    model = MODEL_MAP.get("slide_architect", MODEL_MAP.get("analysis_agent"))

    try:
        llm_result = await call_llm(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=SlideBlueprint,
            max_tokens=16000,
        )

        blueprint = llm_result.parsed

        logger.info(
            "Slide blueprint complete: %d entries",
            len(blueprint.entries),
        )

        # Update session accounting
        session = state.session.model_copy(deep=True)
        session.total_llm_calls += 1
        session.total_input_tokens += llm_result.input_tokens
        session.total_output_tokens += llm_result.output_tokens

        return {
            "slide_blueprint": blueprint,
            "session": session,
        }

    except Exception as e:
        logger.error("Slide Architect failed: %s", e)

        return {
            "slide_blueprint": SlideBlueprint(entries=[]),
            "errors": state.errors + [
                ErrorInfo(
                    agent="slide_architect",
                    error_type="LLMError",
                    message=str(e),
                ),
            ],
            "last_error": ErrorInfo(
                agent="slide_architect",
                error_type="LLMError",
                message=str(e),
            ),
        }
