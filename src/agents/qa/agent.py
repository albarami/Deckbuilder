"""QA Agent — No Free Facts enforcer and final quality gate.

In template_v2 mode, QA validates ONLY b_variable slides — template-owned
content (A1 clones, pool clones, section dividers) is excluded.
"""

import json
import logging

from src.config.models import MODEL_MAP
from src.models.enums import LayoutType, PipelineStage, RendererMode
from src.models.qa import QAResult
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Template constraints from Prompt Library Agent 7.
# Defined here as a constant — future M7 pipeline node may load from
# template metadata, but for now the Prompt Library values are canonical.
TEMPLATE_CONSTRAINTS: dict[str, object] = {
    "max_title_chars": 80,
    "max_bullet_chars": 150,
    "max_bullets_per_slide": 6,
    "valid_layout_types": [lt.value for lt in LayoutType],
}


def _get_variable_asset_ids(state: DeckForgeState) -> set[str]:
    """Extract asset_ids of b_variable entries from the manifest.

    In template_v2 mode, only b_variable slides need QA validation.
    Template-owned content (A1 clones, pool clones, dividers) is excluded.
    """
    if state.proposal_manifest is None:
        return set()
    return {
        e.asset_id
        for e in state.proposal_manifest.entries
        if e.entry_type == "b_variable"
    }


async def run(state: DeckForgeState) -> DeckForgeState:
    """QA Agent — validate slides against No Free Facts and template rules.

    In template_v2 mode, validates ONLY b_variable slides from the manifest.
    Template-owned content (A1 clones, pool clones, section dividers) is
    excluded because it is pre-approved institutional content.

    In legacy mode, validates all slides (unchanged behavior).

    Inputs from state: written_slides (slides to validate), report_markdown
    (approved report), reference_index (claims + gaps), waivers, rfp_context
    (evaluation criteria).  Template constraints are a module-level constant.

    If unresolved critical gaps exist, result.deck_summary.fail_close = True.
    The pipeline node (M7) checks fail_close to block deck export.
    """
    slides = []
    if state.written_slides:
        all_slides = state.written_slides.slides

        # In template_v2 mode, validate ONLY b_variable slides — strict scope.
        # Uses manifest_asset_id provenance (stamped by build_slides_node)
        # to filter — NOT slide_id (different namespace from manifest).
        if state.renderer_mode == RendererMode.TEMPLATE_V2:
            variable_ids = _get_variable_asset_ids(state)
            if variable_ids:
                filtered = [
                    s for s in all_slides
                    if s.manifest_asset_id in variable_ids
                ]
                logger.info(
                    "QA (v2 mode): validating %d b_variable slides "
                    "(skipping %d template-owned)",
                    len(filtered),
                    len(all_slides) - len(filtered),
                )
                slides = [s.model_dump(mode="json") for s in filtered]
            else:
                # No manifest or no variable IDs — validate zero slides
                # (strict: never fall back to all slides in v2 mode)
                logger.warning(
                    "QA (v2 mode): no b_variable slide IDs found — "
                    "validating zero slides"
                )
                slides = []
        else:
            slides = [s.model_dump(mode="json") for s in all_slides]

    claim_index = []
    unresolved_gaps = []
    if state.reference_index:
        claim_index = [c.model_dump(mode="json") for c in state.reference_index.claims]
        unresolved_gaps = [g.model_dump(mode="json") for g in state.reference_index.gaps]

    waived_gaps = [w.model_dump(mode="json") for w in state.waivers]

    evaluation_criteria = None
    if state.rfp_context and state.rfp_context.evaluation_criteria:
        evaluation_criteria = state.rfp_context.evaluation_criteria.model_dump(mode="json")

    user_message = json.dumps({
        "slides": slides,
        "approved_report": state.report_markdown,
        "claim_index": claim_index,
        "unresolved_gaps": unresolved_gaps,
        "waived_gaps": waived_gaps,
        "evaluation_criteria": evaluation_criteria,
        "template_constraints": TEMPLATE_CONSTRAINTS,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["qa_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=QAResult,
            max_tokens=16000,
        )
        qa_result = result.parsed
        state.current_stage = PipelineStage.QA
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1

        # Defensive fallback: if QA returned a parsed result but deck_summary
        # is missing or empty (e.g. LLM truncation), force fail_close=True so
        # the pipeline never silently passes with no real validation.
        ds = qa_result.deck_summary
        if ds.total_slides == 0 and len(slides) > 0:
            logger.warning(
                "QA returned empty deck_summary for %d slides — forcing fail_close",
                len(slides),
            )
            ds.fail_close = True
            ds.fail_close_reason = (
                "QA returned empty validation (possible LLM truncation). "
                "Deck cannot be exported without real QA validation."
            )
            ds.total_slides = len(slides)

        state.qa_result = qa_result

    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="qa_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
