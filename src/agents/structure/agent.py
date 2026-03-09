"""Structure Agent — converts approved Research Report into slide-by-slide outline."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.slides import SlideOutline
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


async def run(state: DeckForgeState) -> DeckForgeState:
    """Structure Agent — generate the slide outline from the approved report.

    All inputs come from state: report_markdown (the approved report),
    rfp_context, presentation_type, output_language.  The outline is
    reviewed at Gate 4 before any slide content is written.

    The agent does NOT add new content — it restructures existing approved
    content into slide format.  content_guidance may only reference approved
    report sections, claim IDs, and content type instructions.
    """
    evaluation_criteria = None
    if state.rfp_context and state.rfp_context.evaluation_criteria:
        evaluation_criteria = state.rfp_context.evaluation_criteria.model_dump(mode="json")

    user_message = json.dumps({
        "approved_report": state.report_markdown,
        "rfp_context": state.rfp_context.model_dump(mode="json") if state.rfp_context else None,
        "presentation_type": state.presentation_type,
        "evaluation_criteria": evaluation_criteria,
        "output_language": state.output_language,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["structure_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=SlideOutline,
        )
        state.slide_outline = result.parsed
        state.current_stage = PipelineStage.OUTLINE_REVIEW
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="structure_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
