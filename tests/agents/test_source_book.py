"""Tests for Phase 3: Source Book Generation.

Verifies:
1. SourceBook and SourceBookReview schemas validate correctly (7 sections)
2. DeckForgeState has source_book field
3. Source Book Writer agent builds user message from real state
4. Source Book Reviewer agent builds user message from Source Book
5. Orchestrator iteration logic (converge within max passes)
6. DOCX export produces valid file with all 7 sections
7. source_book_node is wired into graph between proposal_strategy and gate_3
8. MODEL_MAP has source_book_writer and source_book_reviewer keys
9. report_markdown populated from Source Book content
"""

import json
import os
import tempfile

import pytest

from src.models.source_book import (
    CapabilityMapping,
    ClientProblemFraming,
    ConsultantProfile,
    EvidenceLedger,
    EvidenceLedgerEntry,
    ExternalEvidenceEntry,
    ExternalEvidenceSection,
    PhaseDetail,
    ProjectExperience,
    ProposedSolution,
    RFPInterpretation,
    SectionCritique,
    SlideBlueprintEntry,
    SourceBook,
    SourceBookReview,
    WhyStrategicGears,
)
from src.models.state import DeckForgeState

# ──────────────────────────────────────────────────────────────
# 1. Schema validation
# ──────────────────────────────────────────────────────────────


class TestSourceBookSchema:
    """Verify SourceBook Pydantic models for all 7 sections."""

    def test_empty_source_book(self):
        sb = SourceBook()
        assert sb.client_name == ""
        assert sb.rfp_name == ""
        assert sb.language == "en"
        assert sb.pass_number == 1
        # All 7 sections present
        assert sb.rfp_interpretation is not None
        assert sb.client_problem_framing is not None
        assert sb.why_strategic_gears is not None
        assert sb.external_evidence is not None
        assert sb.proposed_solution is not None
        assert sb.slide_blueprints == []
        assert sb.evidence_ledger is not None

    def test_full_source_book(self):
        sb = SourceBook(
            client_name="Ministry of Finance",
            rfp_name="Digital Transformation Advisory",
            language="en",
            generation_date="2026-03-22",
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="The client seeks advisory on digital transformation.",
                constraints_and_compliance="Must comply with Vision 2030 standards.",
                unstated_evaluator_priorities="Local content, Saudization",
                probable_scoring_logic="70/30 technical/financial split",
                key_compliance_requirements=["COMP-001", "COMP-002"],
            ),
            client_problem_framing=ClientProblemFraming(
                current_state_challenge="Legacy systems impede efficiency.",
                why_it_matters_now="Vision 2030 deadline approaching.",
                transformation_logic="Phased migration to cloud.",
                risk_if_unchanged="Continued dependence on legacy.",
            ),
            why_strategic_gears=WhyStrategicGears(
                capability_mapping=[
                    CapabilityMapping(
                        rfp_requirement="SAP migration",
                        sg_capability="10+ SAP HANA deployments",
                        evidence_ids=["CLM-0001", "CLM-0005"],
                        strength="strong",
                    ),
                ],
                named_consultants=[
                    ConsultantProfile(
                        name="Ahmad Al-Rashid",
                        role="Lead SAP Architect",
                        relevance="15 years SAP in government",
                        evidence_ids=["CLM-0020"],
                    ),
                ],
                project_experience=[
                    ProjectExperience(
                        project_name="SIDF SAP Migration",
                        client="SIDF",
                        outcomes="Migrated 200+ users to HANA",
                        evidence_ids=["CLM-0001"],
                    ),
                ],
                certifications_and_compliance="ISO 27001, SAP Gold Partner",
            ),
            external_evidence=ExternalEvidenceSection(
                entries=[
                    ExternalEvidenceEntry(
                        source_id="EXT-001",
                        title="Cloud Migration Best Practices",
                        year=2025,
                        relevance="Supports phased migration approach",
                        key_finding="82% of government orgs see ROI within 18 months",
                        source_type="academic_paper",
                    ),
                ],
                coverage_assessment="Strong academic backing for cloud migration.",
            ),
            proposed_solution=ProposedSolution(
                methodology_overview="Agile with waterfall governance gates.",
                phase_details=[
                    PhaseDetail(
                        phase_name="Phase 1: Assessment",
                        activities=["Current-state analysis", "Stakeholder mapping"],
                        deliverables=["Assessment report", "Migration plan"],
                        governance="Weekly steering committee",
                    ),
                ],
                governance_framework="PMO with weekly checkpoints.",
                timeline_logic="18-month program in 3 phases.",
                value_case_and_differentiation="SG is the only firm with both SAP and gov sector.",
            ),
            slide_blueprints=[
                SlideBlueprintEntry(
                    slide_number=1,
                    section="Cover",
                    layout="TITLE",
                    purpose="Set the tone",
                    title="Digital Transformation Advisory",
                    key_message="SG: Your partner for Vision 2030",
                    bullet_logic=[],
                    proof_points=[],
                    visual_guidance="Use SG brand template cover",
                ),
                SlideBlueprintEntry(
                    slide_number=5,
                    section="Why SG",
                    layout="CONTENT_1COL",
                    purpose="Demonstrate SAP expertise",
                    title="Proven SAP Migration Track Record",
                    key_message="10+ government SAP deployments",
                    bullet_logic=[
                        "SIDF: 200+ users migrated [CLM-0001]",
                        "MoF: Full HANA implementation [CLM-0005]",
                    ],
                    proof_points=["CLM-0001", "CLM-0005", "EXT-001"],
                    visual_guidance="Timeline showing project sequence",
                    must_have_evidence=["CLM-0001"],
                    forbidden_content=["Generic SAP claims without project names"],
                ),
            ],
            evidence_ledger=EvidenceLedger(
                entries=[
                    EvidenceLedgerEntry(
                        claim_id="CLM-0001",
                        claim_text="SG delivered SAP HANA migration for SIDF",
                        source_type="internal",
                        source_reference="DOC-001, Slide 5",
                        confidence=0.95,
                        verifiability_status="verified",
                    ),
                    EvidenceLedgerEntry(
                        claim_id="EXT-001",
                        claim_text="82% ROI within 18 months",
                        source_type="external",
                        source_reference="Cloud Migration Best Practices (2025)",
                        confidence=0.80,
                        verifiability_status="partially_verified",
                    ),
                ],
            ),
        )
        assert sb.client_name == "Ministry of Finance"
        assert len(sb.why_strategic_gears.capability_mapping) == 1
        assert sb.why_strategic_gears.capability_mapping[0].strength == "strong"
        assert len(sb.slide_blueprints) == 2
        assert sb.slide_blueprints[1].slide_number == 5
        assert "CLM-0001" in sb.slide_blueprints[1].proof_points
        assert len(sb.evidence_ledger.entries) == 2

    def test_capability_strength_validation(self):
        """strength must be one of the allowed literals."""
        with pytest.raises(Exception):
            CapabilityMapping(
                rfp_requirement="Test",
                sg_capability="Test",
                evidence_ids=["CLM-0001"],
                strength="invalid",
            )

    def test_evidence_ledger_status_validation(self):
        """verifiability_status must be one of the allowed literals."""
        with pytest.raises(Exception):
            EvidenceLedgerEntry(
                claim_id="CLM-0001",
                verifiability_status="invalid",
            )

    def test_serialization_roundtrip(self):
        sb = SourceBook(
            client_name="Test Client",
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="Test scope",
                key_compliance_requirements=["COMP-001"],
            ),
            slide_blueprints=[
                SlideBlueprintEntry(
                    slide_number=1,
                    title="Test Slide",
                    proof_points=["CLM-0001"],
                ),
            ],
        )
        dumped = sb.model_dump(mode="json")
        restored = SourceBook.model_validate(dumped)
        assert restored.client_name == "Test Client"
        assert len(restored.slide_blueprints) == 1
        assert restored.slide_blueprints[0].proof_points == ["CLM-0001"]

    def test_capability_mapping_requires_evidence_ids(self):
        """CapabilityMapping must have at least 1 evidence_id."""
        with pytest.raises(Exception):
            CapabilityMapping(
                rfp_requirement="SAP migration",
                sg_capability="10+ deployments",
                evidence_ids=[],  # empty — should fail
                strength="strong",
            )

    def test_project_experience_requires_evidence_ids(self):
        """ProjectExperience must have at least 1 evidence_id."""
        with pytest.raises(Exception):
            ProjectExperience(
                project_name="SIDF SAP Migration",
                client="SIDF",
                outcomes="Migrated 200+ users",
                evidence_ids=[],  # empty — should fail
            )

    def test_slide_blueprint_proof_points_required_with_must_have(self):
        """proof_points must be non-empty when must_have_evidence is set."""
        with pytest.raises(Exception):
            SlideBlueprintEntry(
                slide_number=5,
                title="Why SG",
                must_have_evidence=["CLM-0001"],
                proof_points=[],  # empty but must_have set — should fail
            )

    def test_slide_blueprint_proof_points_optional_without_must_have(self):
        """proof_points can be empty when must_have_evidence is empty (e.g., Cover slide)."""
        bp = SlideBlueprintEntry(
            slide_number=1,
            section="Cover",
            title="Cover Slide",
            proof_points=[],
            must_have_evidence=[],
        )
        assert bp.proof_points == []

    def test_all_seven_sections_are_distinct_fields(self):
        """Verify the 7 sections map to 7 distinct model fields."""
        sb = SourceBook()
        section_fields = [
            "rfp_interpretation",
            "client_problem_framing",
            "why_strategic_gears",
            "external_evidence",
            "proposed_solution",
            "slide_blueprints",
            "evidence_ledger",
        ]
        for field_name in section_fields:
            assert hasattr(sb, field_name), f"Missing section field: {field_name}"
        assert len(section_fields) == 7


class TestSourceBookReviewSchema:
    """Verify SourceBookReview Pydantic model."""

    def test_empty_review(self):
        review = SourceBookReview()
        assert review.overall_score == 3
        assert review.competitive_viability == "adequate"
        assert review.pass_threshold_met is False
        assert review.rewrite_required is True

    def test_passing_review(self):
        review = SourceBookReview(
            section_critiques=[
                SectionCritique(
                    section_id="rfp_interpretation",
                    score=4,
                    issues=[],
                ),
                SectionCritique(
                    section_id="why_strategic_gears",
                    score=5,
                    issues=[],
                ),
            ],
            overall_score=4,
            competitive_viability="strong",
            pass_threshold_met=True,
            rewrite_required=False,
        )
        assert review.pass_threshold_met is True
        assert review.rewrite_required is False

    def test_failing_review_with_unsupported_claims(self):
        review = SourceBookReview(
            section_critiques=[
                SectionCritique(
                    section_id="why_strategic_gears",
                    score=2,
                    issues=["Claims not backed by evidence"],
                    unsupported_claims=["Extensive SAP experience"],
                    fluff_detected=["deep expertise", "proven track record"],
                    rewrite_instructions=["Replace vague claims with specific evidence"],
                ),
            ],
            overall_score=2,
            competitive_viability="weak",
            pass_threshold_met=False,
            rewrite_required=True,
        )
        assert review.rewrite_required is True
        assert len(review.section_critiques[0].unsupported_claims) == 1
        assert len(review.section_critiques[0].fluff_detected) == 2

    def test_viability_validation(self):
        """competitive_viability must be one of the allowed literals."""
        with pytest.raises(Exception):
            SourceBookReview(competitive_viability="invalid")


# ──────────────────────────────────────────────────────────────
# 2. State field
# ──────────────────────────────────────────────────────────────


class TestStateField:
    """Verify source_book is on DeckForgeState."""

    def test_default_is_none(self):
        state = DeckForgeState()
        assert state.source_book is None

    def test_can_set_source_book(self):
        sb = SourceBook(client_name="Test", rfp_name="Test RFP")
        state = DeckForgeState(source_book=sb)
        assert state.source_book is not None
        assert state.source_book.client_name == "Test"


# ──────────────────────────────────────────────────────────────
# 3. Writer agent user message construction
# ──────────────────────────────────────────────────────────────


class TestWriterUserMessage:
    """Verify the Source Book Writer builds user messages from real state fields."""

    def test_builds_message_from_empty_state(self):
        from src.agents.source_book.writer import _build_user_message

        state = DeckForgeState()
        msg = _build_user_message(state)
        assert isinstance(msg, str)
        parsed = json.loads(msg)
        assert "rfp_context" in parsed
        assert "reference_index" in parsed
        assert "proposal_strategy" in parsed

    def test_builds_message_with_strategy(self):
        from src.agents.source_book.writer import _build_user_message
        from src.models.proposal_strategy import ProposalStrategy, WinTheme

        strategy = ProposalStrategy(
            rfp_interpretation="Test interpretation",
            proposal_thesis="SG is the right choice.",
            win_themes=[
                WinTheme(
                    theme="SAP expertise",
                    supporting_evidence=["CLM-0001"],
                    differentiator_strength="strong",
                ),
            ],
        )
        state = DeckForgeState(
            proposal_strategy=strategy,
            sector="government",
            geography="Saudi Arabia",
        )
        msg = _build_user_message(state)
        parsed = json.loads(msg)
        assert parsed["proposal_strategy"] is not None
        assert parsed["sector"] == "government"

    def test_includes_reviewer_feedback_on_rewrite(self):
        from src.agents.source_book.writer import _build_user_message

        state = DeckForgeState()
        msg = _build_user_message(state, reviewer_feedback="Fix Section 3 evidence gaps")
        parsed = json.loads(msg)
        assert parsed["reviewer_feedback"] == "Fix Section 3 evidence gaps"


# ──────────────────────────────────────────────────────────────
# 4. Reviewer agent
# ──────────────────────────────────────────────────────────────


class TestReviewerUserMessage:
    """Verify the Source Book Reviewer builds messages from Source Book."""

    def test_builds_message_from_source_book(self):
        from src.agents.source_book.reviewer import _build_user_message

        sb = SourceBook(
            client_name="Test Client",
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="Test scope",
            ),
        )
        state = DeckForgeState(source_book=sb)
        msg = _build_user_message(state)
        parsed = json.loads(msg)
        assert "source_book" in parsed
        assert parsed["source_book"]["client_name"] == "Test Client"


# ──────────────────────────────────────────────────────────────
# 5. Orchestrator iteration logic
# ──────────────────────────────────────────────────────────────


class TestOrchestratorLogic:
    """Verify orchestrator converges within max passes."""

    def test_passes_on_first_try(self):
        """If review passes threshold, should stop after 1 pass."""
        from src.agents.source_book.orchestrator import should_continue_iteration

        review = SourceBookReview(
            overall_score=4,
            pass_threshold_met=True,
            rewrite_required=False,
        )
        assert should_continue_iteration(review, current_pass=1, max_passes=5) is False

    def test_continues_on_low_score(self):
        """If overall_score < 4, should continue."""
        from src.agents.source_book.orchestrator import should_continue_iteration

        review = SourceBookReview(
            overall_score=2,
            pass_threshold_met=False,
            rewrite_required=True,
        )
        assert should_continue_iteration(review, current_pass=1, max_passes=5) is True

    def test_stops_at_max_passes(self):
        """Even if review fails, should stop at max passes (5)."""
        from src.agents.source_book.orchestrator import should_continue_iteration

        review = SourceBookReview(
            overall_score=2,
            pass_threshold_met=False,
            rewrite_required=True,
        )
        # Pass 4 should continue (under max)
        assert should_continue_iteration(review, current_pass=4, max_passes=5) is True
        # Pass 5 should stop (at max)
        assert should_continue_iteration(review, current_pass=5, max_passes=5) is False

    def test_default_max_passes_is_5(self):
        """Design contract: default max_passes must be 5."""
        import inspect

        from src.agents.source_book.orchestrator import should_continue_iteration

        sig = inspect.signature(should_continue_iteration)
        default = sig.parameters["max_passes"].default
        assert default == 5, f"Default max_passes is {default}, expected 5"

    def test_build_reviewer_feedback_string(self):
        """Feedback string should summarize critique for rewrite."""
        from src.agents.source_book.orchestrator import build_reviewer_feedback

        review = SourceBookReview(
            section_critiques=[
                SectionCritique(
                    section_id="why_strategic_gears",
                    score=2,
                    issues=["Claims not backed"],
                    rewrite_instructions=["Add evidence IDs"],
                    unsupported_claims=["Extensive experience"],
                ),
            ],
            overall_score=2,
            coherence_issues=["Repetition in sections 3 and 5"],
        )
        feedback = build_reviewer_feedback(review)
        assert "why_strategic_gears" in feedback
        assert "Add evidence IDs" in feedback
        assert "Repetition" in feedback


# ──────────────────────────────────────────────────────────────
# 6. DOCX export
# ──────────────────────────────────────────────────────────────


class TestDocxExport:
    """Verify DOCX export produces valid file with all 7 sections."""

    @pytest.mark.asyncio
    async def test_export_empty_source_book(self):
        from src.services.source_book_export import export_source_book_docx

        sb = SourceBook(client_name="Test", rfp_name="Test RFP")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "source_book.docx")
            result = await export_source_book_docx(sb, path)
            assert os.path.exists(result)
            assert result.endswith(".docx")
            # File should be non-trivial (>1KB for a DOCX with structure)
            assert os.path.getsize(result) > 1000

    @pytest.mark.asyncio
    async def test_export_full_source_book_has_all_sections(self):
        """DOCX should contain heading text for all 7 sections."""
        from docx import Document

        from src.services.source_book_export import export_source_book_docx

        sb = SourceBook(
            client_name="Ministry of Finance",
            rfp_name="Digital Transformation",
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="The client seeks advisory.",
            ),
            client_problem_framing=ClientProblemFraming(
                current_state_challenge="Legacy systems impede efficiency.",
            ),
            why_strategic_gears=WhyStrategicGears(
                capability_mapping=[
                    CapabilityMapping(
                        rfp_requirement="SAP",
                        sg_capability="10+ deployments",
                        evidence_ids=["CLM-0001"],
                        strength="strong",
                    ),
                ],
            ),
            external_evidence=ExternalEvidenceSection(
                entries=[
                    ExternalEvidenceEntry(
                        source_id="EXT-001",
                        title="Cloud Best Practices",
                        year=2025,
                        key_finding="82% ROI",
                    ),
                ],
            ),
            proposed_solution=ProposedSolution(
                methodology_overview="Agile with governance.",
            ),
            slide_blueprints=[
                SlideBlueprintEntry(
                    slide_number=1,
                    section="Cover",
                    title="Test Slide",
                    key_message="Test message",
                    proof_points=["CLM-0001"],
                ),
            ],
            evidence_ledger=EvidenceLedger(
                entries=[
                    EvidenceLedgerEntry(
                        claim_id="CLM-0001",
                        claim_text="SG delivered SAP",
                        confidence=0.95,
                        verifiability_status="verified",
                    ),
                ],
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "source_book.docx")
            await export_source_book_docx(sb, path)

            # Read the DOCX and check for section headings
            doc = Document(path)
            all_text = " ".join(p.text for p in doc.paragraphs)
            assert "RFP Interpretation" in all_text
            assert "Client Problem Framing" in all_text
            assert "Why Strategic Gears" in all_text
            assert "External Evidence" in all_text
            assert "Proposed Solution" in all_text
            assert "Slide-by-Slide Blueprint" in all_text
            assert "Evidence Ledger" in all_text

    @pytest.mark.asyncio
    async def test_export_includes_tables(self):
        """DOCX should contain tables for structured sections."""
        from docx import Document

        from src.services.source_book_export import export_source_book_docx

        sb = SourceBook(
            why_strategic_gears=WhyStrategicGears(
                capability_mapping=[
                    CapabilityMapping(
                        rfp_requirement="SAP",
                        sg_capability="10+ deployments",
                        evidence_ids=["CLM-0001"],
                        strength="strong",
                    ),
                ],
            ),
            evidence_ledger=EvidenceLedger(
                entries=[
                    EvidenceLedgerEntry(
                        claim_id="CLM-0001",
                        claim_text="SG delivered SAP",
                        confidence=0.95,
                        verifiability_status="verified",
                    ),
                ],
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "source_book.docx")
            await export_source_book_docx(sb, path)
            doc = Document(path)
            # Should have at least 2 tables (capability mapping + evidence ledger)
            assert len(doc.tables) >= 2


# ──────────────────────────────────────────────────────────────
# 6b. DOCX path persistence + export failure surfacing
# ──────────────────────────────────────────────────────────────


class TestDocxPathPersistence:
    """Verify DOCX path is persisted in state and export failures are surfaced."""

    @pytest.mark.asyncio
    async def test_successful_export_populates_report_docx_path(self):
        """source_book_node should set report_docx_path on successful export."""
        from unittest.mock import AsyncMock, patch

        from src.models.source_book import SourceBookReview
        from src.services.llm import LLMResponse

        mock_book = SourceBook(
            client_name="Test",
            rfp_name="Test RFP",
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="Test scope",
            ),
        )
        mock_review = SourceBookReview(
            overall_score=4,
            pass_threshold_met=True,
            rewrite_required=False,
        )

        writer_response = LLMResponse(
            parsed=mock_book,
            input_tokens=5000,
            output_tokens=3000,
            model="claude-opus-4-20250514",
            latency_ms=8000,
        )
        reviewer_response = LLMResponse(
            parsed=mock_review,
            input_tokens=4000,
            output_tokens=1500,
            model="gpt-5.4",
            latency_ms=3000,
        )

        call_count = 0

        async def mock_call_llm(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return writer_response
            return reviewer_response

        with (
            patch(
                "src.agents.source_book.writer.call_llm",
                new_callable=AsyncMock,
                side_effect=mock_call_llm,
            ),
            patch(
                "src.agents.source_book.reviewer.call_llm",
                new_callable=AsyncMock,
                side_effect=mock_call_llm,
            ),
        ):
            from src.pipeline.graph import source_book_node

            state = DeckForgeState()
            result = await source_book_node(state)

        assert "report_docx_path" in result
        assert result["report_docx_path"] is not None
        assert result["report_docx_path"].endswith("source_book.docx")
        # No errors from export
        assert "errors" not in result or not any(
            e.error_type == "DocxExportError"
            for e in result.get("errors", [])
        )

    @pytest.mark.asyncio
    async def test_export_failure_surfaces_error(self):
        """If DOCX export fails, error must be in state.errors."""
        from unittest.mock import AsyncMock, patch

        from src.models.source_book import SourceBookReview
        from src.services.llm import LLMResponse

        mock_book = SourceBook(client_name="Test")
        mock_review = SourceBookReview(
            overall_score=4,
            pass_threshold_met=True,
            rewrite_required=False,
        )

        writer_response = LLMResponse(
            parsed=mock_book,
            input_tokens=5000,
            output_tokens=3000,
            model="claude-opus-4-20250514",
            latency_ms=8000,
        )
        reviewer_response = LLMResponse(
            parsed=mock_review,
            input_tokens=4000,
            output_tokens=1500,
            model="gpt-5.4",
            latency_ms=3000,
        )

        call_count = 0

        async def mock_call_llm(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return writer_response
            return reviewer_response

        with (
            patch(
                "src.agents.source_book.writer.call_llm",
                new_callable=AsyncMock,
                side_effect=mock_call_llm,
            ),
            patch(
                "src.agents.source_book.reviewer.call_llm",
                new_callable=AsyncMock,
                side_effect=mock_call_llm,
            ),
            patch(
                "src.services.source_book_export.export_source_book_docx",
                new_callable=AsyncMock,
                side_effect=PermissionError("Disk full"),
            ),
        ):
            from src.pipeline.graph import source_book_node

            state = DeckForgeState()
            result = await source_book_node(state)

        # DOCX path should be None on failure
        assert result["report_docx_path"] is None
        # Error must be surfaced structurally
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert any(
            e.error_type == "DocxExportError" for e in result["errors"]
        )
        assert "last_error" in result
        assert result["last_error"].error_type == "DocxExportError"


# ──────────────────────────────────────────────────────────────
# 7. Graph wiring
# ──────────────────────────────────────────────────────────────


class TestGraphWiring:
    """Verify source_book_node is in graph between proposal_strategy and gate_3."""

    def test_source_book_node_exists(self):
        from src.pipeline.graph import source_book_node

        assert callable(source_book_node)

    def test_graph_has_source_book_node(self):
        from src.pipeline.graph import build_graph

        graph = build_graph()
        g = graph.get_graph()
        node_names = [n.name if hasattr(n, "name") else str(n) for n in g.nodes]
        assert "source_book" in node_names

    def test_graph_flow_order(self):
        """Verify: proposal_strategy -> source_book -> assembly_plan.

        Note: Phase 4 will move assembly_plan after gate_3. For Phase 3,
        source_book sits between proposal_strategy and assembly_plan.
        """
        from src.pipeline.graph import build_graph

        graph = build_graph()
        g = graph.get_graph()

        edges: dict[str, list[str]] = {}
        for edge in g.edges:
            src = edge.source.name if hasattr(edge.source, "name") else str(edge.source)
            tgt = edge.target.name if hasattr(edge.target, "name") else str(edge.target)
            edges.setdefault(src, []).append(tgt)

        # proposal_strategy -> source_book
        assert "source_book" in edges.get("proposal_strategy", []), (
            f"proposal_strategy edges: {edges.get('proposal_strategy', [])}"
        )
        # source_book -> assembly_plan
        assert "assembly_plan" in edges.get("source_book", []), (
            f"source_book edges: {edges.get('source_book', [])}"
        )


# ──────────────────────────────────────────────────────────────
# 8. MODEL_MAP
# ──────────────────────────────────────────────────────────────


class TestModelMap:
    def test_source_book_writer_in_model_map(self):
        from src.config.models import MODEL_MAP

        assert "source_book_writer" in MODEL_MAP

    def test_source_book_reviewer_in_model_map(self):
        from src.config.models import MODEL_MAP

        assert "source_book_reviewer" in MODEL_MAP

    def test_writer_uses_opus(self):
        """Source Book Writer should use Opus (long-form structured writing)."""
        from src.config.models import MODEL_MAP

        model = MODEL_MAP["source_book_writer"]
        assert "opus" in model.lower()

    def test_reviewer_uses_gpt(self):
        """Source Book Reviewer should use GPT-5.4 (critique role)."""
        from src.config.models import MODEL_MAP

        model = MODEL_MAP["source_book_reviewer"]
        assert "gpt" in model.lower()


# ──────────────────────────────────────────────────────────────
# 9. report_markdown population
# ──────────────────────────────────────────────────────────────


class TestReportMarkdownPopulation:
    """Verify Source Book content populates report_markdown."""

    def test_source_book_to_markdown(self):
        from src.agents.source_book.orchestrator import source_book_to_markdown

        sb = SourceBook(
            client_name="Test Client",
            rfp_name="Test RFP",
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="The client seeks advisory.",
                constraints_and_compliance="Must comply with standards.",
            ),
            client_problem_framing=ClientProblemFraming(
                current_state_challenge="Legacy systems impede.",
                risk_if_unchanged="Continued legacy dependence.",
            ),
            proposed_solution=ProposedSolution(
                methodology_overview="Agile with governance.",
            ),
        )
        md = source_book_to_markdown(sb)
        assert isinstance(md, str)
        assert "Test Client" in md
        assert "RFP Interpretation" in md
        assert "Client Problem Framing" in md
        assert "Proposed Solution" in md
        assert len(md) > 50


# ──────────────────────────────────────────────────────────────
# 10. Prompt content
# ──────────────────────────────────────────────────────────────


class TestPromptContent:
    def test_writer_prompt_has_section_framework(self):
        from src.agents.source_book.writer import SYSTEM_PROMPT

        assert "RFP INTERPRETATION" in SYSTEM_PROMPT
        assert "CLIENT PROBLEM FRAMING" in SYSTEM_PROMPT
        assert "WHY STRATEGIC GEARS" in SYSTEM_PROMPT
        assert "EXTERNAL EVIDENCE" in SYSTEM_PROMPT
        assert "PROPOSED SOLUTION" in SYSTEM_PROMPT
        assert "SLIDE-BY-SLIDE BLUEPRINT" in SYSTEM_PROMPT or "SLIDE BLUEPRINT" in SYSTEM_PROMPT
        assert "EVIDENCE LEDGER" in SYSTEM_PROMPT

    def test_writer_prompt_requires_evidence_ids(self):
        from src.agents.source_book.writer import SYSTEM_PROMPT

        assert "CLM-" in SYSTEM_PROMPT
        assert "EXT-" in SYSTEM_PROMPT

    def test_reviewer_prompt_has_critique_framework(self):
        from src.agents.source_book.reviewer import SYSTEM_PROMPT

        assert "score" in SYSTEM_PROMPT.lower()
        assert "unsupported" in SYSTEM_PROMPT.lower() or "evidence" in SYSTEM_PROMPT.lower()
        assert "fluff" in SYSTEM_PROMPT.lower() or "vague" in SYSTEM_PROMPT.lower()
