"""Proposal Strategist agent — strategic reasoning for proposal development.

Consumes RFP context, reference index (internal evidence), and external
evidence pack to produce a ProposalStrategy with win themes, evaluator
priorities, and a proposal thesis.
"""

from __future__ import annotations

import json
import logging

from src.config.models import MODEL_MAP
from src.models.proposal_strategy import ProposalStrategy
from src.models.state import DeckForgeState
from src.services.llm import call_llm

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _build_user_message(state: DeckForgeState) -> str:
    """Build the user message from state fields.

    Serializes RFP context, reference index, and external evidence pack
    into a JSON payload for the LLM. Truncates large fields to stay
    within token limits.
    """
    # RFP context
    rfp_dump = None
    if state.rfp_context:
        rfp_dump = state.rfp_context.model_dump(mode="json")

    # Reference index — compact to relevant fields
    ref_index_dump = None
    if state.reference_index:
        ri = state.reference_index
        ref_index_dump = {
            "total_claims": len(ri.claims),
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "claim_text": c.claim_text,
                    "source_doc_id": c.source_doc_id,
                    "confidence": c.confidence,
                    "category": c.category,
                }
                for c in ri.claims[:100]  # cap at 100 claims
            ],
            "case_studies": [
                cs.model_dump(mode="json") for cs in ri.case_studies[:20]
            ],
            "team_profiles": [
                tp.model_dump(mode="json") for tp in ri.team_profiles[:30]
            ],
            "compliance_evidence": [
                ce.model_dump(mode="json") for ce in ri.compliance_evidence[:20]
            ],
            "frameworks": [
                fw.model_dump(mode="json") for fw in ri.frameworks[:10]
            ],
            "gaps": [
                g.model_dump(mode="json") for g in ri.gaps[:20]
            ],
        }

    # External evidence pack
    ext_evidence_dump = None
    if state.external_evidence_pack:
        ext_evidence_dump = state.external_evidence_pack.model_dump(mode="json")

    payload = {
        "rfp_context": rfp_dump,
        "reference_index": ref_index_dump,
        "external_evidence_pack": ext_evidence_dump,
        "output_language": state.output_language,
        "sector": state.sector,
        "geography": state.geography,
    }

    return json.dumps(payload, ensure_ascii=False, default=str)


async def run(state: DeckForgeState) -> dict:
    """Run the Proposal Strategist agent.

    Returns a dict with keys matching DeckForgeState fields to update.
    """
    user_message = _build_user_message(state)

    logger.info(
        "Proposal Strategist payload: chars=%d, has_ref_index=%s, has_ext_evidence=%s",
        len(user_message),
        state.reference_index is not None,
        state.external_evidence_pack is not None,
    )

    model = MODEL_MAP.get("proposal_strategist", MODEL_MAP.get("analysis_agent"))

    try:
        llm_result = await call_llm(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=ProposalStrategy,
            max_tokens=8000,
            temperature=0.1,  # slight creativity for strategic reasoning
        )

        strategy = llm_result.parsed

        # Validate: warn if no strong win themes
        strong_themes = [
            t for t in strategy.win_themes
            if t.differentiator_strength in ("unique", "strong")
        ]
        if not strong_themes:
            logger.warning(
                "Proposal Strategist produced %d win themes but NONE with "
                "'unique' or 'strong' differentiator strength",
                len(strategy.win_themes),
            )

        # Validate: warn if all evaluator priorities have weak/no evidence
        if strategy.unstated_evaluator_priorities:
            all_weak = all(
                p.evidence_available in ("weak", "none")
                for p in strategy.unstated_evaluator_priorities
            )
            if all_weak:
                logger.warning(
                    "CRITICAL: All %d evaluator priorities have 'weak' or 'none' "
                    "evidence — proposal may not be competitive",
                    len(strategy.unstated_evaluator_priorities),
                )

        logger.info(
            "Proposal strategy complete: %d win themes, %d evaluator priorities, "
            "%d evidence gaps",
            len(strategy.win_themes),
            len(strategy.unstated_evaluator_priorities),
            len(strategy.evidence_gaps),
        )

        # Update session accounting
        session = state.session.model_copy(deep=True)
        session.total_llm_calls += 1
        session.total_input_tokens += llm_result.input_tokens
        session.total_output_tokens += llm_result.output_tokens
        session.total_cost_usd += llm_result.cost_usd

        return {
            "proposal_strategy": strategy,
            "session": session,
        }

    except Exception as e:
        logger.error("Proposal Strategist failed: %s", e)
        from src.models.state import ErrorInfo

        return {
            "proposal_strategy": ProposalStrategy(
                rfp_interpretation="Proposal strategy generation failed.",
                evidence_gaps=[f"Strategy agent error: {e}"],
            ),
            "errors": state.errors + [
                ErrorInfo(
                    agent="proposal_strategist",
                    error_type="LLMError",
                    message=str(e),
                ),
            ],
            "last_error": ErrorInfo(
                agent="proposal_strategist",
                error_type="LLMError",
                message=str(e),
            ),
        }
