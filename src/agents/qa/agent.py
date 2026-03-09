"""QA Agent — No Free Facts enforcer and final quality gate."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import LayoutType, PipelineStage
from src.models.qa import QAResult
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT

# Template constraints from Prompt Library Agent 7.
# Defined here as a constant — future M7 pipeline node may load from
# template metadata, but for now the Prompt Library values are canonical.
TEMPLATE_CONSTRAINTS: dict[str, object] = {
    "max_title_chars": 80,
    "max_bullet_chars": 150,
    "max_bullets_per_slide": 6,
    "valid_layout_types": [lt.value for lt in LayoutType],
}


async def run(state: DeckForgeState) -> DeckForgeState:
    """QA Agent — validate every slide against No Free Facts and template rules.

    Inputs from state: written_slides (slides to validate), report_markdown
    (approved report), reference_index (claims + gaps), waivers, rfp_context
    (evaluation criteria).  Template constraints are a module-level constant.

    If unresolved critical gaps exist, result.deck_summary.fail_close = True.
    The pipeline node (M7) checks fail_close to block deck export.
    """
    slides = []
    if state.written_slides:
        slides = [s.model_dump(mode="json") for s in state.written_slides.slides]

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
        )
        state.qa_result = result.parsed
        state.current_stage = PipelineStage.QA
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
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
