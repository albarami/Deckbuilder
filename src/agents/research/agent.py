"""Research Agent — generates the fully-cited Research Report."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.report import ResearchReport
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


async def run(state: DeckForgeState) -> DeckForgeState:
    """Research Agent — generate the comprehensive Research Report.

    All inputs come from state: reference_index, rfp_context, output_language,
    user_notes.  The report is the SOLE content source for the deck and is
    reviewed at Gate 3 before any slides are created.

    NOTE — output size risk: ResearchReport may be large enough to challenge
    structured output token limits (architecture doc Section 9).  For now,
    LLMError handling covers this.  Future: partial report save + retry from
    last checkpoint.
    """
    user_message = json.dumps({
        "reference_index": state.reference_index.model_dump(mode="json") if state.reference_index else None,
        "rfp_context": state.rfp_context.model_dump(mode="json") if state.rfp_context else None,
        "output_language": state.output_language,
        "user_strategic_notes": state.user_notes or None,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["research_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=ResearchReport,
            max_tokens=16000,
        )
        state.research_report = result.parsed
        state.report_markdown = result.parsed.full_markdown
        state.current_stage = PipelineStage.REPORT_REVIEW
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="research_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
