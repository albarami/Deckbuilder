"""Conversation Manager — bridge between human intent and system operations."""

import json

from src.config.models import MODEL_MAP
from src.models.actions import ConversationResponse
from src.models.enums import PipelineStage
from src.models.state import ConversationTurn, DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT

# Maximum conversation history turns to include in the user message.
_MAX_HISTORY_TURNS = 10


async def run(
    state: DeckForgeState,
    user_message: str,
) -> DeckForgeState:
    """Conversation Manager — interpret user requests into structured actions.

    Takes the user's natural language message and the current pipeline state,
    then produces a ConversationResponse with a structured action for the
    Workflow Controller to execute.

    Does NOT change state.current_stage — only the Workflow Controller
    decides stage transitions based on the returned action.
    """
    # Build lightweight session_state summary (not full state serialization)
    session_state: dict[str, object] = {
        "current_stage": state.current_stage,
        "has_rfp_context": state.rfp_context is not None,
        "has_report": bool(state.report_markdown),
        "has_slide_outline": state.slide_outline is not None,
        "has_written_slides": state.written_slides is not None,
        "has_qa_result": state.qa_result is not None,
        "total_slides": (
            len(state.written_slides.slides)
            if state.written_slides
            else 0
        ),
        "output_language": state.output_language,
        "presentation_type": state.presentation_type,
    }

    # Truncate conversation history to last N turns
    recent_history = state.conversation_history[-_MAX_HISTORY_TURNS:]
    history_dicts = [t.model_dump(mode="json") for t in recent_history]

    llm_user_message = json.dumps({
        "user_message": user_message,
        "session_state": session_state,
        "user_role": state.session.user_role,
        "conversation_history": history_dicts,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["conversation_manager"],
            system_prompt=SYSTEM_PROMPT,
            user_message=llm_user_message,
            response_model=ConversationResponse,
        )
        state.last_action = result.parsed
        # Append user turn + assistant turn
        state.conversation_history.append(
            ConversationTurn(role="user", content=user_message)
        )
        state.conversation_history.append(
            ConversationTurn(
                role="assistant",
                content=result.parsed.response_to_user,
            )
        )
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="conversation_manager",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
