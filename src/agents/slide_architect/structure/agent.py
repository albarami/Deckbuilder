"""Template-locked Structure Agent runtime."""

from __future__ import annotations

import json

from src.config.models import MODEL_MAP
from src.models.enums import LayoutType, PipelineStage
from src.models.slide_blueprint import SlideBlueprint
from src.models.slides import SlideObject, SlideOutline
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


def _layout_for_section(section_id: str) -> LayoutType:
    """Map canonical section IDs to legacy outline layout types."""
    if section_id == "S01":
        return LayoutType.TITLE
    if section_id == "S03":
        return LayoutType.AGENDA
    if section_id in {"S04", "S06", "S08", "S10", "S12", "S13", "S17", "S19", "S21", "S23", "S25", "S27", "S29"}:
        return LayoutType.SECTION
    if section_id == "S09":
        return LayoutType.FRAMEWORK
    if section_id == "S11":
        return LayoutType.TIMELINE
    if section_id == "S31":
        return LayoutType.CLOSING
    return LayoutType.CONTENT_1COL


def _blueprint_to_outline(blueprint: SlideBlueprint) -> SlideOutline:
    """Generate a compatibility SlideOutline from blueprint entries."""
    slides: list[SlideObject] = []
    for idx, entry in enumerate(blueprint.entries, start=1):
        title = entry.slide_title or entry.section_name
        key_message = entry.key_message or ""
        guidance_parts: list[str] = [f"section_id={entry.section_id}", f"ownership={entry.ownership}"]
        if entry.house_action:
            guidance_parts.append(f"house_action={entry.house_action}")
        if entry.pool_selection_criteria:
            guidance_parts.append(f"pool_selection_criteria={entry.pool_selection_criteria}")
        if entry.bullet_points:
            guidance_parts.append(f"bullet_points={len(entry.bullet_points)}")
        if entry.evidence_ids:
            guidance_parts.append(f"evidence_ids={','.join(entry.evidence_ids)}")
        guidance = " | ".join(guidance_parts)

        slides.append(
            SlideObject(
                slide_id=f"S-{idx:03d}",
                title=title,
                key_message=key_message,
                layout_type=_layout_for_section(entry.section_id),
                report_section_ref=entry.section_id,
                source_claims=entry.evidence_ids or [],
                content_guidance=guidance,
            )
        )

    return SlideOutline(
        slides=slides,
        slide_count=len(slides),
        weight_allocation={
            "template_locked_contract": "S01-S31 canonical order with ownership-aware fields"
        },
    )


async def run(state: DeckForgeState) -> DeckForgeState:
    """Generate template-locked blueprint from approved report."""
    evaluation_criteria = None
    if state.rfp_context and state.rfp_context.evaluation_criteria:
        evaluation_criteria = state.rfp_context.evaluation_criteria.model_dump(mode="json")

    user_message = json.dumps(
        {
            "approved_report": state.report_markdown,
            "rfp_context": state.rfp_context.model_dump(mode="json") if state.rfp_context else None,
            "presentation_type": state.presentation_type,
            "evaluation_criteria": evaluation_criteria,
            "output_language": state.output_language,
        }
    )

    try:
        result = await call_llm(
            model=MODEL_MAP["structure_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=SlideBlueprint,
            max_tokens=8000,
        )
        state.slide_blueprint = result.parsed
        state.slide_outline = _blueprint_to_outline(result.parsed)
        state.current_stage = PipelineStage.OUTLINE_REVIEW
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(
            ErrorInfo(
                agent="structure_agent",
                error_type=type(e.last_error).__name__,
                message=str(e),
                retries_attempted=e.attempts,
            )
        )
        state.last_error = state.errors[-1]

    return state

