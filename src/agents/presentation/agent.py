"""Presentation Agent — Turn 5: Opus builds final WrittenSlides with layouts."""

import json
import logging
import re

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.slides import WrittenSlides
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, LLMResponse, call_llm

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

PRESENTATION_INITIAL_MAX_TOKENS = 16000
PRESENTATION_RETRY_MAX_TOKENS = 24000
REFERENCE_TAG_PATTERN = re.compile(r"\[Ref:\s*(CLM-\d{4})\]")


def _minimal_rfp_context(state: DeckForgeState) -> dict[str, dict[str, str | None]] | None:
    """Return only the RFP identity fields needed by the presentation step."""
    if not state.rfp_context:
        return None
    return {
        "rfp_name": state.rfp_context.rfp_name.model_dump(mode="json"),
        "issuing_entity": state.rfp_context.issuing_entity.model_dump(mode="json"),
    }


def _build_user_message(state: DeckForgeState, *, compact: bool = False) -> str:
    """Build the presentation-agent payload, with an optional compact retry form."""
    refined_draft = state.deck_drafts[-1] if state.deck_drafts else {}
    final_review = state.deck_reviews[-1] if state.deck_reviews else {}

    if compact:
        report_outline = (
            [section.heading for section in state.research_report.sections]
            if state.research_report
            else []
        )
        user_data = {
            "refined_draft": refined_draft,
            "final_review": final_review,
            "rfp_context": _minimal_rfp_context(state),
            "report_outline": report_outline,
            "evidence_mode": state.evidence_mode,
            "output_language": state.output_language,
        }
    else:
        user_data = {
            "refined_draft": refined_draft,
            "final_review": final_review,
            "rfp_context": _minimal_rfp_context(state),
            "evidence_mode": state.evidence_mode,
            "output_language": state.output_language,
        }

    return json.dumps(user_data, ensure_ascii=False)


def _is_empty_structured_output_error(error: LLMError) -> bool:
    """Return True when the model returned an empty object instead of slides."""
    message = str(error.last_error).lower()
    return "structured output validation failed" in message and "input_value={}" in message


def _apply_written_slides(
    state: DeckForgeState,
    result: LLMResponse[WrittenSlides],
) -> DeckForgeState:
    """Persist a successful presentation-agent result."""
    state.written_slides = _normalize_written_slides(state, result.parsed)
    state.current_stage = PipelineStage.CONTENT_GENERATION
    state.session.total_input_tokens += result.input_tokens
    state.session.total_output_tokens += result.output_tokens
    state.session.total_llm_calls += 1
    return state


def _extract_source_refs(text: str) -> list[str]:
    """Extract claim IDs from inline [Ref: CLM-xxxx] tags."""
    return REFERENCE_TAG_PATTERN.findall(text)


def _strip_source_refs(text: str) -> str:
    """Remove inline [Ref: CLM-xxxx] tags from presentation-facing text."""
    cleaned = REFERENCE_TAG_PATTERN.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" -")


def _normalize_written_slides(
    state: DeckForgeState,
    written_slides: WrittenSlides,
) -> WrittenSlides:
    """Enforce final slide metadata rules against the refined draft."""
    refined_draft = state.deck_drafts[-1] if state.deck_drafts else {}
    draft_slides = refined_draft.get("slides", []) if isinstance(refined_draft, dict) else []

    for index, slide in enumerate(written_slides.slides):
        draft_slide = draft_slides[index] if index < len(draft_slides) else {}
        draft_bullets = draft_slide.get("bullets", []) if isinstance(draft_slide, dict) else []
        draft_notes = draft_slide.get("speaker_notes", "") if isinstance(draft_slide, dict) else ""

        source_refs: list[str] = []
        for text in draft_bullets:
            source_refs.extend(_extract_source_refs(str(text)))
        source_refs.extend(_extract_source_refs(str(draft_notes)))

        if slide.body_content:
            cleaned_text_elements = []
            for text in slide.body_content.text_elements:
                source_refs.extend(_extract_source_refs(text))
                cleaned_text_elements.append(_strip_source_refs(text))
            slide.body_content.text_elements = cleaned_text_elements

        source_refs.extend(_extract_source_refs(slide.speaker_notes))
        slide.speaker_notes = _strip_source_refs(slide.speaker_notes)

        deduped_refs = list(dict.fromkeys([ref for ref in source_refs if ref]))
        if deduped_refs:
            slide.source_refs = deduped_refs

    return written_slides


async def run(state: DeckForgeState) -> DeckForgeState:
    """Presentation Agent — Turn 5 of 5-turn iterative slide builder.

    Reads the refined DeckDraft (latest) and final DeckReview,
    produces the final WrittenSlides output with full SlideObject structures.
    """
    user_message = _build_user_message(state)
    logger.warning("Presentation payload size: chars=%s", len(user_message))

    try:
        result = await call_llm(
            model=MODEL_MAP["research_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=WrittenSlides,
            max_tokens=PRESENTATION_INITIAL_MAX_TOKENS,
        )
        return _apply_written_slides(state, result)
    except LLMError as e:
        if _is_empty_structured_output_error(e):
            compact_user_message = _build_user_message(state, compact=True)
            logger.warning(
                "Presentation Agent returned empty slides payload; retrying compact mode chars=%s",
                len(compact_user_message),
            )
            try:
                retry_result = await call_llm(
                    model=MODEL_MAP["research_agent"],
                    system_prompt=SYSTEM_PROMPT,
                    user_message=compact_user_message,
                    response_model=WrittenSlides,
                    max_tokens=PRESENTATION_RETRY_MAX_TOKENS,
                )
                return _apply_written_slides(state, retry_result)
            except LLMError as retry_error:
                e = retry_error

        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="presentation_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
