"""Submission Transform Agent — converts Research Report to Submission Source Pack.

LLM agent (Opus) that runs between Gate 3 and build_slides.
Reads the approved report, reference index, and RFP context,
then produces a SubmissionSourcePack with content units, evidence bundles,
slide allocation, and per-slide briefs.
"""

import json
import logging

from src.config.models import MODEL_MAP
from src.models.common import DeckForgeBaseModel
from src.models.enums import PipelineStage
from src.models.state import DeckForgeState, ErrorInfo
from src.models.submission import (
    InternalNotePack,
    SubmissionSourcePack,
    UnresolvedIssueRegistry,
)
from src.services.llm import LLMError, call_llm

from . import prompts

SYSTEM_PROMPT = prompts.SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class SubmissionTransformOutput(DeckForgeBaseModel):
    """Combined output from the Submission Transform Agent.

    Three separate objects returned together so a single LLM call
    produces the complete transformation.

    internal_notes and unresolved_issues default to empty when the LLM
    omits them (common when there are no issues to report).
    """

    submission_source_pack: SubmissionSourcePack
    internal_notes: InternalNotePack = InternalNotePack()
    unresolved_issues: UnresolvedIssueRegistry = UnresolvedIssueRegistry()


async def run(state: DeckForgeState) -> DeckForgeState:
    """Run the Submission Transform Agent.

    Reads from state:
      - research_report / report_markdown — approved report content
      - reference_index — structured claims, case studies, team profiles
      - rfp_context — evaluation criteria with weights
      - deck_mode — INTERNAL_REVIEW or CLIENT_SUBMISSION

    Writes to state:
      - submission_source_pack — content units, bundles, allocation, briefs
      - internal_notes — workflow notes for internal review
      - unresolved_issues — blockers for client submission
    """
    user_data = {
        "approved_report": state.report_markdown,
        "deck_mode": state.deck_mode,
        "output_language": state.output_language,
    }

    if state.rfp_context:
        user_data["rfp_context"] = state.rfp_context.model_dump(mode="json")

    if state.reference_index:
        user_data["reference_index"] = state.reference_index.model_dump(mode="json")

    if state.research_report:
        user_data["research_report_structured"] = state.research_report.model_dump(
            mode="json"
        )

    # Waivers
    if state.waivers:
        user_data["waivers"] = [w.model_dump(mode="json") for w in state.waivers]

    user_message = json.dumps(user_data, ensure_ascii=False)

    try:
        result = await call_llm(
            model=MODEL_MAP["submission_transform_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=SubmissionTransformOutput,
            max_tokens=32000,
        )

        output = result.parsed

        state.submission_source_pack = output.submission_source_pack
        state.internal_notes = output.internal_notes
        state.unresolved_issues = output.unresolved_issues

        # Update session token counts
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1

        logger.info(
            "Submission Transform complete: %d content units, %d bundles, %d briefs, %d unresolved issues",
            len(output.submission_source_pack.content_units),
            len(output.submission_source_pack.evidence_bundles),
            len(output.submission_source_pack.slide_briefs),
            len(output.unresolved_issues.issues),
        )

    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(
            ErrorInfo(
                agent="submission_transform_agent",
                error_type=type(e.last_error).__name__,
                message=str(e),
                retries_attempted=e.attempts,
            )
        )
        state.last_error = state.errors[-1]
        logger.error("Submission Transform failed: %s", e)

    return state
