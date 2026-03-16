"""Submission QA Agent — deterministic language lint + blocker check.

No LLM call. Runs after factual_qa (the existing QA agent).
Produces a SubmissionQAResult with language lint results and
unresolved issue status.

Backward-safe: runs cleanly when submission_source_pack, internal_notes,
or unresolved_issues are None — treats missing data as "no unresolved issues".
"""

import logging

from src.models.enums import DeckMode, SubmissionQAStatus
from src.models.state import DeckForgeState
from src.models.submission import (
    LanguageLintResult,
    SubmissionQAResult,
    UnresolvedIssueRegistry,
)
from src.services.density_scorer import score_deck
from src.services.language_linter import lint_slides

logger = logging.getLogger(__name__)


async def run(state: DeckForgeState) -> dict[str, any]:
    """Run the Submission QA Agent (deterministic, no LLM).

    1. Run the language linter on all written slides → LanguageLintResult
    2. Check state.unresolved_issues for any unresolved blockers
    3. Determine status based on deck_mode:
       - CLIENT_SUBMISSION: blockers → BLOCKED
       - INTERNAL_REVIEW: blockers reported but not blocking status

    Writes to state:
      - submission_qa_result — single source of truth for lint + issues
    """
    # -- Gather slides --
    slides = state.written_slides.slides if state.written_slides else []

    # -- Deck mode --
    internal_review_mode = state.deck_mode == DeckMode.INTERNAL_REVIEW

    # -- Language lint --
    if slides:
        lint_result = lint_slides(
            slides,
            internal_review_mode=internal_review_mode,
        )
    else:
        lint_result = LanguageLintResult()

    # -- Density scoring --
    density_result = None
    if slides:
        briefs = None
        if state.submission_source_pack and state.submission_source_pack.slide_briefs:
            briefs = state.submission_source_pack.slide_briefs
        density_result = score_deck(slides, briefs=briefs)

    # -- Evidence provenance --
    evidence_provenance = None
    if slides and state.submission_source_pack:
        from src.services.evidence_provenance import check_evidence_provenance

        briefs_for_prov = (
            state.submission_source_pack.slide_briefs
            if state.submission_source_pack
            else None
        )
        evidence_provenance = check_evidence_provenance(
            slides=slides,
            evidence_bundles=state.submission_source_pack.evidence_bundles,
            briefs=briefs_for_prov,
            deck_mode=state.deck_mode,
        )

    # -- Unresolved issues --
    unresolved = state.unresolved_issues or UnresolvedIssueRegistry()

    # -- Density / provenance flags --
    has_density_blockers = density_result and density_result.blocker_count > 0
    has_density_warnings = density_result and density_result.warning_count > 0

    has_provenance_blockers = (
        evidence_provenance and evidence_provenance.blocker_count > 0
    )

    # -- Determine status --
    if state.deck_mode == DeckMode.CLIENT_SUBMISSION:
        if (
            lint_result.blocker_count > 0
            or unresolved.has_blockers
            or has_density_blockers
            or has_provenance_blockers
        ):
            status = SubmissionQAStatus.BLOCKED
        elif (
            lint_result.warning_count > 0
            or has_density_warnings
            or (evidence_provenance and evidence_provenance.warning_count > 0)
        ):
            status = SubmissionQAStatus.NEEDS_REVIEW
        else:
            status = SubmissionQAStatus.READY
    else:
        # INTERNAL_REVIEW mode
        has_density_issues = has_density_blockers or has_density_warnings

        has_provenance_issues = (
            evidence_provenance
            and (
                evidence_provenance.blocker_count > 0
                or evidence_provenance.warning_count > 0
            )
        )

        if unresolved.has_blockers or has_density_issues or has_provenance_issues:
            status = SubmissionQAStatus.NEEDS_REVIEW
        else:
            status = SubmissionQAStatus.READY

    # -- Build summary --
    summary_parts = [
        f"Lint: {lint_result.blocker_count} blockers, "
        f"{lint_result.warning_count} warnings"
    ]

    if density_result:
        summary_parts.append(
            f"Density: {density_result.blocker_count}B/"
            f"{density_result.warning_count}W, "
            f"{density_result.slides_over_budget} over budget"
        )

    if evidence_provenance and evidence_provenance.issues:
        summary_parts.append(
            f"Provenance: {evidence_provenance.blocker_count}B/"
            f"{evidence_provenance.warning_count}W"
        )

    if unresolved.issues:
        unresolved_count = sum(1 for i in unresolved.issues if not i.resolved)
        summary_parts.append(f"Unresolved issues: {unresolved_count}")

    summary = " | ".join(summary_parts)

    state.submission_qa_result = SubmissionQAResult(
        language_lint=lint_result,
        density_result=density_result,
        evidence_provenance=evidence_provenance,
        unresolved_issues=unresolved,
        status=status,
        summary=summary,
    )

    logger.info(
        "Submission QA complete: status=%s | %s",
        status,
        summary,
    )

    return state
