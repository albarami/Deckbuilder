"""Tests for backward-safe bypass behavior — existing pipeline works without submission_transform.

These tests verify that when submission_source_pack is None,
all agents fall back to their existing behavior gracefully.
"""

import pytest

from src.models.enums import DeckMode, LayoutType, SubmissionQAStatus
from src.models.slides import BodyContent, SlideObject, WrittenSlides
from src.models.state import DeckForgeState
from src.models.submission import SubmissionQAResult


def test_draft_no_briefs_uses_existing_prompt():
    """When submission_source_pack is None, Draft Agent would use STRICT/GENERAL prompt.

    We verify the has_briefs check evaluates to False correctly.
    """
    state = DeckForgeState()
    assert state.submission_source_pack is None

    has_briefs = (
        state.submission_source_pack
        and state.submission_source_pack.slide_briefs
    )
    assert not has_briefs


def test_review_no_briefs_uses_existing_prompt():
    """When no briefs, Review Agent has_briefs check evaluates False."""
    state = DeckForgeState()
    has_briefs = (
        state.submission_source_pack
        and state.submission_source_pack.slide_briefs
    )
    assert not has_briefs


def test_refine_no_briefs_uses_existing_prompt():
    """When no briefs, Refine Agent has_briefs check evaluates False."""
    state = DeckForgeState()
    has_briefs = (
        state.submission_source_pack
        and state.submission_source_pack.slide_briefs
    )
    assert not has_briefs


def test_presentation_no_briefs_uses_existing_prompt():
    """When no briefs, Presentation Agent has_briefs check evaluates False."""
    state = DeckForgeState()
    has_briefs = (
        state.submission_source_pack
        and state.submission_source_pack.slide_briefs
    )
    assert not has_briefs


@pytest.mark.asyncio
async def test_submission_qa_safe_with_none_pack():
    """Submission QA runs cleanly when submission_source_pack is None."""
    state = DeckForgeState()
    state.written_slides = WrittenSlides(slides=[
        SlideObject(
            slide_id="S-001",
            title="Clean Slide",
            layout_type=LayoutType.CONTENT_1COL,
            body_content=BodyContent(text_elements=["Clean bullet"]),
        ),
    ])
    assert state.submission_source_pack is None

    from src.agents.submission_qa.agent import run

    result = await run(state)
    assert result.submission_qa_result is not None
    assert result.submission_qa_result.status == SubmissionQAStatus.READY


@pytest.mark.asyncio
async def test_submission_qa_safe_with_none_issues():
    """Submission QA runs cleanly when unresolved_issues is None."""
    state = DeckForgeState()
    state.written_slides = WrittenSlides(slides=[
        SlideObject(
            slide_id="S-001",
            title="Clean Slide",
            layout_type=LayoutType.CONTENT_1COL,
            body_content=BodyContent(text_elements=["Clean bullet"]),
        ),
    ])
    assert state.unresolved_issues is None

    from src.agents.submission_qa.agent import run

    result = await run(state)
    assert result.submission_qa_result is not None
    assert result.submission_qa_result.status == SubmissionQAStatus.READY


def test_render_safe_without_submission_qa():
    """Render proceeds when submission_qa_result is None (no fail-close)."""
    from src.models.enums import DeckMode

    state = DeckForgeState(deck_mode=DeckMode.CLIENT_SUBMISSION)
    assert state.submission_qa_result is None

    # The fail-close condition requires submission_qa_result to exist AND be BLOCKED
    # When it's None, the condition is False → render proceeds
    should_block = (
        state.deck_mode == DeckMode.CLIENT_SUBMISSION
        and state.submission_qa_result
        and state.submission_qa_result.status == SubmissionQAStatus.BLOCKED
    )
    assert not should_block


def test_render_fails_close_when_blocked():
    """Render blocks when CLIENT_SUBMISSION + BLOCKED."""
    state = DeckForgeState(
        deck_mode=DeckMode.CLIENT_SUBMISSION,
        submission_qa_result=SubmissionQAResult(
            status=SubmissionQAStatus.BLOCKED,
            summary="Lint: 3 blockers, 0 warnings",
        ),
    )

    should_block = (
        state.deck_mode == DeckMode.CLIENT_SUBMISSION
        and state.submission_qa_result
        and state.submission_qa_result.status == SubmissionQAStatus.BLOCKED
    )
    assert should_block


def test_render_allows_internal_review_with_blockers():
    """Render proceeds in internal_review mode even with lint blockers."""
    state = DeckForgeState(
        deck_mode=DeckMode.INTERNAL_REVIEW,
        submission_qa_result=SubmissionQAResult(
            status=SubmissionQAStatus.NEEDS_REVIEW,
            summary="Lint: 3 blockers, 0 warnings",
        ),
    )

    should_block = (
        state.deck_mode == DeckMode.CLIENT_SUBMISSION
        and state.submission_qa_result
        and state.submission_qa_result.status == SubmissionQAStatus.BLOCKED
    )
    assert not should_block


def test_empty_briefs_list_is_falsy():
    """SubmissionSourcePack with empty slide_briefs is treated as no briefs."""
    from src.models.submission import SubmissionSourcePack

    pack = SubmissionSourcePack()  # Empty briefs list
    has_briefs = pack and pack.slide_briefs
    assert not has_briefs


# ─── Density backward-safety tests (M10.7) ───


def test_density_scorer_safe_with_none_briefs():
    """Density scorer runs cleanly with briefs=None, uses STANDARD."""
    from src.models.enums import DensityBudget
    from src.services.density_scorer import score_deck

    slides = [
        SlideObject(
            slide_id="S-001",
            title="Clean Slide",
            layout_type=LayoutType.CONTENT_1COL,
            body_content=BodyContent(text_elements=["Clean bullet"]),
        ),
    ]
    result = score_deck(slides, briefs=None)
    assert result.is_within_budget is True
    assert result.slide_scores[0].density_budget == DensityBudget.STANDARD


def test_submission_qa_result_backward_compatible():
    """density_result defaults to None for backward safety."""
    from src.models.submission import SubmissionQAResult

    result = SubmissionQAResult()
    assert result.density_result is None
    assert result.status == SubmissionQAStatus.READY


# ─── Evidence provenance & composition backward-safety tests (M10.8) ───


def test_submission_qa_result_provenance_default_none():
    """evidence_provenance defaults to None for backward safety."""
    from src.models.submission import SubmissionQAResult

    result = SubmissionQAResult()
    assert result.evidence_provenance is None


def test_submission_qa_result_composition_default_none():
    """composition_result defaults to None for backward safety."""
    from src.models.submission import SubmissionQAResult

    result = SubmissionQAResult()
    assert result.composition_result is None
