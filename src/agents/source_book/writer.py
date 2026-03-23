"""Source Book Writer agent — synthesizes evidence and strategy into Source Book.

Consumes reference_index, external_evidence_pack, proposal_strategy, and
rfp_context to produce a structured SourceBook with 7 sections. Every claim
must cite its source (CLM-xxxx for internal, EXT-xxx for external).
"""

from __future__ import annotations

import json
import logging
import re

from src.config.models import MODEL_MAP
from src.models.source_book import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    RFPInterpretation,
    SourceBook,
)
from src.models.state import DeckForgeState
from src.services.llm import call_llm

from .prompts import WRITER_SYSTEM_PROMPT as SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Patterns for citation references in source book text
_CLM_PATTERN = re.compile(r"CLM-\d{4}")
_EXT_PATTERN = re.compile(r"EXT-\d{3}")


def _build_evidence_ledger_from_citations(source_book: SourceBook) -> EvidenceLedger:
    """Scan sections 1-6 for CLM-xxxx / EXT-xxx citations and build a ledger.

    Fallback when the LLM omits or truncates Section 7.
    """
    # Collect all text from sections 1-6 by serializing to JSON
    sections_data = {
        "rfp_interpretation": source_book.rfp_interpretation.model_dump(mode="json"),
        "client_problem_framing": source_book.client_problem_framing.model_dump(mode="json"),
        "why_strategic_gears": source_book.why_strategic_gears.model_dump(mode="json"),
        "external_evidence": source_book.external_evidence.model_dump(mode="json"),
        "proposed_solution": source_book.proposed_solution.model_dump(mode="json"),
        "slide_blueprints": [bp.model_dump(mode="json") for bp in source_book.slide_blueprints],
    }
    text_blob = json.dumps(sections_data, ensure_ascii=False, default=str)

    # Find unique citation IDs
    clm_ids = sorted(set(_CLM_PATTERN.findall(text_blob)))
    ext_ids = sorted(set(_EXT_PATTERN.findall(text_blob)))

    entries: list[EvidenceLedgerEntry] = []
    for cid in clm_ids:
        entries.append(
            EvidenceLedgerEntry(
                claim_id=cid,
                claim_text=f"Auto-extracted citation {cid}",
                source_type="internal",
                source_reference=cid,
                confidence=0.5,
                verifiability_status="unverified",
            )
        )
    for eid in ext_ids:
        entries.append(
            EvidenceLedgerEntry(
                claim_id=eid,
                claim_text=f"Auto-extracted citation {eid}",
                source_type="external",
                source_reference=eid,
                confidence=0.5,
                verifiability_status="unverified",
            )
        )

    logger.info(
        "Built evidence ledger from citations: %d CLM + %d EXT = %d entries",
        len(clm_ids),
        len(ext_ids),
        len(entries),
    )
    return EvidenceLedger(entries=entries)


def _build_user_message(
    state: DeckForgeState,
    reviewer_feedback: str = "",
) -> str:
    """Build the user message from state fields.

    Serializes all upstream data into a JSON payload for the LLM.
    On rewrite passes, includes reviewer feedback.
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
                    "evidence_span": c.evidence_span,
                    "confidence": c.confidence,
                    "category": c.category,
                }
                for c in ri.claims[:150]  # cap at 150 claims for writer
            ],
            "case_studies": [
                cs.model_dump(mode="json") for cs in ri.case_studies[:30]
            ],
            "team_profiles": [
                tp.model_dump(mode="json") for tp in ri.team_profiles[:40]
            ],
            "compliance_evidence": [
                ce.model_dump(mode="json") for ce in ri.compliance_evidence[:30]
            ],
            "frameworks": [
                fw.model_dump(mode="json") for fw in ri.frameworks[:15]
            ],
            "gaps": [
                g.model_dump(mode="json") for g in ri.gaps[:30]
            ],
        }

    # External evidence pack
    ext_evidence_dump = None
    if state.external_evidence_pack:
        ext_evidence_dump = state.external_evidence_pack.model_dump(mode="json")

    # Proposal strategy
    strategy_dump = None
    if state.proposal_strategy:
        strategy_dump = state.proposal_strategy.model_dump(mode="json")

    # Previous source book (for rewrite passes)
    previous_book_dump = None
    if state.source_book:
        previous_book_dump = state.source_book.model_dump(mode="json")

    # Knowledge graph — named people, projects, clients
    kg_dump = None
    if state.knowledge_graph:
        kg = state.knowledge_graph
        kg_dump = {
            "people": [
                {
                    "person_id": p.person_id,
                    "name": p.name,
                    "current_role": p.current_role,
                    "company": p.company,
                    "years_experience": p.years_experience,
                    "certifications": p.certifications,
                    "domain_expertise": p.domain_expertise,
                    "projects": p.projects,
                }
                for p in kg.people
                if p.person_type == "internal_team"
            ],
            "projects": [
                {
                    "project_id": pr.project_id,
                    "project_name": pr.project_name,
                    "client": pr.client,
                    "sector": pr.sector,
                    "domain_tags": pr.domain_tags,
                    "outcomes": pr.outcomes,
                    "methodologies": pr.methodologies,
                }
                for pr in kg.projects[:30]
            ],
            "clients": [
                {
                    "client_id": c.client_id,
                    "name": c.name,
                    "client_type": c.client_type,
                    "sector": c.sector,
                }
                for c in kg.clients[:20]
            ],
        }

    payload = {
        "rfp_context": rfp_dump,
        "reference_index": ref_index_dump,
        "knowledge_graph": kg_dump,
        "external_evidence_pack": ext_evidence_dump,
        "proposal_strategy": strategy_dump,
        "previous_source_book": previous_book_dump,
        "reviewer_feedback": reviewer_feedback,
        "output_language": state.output_language,
        "sector": state.sector,
        "geography": state.geography,
    }

    return json.dumps(payload, ensure_ascii=False, default=str)


async def run(state: DeckForgeState, reviewer_feedback: str = "") -> dict:
    """Run the Source Book Writer agent.

    Returns a dict with keys matching DeckForgeState fields to update.
    """
    user_message = _build_user_message(state, reviewer_feedback=reviewer_feedback)

    logger.info(
        "Source Book Writer payload: chars=%d, has_ref_index=%s, "
        "has_strategy=%s, rewrite=%s",
        len(user_message),
        state.reference_index is not None,
        state.proposal_strategy is not None,
        bool(reviewer_feedback),
    )

    model = MODEL_MAP.get("source_book_writer", MODEL_MAP.get("analysis_agent"))

    try:
        llm_result = await call_llm(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=SourceBook,
            max_tokens=24000,
            temperature=0.1,
        )

        source_book = llm_result.parsed

        # Set pass number
        current_pass = 1
        if state.source_book:
            current_pass = state.source_book.pass_number + 1
        source_book.pass_number = current_pass

        # Validate: warn if no slide blueprints
        if not source_book.slide_blueprints:
            logger.warning(
                "Source Book Writer produced 0 slide blueprints — "
                "downstream Blueprint extraction will fail"
            )

        # Validate: if evidence ledger is empty, try to populate from citations
        if not source_book.evidence_ledger.entries:
            logger.warning(
                "Source Book Writer produced empty evidence ledger — "
                "attempting to build from citations"
            )
            source_book.evidence_ledger = _build_evidence_ledger_from_citations(
                source_book,
            )
            # Determine max_passes from pipeline config (default 5)
            max_passes = 5
            if source_book.evidence_ledger.entries:
                logger.info(
                    "Evidence ledger populated from citations: %d entries",
                    len(source_book.evidence_ledger.entries),
                )
            elif current_pass >= max_passes - 1:
                logger.error(
                    "Evidence ledger is STILL empty on pass %d (last pass) — "
                    "no citations found in sections 1-6",
                    current_pass,
                )

        logger.info(
            "Source Book written: pass=%d, blueprints=%d, "
            "evidence_entries=%d, capabilities=%d",
            current_pass,
            len(source_book.slide_blueprints),
            len(source_book.evidence_ledger.entries),
            len(source_book.why_strategic_gears.capability_mapping),
        )

        # Update session accounting
        session = state.session.model_copy(deep=True)
        session.total_llm_calls += 1
        session.total_input_tokens += llm_result.input_tokens
        session.total_output_tokens += llm_result.output_tokens

        return {
            "source_book": source_book,
            "session": session,
        }

    except Exception as e:
        logger.error("Source Book Writer failed: %s", e)
        from src.models.state import ErrorInfo

        return {
            "source_book": SourceBook(
                rfp_interpretation=RFPInterpretation(
                    objective_and_scope="Source Book generation failed.",
                ),
            ),
            "errors": state.errors + [
                ErrorInfo(
                    agent="source_book_writer",
                    error_type="LLMError",
                    message=str(e),
                ),
            ],
            "last_error": ErrorInfo(
                agent="source_book_writer",
                error_type="LLMError",
                message=str(e),
            ),
        }
