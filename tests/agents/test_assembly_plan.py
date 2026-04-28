"""Tests for the Assembly Plan Agent.

Tests the deterministic assembly pipeline: LLM output → inclusion policy →
methodology blueprint → case study selection → team selection → slide budget.

LLM calls are mocked — we test that valid LLM output produces correct
deterministic results through the existing infrastructure.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.assembly_plan.agent import (
    AssemblyPlanOutput,
    AssemblyPlanResult,
    MethodologyPhaseSpec,
    RFPMatchingContext,
    _country_to_geography,
    _extract_person_names,
    _load_case_study_candidates,
    _load_team_candidates,
    run,
)
from src.models.common import BilingualText
from src.models.enums import Language, PipelineStage
from src.models.methodology_blueprint import MethodologyBlueprint
from src.models.proposal_manifest import HouseInclusionPolicy
from src.models.rfp import RFPContext
from src.models.state import DeckForgeState
from src.services.selection_policies import (
    CaseStudySelectionResult,
    TeamSelectionResult,
)
from src.services.slide_budgeter import SlideBudget

# ── Fixtures ──────────────────────────────────────────────────────────


def _make_rfp_context() -> RFPContext:
    """Minimal RFP context for testing."""
    return RFPContext(
        rfp_name=BilingualText(en="IT Modernization Program", ar=""),
        issuing_entity=BilingualText(en="Ministry of Finance", ar=""),
        mandate=BilingualText(en="Modernize IT infrastructure", ar=""),
    )


def _make_assembly_output() -> AssemblyPlanOutput:
    """Valid AssemblyPlanOutput for testing the deterministic pipeline."""
    return AssemblyPlanOutput(
        geography="ksa",
        proposal_mode="standard",
        sector="government",
        methodology_phases=[
            MethodologyPhaseSpec(
                phase_name_en="Discovery & Assessment",
                phase_name_ar="الاستكشاف والتقييم",
                activities=["Stakeholder interviews", "Current state analysis", "Gap assessment"],
                deliverables=["Assessment Report", "Gap Analysis"],
                governance_tier="Steering Committee",
            ),
            MethodologyPhaseSpec(
                phase_name_en="Design & Planning",
                phase_name_ar="التصميم والتخطيط",
                activities=["Solution design", "Roadmap development", "Risk planning"],
                deliverables=["Solution Blueprint", "Implementation Roadmap"],
                governance_tier="Project Board",
            ),
            MethodologyPhaseSpec(
                phase_name_en="Implementation & Change",
                phase_name_ar="التنفيذ والتغيير",
                activities=["Phased rollout", "Training delivery", "Change management"],
                deliverables=["Implementation Report", "Training Materials"],
                governance_tier="Working Group",
            ),
            MethodologyPhaseSpec(
                phase_name_en="Transition & Handover",
                phase_name_ar="الانتقال والتسليم",
                activities=["Knowledge transfer", "Sustainability planning"],
                deliverables=["Handover Package"],
                governance_tier="Steering Committee",
            ),
        ],
        methodology_timeline_span="16 weeks",
        rfp_matching_context=RFPMatchingContext(
            sector="government",
            services=["strategy", "digital_cloud_ai"],
            geography="ksa",
            technology_keywords=["cloud migration", "data analytics"],
            capability_tags=["digital transformation", "change management"],
            required_roles=["project_manager", "senior_consultant"],
            language="en",
        ),
        understanding_slides=3,
        timeline_slides=2,
        governance_slides=1,
        win_themes=[
            "Deep KSA public sector transformation experience",
            "Proven digital transformation methodology",
            "Local team with international expertise",
        ],
        rfp_summary="Ministry of Finance seeks IT modernization consulting.",
        client_name="Ministry of Finance",
    )


def _make_catalog_lock() -> dict:
    """Minimal catalog lock with pool entries for testing."""
    return {
        "case_study_pool": [
            {
                "slide_idx": 9,
                "semantic_layout_id": "case_study_detailed",
                "semantic_id": "case_study_9",
            },
            {
                "slide_idx": 33,
                "semantic_layout_id": "case_study_cases",
                "semantic_id": "case_study_33",
            },
            {
                "slide_idx": 34,
                "semantic_layout_id": "case_study_cases",
                "semantic_id": "case_study_34",
            },
            {
                "slide_idx": 35,
                "semantic_layout_id": "case_study_cases",
                "semantic_id": "case_study_35",
            },
            {
                "slide_idx": 36,
                "semantic_layout_id": "case_study_cases",
                "semantic_id": "case_study_36",
            },
        ],
        "service_divider_pool": [
            {
                "slide_idx": 32,
                "semantic_layout_id": "svc_strategy",
                "display_name": "Strategy",
                "semantic_id": "svc_divider_strategy",
                "service_category": "strategy",
            },
        ],
        "team_bio_pool": [
            {
                "slide_idx": 70,
                "semantic_layout_id": "team_two_members",
                "semantic_id": "team_bio_70",
                "team_family": "team_two_members",
                "member_names": [
                    "20+ years of experience",
                    "HATTAN SAATY",
                    "NASSER ALQAHTANI",
                    "MANAGING PARTNER",
                    "Strategy",
                    "Marketing",
                ],
            },
            {
                "slide_idx": 71,
                "semantic_layout_id": "team_two_members",
                "semantic_id": "team_bio_71",
                "team_family": "team_two_members",
                "member_names": [
                    "21+ years of experience",
                    "NAGARAJ PADMANABHAN",
                    "SENIOR PARTNER",
                    "RICHARD PARKIN",
                    "PARTNER",
                    "Digital & cloud transformation",
                ],
            },
            {
                "slide_idx": 72,
                "semantic_layout_id": "team_two_members",
                "semantic_id": "team_bio_72",
                "team_family": "team_two_members",
                "member_names": [
                    "13+ years of experience",
                    "LAITH ABDIN",
                    "PARTNER",
                    "AHMAD ABZAKH",
                    "ASSOCIATE PARTNER",
                    "Strategy development",
                ],
            },
        ],
    }


# ── Unit tests: helper functions ──────────────────────────────────────


class TestCountryToGeography:
    def test_saudi_arabic(self):
        assert _country_to_geography("المملكة العربية السعودية") == "ksa"

    def test_saudi_english(self):
        assert _country_to_geography("Saudi Arabia") == "ksa"

    def test_uae(self):
        assert _country_to_geography("UAE") == "gcc"

    def test_egypt(self):
        assert _country_to_geography("Egypt") == "mena"

    def test_unknown(self):
        assert _country_to_geography("Germany") == "international"

    def test_empty(self):
        assert _country_to_geography("") == "international"


class TestExtractPersonNames:
    def test_extracts_names(self):
        names = _extract_person_names([
            "20+ years of experience",
            "HATTAN SAATY",
            "NASSER ALQAHTANI",
            "MANAGING PARTNER",
            "Strategy",
            "Marketing",
        ])
        assert "HATTAN SAATY" in names
        assert "NASSER ALQAHTANI" in names
        assert len(names) == 2

    def test_skips_roles_and_departments(self):
        names = _extract_person_names([
            "SENIOR PARTNER",
            "Strategy development",
            "RICHARD PARKIN",
        ])
        assert "RICHARD PARKIN" in names
        assert len(names) == 1

    def test_empty_list(self):
        assert _extract_person_names([]) == []


class TestLoadCaseStudyCandidates:
    def test_loads_from_catalog_lock(self):
        catalog_lock = _make_catalog_lock()
        candidates = _load_case_study_candidates(
            catalog_lock, knowledge_graph_path=Path("/nonexistent")
        )
        assert len(candidates) == 5
        assert candidates[0]["asset_id"] == "case_study_9"
        assert candidates[1]["asset_id"] == "case_study_33"

    def test_empty_pool(self):
        candidates = _load_case_study_candidates({})
        assert candidates == []

    def test_all_have_asset_id(self):
        catalog_lock = _make_catalog_lock()
        candidates = _load_case_study_candidates(
            catalog_lock, knowledge_graph_path=Path("/nonexistent")
        )
        for c in candidates:
            assert "asset_id" in c
            assert c["asset_id"]


class TestLoadTeamCandidates:
    def test_loads_from_catalog_lock(self):
        catalog_lock = _make_catalog_lock()
        candidates = _load_team_candidates(
            catalog_lock, knowledge_graph_path=Path("/nonexistent")
        )
        assert len(candidates) == 3
        assert candidates[0]["asset_id"] == "team_bio_70"

    def test_empty_pool(self):
        candidates = _load_team_candidates({})
        assert candidates == []


# ── Unit tests: Pydantic models ───────────────────────────────────────


class TestAssemblyPlanOutput:
    def test_valid_output(self):
        output = _make_assembly_output()
        assert output.geography == "ksa"
        assert output.proposal_mode == "standard"
        assert len(output.methodology_phases) == 4

    def test_methodology_phases_min_3(self):
        """Must have at least 3 methodology phases."""
        with pytest.raises(Exception):
            AssemblyPlanOutput(
                geography="ksa",
                proposal_mode="standard",
                sector="government",
                methodology_phases=[
                    MethodologyPhaseSpec(
                        phase_name_en="Phase 1",
                        activities=["a"],
                        deliverables=["d"],
                    ),
                    MethodologyPhaseSpec(
                        phase_name_en="Phase 2",
                        activities=["a"],
                        deliverables=["d"],
                    ),
                ],
                rfp_matching_context=RFPMatchingContext(),
                win_themes=["theme"],
            )

    def test_methodology_phases_max_5(self):
        """Must have at most 5 methodology phases."""
        with pytest.raises(Exception):
            AssemblyPlanOutput(
                geography="ksa",
                proposal_mode="standard",
                sector="government",
                methodology_phases=[
                    MethodologyPhaseSpec(
                        phase_name_en=f"Phase {i}",
                        activities=["a"],
                        deliverables=["d"],
                    )
                    for i in range(6)
                ],
                rfp_matching_context=RFPMatchingContext(),
                win_themes=["theme"],
            )


# ── Integration test: deterministic pipeline ──────────────────────────


class TestDeterministicPipeline:
    """Test that valid LLM output flows correctly through the existing
    deterministic infrastructure (inclusion policy → methodology blueprint →
    selection → budget).
    """

    def test_full_pipeline_from_output(self):
        """End-to-end: AssemblyPlanOutput → all deterministic steps succeed."""
        from src.models.methodology_blueprint import build_methodology_blueprint
        from src.models.proposal_manifest import build_inclusion_policy
        from src.services.selection_policies import select_case_studies, select_team_members
        from src.services.slide_budgeter import compute_slide_budget

        output = _make_assembly_output()
        catalog_lock = _make_catalog_lock()

        # Step 1: Inclusion policy
        policy = build_inclusion_policy(
            proposal_mode=output.proposal_mode,
            geography=output.geography,
            sector=output.sector,
        )
        assert isinstance(policy, HouseInclusionPolicy)
        assert policy.include_ksa_context is True  # ksa geography
        assert policy.company_profile_depth == "standard"

        # Step 2: Methodology blueprint
        phase_defs = [
            {
                "phase_name_en": p.phase_name_en,
                "phase_name_ar": p.phase_name_ar,
                "activities": p.activities,
                "deliverables": p.deliverables,
                "governance_tier": p.governance_tier,
            }
            for p in output.methodology_phases
        ]
        blueprint = build_methodology_blueprint(
            phase_count=len(output.methodology_phases),
            phases=phase_defs,
            timeline_span=output.methodology_timeline_span,
        )
        assert isinstance(blueprint, MethodologyBlueprint)
        assert blueprint.phase_count == 4

        # Step 3: Case study selection
        cs_candidates = _load_case_study_candidates(
            catalog_lock, knowledge_graph_path=Path("/nonexistent")
        )
        matching_ctx = output.rfp_matching_context.model_dump()
        cs_result = select_case_studies(
            candidates=cs_candidates,
            rfp_context=matching_ctx,
            min_count=policy.case_study_count[0],
            max_count=policy.case_study_count[1],
        )
        assert isinstance(cs_result, CaseStudySelectionResult)
        assert len(cs_result.selected) >= policy.case_study_count[0]

        # Step 4: Team selection
        team_candidates = _load_team_candidates(
            catalog_lock, knowledge_graph_path=Path("/nonexistent")
        )
        team_result = select_team_members(
            candidates=team_candidates,
            rfp_context=matching_ctx,
            min_count=policy.team_bio_count[0],
            max_count=policy.team_bio_count[1],
        )
        assert isinstance(team_result, TeamSelectionResult)
        assert len(team_result.selected) >= policy.team_bio_count[0]

        # Step 5: Slide budget
        budget = compute_slide_budget(
            inclusion_policy=policy,
            methodology_blueprint=blueprint,
            case_study_result=cs_result,
            team_result=team_result,
            understanding_slides=output.understanding_slides,
            timeline_slides=output.timeline_slides,
            governance_slides=output.governance_slides,
        )
        assert isinstance(budget, SlideBudget)
        assert budget.total_slides > 0
        # Cover(3) + sec01(1+3) + sec02(1+ksa+cs+svc) + sec03(1+meth) +
        # sec04(1+2) + sec05(1+leadership+team) + sec06(1+1) +
        # company_profile + closing(2)
        assert "cover" in budget.section_budgets
        assert "section_01" in budget.section_budgets
        assert "section_03" in budget.section_budgets
        assert budget.section_budgets["cover"].slide_count == 3

    def test_ksa_produces_ksa_context_in_budget(self):
        """KSA geography should include KSA context slides in section_02."""
        from src.models.proposal_manifest import build_inclusion_policy

        output = _make_assembly_output()
        assert output.geography == "ksa"

        policy = build_inclusion_policy("standard", "ksa", "government")
        assert policy.include_ksa_context is True

    def test_lite_mode_small_profile(self):
        """Lite mode should produce small company profile."""
        from src.models.proposal_manifest import get_company_profile_ids

        ids = get_company_profile_ids("lite")
        assert len(ids) == 3  # main_cover, overview, why_sg

    def test_standard_mode_standard_profile(self):
        """Standard mode should produce standard company profile."""
        from src.models.proposal_manifest import get_company_profile_ids

        ids = get_company_profile_ids("standard")
        assert len(ids) == 8


# ── Async agent run test ──────────────────────────────────────────────


class TestAgentRun:
    @pytest.mark.asyncio
    async def test_run_success(self):
        """Test that run() produces valid state dict on success."""
        state = DeckForgeState(
            rfp_context=_make_rfp_context(),
            output_language=Language.EN,
        )

        mock_output = _make_assembly_output()
        mock_result = MagicMock()
        mock_result.parsed = mock_output
        mock_result.input_tokens = 1000
        mock_result.output_tokens = 500

        catalog_lock = _make_catalog_lock()

        with patch("src.agents.assembly_plan.agent.call_llm", new_callable=AsyncMock) as mock_llm, \
             patch("src.agents.assembly_plan.agent._load_catalog_lock") as mock_catalog:
            mock_llm.return_value = mock_result
            mock_catalog.return_value = catalog_lock

            result = await run(
                state,
                knowledge_graph_path=Path("/nonexistent"),
            )

        assert result["current_stage"] == PipelineStage.ANALYSIS
        assert "assembly_plan" in result
        assert isinstance(result["assembly_plan"], AssemblyPlanResult)
        assert isinstance(result["methodology_blueprint"], MethodologyBlueprint)
        assert isinstance(result["slide_budget"], SlideBudget)
        assert result["sector"] == "government"
        assert result["geography"] == "ksa"

    @pytest.mark.asyncio
    async def test_run_llm_failure(self):
        """Test that LLM failure produces error state."""
        from src.services.llm import LLMError

        state = DeckForgeState(
            rfp_context=_make_rfp_context(),
        )

        with patch("src.agents.assembly_plan.agent.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = LLMError(
                model="test", attempts=3, last_error=RuntimeError("API error")
            )

            result = await run(state)

        assert result["current_stage"] == PipelineStage.ERROR
        assert len(result["errors"]) > 0
        assert result["last_error"].agent == "assembly_plan"


# ── Service Divider Selection Tests ──────────────────────────────────


class TestServiceDividerSelection:
    """Tests for select_service_divider."""

    def test_exact_sector_match(self):
        """Exact service_category match gets highest score."""
        from src.services.selection_policies import select_service_divider

        pool = [
            {"semantic_id": "svc_a", "service_category": "strategy"},
            {"semantic_id": "svc_b", "service_category": "marketing"},
        ]
        result = select_service_divider(
            rfp_context={"sector": "marketing", "services": [], "capability_tags": []},
            service_divider_pool=pool,
        )
        assert result.selected_service_divider == "svc_b"
        assert result.score >= 5.0

    def test_keyword_match(self):
        """Keyword mapping selects the right divider."""
        from src.services.selection_policies import select_service_divider

        pool = [
            {"semantic_id": "svc_strategy", "service_category": "strategy"},
            {"semantic_id": "svc_digital", "service_category": "digital, cloud, and ai"},
        ]
        result = select_service_divider(
            rfp_context={"sector": "technology", "services": ["digital"], "capability_tags": ["ai"]},
            service_divider_pool=pool,
        )
        assert result.selected_service_divider == "svc_digital"
        assert result.score > 0

    def test_empty_pool_returns_empty(self):
        """Empty pool returns empty string."""
        from src.services.selection_policies import select_service_divider

        result = select_service_divider(
            rfp_context={"sector": "gov", "services": [], "capability_tags": []},
            service_divider_pool=[],
        )
        assert result.selected_service_divider == ""
        assert result.score == 0.0

    def test_fallback_to_first(self):
        """No match falls back to first divider."""
        from src.services.selection_policies import select_service_divider

        pool = [
            {"semantic_id": "svc_strategy", "service_category": "strategy"},
            {"semantic_id": "svc_deals", "service_category": "deals advisory"},
        ]
        result = select_service_divider(
            rfp_context={"sector": "xyz_unknown", "services": [], "capability_tags": []},
            service_divider_pool=pool,
        )
        assert result.selected_service_divider == "svc_strategy"
        assert result.reason == "default_fallback"


# ── Manifest Budget Equality Tests ───────────────────────────────────


class TestManifestBudgetEquality:
    """Tests for manifest/budget equality invariant."""

    def test_matching_counts_pass(self):
        """When budget and manifest match, no error is raised."""
        from src.services.manifest_builder import build_manifest_from_assembly_plan

        catalog_lock = _make_catalog_lock()

        assembly = _make_full_assembly(catalog_lock)

        # Should not raise
        with patch("src.services.manifest_builder.Path.read_text") as mock_read:
            mock_read.return_value = json.dumps(catalog_lock)
            manifest = build_manifest_from_assembly_plan(
                assembly_plan=assembly,
                catalog_lock_path=Path("fake/catalog_lock_en.json"),
                language="en",
            )
        assert manifest.total_slides == assembly.slide_budget.total_slides

    def test_mismatch_raises_error(self):
        """Deliberate mismatch triggers ValueError."""
        from src.services.manifest_builder import build_manifest_from_assembly_plan
        from src.services.slide_budgeter import SlideBudget

        catalog_lock = _make_catalog_lock()
        assembly = _make_full_assembly(catalog_lock)

        # Tamper: set budget to a wrong total
        wrong_budget = SlideBudget(
            total_slides=999,
            section_budgets=assembly.slide_budget.section_budgets,
        )
        # Replace budget with wrong one
        assembly_dict = assembly.model_dump()
        assembly_dict["slide_budget"] = wrong_budget

        tampered = assembly.model_copy(update={"slide_budget": wrong_budget})

        with patch("src.services.manifest_builder.Path.read_text") as mock_read:
            mock_read.return_value = json.dumps(catalog_lock)
            with pytest.raises(ValueError, match="Manifest/budget mismatch"):
                build_manifest_from_assembly_plan(
                    assembly_plan=tampered,
                    catalog_lock_path=Path("fake/catalog_lock_en.json"),
                    language="en",
                )


# ── Gate 3 Assembly Plan Payload Test ────────────────────────────────


class TestGate3AssemblyPlanPayload:
    """Tests for backend Gate 3 assembly-plan payload."""

    def test_gate3_returns_assembly_plan_payload(self):
        """When assembly_plan is set, Gate 3 returns ASSEMBLY_PLAN_REVIEW."""
        from backend.models.api_models import Gate3AssemblyPlanData, GatePayloadType
        from backend.services.pipeline_runtime import _build_gate_payloads

        state = DeckForgeState()
        # Set a minimal assembly_plan
        state.assembly_plan = {
            "llm_output": {
                "proposal_mode": "standard",
                "geography": "ksa",
                "sector": "government",
                "methodology_phases": [],
                "win_themes": ["theme1"],
            },
            "case_study_result": {"selected": []},
            "team_result": {"selected": []},
            "slide_budget": {"total_slides": 40},
        }

        payload_type, gate_data = _build_gate_payloads("test-session", state, 3)
        assert payload_type == GatePayloadType.ASSEMBLY_PLAN_REVIEW
        assert isinstance(gate_data, Gate3AssemblyPlanData)
        assert gate_data.proposal_mode == "standard"
        assert gate_data.geography == "ksa"

    def test_gate3_falls_back_to_report_review(self):
        """When assembly_plan is None, Gate 3 returns REPORT_REVIEW."""
        from backend.models.api_models import Gate3ReportReviewData, GatePayloadType
        from backend.services.pipeline_runtime import _build_gate_payloads

        state = DeckForgeState()
        state.assembly_plan = None

        payload_type, gate_data = _build_gate_payloads("test-session", state, 3)
        assert payload_type == GatePayloadType.REPORT_REVIEW
        assert isinstance(gate_data, Gate3ReportReviewData)


# ── Helpers for new tests ────────────────────────────────────────────


def _make_full_assembly(catalog_lock: dict):
    """Build a complete AssemblyPlanResult for testing."""
    from src.models.methodology_blueprint import build_methodology_blueprint
    from src.models.proposal_manifest import build_inclusion_policy
    from src.services.selection_policies import (
        select_case_studies,
        select_service_divider,
        select_team_members,
    )
    from src.services.slide_budgeter import compute_slide_budget

    policy = build_inclusion_policy(
        geography="ksa", proposal_mode="standard", sector="government",
    )
    phases = [
        {"phase_name_en": f"Phase {i}", "activities": ["a"], "deliverables": ["d"]}
        for i in range(4)
    ]
    blueprint = build_methodology_blueprint(
        phase_count=4, phases=phases, timeline_span="12w",
    )

    rfp_ctx = {
        "sector": "government", "services": ["strategy"],
        "geography": "ksa", "technology_keywords": [],
        "capability_tags": [], "language": "en", "required_roles": [],
    }

    cs_pool = catalog_lock.get("case_study_pool", [])
    if isinstance(cs_pool, dict):
        cs_list = []
        for entries in cs_pool.values():
            if isinstance(entries, list):
                cs_list.extend(entries)
        cs_pool = cs_list

    cs_candidates = [
        {"asset_id": c.get("semantic_id", ""), "sector": "", "services": [],
         "geography": "", "technology_keywords": [], "capability_tags": []}
        for c in cs_pool
    ]
    team_pool = catalog_lock.get("team_bio_pool", [])
    team_candidates = [
        {"asset_id": t.get("semantic_id", ""), "sector_experience": [],
         "services": [], "role": "", "geography_experience": [],
         "technology_keywords": [], "languages": ["en"]}
        for t in team_pool
    ]

    cs_result = select_case_studies(
        candidates=cs_candidates, rfp_context=rfp_ctx,
        min_count=policy.case_study_count[0],
        max_count=policy.case_study_count[1],
    )
    team_result = select_team_members(
        candidates=team_candidates, rfp_context=rfp_ctx,
        min_count=policy.team_bio_count[0],
        max_count=policy.team_bio_count[1],
    )
    svc_result = select_service_divider(
        rfp_context=rfp_ctx,
        service_divider_pool=catalog_lock.get("service_divider_pool", []),
    )

    budget = compute_slide_budget(
        inclusion_policy=policy, methodology_blueprint=blueprint,
        case_study_result=cs_result, team_result=team_result,
        understanding_slides=3, timeline_slides=2, governance_slides=1,
    )

    llm_out = AssemblyPlanOutput(
        geography="ksa", proposal_mode="standard", sector="government",
        methodology_phases=[
            MethodologyPhaseSpec(
                phase_name_en=f"Phase {i}", activities=["a"], deliverables=["d"],
            )
            for i in range(4)
        ],
        rfp_matching_context=RFPMatchingContext(
            sector="government", services=["strategy"], geography="ksa",
        ),
        understanding_slides=3, timeline_slides=2, governance_slides=1,
    )

    return AssemblyPlanResult(
        llm_output=llm_out, inclusion_policy=policy,
        methodology_blueprint=blueprint,
        case_study_result=cs_result, team_result=team_result,
        slide_budget=budget, service_divider_result=svc_result,
    )
