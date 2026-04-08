"""Tests for Engine 1 evidence discipline and generic behavior.

Verifies:
1. Assertion classification schema validates correctly
2. Absolute language sanitizer catches and softens unsupported absolutes
3. Benchmark governance enforces analogue framing, not proof framing
4. Inference rendering prevents inference-as-fact in evaluator logic
5. Requirement density detector classifies RFP density correctly
6. Coherence validator catches cross-section inconsistencies
7. Evaluation hypotheses always labeled as INFERENCE when weights absent
8. Classification enforcement fixes mislabeled claims
9. Compliance rows carry through from Section 1
10. Full pipeline integration: density → classification → coherence
"""

import pytest

from src.models.source_book import (
    AssertionLabel,
    ClassifiedClaim,
    CoherenceResult,
    ComplianceRow,
    DeliveryControlRow,
    EvaluationHypothesis,
    EvidenceLedger,
    EvidenceLedgerEntry,
    ExternalEvidenceSection,
    ProposedSolution,
    RFPInterpretation,
    SlideBlueprintEntry,
    SourceBook,
    WhyStrategicGears,
    CapabilityMapping,
)


# ──────────────────────────────────────────────────────────────
# 1. Assertion classification schema
# ──────────────────────────────────────────────────────────────


class TestAssertionClassificationSchema:
    """Verify assertion classification models validate correctly."""

    def test_assertion_label_values(self):
        assert AssertionLabel.DIRECT_RFP_FACT == "DIRECT_RFP_FACT"
        assert AssertionLabel.INFERENCE == "INFERENCE"
        assert AssertionLabel.EXTERNAL_BENCHMARK == "EXTERNAL_BENCHMARK"
        assert AssertionLabel.INTERNAL_PROOF_PLACEHOLDER == "INTERNAL_PROOF_PLACEHOLDER"

    def test_classified_claim_defaults(self):
        claim = ClassifiedClaim()
        assert claim.label == AssertionLabel.INFERENCE
        assert claim.confidence == "medium"
        assert claim.claim_text == ""
        assert claim.basis == ""

    def test_classified_claim_direct_rfp_fact(self):
        claim = ClassifiedClaim(
            claim_text="The RFP requires ISO 27001 certification",
            label=AssertionLabel.DIRECT_RFP_FACT,
            basis="RFP Section 4.2.1",
            confidence="high",
        )
        assert claim.label == AssertionLabel.DIRECT_RFP_FACT
        assert claim.confidence == "high"

    def test_compliance_row_defaults(self):
        row = ComplianceRow()
        assert row.label == AssertionLabel.DIRECT_RFP_FACT
        assert row.requirement_id == ""

    def test_delivery_control_row(self):
        row = DeliveryControlRow(
            control_area="Reporting",
            rfp_requirement="Weekly status reports",
            proposed_mechanism="PMO dashboard",
            verification_method="Client sign-off",
        )
        assert row.label == AssertionLabel.DIRECT_RFP_FACT

    def test_evaluation_hypothesis_inference_default(self):
        hyp = EvaluationHypothesis(
            criterion="Technical approach",
            basis="Common for government RFPs",
            weight_estimate="~30%",
        )
        assert hyp.label == AssertionLabel.INFERENCE
        assert hyp.confidence == "medium"

    def test_coherence_result_defaults(self):
        result = CoherenceResult()
        assert result.governance_naming_consistent is True
        assert result.evidence_posture_consistent is True
        assert result.compliance_carried_through is True
        assert result.absolutes_found == []
        assert result.absolutes_softened == 0

    def test_rfp_interpretation_structured_fields(self):
        rfp = RFPInterpretation(
            objective_and_scope="Test scope",
            explicit_requirements=[
                ClassifiedClaim(
                    claim_text="Must have ISO 27001",
                    label=AssertionLabel.DIRECT_RFP_FACT,
                    basis="Section 4.2",
                    confidence="high",
                ),
            ],
            inferred_requirements=[
                ClassifiedClaim(
                    claim_text="Evaluators likely favor Saudization",
                    label=AssertionLabel.INFERENCE,
                    basis="Government RFP pattern",
                    confidence="medium",
                ),
            ],
            assumptions=["Evaluation committee includes technical evaluators"],
            ambiguities=["Cloud infrastructure scope unclear"],
            compliance_rows=[
                ComplianceRow(
                    requirement_id="COMP-001",
                    requirement_text="ISO 27001",
                    sg_response="SG holds ISO 27001:2022",
                    evidence_ref="CLM-0015",
                ),
            ],
            evaluation_hypotheses=[
                EvaluationHypothesis(
                    criterion="Technical approach",
                    basis="Common pattern",
                    confidence="medium",
                    weight_estimate="~30%",
                ),
            ],
        )
        assert len(rfp.explicit_requirements) == 1
        assert len(rfp.inferred_requirements) == 1
        assert rfp.explicit_requirements[0].label == AssertionLabel.DIRECT_RFP_FACT
        assert rfp.inferred_requirements[0].label == AssertionLabel.INFERENCE
        assert len(rfp.compliance_rows) == 1
        assert len(rfp.evaluation_hypotheses) == 1

    def test_source_book_has_density_and_coherence(self):
        sb = SourceBook()
        assert sb.requirement_density == "medium"
        assert sb.coherence is not None
        assert sb.coherence.issues == []

    def test_serialization_roundtrip_with_new_fields(self):
        sb = SourceBook(
            rfp_interpretation=RFPInterpretation(
                explicit_requirements=[
                    ClassifiedClaim(
                        claim_text="Must deliver within 18 months",
                        label=AssertionLabel.DIRECT_RFP_FACT,
                    ),
                ],
                evaluation_hypotheses=[
                    EvaluationHypothesis(
                        criterion="Team quality",
                        label=AssertionLabel.INFERENCE,
                        weight_estimate="~25%",
                    ),
                ],
            ),
            requirement_density="high",
        )
        dumped = sb.model_dump(mode="json")
        restored = SourceBook.model_validate(dumped)
        assert restored.requirement_density == "high"
        assert len(restored.rfp_interpretation.explicit_requirements) == 1
        assert restored.rfp_interpretation.explicit_requirements[0].label == AssertionLabel.DIRECT_RFP_FACT
        assert len(restored.rfp_interpretation.evaluation_hypotheses) == 1


# ──────────────────────────────────────────────────────────────
# 2. Absolute language sanitizer
# ──────────────────────────────────────────────────────────────


class TestAbsoluteSanitizer:
    """Verify absolute language is softened without evidence grounding."""

    def test_english_absolutes_softened(self):
        from src.agents.source_book.assertion_classifier import soften_absolutes

        text = "SG guarantees delivery within 18 months with zero risk."
        result, count = soften_absolutes(text)
        assert "guarantees" not in result.lower()
        assert "zero risk" not in result.lower()
        assert count >= 2

    def test_arabic_absolutes_softened(self):
        from src.agents.source_book.assertion_classifier import soften_absolutes

        text = "نضمن تحقيق الأهداف بدون أي مخاطر"
        result, count = soften_absolutes(text)
        assert "نضمن تحقيق" not in result
        assert count >= 1

    def test_safe_text_unchanged(self):
        from src.agents.source_book.assertion_classifier import soften_absolutes

        text = "SG proposes a structured approach to delivery."
        result, count = soften_absolutes(text)
        assert result == text
        assert count == 0

    def test_multiple_absolutes_in_one_sentence(self):
        from src.agents.source_book.assertion_classifier import soften_absolutes

        text = "SG absolutely guarantees full compliance without fail."
        result, count = soften_absolutes(text)
        assert "absolutely" not in result.lower()
        assert "guarantees" not in result.lower()
        assert count >= 2


# ──────────────────────────────────────────────────────────────
# 3. Benchmark governance
# ──────────────────────────────────────────────────────────────


class TestBenchmarkGovernance:
    """Verify benchmarks are framed as analogues, not proof of SG."""

    def test_proof_framing_fixed(self):
        from src.agents.source_book.assertion_classifier import apply_benchmark_governance

        text = "EXT-001 proves that SG can deliver digital transformation."
        result, count = apply_benchmark_governance(text)
        assert "proves that SG" not in result
        assert count >= 1

    def test_analogue_framing_preserved(self):
        from src.agents.source_book.assertion_classifier import apply_benchmark_governance

        text = "International best practice [EXT-001] supports this approach."
        result, count = apply_benchmark_governance(text)
        assert result == text
        assert count == 0

    def test_validates_sg_capability_fixed(self):
        from src.agents.source_book.assertion_classifier import apply_benchmark_governance

        text = "This benchmark validates SG experience in the sector."
        result, count = apply_benchmark_governance(text)
        assert "validates SG experience" not in result
        assert count >= 1


# ──────────────────────────────────────────────────────────────
# 4. Inference rendering
# ──────────────────────────────────────────────────────────────


class TestInferenceRendering:
    """Verify inference is not presented as established fact."""

    def test_evaluators_will_softened(self):
        from src.agents.source_book.assertion_classifier import _enforce_inference_rendering

        text = "The evaluators will prioritize technical capability."
        result, count = _enforce_inference_rendering(text)
        assert "likely" in result.lower()
        assert count >= 1

    def test_scoring_will_favor_softened(self):
        from src.agents.source_book.assertion_classifier import _enforce_inference_rendering

        text = "The scoring will favor firms with local presence."
        result, count = _enforce_inference_rendering(text)
        assert "likely" in result.lower()
        assert count >= 1

    def test_rfp_fact_not_softened(self):
        from src.agents.source_book.assertion_classifier import _enforce_inference_rendering

        text = "The RFP states a 70/30 technical/financial split."
        result, count = _enforce_inference_rendering(text)
        assert result == text
        assert count == 0


# ──────────────────────────────────────────────────────────────
# 5. Requirement density detection
# ──────────────────────────────────────────────────────────────


class TestRequirementDensityDetector:
    """Verify density detection classifies RFPs correctly."""

    def test_empty_state_is_low(self):
        from src.agents.source_book.requirement_detector import detect_requirement_density
        from src.models.state import DeckForgeState

        state = DeckForgeState()
        result = detect_requirement_density(state)
        assert result.density == "low"
        assert result.should_generate_compliance_matrix is False
        assert result.should_generate_delivery_matrix is False

    def test_high_density_detection(self):
        from src.agents.source_book.requirement_detector import _count_matches, _COMPILED_PRESCRIPTIVE

        text = (
            "The contractor must comply with ISO 27001. "
            "All deliverables shall be submitted within 30 days. "
            "Mandatory SLA of 99.9% uptime required. "
            "The contractor must provide at least 5 certified consultants. "
            "KPI reporting is mandatory on a monthly basis. "
            "Minimum 10 years of experience required. "
            "Performance metric tracking shall be implemented. "
            "The contractor shall conform to all regulatory requirements. "
            "Penalty clauses apply for late delivery. "
            "Liquidated damages of 1% per week for delays. "
            "Service level agreements must be signed. "
            "Deadline for Phase 1 is Q2 2026. "
            "At least 3 local team members required. "
            "No fewer than 20 deliverables expected. "
            "The firm must submit within the deadline. "
        )
        count = _count_matches(text, _COMPILED_PRESCRIPTIVE)
        assert count >= 10

    def test_density_analysis_signals(self):
        from src.agents.source_book.requirement_detector import detect_requirement_density
        from src.models.state import DeckForgeState

        state = DeckForgeState()
        result = detect_requirement_density(state)
        assert isinstance(result.signals, list)
        assert len(result.signals) >= 1


# ──────────────────────────────────────────────────────────────
# 6. Coherence validator
# ──────────────────────────────────────────────────────────────


class TestCoherenceValidator:
    """Verify cross-section coherence detection."""

    def test_empty_source_book_passes(self):
        from src.agents.source_book.coherence_validator import validate_coherence

        sb = SourceBook()
        result = validate_coherence(sb)
        assert result.governance_naming_consistent is True
        assert result.evidence_posture_consistent is True

    def test_evidence_posture_gap_detected(self):
        from src.agents.source_book.coherence_validator import validate_coherence

        sb = SourceBook(
            slide_blueprints=[
                SlideBlueprintEntry(
                    slide_number=5,
                    title="Why SG",
                    proof_points=["CLM-GAP"],
                ),
            ],
            evidence_ledger=EvidenceLedger(
                entries=[
                    EvidenceLedgerEntry(
                        claim_id="CLM-GAP",
                        claim_text="Some claim",
                        verifiability_status="gap",
                    ),
                ],
            ),
        )
        result = validate_coherence(sb)
        assert result.evidence_posture_consistent is False
        assert any("CLM-GAP" in issue for issue in result.issues)

    def test_capability_strength_vs_gap_evidence(self):
        from src.agents.source_book.coherence_validator import validate_coherence

        sb = SourceBook(
            why_strategic_gears=WhyStrategicGears(
                capability_mapping=[
                    CapabilityMapping(
                        rfp_requirement="SAP migration",
                        sg_capability="10+ deployments",
                        evidence_ids=["CLM-WEAK"],
                        strength="strong",
                    ),
                ],
            ),
            evidence_ledger=EvidenceLedger(
                entries=[
                    EvidenceLedgerEntry(
                        claim_id="CLM-WEAK",
                        claim_text="SAP experience",
                        verifiability_status="gap",
                    ),
                ],
            ),
        )
        result = validate_coherence(sb)
        assert any("strong" in issue and "gap" in issue for issue in result.issues)

    def test_absolutes_detected(self):
        from src.agents.source_book.coherence_validator import validate_coherence

        sb = SourceBook(
            proposed_solution=ProposedSolution(
                methodology_overview="SG guarantees 100% compliance with zero risk.",
            ),
        )
        result = validate_coherence(sb)
        assert len(result.absolutes_found) >= 1


# ──────────────────────────────────────────────────────────────
# 7. Evaluation hypotheses validation
# ──────────────────────────────────────────────────────────────


class TestEvaluationHypotheses:
    """Verify evaluation hypotheses are always INFERENCE when weights absent."""

    def test_mislabeled_hypothesis_fixed(self):
        from src.agents.source_book.assertion_classifier import validate_evaluation_hypotheses

        hypotheses = [
            EvaluationHypothesis(
                criterion="Technical approach",
                label=AssertionLabel.DIRECT_RFP_FACT,  # Wrong — should be INFERENCE
                confidence="medium",
                weight_estimate="~30%",
            ),
        ]
        result = validate_evaluation_hypotheses(hypotheses)
        assert result[0].label == AssertionLabel.INFERENCE

    def test_hypothesis_gets_basis_if_missing(self):
        from src.agents.source_book.assertion_classifier import validate_evaluation_hypotheses

        hypotheses = [
            EvaluationHypothesis(
                criterion="Team quality",
                basis="",  # Empty
            ),
        ]
        result = validate_evaluation_hypotheses(hypotheses)
        assert result[0].basis != ""


# ──────────────────────────────────────────────────────────────
# 8. Classification enforcement integration
# ──────────────────────────────────────────────────────────────


class TestClassificationEnforcement:
    """Verify full classification enforcement pass on source book."""

    def test_enforce_on_empty_source_book(self):
        from src.agents.source_book.assertion_classifier import enforce_classification

        sb = SourceBook()
        report = enforce_classification(sb)
        assert report.total_claims_checked == 0
        assert report.misclassified_fixed == 0
        assert report.absolutes_softened == 0

    def test_enforce_fixes_mislabeled_claim(self):
        from src.agents.source_book.assertion_classifier import enforce_classification

        sb = SourceBook(
            rfp_interpretation=RFPInterpretation(
                explicit_requirements=[
                    ClassifiedClaim(
                        claim_text="EXT-001 supports phased approach",
                        label=AssertionLabel.DIRECT_RFP_FACT,  # Should be EXTERNAL_BENCHMARK
                        basis="EXT-001 McKinsey report",
                    ),
                ],
            ),
        )
        report = enforce_classification(sb)
        assert report.misclassified_fixed >= 1
        assert sb.rfp_interpretation.explicit_requirements[0].label == AssertionLabel.EXTERNAL_BENCHMARK

    def test_enforce_softens_absolutes_in_prose(self):
        from src.agents.source_book.assertion_classifier import enforce_classification

        sb = SourceBook(
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="SG guarantees delivery with zero risk.",
            ),
        )
        report = enforce_classification(sb)
        assert report.absolutes_softened >= 1
        assert "guarantees" not in sb.rfp_interpretation.objective_and_scope.lower()

    def test_enforce_benchmark_governance(self):
        from src.agents.source_book.assertion_classifier import enforce_classification

        sb = SourceBook(
            external_evidence=ExternalEvidenceSection(
                coverage_assessment="EXT-001 proves that SG can deliver transformation.",
            ),
        )
        report = enforce_classification(sb)
        assert report.benchmark_governance_fixes >= 1
        assert "proves that SG" not in sb.external_evidence.coverage_assessment

    def test_enforce_inference_rendering(self):
        from src.agents.source_book.assertion_classifier import enforce_classification

        sb = SourceBook(
            rfp_interpretation=RFPInterpretation(
                probable_scoring_logic="The evaluators will prioritize local content.",
            ),
        )
        report = enforce_classification(sb)
        assert report.inference_rendering_fixes >= 1
        assert "likely" in sb.rfp_interpretation.probable_scoring_logic.lower()


# ──────────────────────────────────────────────────────────────
# 9. Compliance carry-through
# ──────────────────────────────────────────────────────────────


class TestComplianceCarryThrough:
    """Verify Section 1 compliance requirements appear in Section 5/6."""

    def test_unaddressed_compliance_flagged(self):
        from src.agents.source_book.coherence_validator import validate_coherence

        sb = SourceBook(
            rfp_interpretation=RFPInterpretation(
                key_compliance_requirements=[
                    "COMP-001 | ISO 27001 certification required",
                    "COMP-002 | Minimum 5 certified TOGAF architects",
                ],
            ),
            proposed_solution=ProposedSolution(
                methodology_overview="Agile methodology with governance.",
            ),
        )
        result = validate_coherence(sb)
        assert result.compliance_carried_through is False
        assert any("compliance" in issue.lower() for issue in result.issues)

    def test_addressed_compliance_passes(self):
        from src.agents.source_book.coherence_validator import validate_coherence

        sb = SourceBook(
            rfp_interpretation=RFPInterpretation(
                key_compliance_requirements=[
                    "COMP-001 | ISO 27001 certification required",
                ],
            ),
            proposed_solution=ProposedSolution(
                methodology_overview="ISO 27001 compliant methodology with certification verification.",
            ),
        )
        result = validate_coherence(sb)
        assert result.compliance_carried_through is True


# ──────────────────────────────────────────────────────────────
# 10. Full pipeline integration
# ──────────────────────────────────────────────────────────────


class TestFullPipelineIntegration:
    """Verify density → classification → coherence pipeline works together."""

    def test_full_pipeline_on_source_book(self):
        from src.agents.source_book.assertion_classifier import enforce_classification
        from src.agents.source_book.coherence_validator import validate_coherence

        sb = SourceBook(
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="The client absolutely guarantees budget availability.",
                probable_scoring_logic="The evaluators will prioritize technical depth.",
                explicit_requirements=[
                    ClassifiedClaim(
                        claim_text="RFP requires ISO 27001",
                        label=AssertionLabel.DIRECT_RFP_FACT,
                        basis="Section 4.2",
                        confidence="high",
                    ),
                ],
                inferred_requirements=[
                    ClassifiedClaim(
                        claim_text="Evaluators likely value Saudization",
                        label=AssertionLabel.INFERENCE,
                        basis="Government RFP pattern",
                        confidence="medium",
                    ),
                ],
                evaluation_hypotheses=[
                    EvaluationHypothesis(
                        criterion="Technical approach",
                        label=AssertionLabel.DIRECT_RFP_FACT,  # Will be fixed
                        basis="Common pattern",
                        weight_estimate="~30%",
                    ),
                ],
                key_compliance_requirements=["COMP-001 | ISO 27001 required"],
            ),
            external_evidence=ExternalEvidenceSection(
                coverage_assessment="EXT-001 confirms SG capability in transformation.",
            ),
            proposed_solution=ProposedSolution(
                methodology_overview="ISO 27001 aligned methodology.",
            ),
            requirement_density="medium",
        )

        # Step 1: Classification enforcement
        report = enforce_classification(sb)
        assert report.absolutes_softened >= 1
        assert report.inference_rendering_fixes >= 1

        # Step 2: Coherence validation
        coherence = validate_coherence(sb)
        assert isinstance(coherence, CoherenceResult)

        # Verify pipeline results are stored on source book
        assert sb.coherence is not None
        assert sb.coherence.absolutes_softened >= 1

    def test_generic_across_rfp_types(self):
        """Verify system works for different RFP types without RFP-specific code."""
        from src.agents.source_book.assertion_classifier import enforce_classification
        from src.agents.source_book.coherence_validator import validate_coherence

        rfp_types = [
            ("IT Digital Transformation", "en", "high"),
            ("Management Consulting Advisory", "en", "medium"),
            ("استشارات التحول الرقمي", "ar", "high"),
            ("Open-ended Strategy Study", "en", "low"),
        ]

        for rfp_name, lang, density in rfp_types:
            sb = SourceBook(
                rfp_name=rfp_name,
                language=lang,
                requirement_density=density,
                rfp_interpretation=RFPInterpretation(
                    objective_and_scope=f"Scope for {rfp_name}",
                ),
            )
            report = enforce_classification(sb)
            coherence = validate_coherence(sb)
            # Should work for ALL types without errors
            assert isinstance(report.total_claims_checked, int)
            assert isinstance(coherence, CoherenceResult)
