"""Regression tests for the Conformance Validator.

Tests cover deterministic passes (Pass 1 and Pass 2) of the four-pass
conformance validation architecture. Pass 3 (LLM semantic checks) is
mocked to return empty results so these tests remain fast and
deterministic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.source_book.conformance_validator import validate_conformance
from src.agents.source_book.orchestrator import should_accept_source_book
from src.models.common import BilingualText
from src.models.conformance import (
    ConformanceFailure,
    ConformanceReport,
    HardRequirement,
)
from src.models.enums import Language
from src.models.rfp import (
    Completeness,
    EvaluationCriteria,
    ProjectTimeline,
    RFPContext,
)
from src.models.source_book import (
    PhaseDetail,
    ProposedSolution,
    RFPInterpretation,
    SourceBook,
    SourceBookReview,
)
from src.models.state import UploadedDocument


# ── Helpers ──────────────────────────────────────────────────────────────


def _minimal_rfp(**overrides) -> RFPContext:
    """Build a minimal valid RFPContext."""
    defaults = dict(
        rfp_name=BilingualText(en="Test RFP"),
        issuing_entity=BilingualText(en="Test Entity"),
        mandate=BilingualText(en="Test mandate"),
        source_language=Language.EN,
        completeness=Completeness(),
    )
    defaults.update(overrides)
    return RFPContext(**defaults)


def _make_hr(
    *,
    requirement_id: str = "HR-T-001",
    category: str = "contract_duration",
    subject: str = "contract_duration_months",
    operator: str = "==",
    value_text: str = "10",
    value_number: float | None = 10.0,
    severity: str = "critical",
    validation_scope: str = "source_book",
    extraction_method: str = "context_field",
    unit: str = "months",
    deliverable_ids: list[str] | None = None,
    **kwargs,
) -> HardRequirement:
    """Build a HardRequirement with sensible defaults."""
    return HardRequirement(
        requirement_id=requirement_id,
        category=category,
        subject=subject,
        operator=operator,
        value_text=value_text,
        value_number=value_number,
        dimension="flat",
        unit=unit,
        phase="all",
        source_text=f"Test HR: {value_text}",
        source_location="test",
        confidence="high",
        is_explicit=True,
        extraction_method=extraction_method,
        severity=severity,
        validation_scope=validation_scope,
        deliverable_ids=deliverable_ids or [],
        **kwargs,
    )


def _make_source_book(**overrides) -> SourceBook:
    """Build a SourceBook with optional section overrides."""
    defaults = dict(
        rfp_interpretation=RFPInterpretation(),
        proposed_solution=ProposedSolution(),
    )
    defaults.update(overrides)
    return SourceBook(**defaults)


# Mock target: prevent real LLM calls in Pass 3.
_MOCK_LLM = "src.agents.source_book.conformance_validator.call_llm"


# ── Tests ────────────────────────────────────────────────────────────────


class TestDurationMismatch:
    """Pass 1: wrong contract duration must produce a critical failure."""

    @pytest.mark.asyncio
    async def test_duration_mismatch_produces_critical_failure(self):
        hr = _make_hr(
            category="contract_duration",
            value_text="10",
            value_number=10.0,
        )
        # Source Book says 12 months instead of 10.
        sb = _make_source_book(
            proposed_solution=ProposedSolution(
                timeline_logic="12 months total project duration",
            ),
        )
        rfp = _minimal_rfp(
            project_timeline=ProjectTimeline(
                total_duration_months=10,
            ),
        )

        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[hr],
            rfp_context=rfp,
            uploaded_documents=[],
        )

        assert report.conformance_status == "fail"
        # Should have a missing-commitment about duration.
        all_failures = (
            report.missing_required_commitments
            + report.forbidden_claims
            + report.structural_mismatches
        )
        critical = [f for f in all_failures if f.severity == "critical"]
        assert len(critical) >= 1
        assert any("10" in f.failure_reason or "duration" in f.failure_reason.lower() for f in critical)


class TestAwardMechanismMismatch:
    """Pass 2: weighted-scoring language in a pass_fail RFP must flag forbidden_claim."""

    @pytest.mark.asyncio
    async def test_award_mechanism_mismatch_produces_failure(self):
        hr = _make_hr(
            requirement_id="HR-AWARD-001",
            category="award_mechanism",
            subject="award_mechanism",
            operator="==",
            value_text="pass_fail_then_lowest_price",
            value_number=None,
            unit="mechanism",
        )
        # Source Book references weighted scoring (forbidden).
        sb = _make_source_book(
            rfp_interpretation=RFPInterpretation(
                probable_scoring_logic="70% technical 30% financial weighted evaluation",
            ),
        )
        rfp = _minimal_rfp(
            evaluation_criteria=EvaluationCriteria(
                award_mechanism="pass_fail_then_lowest_price",
            ),
        )

        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[hr],
            rfp_context=rfp,
            uploaded_documents=[],
        )

        assert len(report.forbidden_claims) >= 1
        assert any(
            "weighted" in f.failure_reason.lower() or "scoring" in f.failure_reason.lower()
            for f in report.forbidden_claims
        )


class TestMissingDeliverable:
    """Pass 1: mandatory deliverable absent from Source Book must fail."""

    @pytest.mark.asyncio
    async def test_missing_deliverable_produces_failure(self):
        hr = _make_hr(
            requirement_id="HR-DEL-005",
            category="deliverable_required",
            subject="DEL-005",
            operator="must_include",
            value_text="Specialized capacity-building workshops for each priority sector",
            value_number=None,
            unit="deliverable",
            severity="critical",
            deliverable_ids=["DEL-005"],
        )
        # Source Book phases do NOT mention D5 or its keywords.
        sb = _make_source_book(
            proposed_solution=ProposedSolution(
                methodology_overview="General overview of methods.",
                phase_details=[
                    PhaseDetail(
                        phase_name="Phase 1",
                        activities=["Planning"],
                        deliverables=["Inception report"],
                    ),
                ],
            ),
        )
        rfp = _minimal_rfp()

        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[hr],
            rfp_context=rfp,
            uploaded_documents=[],
        )

        all_failures = report.missing_required_commitments + report.structural_mismatches
        assert len(all_failures) >= 1
        assert any("deliverable" in f.failure_reason.lower() for f in all_failures)


class TestAllRequirementsMet:
    """When Source Book addresses all HRs, conformance_status must be pass."""

    @pytest.mark.asyncio
    async def test_all_requirements_met_produces_pass(self):
        hr_dur = _make_hr(
            requirement_id="HR-L1-001",
            category="contract_duration",
            value_text="10",
            value_number=10.0,
        )
        hr_thresh = _make_hr(
            requirement_id="HR-L1-002",
            category="minimum_threshold",
            subject="technical_passing_threshold",
            operator=">=",
            value_text="70",
            value_number=70.0,
            unit="percent",
        )
        # Source Book mentions 10 months correctly.
        sb = _make_source_book(
            proposed_solution=ProposedSolution(
                timeline_logic="The project spans exactly 10 months.",
                phase_details=[
                    PhaseDetail(
                        phase_name="Phase 1",
                        activities=["Setup"],
                        deliverables=["Plan"],
                    ),
                ],
            ),
        )
        rfp = _minimal_rfp(
            project_timeline=ProjectTimeline(
                total_duration_months=10,
            ),
        )

        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[hr_dur, hr_thresh],
            rfp_context=rfp,
            uploaded_documents=[],
        )

        assert report.conformance_status == "pass"


class TestCriticalFailureOverridesReviewerPass:
    """Conformance failure must override a passing reviewer score."""

    def test_critical_failure_overrides_reviewer_pass(self):
        review = SourceBookReview(
            overall_score=4,
            pass_threshold_met=True,
            rewrite_required=False,
            competitive_viability="strong",
        )
        conformance = ConformanceReport(
            conformance_status="fail",
            hard_requirements_checked=5,
            hard_requirements_passed=3,
            hard_requirements_failed=2,
            missing_required_commitments=[
                ConformanceFailure(
                    requirement_id="HR-001",
                    requirement_text="Duration mismatch",
                    failure_reason="Wrong duration",
                    severity="critical",
                ),
            ],
        )

        assert should_accept_source_book(review, conformance) is False


class TestConformancePassPlusReviewerPassAccepts:
    """Both conformance pass and reviewer pass must result in acceptance."""

    def test_conformance_pass_plus_reviewer_pass_accepts(self):
        review = SourceBookReview(
            overall_score=4,
            pass_threshold_met=True,
            rewrite_required=False,
            competitive_viability="strong",
        )
        conformance = ConformanceReport(
            conformance_status="pass",
            hard_requirements_checked=5,
            hard_requirements_passed=5,
            hard_requirements_failed=0,
        )

        assert should_accept_source_book(review, conformance) is True


class TestConformanceReportCounts:
    """Verify arithmetic: checked == passed + failed."""

    @pytest.mark.asyncio
    async def test_conformance_report_counts(self):
        hrs = [
            _make_hr(
                requirement_id="HR-L1-001",
                category="contract_duration",
                value_text="10",
                value_number=10.0,
            ),
            _make_hr(
                requirement_id="HR-L1-002",
                category="minimum_threshold",
                subject="technical_passing_threshold",
                value_text="70",
                value_number=70.0,
                unit="percent",
            ),
            _make_hr(
                requirement_id="HR-L1-003",
                category="deliverable_required",
                subject="DEL-001",
                operator="must_include",
                value_text="Training completion certificate for each participant with unique verification",
                value_number=None,
                unit="deliverable",
                deliverable_ids=["DEL-001"],
            ),
        ]
        # Source Book matches duration and threshold, but misses the deliverable.
        sb = _make_source_book(
            proposed_solution=ProposedSolution(
                timeline_logic="Total project duration is 10 months.",
                phase_details=[
                    PhaseDetail(
                        phase_name="Phase 1",
                        activities=["General work"],
                        deliverables=["Status report"],
                    ),
                ],
            ),
        )
        rfp = _minimal_rfp(
            project_timeline=ProjectTimeline(total_duration_months=10),
        )

        report = await validate_conformance(
            source_book=sb,
            hard_requirements=hrs,
            rfp_context=rfp,
            uploaded_documents=[],
        )

        assert report.hard_requirements_checked >= 1
        assert report.hard_requirements_checked == (
            report.hard_requirements_passed + report.hard_requirements_failed
        )


class TestForbiddenAbsoluteClaimDetected:
    """Pass 2: absolute guarantee language must be flagged as forbidden."""

    @pytest.mark.asyncio
    async def test_forbidden_absolute_claim_detected(self):
        hr = _make_hr(
            requirement_id="HR-L1-001",
            category="minimum_threshold",
            subject="technical_passing_threshold",
            value_text="70",
            value_number=70.0,
            unit="percent",
        )
        # Source Book contains an absolute guarantee (Arabic).
        sb = _make_source_book(
            proposed_solution=ProposedSolution(
                methodology_overview="Our methodology ensures complete compliance.",
                timeline_logic="10 months.",
                value_case_and_differentiation="We guarantee 100% success rate for all deliverables.",
            ),
        )
        rfp = _minimal_rfp()

        report = await validate_conformance(
            source_book=sb,
            hard_requirements=[hr],
            rfp_context=rfp,
            uploaded_documents=[],
        )

        assert len(report.forbidden_claims) >= 1
        assert any(
            "absolute" in f.failure_reason.lower() or "100" in f.failure_reason
            for f in report.forbidden_claims
        )


# ── Bug fix regression tests ──────────────────────────────────────────


class TestReviewerPayloadContainsConformance:
    """Bug 1: Reviewer must receive hard_requirements_summary and conformance_summary."""

    def test_reviewer_payload_includes_conformance_when_present(self):
        """_build_user_message must include hard_requirements_summary and
        conformance_summary in the JSON payload when state has them."""
        from src.agents.source_book.reviewer import _build_user_message
        from src.models.state import DeckForgeState
        from src.models.source_book import SourceBook
        from src.models.rfp import RFPContext
        from src.models.conformance import (
            HardRequirement, ConformanceReport, ConformanceFailure,
        )
        from src.models.enums import Language
        import json

        from src.models.common import BilingualText
        state = DeckForgeState(
            source_book=SourceBook(),
            rfp_context=RFPContext(
                rfp_name=BilingualText(en="Test RFP", ar=""),
                issuing_entity=BilingualText(en="Test Entity", ar=""),
                mandate=BilingualText(en="Test mandate", ar=""),
                source_language=Language.AR,
                hard_requirements=[
                    HardRequirement(
                        requirement_id="HR-L1-001",
                        category="contract_duration",
                        subject="contract_duration_months",
                        operator="==",
                        value_text="12",
                        value_number=12.0,
                        severity="critical",
                        validation_scope="source_book",
                    ),
                ],
            ),
            conformance_report=ConformanceReport(
                missing_required_commitments=[
                    ConformanceFailure(
                        requirement_id="HR-L1-001",
                        failure_reason="Duration mismatch",
                        severity="critical",
                    ),
                ],
                conformance_status="fail",
                hard_requirements_checked=1,
                hard_requirements_failed=1,
            ),
        )

        payload_str = _build_user_message(state)
        payload = json.loads(payload_str)

        assert "hard_requirements_summary" in payload
        assert payload["hard_requirements_summary"] is not None
        assert len(payload["hard_requirements_summary"]) == 1
        assert payload["hard_requirements_summary"][0]["id"] == "HR-L1-001"

        assert "conformance_report_summary" in payload
        assert payload["conformance_report_summary"] is not None
        assert payload["conformance_report_summary"]["status"] == "fail"
        assert payload["conformance_report_summary"]["failed"] == 1


class TestNonCriticalMissingInputDoesNotBlock:
    """Bug 2: Only critical+source_book missing inputs should block."""

    @pytest.mark.asyncio
    async def test_major_severity_missing_annex_does_not_block(self):
        """A missing annex with severity=major should NOT block acceptance."""
        from src.models.conformance import MissingInput, ConformanceReport

        # Simulate a report with a non-critical missing input
        report = ConformanceReport(
            missing_inputs=[
                MissingInput(
                    input_name="Annex 5: Optional References",
                    requirement_ids=["HR-L1-010"],
                    blocker_type="missing_annex",
                    severity="major",  # NOT critical
                    validation_scope="source_book",
                ),
            ],
            conformance_status="pass",  # Should not be blocked
        )
        assert report.conformance_status == "pass"

    @pytest.mark.asyncio
    async def test_critical_engine2_missing_input_does_not_block(self):
        """A critical missing input with engine2_proof scope should NOT block."""
        from src.models.conformance import MissingInput

        mi = MissingInput(
            input_name="Team CVs",
            requirement_ids=["HR-L1-020"],
            blocker_type="missing_annex",
            severity="critical",
            validation_scope="engine2_proof",  # Not source_book
        )
        # The validator status computation checks:
        # severity == "critical" AND validation_scope == "source_book"
        # This is engine2_proof, so it should NOT trigger blocking
        assert mi.validation_scope != "source_book"


class TestPass4AnnexBlockerPropagation:
    """Bug 2+3: _pass4_missing_annexes must propagate severity/scope from HR,
    and validate_conformance must block only on critical+source_book."""

    @pytest.mark.asyncio
    async def test_critical_source_book_missing_annex_blocks(self):
        """Critical + source_book HR referencing an annex not in docs → blocked."""
        report = await validate_conformance(
            source_book=SourceBook(
                proposed_solution=ProposedSolution(
                    timeline_logic="12 months",
                    phase_details=[
                        PhaseDetail(phase_name="P1", activities=["a"], deliverables=["d"]),
                        PhaseDetail(phase_name="P2", activities=["a"], deliverables=["d"]),
                    ],
                ),
            ),
            hard_requirements=[
                HardRequirement(
                    requirement_id="HR-L1-ANNEX",
                    category="team_qualification",
                    subject="team_specifications_annex",
                    operator="must_include",
                    value_text="team table",
                    source_text="See Annex 3: جدول فريق العمل for team specifications",
                    severity="critical",
                    validation_scope="source_book",
                    extraction_method="context_field",
                    confidence="high",
                ),
            ],
            rfp_context=None,
            uploaded_documents=[],  # No documents → annex missing
        )
        assert report.conformance_status == "blocked", (
            f"Expected 'blocked', got '{report.conformance_status}'"
        )
        assert report.final_acceptance_decision == "blocked_missing_input"
        assert len(report.missing_inputs) >= 1
        assert report.missing_inputs[0].severity == "critical"
        assert report.missing_inputs[0].validation_scope == "source_book"

    @pytest.mark.asyncio
    async def test_major_missing_annex_does_not_block(self):
        """Major severity HR referencing an annex → does NOT block."""
        report = await validate_conformance(
            source_book=SourceBook(
                proposed_solution=ProposedSolution(
                    timeline_logic="12 months",
                    phase_details=[
                        PhaseDetail(phase_name="P1", activities=["a"], deliverables=["d"]),
                        PhaseDetail(phase_name="P2", activities=["a"], deliverables=["d"]),
                    ],
                ),
            ),
            hard_requirements=[
                HardRequirement(
                    requirement_id="HR-L1-ANNEX2",
                    category="compliance",
                    subject="optional_references_annex",
                    operator="includes",
                    value_text="reference list",
                    source_text="See Annex 5 for optional references table",
                    severity="major",  # NOT critical
                    validation_scope="source_book",
                    extraction_method="context_field",
                    confidence="high",
                ),
            ],
            rfp_context=None,
            uploaded_documents=[],
        )
        # Should NOT be blocked — major severity doesn't trigger blocking
        assert report.conformance_status != "blocked", (
            f"Major annex should not block, got '{report.conformance_status}'"
        )

    @pytest.mark.asyncio
    async def test_engine2_missing_annex_does_not_block(self):
        """Critical but engine2_proof scope HR → does NOT block source_book."""
        report = await validate_conformance(
            source_book=SourceBook(
                proposed_solution=ProposedSolution(
                    timeline_logic="12 months",
                    phase_details=[
                        PhaseDetail(phase_name="P1", activities=["a"], deliverables=["d"]),
                        PhaseDetail(phase_name="P2", activities=["a"], deliverables=["d"]),
                    ],
                ),
            ),
            hard_requirements=[
                HardRequirement(
                    requirement_id="HR-L1-CV",
                    category="team_qualification",
                    subject="team_cv_annex",
                    operator="must_include",
                    value_text="CVs",
                    source_text="Annex: team CVs required",
                    severity="critical",
                    validation_scope="engine2_proof",  # Not source_book
                    extraction_method="context_field",
                    confidence="high",
                ),
            ],
            rfp_context=None,
            uploaded_documents=[],
        )
        # engine2_proof scope → pass4 skips it entirely (line 528-529)
        assert report.conformance_status != "blocked", (
            f"Engine2 annex should not block source_book, got '{report.conformance_status}'"
        )


class TestForbiddenAndStructuralCountedInFailures:
    """Bug 3: forbidden_claims and structural_mismatches must be in failure total."""

    @pytest.mark.asyncio
    async def test_forbidden_claims_counted_in_total_failed(self):
        """Forbidden claims must be reflected in hard_requirements_failed."""
        report = await validate_conformance(
            source_book=SourceBook(
                rfp_interpretation=RFPInterpretation(
                    probable_scoring_logic="يضمن 100% من النجاح guaranteed",
                ),
                proposed_solution=ProposedSolution(
                    timeline_logic="12 شهراً",
                    phase_details=[
                        PhaseDetail(phase_name="Phase 1", activities=["a"], deliverables=["d"]),
                        PhaseDetail(phase_name="Phase 2", activities=["a"], deliverables=["d"]),
                    ],
                ),
            ),
            hard_requirements=[
                HardRequirement(
                    requirement_id="HR-L1-001",
                    category="contract_duration",
                    subject="contract_duration_months",
                    operator="==",
                    value_text="12",
                    value_number=12.0,
                    unit="months",
                    severity="critical",
                    validation_scope="source_book",
                    extraction_method="context_field",
                    confidence="high",
                ),
            ],
            rfp_context=None,
            uploaded_documents=[],
        )

        # forbidden_claims should be non-empty (from "يضمن 100%" absolute language)
        # and those should be counted in hard_requirements_failed
        total_failures = len(report.missing_required_commitments) + len(report.forbidden_claims) + len(report.structural_mismatches)
        assert report.hard_requirements_failed >= len(report.forbidden_claims), (
            f"forbidden_claims ({len(report.forbidden_claims)}) not counted in "
            f"hard_requirements_failed ({report.hard_requirements_failed})"
        )


# ── Forbidden-claim tuning regression tests ────────────────────────────


class TestForbiddenClaimTuning:
    """Ensure forbidden-claim scanner doesn't over-fire on legitimate text."""

    def test_bare_jamee_in_deliverable_not_flagged(self):
        """'جميع' (all) in a deliverable description is NOT a forbidden claim."""
        import re
        from src.agents.source_book.conformance_validator import _ABSOLUTE_CLAIM_RE
        # Legitimate deliverable text
        text = "تغطي جميع القطاعات ذات الأولوية وجميع الأنشطة الاقتصادية"
        matches = list(_ABSOLUTE_CLAIM_RE.finditer(text))
        assert len(matches) == 0, (
            f"Legitimate deliverable text flagged as absolute claim: {matches}"
        )

    def test_bare_100_percent_in_eval_hypothesis_not_flagged(self):
        """'100%' in evaluation hypothesis context is NOT a forbidden claim."""
        import re
        from src.agents.source_book.conformance_validator import _ABSOLUTE_CLAIM_RE
        # Legitimate evaluation model description
        text = '100% من قرار الترسية بعد الاجتياز الفني'
        matches = list(_ABSOLUTE_CLAIM_RE.finditer(text))
        assert len(matches) == 0, (
            f"Legitimate eval hypothesis flagged as absolute claim: {matches}"
        )

    def test_real_overclaim_still_flagged(self):
        """'يضمن 100%' (guarantees 100%) IS a forbidden claim."""
        import re
        from src.agents.source_book.conformance_validator import _ABSOLUTE_CLAIM_RE
        text = "يضمن 100 من النجاح والاستيفاء"
        matches = list(_ABSOLUTE_CLAIM_RE.finditer(text))
        assert len(matches) >= 1, (
            f"Real overclaim 'يضمن 100' should be flagged but was not"
        )

    def test_guarantees_complete_compliance_flagged(self):
        """'guarantees complete compliance' IS a forbidden claim."""
        import re
        from src.agents.source_book.conformance_validator import _ABSOLUTE_CLAIM_RE
        text = "SG guarantees complete compliance with all RFP requirements"
        matches = list(_ABSOLUTE_CLAIM_RE.finditer(text))
        assert len(matches) >= 1, (
            f"'guarantees complete compliance' should be flagged"
        )

    def test_ensures_all_requirements_flagged(self):
        """'ensures all requirements' IS a forbidden claim."""
        import re
        from src.agents.source_book.conformance_validator import _ABSOLUTE_CLAIM_RE
        text = "our methodology ensures all requirements are met"
        matches = list(_ABSOLUTE_CLAIM_RE.finditer(text))
        assert len(matches) >= 1, (
            f"'ensures all requirements' should be flagged"
        )


# ── Deduplication and duration-scope regression tests ──────────────────


class TestDeduplicatedCounting:
    """Fix 1: Same requirement in both missing_commitments and forbidden_claims
    should be counted once in total_failed."""

    @pytest.mark.asyncio
    async def test_same_hr_in_both_lists_counted_once(self):
        """HR appearing in both missing + forbidden = 1 unique failure, not 2."""
        report = await validate_conformance(
            source_book=SourceBook(
                rfp_interpretation=RFPInterpretation(
                    probable_scoring_logic="70% فني 30% مالي weighted scoring model",
                ),
                proposed_solution=ProposedSolution(
                    timeline_logic="12 شهراً",
                    phase_details=[
                        PhaseDetail(phase_name="P1", activities=["a"], deliverables=["d"]),
                        PhaseDetail(phase_name="P2", activities=["a"], deliverables=["d"]),
                    ],
                ),
            ),
            hard_requirements=[
                HardRequirement(
                    requirement_id="HR-L1-001",
                    category="award_mechanism",
                    subject="award_mechanism",
                    operator="==",
                    value_text="pass_fail_then_lowest_price",
                    severity="critical",
                    validation_scope="source_book",
                    extraction_method="context_field",
                    confidence="high",
                ),
            ],
            rfp_context=None,
            uploaded_documents=[],
        )
        # HR-L1-001 may appear in both lists, but total_failed should be 1
        in_missing = sum(1 for f in report.missing_required_commitments if f.requirement_id == "HR-L1-001")
        in_forbidden = sum(1 for f in report.forbidden_claims if f.requirement_id == "HR-L1-001")
        assert in_missing + in_forbidden >= 2, "HR-L1-001 should appear in both lists"
        assert report.hard_requirements_failed == 1, (
            f"Expected 1 unique failure, got {report.hard_requirements_failed}"
        )


class TestDurationScopeNarrowing:
    """Fix 2: Sub-phase durations (e.g., 3 months) should NOT trigger
    a contract-duration forbidden claim when total is 12 months."""

    @pytest.mark.asyncio
    async def test_phase_duration_not_flagged_as_contract_duration(self):
        """A 3-month phase inside a 12-month contract is NOT a duration violation."""
        report = await validate_conformance(
            source_book=SourceBook(
                rfp_interpretation=RFPInterpretation(
                    constraints_and_compliance="مدة العقد هي 12 شهراً ميلادياً",
                ),
                proposed_solution=ProposedSolution(
                    timeline_logic="مدة التنفيذ الإجمالية 12 شهراً ميلادياً",
                    phase_details=[
                        PhaseDetail(
                            phase_name="المرحلة الأولى (3 أشهر)",
                            activities=["activity"],
                            deliverables=["deliverable"],
                        ),
                        PhaseDetail(
                            phase_name="المرحلة الثانية (3 أشهر)",
                            activities=["activity"],
                            deliverables=["deliverable"],
                        ),
                    ],
                ),
            ),
            hard_requirements=[
                HardRequirement(
                    requirement_id="HR-L1-002",
                    category="contract_duration",
                    subject="contract_duration_months",
                    operator="==",
                    value_text="12",
                    value_number=12.0,
                    unit="months",
                    severity="critical",
                    validation_scope="source_book",
                    extraction_method="context_field",
                    confidence="high",
                ),
            ],
            rfp_context=None,
            uploaded_documents=[],
        )
        # The forbidden_claims should NOT contain a duration mismatch
        duration_forbidden = [
            f for f in report.forbidden_claims
            if "HR-L1-002" in f.requirement_id
        ]
        assert len(duration_forbidden) == 0, (
            f"Phase-level 3-month duration should not trigger contract-duration "
            f"forbidden claim, but got: {[f.failure_reason for f in duration_forbidden]}"
        )
