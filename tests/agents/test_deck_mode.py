"""Tests for deck mode behavior — DeckMode enum and gate summary integration."""

from src.models.enums import DeckMode


def test_deck_mode_defaults_internal_review():
    """DeckForgeState defaults to INTERNAL_REVIEW mode."""
    from src.models.state import DeckForgeState

    state = DeckForgeState()
    assert state.deck_mode == DeckMode.INTERNAL_REVIEW


def test_deck_mode_enum_values():
    """DeckMode has exactly two values."""
    assert DeckMode.INTERNAL_REVIEW == "internal_review"
    assert DeckMode.CLIENT_SUBMISSION == "client_submission"
    assert len(DeckMode) == 2


def test_gate_3_summary_shows_deck_mode():
    """Gate 3 summary includes the deck mode."""
    from src.models.state import DeckForgeState
    from src.pipeline.graph import _gate_3_summary

    state = DeckForgeState(report_markdown="Test report content")
    summary = _gate_3_summary(state)
    assert "Mode:" in summary
    assert "internal_review" in summary


def test_gate_4_summary_shows_deck_mode():
    """Gate 4 summary includes the deck mode."""
    from src.models.state import DeckForgeState
    from src.pipeline.graph import _gate_4_summary

    state = DeckForgeState()
    summary = _gate_4_summary(state)
    assert "Mode:" in summary


def test_gate_5_summary_shows_deck_mode():
    """Gate 5 summary includes the deck mode."""
    from src.models.state import DeckForgeState
    from src.pipeline.graph import _gate_5_summary

    state = DeckForgeState()
    summary = _gate_5_summary(state)
    assert "Mode:" in summary


def test_gate_4_summary_shows_unresolved_blockers():
    """Gate 4 summary shows unresolved blocker count when present."""
    from src.models.enums import BlockerType
    from src.models.state import DeckForgeState
    from src.models.submission import UnresolvedIssue, UnresolvedIssueRegistry
    from src.pipeline.graph import _gate_4_summary

    state = DeckForgeState(
        unresolved_issues=UnresolvedIssueRegistry(
            issues=[
                UnresolvedIssue(
                    issue_id="UI-001",
                    description="Missing cert",
                    blocker_type=BlockerType.MISSING_EVIDENCE,
                    resolution_action="Get cert",
                    resolved=False,
                ),
            ],
            has_blockers=True,
        ),
    )
    summary = _gate_4_summary(state)
    assert "Unresolved blockers:" in summary


def test_gate_5_summary_shows_submission_qa():
    """Gate 5 summary shows submission QA status when present."""
    from src.models.enums import SubmissionQAStatus
    from src.models.state import DeckForgeState
    from src.models.submission import SubmissionQAResult
    from src.pipeline.graph import _gate_5_summary

    state = DeckForgeState(
        submission_qa_result=SubmissionQAResult(
            status=SubmissionQAStatus.READY,
            summary="Lint: 0 blockers, 2 warnings",
        ),
    )
    summary = _gate_5_summary(state)
    assert "Submission QA:" in summary
    assert "ready" in summary


def test_state_serialization_with_deck_mode():
    """DeckForgeState with deck_mode serializes and deserializes."""
    from src.models.state import DeckForgeState

    state = DeckForgeState(deck_mode=DeckMode.CLIENT_SUBMISSION)
    json_str = state.model_dump_json()
    restored = DeckForgeState.model_validate_json(json_str)
    assert restored.deck_mode == DeckMode.CLIENT_SUBMISSION


# ─── Density in Gate 5 (M10.7) ───


def test_gate_5_summary_includes_density_slide_ids():
    """Gate 5 summary shows blocker slide IDs and split suggestion slide IDs."""
    from src.models.enums import DensityBudget, DensityViolationSeverity, LayoutType
    from src.models.state import DeckForgeState
    from src.models.submission import (
        DensityResult,
        DensityViolation,
        SlideDensityScore,
        SplitSuggestion,
        SubmissionQAResult,
    )
    from src.pipeline.graph import _gate_5_summary

    state = DeckForgeState(
        submission_qa_result=SubmissionQAResult(
            density_result=DensityResult(
                slide_scores=[
                    SlideDensityScore(
                        slide_id="S-007",
                        layout_type=LayoutType.CONTENT_1COL,
                        density_budget=DensityBudget.STANDARD,
                        bullet_count=10,
                        total_chars=1500,
                        max_bullet_chars=200,
                        budget_utilization_pct=150.0,
                        violations=[DensityViolation(
                            field="bullet_count",
                            actual=10,
                            limit=6,
                            severity=DensityViolationSeverity.BLOCKER,
                            message="10 bullets exceed limit of 6",
                        )],
                        split_suggestion=SplitSuggestion(
                            source_slide_id="S-007",
                            reason="Over budget",
                            suggested_split_point=3,
                            estimated_slide_a_chars=600,
                            estimated_slide_b_chars=900,
                        ),
                        passes=False,
                    ),
                    SlideDensityScore(
                        slide_id="S-014",
                        layout_type=LayoutType.CONTENT_1COL,
                        density_budget=DensityBudget.STANDARD,
                        bullet_count=11,
                        total_chars=1400,
                        max_bullet_chars=180,
                        budget_utilization_pct=140.0,
                        violations=[DensityViolation(
                            field="bullet_count",
                            actual=11,
                            limit=6,
                            severity=DensityViolationSeverity.BLOCKER,
                            message="11 bullets exceed limit of 6",
                        )],
                        passes=False,
                    ),
                ],
                blocker_count=2,
                warning_count=0,
                is_within_budget=False,
            ),
        ),
    )
    summary = _gate_5_summary(state)
    assert "S-007" in summary
    assert "S-014" in summary
    assert "Density:" in summary


def test_gate_5_summary_includes_provenance():
    """Gate 5 summary shows provenance blocker IDs when present."""
    from src.models.enums import DensityViolationSeverity, EvidenceStrength
    from src.models.state import DeckForgeState
    from src.models.submission import (
        EvidenceProvenanceResult,
        ProvenanceIssue,
        SubmissionQAResult,
    )
    from src.pipeline.graph import _gate_5_summary

    state = DeckForgeState(
        submission_qa_result=SubmissionQAResult(
            evidence_provenance=EvidenceProvenanceResult(
                issues=[
                    ProvenanceIssue(
                        slide_id="S-005",
                        bundle_id="EB-003",
                        bundle_strength=EvidenceStrength.PLACEHOLDER,
                        rule="placeholder_on_proof_slide",
                        severity=DensityViolationSeverity.BLOCKER,
                        message="PLACEHOLDER bundle on proof slide",
                    ),
                    ProvenanceIssue(
                        slide_id="S-012",
                        bundle_id="EB-007",
                        bundle_strength=EvidenceStrength.PLACEHOLDER,
                        rule="placeholder_on_proof_slide",
                        severity=DensityViolationSeverity.BLOCKER,
                        message="PLACEHOLDER bundle on proof slide",
                    ),
                ],
                blocker_count=2,
                warning_count=0,
            ),
        ),
    )
    summary = _gate_5_summary(state)
    assert "Provenance:" in summary
    assert "S-005" in summary
    assert "S-012" in summary
    assert "2 blockers" in summary


def test_gate_5_summary_density_ids_sorted():
    """Density IDs appear in slide order (deterministic)."""
    from src.models.enums import DensityBudget, DensityViolationSeverity, LayoutType
    from src.models.state import DeckForgeState
    from src.models.submission import (
        DensityResult,
        DensityViolation,
        SlideDensityScore,
        SubmissionQAResult,
    )
    from src.pipeline.graph import _gate_5_summary

    # Feed slides in order: S-003, S-007, S-014
    scores = []
    for sid in ["S-003", "S-007", "S-014"]:
        scores.append(SlideDensityScore(
            slide_id=sid,
            layout_type=LayoutType.CONTENT_1COL,
            density_budget=DensityBudget.STANDARD,
            bullet_count=10,
            total_chars=1500,
            max_bullet_chars=200,
            budget_utilization_pct=150.0,
            violations=[DensityViolation(
                field="bullet_count",
                actual=10,
                limit=6,
                severity=DensityViolationSeverity.BLOCKER,
                message="Over",
            )],
            passes=False,
        ))

    state = DeckForgeState(
        submission_qa_result=SubmissionQAResult(
            density_result=DensityResult(
                slide_scores=scores,
                blocker_count=3,
                is_within_budget=False,
            ),
        ),
    )
    summary = _gate_5_summary(state)
    # Verify they appear in order
    pos_003 = summary.index("S-003")
    pos_007 = summary.index("S-007")
    pos_014 = summary.index("S-014")
    assert pos_003 < pos_007 < pos_014
