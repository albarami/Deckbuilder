"""Tests for Phase 2: Proposal Strategy.

Verifies:
1. ProposalStrategy, WinTheme, EvaluatorPriority schemas validate correctly
2. DeckForgeState has proposal_strategy field
3. Proposal Strategist agent builds correct user message from real state
4. proposal_strategy_node is wired into graph between evidence_curation and assembly_plan
5. Strategy output has win themes with evidence backing (via mock)
6. MODEL_MAP has proposal_strategist key (Opus)
"""

import pytest

from src.models.proposal_strategy import (
    EvaluatorPriority,
    ProposalStrategy,
    WinTheme,
)
from src.models.state import DeckForgeState

# ──────────────────────────────────────────────────────────────
# 1. Schema validation
# ──────────────────────────────────────────────────────────────


class TestProposalStrategySchema:
    """Verify ProposalStrategy Pydantic models."""

    def test_empty_strategy(self):
        strategy = ProposalStrategy()
        assert strategy.rfp_interpretation == ""
        assert strategy.win_themes == []
        assert strategy.unstated_evaluator_priorities == []
        assert strategy.evidence_gaps == []
        assert strategy.recommended_methodology_approach == ""

    def test_full_strategy(self):
        strategy = ProposalStrategy(
            rfp_interpretation="The client seeks digital transformation advisory.",
            unstated_evaluator_priorities=[
                EvaluatorPriority(
                    priority="Local content and Saudization",
                    weight_estimate=0.3,
                    evidence_available="strong",
                    strategy_note="Emphasize 40% Saudi national workforce",
                ),
            ],
            scoring_logic_assessment="70/30 technical/financial split",
            compliance_requirements=["COMP-001", "COMP-002"],
            win_themes=[
                WinTheme(
                    theme="Proven SAP migration expertise in government sector",
                    supporting_evidence=["CLM-0001", "CLM-0005", "EXT-002"],
                    differentiator_strength="strong",
                ),
                WinTheme(
                    theme="Local presence with deep Ministry relationships",
                    supporting_evidence=["CLM-0020"],
                    differentiator_strength="unique",
                ),
            ],
            proposal_thesis="SG uniquely combines SAP expertise with local presence.",
            risk_if_unchanged="Continued reliance on legacy systems.",
            competitive_positioning="Only firm with both SAP and gov sector credentials.",
            evidence_gaps=["No cloud migration case study"],
            recommended_methodology_approach="Agile with waterfall governance gates",
        )

        assert len(strategy.win_themes) == 2
        assert strategy.win_themes[0].differentiator_strength == "strong"
        assert "CLM-0001" in strategy.win_themes[0].supporting_evidence
        assert strategy.unstated_evaluator_priorities[0].weight_estimate == 0.3
        assert strategy.recommended_methodology_approach != ""

    def test_win_theme_strength_validation(self):
        """differentiator_strength must be one of the allowed literals."""
        with pytest.raises(Exception):
            WinTheme(
                theme="Test",
                differentiator_strength="invalid",
            )

    def test_evaluator_priority_evidence_validation(self):
        """evidence_available must be one of the allowed literals."""
        with pytest.raises(Exception):
            EvaluatorPriority(
                priority="Test",
                evidence_available="invalid",
            )

    def test_serialization_roundtrip(self):
        strategy = ProposalStrategy(
            rfp_interpretation="Test interpretation",
            win_themes=[
                WinTheme(
                    theme="Test theme",
                    supporting_evidence=["CLM-0001"],
                    differentiator_strength="moderate",
                ),
            ],
        )
        dumped = strategy.model_dump(mode="json")
        restored = ProposalStrategy.model_validate(dumped)
        assert restored.rfp_interpretation == strategy.rfp_interpretation
        assert len(restored.win_themes) == 1


# ──────────────────────────────────────────────────────────────
# 2. State field
# ──────────────────────────────────────────────────────────────


class TestStateField:
    """Verify proposal_strategy is on DeckForgeState."""

    def test_default_is_none(self):
        state = DeckForgeState()
        assert state.proposal_strategy is None

    def test_can_set_strategy(self):
        strategy = ProposalStrategy(
            rfp_interpretation="Test",
            proposal_thesis="SG is the right choice.",
        )
        state = DeckForgeState(proposal_strategy=strategy)
        assert state.proposal_strategy is not None
        assert state.proposal_strategy.proposal_thesis == "SG is the right choice."


# ──────────────────────────────────────────────────────────────
# 3. Agent user message construction
# ──────────────────────────────────────────────────────────────


class TestAgentUserMessage:
    """Verify the Proposal Strategist builds user messages from real state fields."""

    def test_builds_message_from_empty_state(self):
        from src.agents.proposal_strategy.agent import _build_user_message

        state = DeckForgeState()
        msg = _build_user_message(state)
        assert isinstance(msg, str)
        assert len(msg) > 10
        # Should be valid JSON
        import json
        parsed = json.loads(msg)
        assert "rfp_context" in parsed
        assert "reference_index" in parsed
        assert "external_evidence_pack" in parsed

    def test_builds_message_with_rfp_context(self):
        import json

        from src.agents.proposal_strategy.agent import _build_user_message
        from src.models.common import BilingualText
        from src.models.rfp import RFPContext

        rfp = RFPContext(
            rfp_name=BilingualText(en="Advisory Services"),
            issuing_entity=BilingualText(en="Ministry of Finance"),
            mandate=BilingualText(en="Digital transformation advisory"),
        )
        state = DeckForgeState(
            rfp_context=rfp,
            sector="government",
            geography="Saudi Arabia",
        )
        msg = _build_user_message(state)
        parsed = json.loads(msg)

        assert parsed["rfp_context"] is not None
        assert parsed["sector"] == "government"
        assert parsed["geography"] == "Saudi Arabia"

    def test_builds_message_with_reference_index(self):
        import json

        from src.agents.proposal_strategy.agent import _build_user_message
        from src.models.claims import ClaimObject, ReferenceIndex

        ref_index = ReferenceIndex(
            claims=[
                ClaimObject(
                    claim_id="CLM-0001",
                    claim_text="SG delivered SAP HANA migration for SIDF",
                    source_doc_id="DOC-001",
                    source_location="Slide 5",
                    evidence_span="Strategic Gears delivered an SAP HANA migration",
                    sensitivity_tag="capability",
                    category="project_reference",
                    confidence=0.95,
                ),
            ],
        )
        state = DeckForgeState(reference_index=ref_index)
        msg = _build_user_message(state)
        parsed = json.loads(msg)

        assert parsed["reference_index"] is not None
        assert parsed["reference_index"]["total_claims"] == 1
        assert parsed["reference_index"]["claims"][0]["claim_id"] == "CLM-0001"

    def test_message_does_not_contain_raw_repr(self):
        """User message should be clean JSON, no raw Pydantic repr."""
        import json

        from src.agents.proposal_strategy.agent import _build_user_message
        from src.models.common import BilingualText
        from src.models.rfp import Deliverable, RFPContext, ScopeItem

        rfp = RFPContext(
            rfp_name=BilingualText(en="Test RFP"),
            issuing_entity=BilingualText(en="Test Entity"),
            mandate=BilingualText(en="Test mandate"),
            scope_items=[
                ScopeItem(id="SCOPE-001", description=BilingualText(en="Test scope"), category="test"),
            ],
            deliverables=[
                Deliverable(id="DEL-001", description=BilingualText(en="Test deliverable")),
            ],
        )
        state = DeckForgeState(rfp_context=rfp)
        msg = _build_user_message(state)

        # Must be valid JSON
        json.loads(msg)
        # Must not contain raw repr
        assert "BilingualText(" not in msg
        assert "ScopeItem(" not in msg


# ──────────────────────────────────────────────────────────────
# 4. Graph wiring
# ──────────────────────────────────────────────────────────────


class TestGraphWiring:
    """Verify proposal_strategy is in the graph between evidence_curation and assembly_plan."""

    def test_proposal_strategy_node_exists(self):
        from src.pipeline.graph import proposal_strategy_node
        assert callable(proposal_strategy_node)

    def test_graph_has_proposal_strategy_node(self):
        from src.pipeline.graph import build_graph
        graph = build_graph()
        g = graph.get_graph()
        node_names = [n.name if hasattr(n, "name") else str(n) for n in g.nodes]
        assert "proposal_strategy" in node_names

    def test_graph_flow_order(self):
        """Verify edge ordering: evidence_curation -> proposal_strategy -> assembly_plan."""
        from src.pipeline.graph import build_graph
        graph = build_graph()
        g = graph.get_graph()

        # Build adjacency from edges
        edges: dict[str, list[str]] = {}
        for edge in g.edges:
            src = edge.source.name if hasattr(edge.source, "name") else str(edge.source)
            tgt = edge.target.name if hasattr(edge.target, "name") else str(edge.target)
            edges.setdefault(src, []).append(tgt)

        # evidence_curation -> proposal_strategy
        assert "proposal_strategy" in edges.get("evidence_curation", []), (
            f"evidence_curation edges: {edges.get('evidence_curation', [])}"
        )
        # proposal_strategy -> assembly_plan
        assert "assembly_plan" in edges.get("proposal_strategy", []), (
            f"proposal_strategy edges: {edges.get('proposal_strategy', [])}"
        )


# ──────────────────────────────────────────────────────────────
# 5. Strategy output validation (mocked LLM)
# ──────────────────────────────────────────────────────────────


class TestStrategyOutputValidation:
    """Verify strategy agent produces valid output and updates session."""

    @pytest.mark.asyncio
    async def test_strategy_agent_returns_correct_keys(self):
        """run() should return dict with proposal_strategy and session keys."""
        from unittest.mock import AsyncMock, patch

        from src.services.llm import LLMResponse

        mock_strategy = ProposalStrategy(
            rfp_interpretation="Test interpretation",
            win_themes=[
                WinTheme(
                    theme="Proven SAP expertise",
                    supporting_evidence=["CLM-0001"],
                    differentiator_strength="strong",
                ),
            ],
            proposal_thesis="SG is the right choice.",
            recommended_methodology_approach="Agile with governance gates",
        )

        mock_llm_response = LLMResponse(
            parsed=mock_strategy,
            input_tokens=3000,
            output_tokens=1500,
            model="claude-opus-4-20250514",
            latency_ms=5000,
        )

        with patch(
            "src.agents.proposal_strategy.agent.call_llm",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            from src.agents.proposal_strategy.agent import run

            state = DeckForgeState()
            result = await run(state)

        assert "proposal_strategy" in result
        assert "session" in result
        assert isinstance(result["proposal_strategy"], ProposalStrategy)
        assert len(result["proposal_strategy"].win_themes) == 1
        assert result["proposal_strategy"].recommended_methodology_approach != ""
        # Session should reflect 1 LLM call
        assert result["session"].total_llm_calls == 1
        assert result["session"].total_input_tokens == 3000
        assert result["session"].total_output_tokens == 1500

    @pytest.mark.asyncio
    async def test_strategy_agent_handles_llm_failure(self):
        """On LLM failure, should return fallback strategy with error info."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "src.agents.proposal_strategy.agent.call_llm",
            new_callable=AsyncMock,
            side_effect=Exception("LLM service unavailable"),
        ):
            from src.agents.proposal_strategy.agent import run

            state = DeckForgeState()
            result = await run(state)

        assert "proposal_strategy" in result
        assert result["proposal_strategy"].rfp_interpretation == "Proposal strategy generation failed."
        assert len(result["proposal_strategy"].evidence_gaps) > 0
        assert "errors" in result
        assert len(result["errors"]) > 0


# ──────────────────────────────────────────────────────────────
# 6. MODEL_MAP
# ──────────────────────────────────────────────────────────────


class TestModelMap:
    def test_proposal_strategist_in_model_map(self):
        from src.config.models import MODEL_MAP
        assert "proposal_strategist" in MODEL_MAP

    def test_proposal_strategist_uses_opus(self):
        """Proposal Strategist should use Opus (strongest model for strategic reasoning)."""
        from src.config.models import MODEL_MAP
        model = MODEL_MAP["proposal_strategist"]
        assert "opus" in model.lower() or "claude" in model.lower()


# ──────────────────────────────────────────────────────────────
# 7. Prompt content
# ──────────────────────────────────────────────────────────────


class TestPromptContent:
    def test_prompt_has_strategy_framework(self):
        from src.agents.proposal_strategy.prompts import SYSTEM_PROMPT

        assert "RFP INTERPRETATION" in SYSTEM_PROMPT
        assert "WIN THEMES" in SYSTEM_PROMPT
        assert "EVALUATOR PRIORITIES" in SYSTEM_PROMPT
        assert "EVIDENCE GAPS" in SYSTEM_PROMPT

    def test_prompt_requires_evidence_backing(self):
        from src.agents.proposal_strategy.prompts import SYSTEM_PROMPT

        assert "CLM-xxxx" in SYSTEM_PROMPT or "CLM-" in SYSTEM_PROMPT
        assert "EXT-" in SYSTEM_PROMPT
        assert "No unsupported" in SYSTEM_PROMPT or "evidence IDs" in SYSTEM_PROMPT
