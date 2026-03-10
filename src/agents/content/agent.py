"""Content Agent — writes consulting-grade slide copy from the approved report."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.slides import WrittenSlides
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


async def run(state: DeckForgeState) -> DeckForgeState:
    """Content Agent — write slide body text, speaker notes, and chart specs.

    All inputs come from state: slide_outline (from Structure Agent),
    report_markdown (the approved report), output_language.

    The agent does NOT add new facts — it distills the approved report into
    slide copy.  No inline [Ref:] tags; references go into source_refs.
    """
    user_message = json.dumps({
        "slide_outline": state.slide_outline.model_dump(mode="json") if state.slide_outline else None,
        "approved_report": state.report_markdown,
        "output_language": state.output_language,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["content_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=WrittenSlides,
            max_tokens=16000,
        )
        state.written_slides = result.parsed
        state.current_stage = PipelineStage.CONTENT_GENERATION
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="content_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
