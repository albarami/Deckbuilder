"""Source Book Writer agent — split-call architecture for deep content.

Consumes reference_index, external_evidence_pack, proposal_strategy, and
rfp_context to produce a structured SourceBook with 7 sections.

Split-call architecture:
  Stage 1a: Sections 1-2 (RFP Interpretation + Client Problem Framing)
  Stage 1b: Section 3 (Why Strategic Gears — team, projects, capabilities)
  Stage 1c: Section 4 (External Evidence curation)
  Stage 1d: Section 5 (Proposed Solution — methodology, governance, timeline)
  Stage 2a: Section 6 (Slide blueprints)
  Stage 2b: Section 7 (Evidence ledger)

Each stage gets its own LLM call with full token budget so the model
can produce deep prose content without JSON overhead from other sections
competing for tokens.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from src.config.models import MODEL_MAP
from src.models.source_book import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    RFPInterpretation,
    SourceBook,
    SourceBookSection3,
    SourceBookSection4,
    SourceBookSection5,
    SourceBookSection6,
    SourceBookSection7,
    SourceBookSections12,
)
from src.models.state import DeckForgeState
from src.services.llm import call_llm

from .prompts import (
    STAGE1A_SECTIONS12_PROMPT,
    STAGE1B_SECTION3_PROMPT,
    STAGE1C_SECTION4_PROMPT,
    STAGE1D_SECTION5_PROMPT,
    STAGE2A_BLUEPRINTS_PROMPT,
    STAGE2B_EVIDENCE_LEDGER_PROMPT,
    WRITER_SYSTEM_PROMPT,
)

# Legacy alias used by tests
SYSTEM_PROMPT = WRITER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Patterns for citation references in source book text
_CLM_PATTERN = re.compile(r"CLM-\d{4}")
_EXT_PATTERN = re.compile(r"EXT-\d{3}")

# Banned hedge words/phrases for executive tone enforcement
_HEDGE_PATTERNS = [
    "illustrative",
    "pending",
    "preliminary",
    "indicative",
    "subject to",
    "may require",
    "could be",
    "would need",
    "to be determined",
    "further analysis",
    "TBD",
    "to be confirmed",
    "validation required",
    "could potentially",
    "may be adjusted",
]


def _build_evidence_ledger_from_citations(source_book: SourceBook) -> EvidenceLedger:
    """Scan sections 1-6 for CLM-xxxx / EXT-xxx citations and build a ledger."""
    sections_data = {
        "rfp_interpretation": source_book.rfp_interpretation.model_dump(mode="json"),
        "client_problem_framing": source_book.client_problem_framing.model_dump(mode="json"),
        "why_strategic_gears": source_book.why_strategic_gears.model_dump(mode="json"),
        "external_evidence": source_book.external_evidence.model_dump(mode="json"),
        "proposed_solution": source_book.proposed_solution.model_dump(mode="json"),
        "slide_blueprints": [bp.model_dump(mode="json") for bp in source_book.slide_blueprints],
    }
    text_blob = json.dumps(sections_data, ensure_ascii=False, default=str)

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


def _scan_for_hedges(source_book: SourceBook) -> list[str]:
    """Scan all text fields for banned hedge phrases."""
    text_blob = json.dumps(
        source_book.model_dump(mode="json"),
        ensure_ascii=False,
        default=str,
    )
    matches: list[str] = []
    for phrase in _HEDGE_PATTERNS:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, text_blob, re.IGNORECASE):
            matches.append(phrase)
    return matches


def _strip_dangling_ext_citations(
    source_book: SourceBook,
    state: DeckForgeState,
) -> SourceBook:
    """Remove EXT-xxx citations that don't exist in the external evidence pack."""
    valid_ext_ids: set[str] = set()
    if state.external_evidence_pack:
        for src in getattr(state.external_evidence_pack, "sources", []):
            sid = getattr(src, "source_id", "")
            if sid:
                valid_ext_ids.add(sid)

    text_blob = json.dumps(
        source_book.model_dump(mode="json"),
        ensure_ascii=False,
        default=str,
    )
    all_ext_ids = set(_EXT_PATTERN.findall(text_blob))
    dangling = all_ext_ids - valid_ext_ids

    if not dangling:
        logger.info("EXT citation check: all %d EXT IDs are valid", len(all_ext_ids))
        return source_book

    logger.warning(
        "EXT citation check: stripping %d dangling IDs: %s (valid: %s)",
        len(dangling),
        sorted(dangling),
        sorted(valid_ext_ids),
    )

    dangling_pattern = re.compile(
        r"\s*\[?(" + "|".join(re.escape(d) for d in dangling) + r")\]?\s*"
    )

    def _clean_str(val: str) -> str:
        return dangling_pattern.sub(" ", val).strip()

    def _clean_list(items: list[str]) -> list[str]:
        return [_clean_str(s) for s in items if _clean_str(s)]

    for bp in source_book.slide_blueprints:
        if bp.proof_points:
            bp.proof_points = [p for p in bp.proof_points if p not in dangling]
        if bp.must_have_evidence:
            bp.must_have_evidence = [m for m in bp.must_have_evidence if m not in dangling]
        if bp.bullet_logic:
            bp.bullet_logic = _clean_list(bp.bullet_logic)

    if source_book.evidence_ledger.entries:
        original_count = len(source_book.evidence_ledger.entries)
        source_book.evidence_ledger.entries = [
            e for e in source_book.evidence_ledger.entries
            if e.claim_id not in dangling
        ]
        removed = original_count - len(source_book.evidence_ledger.entries)
        if removed:
            logger.info("Removed %d dangling EXT entries from evidence ledger", removed)

    return source_book


async def _rewrite_hedges(
    source_book: SourceBook,
    hedges_found: list[str],
) -> SourceBook:
    """Make one LLM call to rewrite sentences containing banned hedges."""
    hedge_list = ", ".join(f'"{h}"' for h in hedges_found)

    system = (
        "You are an executive writing editor. The Source Book below "
        "contains hedging language that must be removed. Rewrite every "
        "sentence containing a banned word with direct, confident statements. "
        f"Remove ALL instances of: {hedge_list}. "
        "Do NOT change any other content. Output the full corrected SourceBook JSON."
    )

    user_msg = json.dumps(
        source_book.model_dump(mode="json"),
        ensure_ascii=False,
        default=str,
    )

    model = MODEL_MAP.get("source_book_writer", MODEL_MAP.get("analysis_agent"))

    try:
        async with asyncio.timeout(120):
            result = await call_llm(
                model=model,
                system_prompt=system,
                user_message=user_msg,
                response_model=SourceBook,
                max_tokens=32000,
                temperature=0.0,
            )
        cleaned = result.parsed
        cleaned.pass_number = source_book.pass_number
        if not cleaned.slide_blueprints and source_book.slide_blueprints:
            cleaned.slide_blueprints = source_book.slide_blueprints
        if not cleaned.evidence_ledger.entries and source_book.evidence_ledger.entries:
            cleaned.evidence_ledger = source_book.evidence_ledger
        logger.info("Hedge rewrite complete — removed %d hedge patterns", len(hedges_found))
        return cleaned
    except Exception as e:
        logger.warning("Hedge rewrite failed: %s — keeping original", e)
        return source_book


def _build_shared_context(
    state: DeckForgeState,
    reviewer_feedback: str = "",
) -> dict:
    """Build the shared context dict that all stage calls can draw from."""
    rfp_dump = None
    if state.rfp_context:
        rfp_dump = state.rfp_context.model_dump(mode="json")

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
                for c in ri.claims[:150]
            ],
            "case_studies": [cs.model_dump(mode="json") for cs in ri.case_studies[:30]],
            "team_profiles": [tp.model_dump(mode="json") for tp in ri.team_profiles[:40]],
            "compliance_evidence": [ce.model_dump(mode="json") for ce in ri.compliance_evidence[:30]],
            "frameworks": [fw.model_dump(mode="json") for fw in ri.frameworks[:15]],
            "gaps": [g.model_dump(mode="json") for g in ri.gaps[:30]],
        }

    ext_evidence_dump = None
    if state.external_evidence_pack:
        ext_evidence_dump = state.external_evidence_pack.model_dump(mode="json")

    strategy_dump = None
    if state.proposal_strategy:
        strategy_dump = state.proposal_strategy.model_dump(mode="json")

    kg_dump = None
    if state.knowledge_graph:
        kg = state.knowledge_graph
        internal_people = [
            p for p in kg.people if p.person_type == "internal_team"
        ]
        kg_dump = {
            # Explicit counts so the LLM knows exactly what data exists
            "_DATA_BOUNDARY": {
                "internal_team_count": len(internal_people),
                "project_count": len(kg.projects),
                "client_count": len(kg.clients),
                "WARNING": (
                    f"You have EXACTLY {len(internal_people)} named team members "
                    f"and {len(kg.projects)} projects in the knowledge graph. "
                    "Do NOT invent additional names or projects beyond this data. "
                    "Use open_role_profile for team roles without KG matches."
                ),
            },
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
                for p in internal_people
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

    # Timeline and team constraints from RFP
    rfp_timeline_dump = None
    rfp_team_requirements_dump = None
    mandatory_constraints: list[str] = []
    if state.rfp_context:
        if state.rfp_context.project_timeline:
            rfp_timeline_dump = state.rfp_context.project_timeline.model_dump(mode="json")
        if state.rfp_context.team_requirements:
            rfp_team_requirements_dump = [
                tr.model_dump(mode="json") for tr in state.rfp_context.team_requirements
            ]

    if rfp_timeline_dump:
        dur = rfp_timeline_dump.get("total_duration", "")
        months = rfp_timeline_dump.get("total_duration_months")
        if dur or months:
            mandatory_constraints.append(
                f"MANDATORY TIMELINE: The RFP states the project duration is "
                f"{dur or str(months) + ' months'}. Use this EXACT duration."
            )
        sched = rfp_timeline_dump.get("deliverable_schedule", [])
        if sched:
            milestones = "; ".join(
                f"{s.get('milestone', '?')} due {s.get('due_date', '?')}" for s in sched
            )
            mandatory_constraints.append(f"MANDATORY MILESTONES: {milestones}")

    if rfp_team_requirements_dump:
        roles = []
        for req in rfp_team_requirements_dump:
            rt = req.get("role_title", {})
            title = rt.get("en") or rt.get("ar") or str(rt)
            edu = req.get("education", "")
            certs = req.get("certifications", [])
            yrs = req.get("min_years_experience")
            parts = [title]
            if edu:
                parts.append(edu)
            if certs:
                parts.append(", ".join(certs))
            if yrs:
                parts.append(f"{yrs}+ years")
            roles.append(" / ".join(parts))
        if roles:
            mandatory_constraints.append(
                "MANDATORY TEAM ROLES (from RFP): "
                + " | ".join(roles)
                + ". Map each RFP role to a proposed consultant."
            )

    available_ext_ids: list[str] = []
    if state.external_evidence_pack:
        for src in getattr(state.external_evidence_pack, "sources", []):
            sid = getattr(src, "source_id", "")
            if sid:
                available_ext_ids.append(sid)

    return {
        "mandatory_constraints": mandatory_constraints or None,
        "available_ext_ids": available_ext_ids or None,
        "rfp_context": rfp_dump,
        "rfp_project_timeline": rfp_timeline_dump,
        "rfp_team_requirements": rfp_team_requirements_dump,
        "reference_index": ref_index_dump,
        "knowledge_graph": kg_dump,
        "external_evidence_pack": ext_evidence_dump,
        "proposal_strategy": strategy_dump,
        "reviewer_feedback": reviewer_feedback or None,
        "output_language": state.output_language,
        "sector": state.sector,
        "geography": state.geography,
    }


def _build_stage_payload(
    shared_ctx: dict,
    previous_section_data: dict | None = None,
    keep_keys: list[str] | None = None,
    drop_keys: list[str] | None = None,
) -> str:
    """Build a JSON payload for a stage call with context filtering.

    Args:
        shared_ctx: Full shared context from _build_shared_context.
        previous_section_data: Previous section output for rewrite passes.
        keep_keys: If provided, ONLY include these keys from shared_ctx.
        drop_keys: If provided, DROP these keys from shared_ctx.

    This ensures each stage receives only the context it needs, keeping
    the input payload small enough that max_tokens isn't consumed by input.
    """
    if keep_keys:
        payload = {k: shared_ctx[k] for k in keep_keys if k in shared_ctx}
    elif drop_keys:
        payload = {k: v for k, v in shared_ctx.items() if k not in drop_keys}
    else:
        payload = dict(shared_ctx)
    if previous_section_data:
        payload["previous_section_content"] = previous_section_data
    return json.dumps(payload, ensure_ascii=False, default=str)


def _dump_sections_15(source_book: SourceBook) -> str:
    """Serialize Sections 1-5 as JSON context for Stage 2a/2b."""
    return json.dumps(
        {
            "client_name": source_book.client_name,
            "rfp_name": source_book.rfp_name,
            "language": source_book.language,
            "rfp_interpretation": source_book.rfp_interpretation.model_dump(mode="json"),
            "client_problem_framing": source_book.client_problem_framing.model_dump(mode="json"),
            "why_strategic_gears": source_book.why_strategic_gears.model_dump(mode="json"),
            "external_evidence": source_book.external_evidence.model_dump(mode="json"),
            "proposed_solution": source_book.proposed_solution.model_dump(mode="json"),
        },
        ensure_ascii=False,
        default=str,
    )


async def _generate_sections_12(
    shared_ctx: dict,
    model: str,
    previous_book: SourceBook | None = None,
) -> SourceBookSections12:
    """Stage 1a: Sections 1-2 (RFP Interpretation + Client Problem Framing).

    Needs: rfp_context, proposal_strategy, reference_index (for compliance mapping),
    mandatory_constraints, reviewer_feedback, output_language.
    Drops: knowledge_graph, external_evidence_pack (not needed for RFP interpretation).
    """
    prev_data = None
    if previous_book:
        prev_data = {
            "rfp_interpretation": previous_book.rfp_interpretation.model_dump(mode="json"),
            "client_problem_framing": previous_book.client_problem_framing.model_dump(mode="json"),
        }
    payload = _build_stage_payload(
        shared_ctx, prev_data,
        drop_keys=["knowledge_graph", "external_evidence_pack"],
    )
    logger.info("Stage 1a (Sections 1-2): input chars=%d", len(payload))

    result = await call_llm(
        model=model,
        system_prompt=STAGE1A_SECTIONS12_PROMPT,
        user_message=payload,
        response_model=SourceBookSections12,
        max_tokens=16000,
        temperature=0.1,
    )

    s12 = result.parsed
    logger.info(
        "Stage 1a complete: compliance_items=%d",
        len(s12.rfp_interpretation.key_compliance_requirements),
    )
    return s12


async def _generate_section_3(
    shared_ctx: dict,
    model: str,
    previous_book: SourceBook | None = None,
) -> SourceBookSection3:
    """Stage 1b: Section 3 (Why Strategic Gears).

    Needs: knowledge_graph (team, projects), reference_index, mandatory_constraints
    (for team roles), rfp_team_requirements, proposal_strategy, available_ext_ids.
    Drops: full rfp_context (too large), external_evidence_pack (not needed here).
    """
    prev_data = None
    if previous_book:
        prev_data = {
            "why_strategic_gears": previous_book.why_strategic_gears.model_dump(mode="json"),
        }
    payload = _build_stage_payload(
        shared_ctx, prev_data,
        keep_keys=[
            "knowledge_graph", "reference_index", "mandatory_constraints",
            "rfp_team_requirements", "proposal_strategy", "available_ext_ids",
            "reviewer_feedback", "output_language", "sector", "geography",
        ],
    )
    logger.info("Stage 1b (Section 3): input chars=%d", len(payload))

    result = await call_llm(
        model=model,
        system_prompt=STAGE1B_SECTION3_PROMPT,
        user_message=payload,
        response_model=SourceBookSection3,
        max_tokens=24000,
        temperature=0.1,
    )

    s3 = result.parsed
    logger.info(
        "Stage 1b complete: consultants=%d, projects=%d, capabilities=%d",
        len(s3.why_strategic_gears.named_consultants),
        len(s3.why_strategic_gears.project_experience),
        len(s3.why_strategic_gears.capability_mapping),
    )
    return s3


async def _generate_section_4(
    shared_ctx: dict,
    model: str,
    previous_book: SourceBook | None = None,
) -> SourceBookSection4:
    """Stage 1c: Section 4 (External Evidence).

    Needs: external_evidence_pack, available_ext_ids, proposal_strategy.
    Drops: rfp_context, knowledge_graph, reference_index (not needed for evidence curation).
    """
    prev_data = None
    if previous_book:
        prev_data = {
            "external_evidence": previous_book.external_evidence.model_dump(mode="json"),
        }
    payload = _build_stage_payload(
        shared_ctx, prev_data,
        keep_keys=[
            "external_evidence_pack", "available_ext_ids", "proposal_strategy",
            "reviewer_feedback", "output_language",
        ],
    )
    logger.info("Stage 1c (Section 4): input chars=%d", len(payload))

    result = await call_llm(
        model=model,
        system_prompt=STAGE1C_SECTION4_PROMPT,
        user_message=payload,
        response_model=SourceBookSection4,
        max_tokens=8000,
        temperature=0.1,
    )

    s4 = result.parsed
    logger.info(
        "Stage 1c complete: evidence_entries=%d",
        len(s4.external_evidence.entries),
    )
    return s4


async def _generate_section_5(
    shared_ctx: dict,
    model: str,
    previous_book: SourceBook | None = None,
) -> SourceBookSection5:
    """Stage 1d: Section 5 (Proposed Solution — highest weight).

    This is the MOST IMPORTANT section. It gets an RFP-rich but lean context:
    keeps ALL fields needed for elite methodology (scope, deliverables,
    evaluation criteria, compliance, team requirements, timeline, mandate)
    but drops raw document text and KG data that don't inform methodology.

    Quality principle: NEVER strip context that could make methodology
    more specific, more RFP-aligned, or more evaluator-targeted.
    """
    prev_data = None
    if previous_book:
        prev_data = {
            "proposed_solution": previous_book.proposed_solution.model_dump(mode="json"),
        }

    # Build an RFP-RICH payload — keep everything evaluators care about
    # for methodology, but drop knowledge_graph (team/projects not needed
    # for methodology design) and external_evidence_pack
    rfp_for_methodology = None
    if shared_ctx.get("rfp_context"):
        rfp = shared_ctx["rfp_context"]
        rfp_for_methodology = {
            "rfp_name": rfp.get("rfp_name", ""),
            "issuing_entity": rfp.get("issuing_entity", ""),
            "mandate": rfp.get("mandate", ""),
            "scope_items": rfp.get("scope_items", []),
            "deliverables": rfp.get("deliverables", []),
            "evaluation_criteria": rfp.get("evaluation_criteria"),
            "compliance_requirements": rfp.get("compliance_requirements", []),
            "team_requirements": rfp.get("team_requirements", []),
            "project_timeline": rfp.get("project_timeline"),
        }

    methodology_payload = {
        "mandatory_constraints": shared_ctx.get("mandatory_constraints"),
        "rfp_project_timeline": shared_ctx.get("rfp_project_timeline"),
        "rfp_team_requirements": shared_ctx.get("rfp_team_requirements"),
        "rfp_context": rfp_for_methodology,
        "proposal_strategy": shared_ctx.get("proposal_strategy"),
        "reference_index": shared_ctx.get("reference_index"),
        "available_ext_ids": shared_ctx.get("available_ext_ids"),
        "reviewer_feedback": shared_ctx.get("reviewer_feedback"),
        "output_language": shared_ctx.get("output_language"),
        "sector": shared_ctx.get("sector"),
        "geography": shared_ctx.get("geography"),
    }
    if prev_data:
        methodology_payload["previous_section_content"] = prev_data

    payload = json.dumps(methodology_payload, ensure_ascii=False, default=str)
    logger.info("Stage 1d (Section 5): input chars=%d", len(payload))

    result = await call_llm(
        model=model,
        system_prompt=STAGE1D_SECTION5_PROMPT,
        user_message=payload,
        response_model=SourceBookSection5,
        max_tokens=32000,
        temperature=0.1,
    )

    s5 = result.parsed
    logger.info(
        "Stage 1d complete: phases=%d, governance_len=%d, methodology_len=%d",
        len(s5.proposed_solution.phase_details),
        len(s5.proposed_solution.governance_framework),
        len(s5.proposed_solution.methodology_overview),
    )
    return s5


async def _generate_blueprints(
    source_book: SourceBook,
    model: str,
) -> SourceBookSection6:
    """Stage 2a: Dedicated LLM call for slide blueprints only."""
    context = _dump_sections_15(source_book)
    logger.info("Stage 2a (blueprints): input chars=%d", len(context))

    result = await call_llm(
        model=model,
        system_prompt=STAGE2A_BLUEPRINTS_PROMPT,
        user_message=context,
        response_model=SourceBookSection6,
        max_tokens=48000,
        temperature=0.1,
    )

    section6 = result.parsed
    logger.info("Stage 2a produced: %d blueprints", len(section6.slide_blueprints))
    return section6


async def _generate_evidence_ledger(
    source_book: SourceBook,
    model: str,
) -> SourceBookSection7:
    """Stage 2b: Dedicated LLM call for evidence ledger only."""
    context = json.dumps(
        {
            "sections_1_5": json.loads(_dump_sections_15(source_book)),
            "slide_blueprints": [
                bp.model_dump(mode="json") for bp in source_book.slide_blueprints
            ],
        },
        ensure_ascii=False,
        default=str,
    )
    logger.info("Stage 2b (evidence ledger): input chars=%d", len(context))

    result = await call_llm(
        model=model,
        system_prompt=STAGE2B_EVIDENCE_LEDGER_PROMPT,
        user_message=context,
        response_model=SourceBookSection7,
        max_tokens=16000,
        temperature=0.1,
    )

    section7 = result.parsed
    logger.info(
        "Stage 2b produced: %d evidence entries",
        len(section7.evidence_ledger.entries),
    )
    return section7


async def run(state: DeckForgeState, reviewer_feedback: str = "") -> dict:
    """Run the Source Book Writer agent (six-stage split-call architecture).

    Stage 1a: Sections 1-2 (RFP Interpretation + Problem Framing)
    Stage 1b: Section 3 (Why Strategic Gears)
    Stage 1c: Section 4 (External Evidence)
    Stage 1d: Section 5 (Proposed Solution / Methodology)
    Stage 2a: Section 6 (Slide blueprints)
    Stage 2b: Section 7 (Evidence ledger)

    Each stage gets its own LLM call and dedicated token budget.
    """
    model = MODEL_MAP.get("source_book_writer", MODEL_MAP.get("analysis_agent"))

    # Track fallback usage per pass
    fallback_events: list[str] = []

    # Determine pass number
    current_pass = 1
    if state.source_book:
        current_pass = state.source_book.pass_number + 1

    shared_ctx = _build_shared_context(state, reviewer_feedback=reviewer_feedback)
    previous_book = state.source_book if state.source_book and current_pass > 1 else None

    logger.info(
        "Source Book Writer: pass=%d, has_ref_index=%s, has_strategy=%s, rewrite=%s",
        current_pass,
        state.reference_index is not None,
        state.proposal_strategy is not None,
        bool(reviewer_feedback),
    )

    try:
        # ── Stage 1a: Sections 1-2 ────────────────────────────
        try:
            s12 = await _generate_sections_12(shared_ctx, model, previous_book)
        except Exception as e:
            if previous_book:
                logger.warning("Stage 1a failed on rewrite — preserving previous: %s", e)
                s12 = SourceBookSections12(
                    client_name=previous_book.client_name,
                    rfp_name=previous_book.rfp_name,
                    language=previous_book.language,
                    generation_date=previous_book.generation_date,
                    rfp_interpretation=previous_book.rfp_interpretation,
                    client_problem_framing=previous_book.client_problem_framing,
                )
                fallback_events.append("stage1a_preserved_previous")
            else:
                raise

        # ── Stage 1b: Section 3 ────────────────────────────────
        try:
            s3 = await _generate_section_3(shared_ctx, model, previous_book)
        except Exception as e:
            if previous_book:
                logger.warning("Stage 1b failed on rewrite — preserving previous: %s", e)
                s3 = SourceBookSection3(
                    why_strategic_gears=previous_book.why_strategic_gears,
                )
                fallback_events.append("stage1b_preserved_previous")
            else:
                raise

        # ── Stage 1c: Section 4 (can run with lighter model) ──
        try:
            s4 = await _generate_section_4(shared_ctx, model, previous_book)
        except Exception as e:
            if previous_book:
                logger.warning("Stage 1c failed on rewrite — preserving previous: %s", e)
                s4 = SourceBookSection4(
                    external_evidence=previous_book.external_evidence,
                )
                fallback_events.append("stage1c_preserved_previous")
            else:
                raise

        # ── Stage 1d: Section 5 ────────────────────────────────
        try:
            s5 = await _generate_section_5(shared_ctx, model, previous_book)
        except Exception as e:
            if previous_book:
                logger.warning("Stage 1d failed on rewrite — preserving previous: %s", e)
                s5 = SourceBookSection5(
                    proposed_solution=previous_book.proposed_solution,
                )
                fallback_events.append("stage1d_preserved_previous")
            else:
                raise

        # ── Assemble SourceBook from split-call outputs ────────
        source_book = SourceBook(
            client_name=s12.client_name,
            rfp_name=s12.rfp_name,
            language=s12.language,
            generation_date=s12.generation_date,
            rfp_interpretation=s12.rfp_interpretation,
            client_problem_framing=s12.client_problem_framing,
            why_strategic_gears=s3.why_strategic_gears,
            external_evidence=s4.external_evidence,
            proposed_solution=s5.proposed_solution,
            pass_number=current_pass,
        )

        # Deduplicate projects by case-insensitive name
        if source_book.why_strategic_gears.project_experience:
            seen: dict[str, bool] = {}
            unique_projects = []
            for proj in source_book.why_strategic_gears.project_experience:
                key = proj.project_name.strip().lower()
                if key not in seen:
                    seen[key] = True
                    unique_projects.append(proj)
            if len(unique_projects) < len(source_book.why_strategic_gears.project_experience):
                logger.info(
                    "Deduped projects: %d → %d",
                    len(source_book.why_strategic_gears.project_experience),
                    len(unique_projects),
                )
            source_book.why_strategic_gears.project_experience = unique_projects

        logger.info(
            "Stage 1 complete: pass=%d, capabilities=%d, consultants=%d, projects=%d",
            current_pass,
            len(source_book.why_strategic_gears.capability_mapping),
            len(source_book.why_strategic_gears.named_consultants),
            len(source_book.why_strategic_gears.project_experience),
        )

        # ── Stage 2a: Section 6 (blueprints) ──────────────────
        section6 = await _generate_blueprints(source_book, model)
        source_book.slide_blueprints = section6.slide_blueprints

        if not source_book.slide_blueprints:
            if state.source_book and state.source_book.slide_blueprints:
                source_book.slide_blueprints = state.source_book.slide_blueprints
                fallback_events.append("stage2a_blueprints_preserved_from_previous_pass")
                logger.warning(
                    "Stage 2a produced 0 blueprints on pass %d — preserved %d from previous",
                    current_pass,
                    len(source_book.slide_blueprints),
                )
            else:
                logger.error("Stage 2a produced 0 blueprints and no previous to fall back to")

        # ── Stage 2b: Section 7 (evidence ledger) ─────────────
        section7 = await _generate_evidence_ledger(source_book, model)
        source_book.evidence_ledger = section7.evidence_ledger

        if not source_book.evidence_ledger.entries:
            logger.warning("Stage 2b empty — building from citations (fallback)")
            source_book.evidence_ledger = _build_evidence_ledger_from_citations(source_book)
            fallback_events.append("stage2b_evidence_ledger_from_citations")

        # ── EXT citation coherence check ─────────────────────
        source_book = _strip_dangling_ext_citations(source_book, state)

        # ── Hedge scanner ──────────────────────────────────────
        hedges = _scan_for_hedges(source_book)
        if hedges:
            logger.warning("Hedge scanner found %d banned phrases: %s", len(hedges), ", ".join(hedges))
            source_book = await _rewrite_hedges(source_book, hedges)
            remaining = _scan_for_hedges(source_book)
            if remaining:
                logger.warning("Hedge rewrite: %d phrases remain — second pass", len(remaining))
                source_book = await _rewrite_hedges(source_book, remaining)
        else:
            logger.info("Hedge scanner: zero banned phrases found")

        logger.info(
            "Source Book written: pass=%d, blueprints=%d, evidence=%d, capabilities=%d",
            current_pass,
            len(source_book.slide_blueprints),
            len(source_book.evidence_ledger.entries),
            len(source_book.why_strategic_gears.capability_mapping),
        )

        # Update session accounting (6 stages: 1a + 1b + 1c + 1d + 2a + 2b)
        session = state.session.model_copy(deep=True)
        session.total_llm_calls += 6

        return {
            "source_book": source_book,
            "session": session,
            "fallback_events": fallback_events,
        }

    except Exception as e:
        logger.error("Source Book Writer failed: %s", e)
        from src.models.state import ErrorInfo

        preserved_book = state.source_book if state.source_book else SourceBook(
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="Source Book generation failed.",
            ),
        )

        return {
            "source_book": preserved_book,
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


# ── Legacy compatibility ──────────────────────────────────────
# Keep _build_user_message available for any code that imports it
def _build_user_message(state: DeckForgeState, reviewer_feedback: str = "") -> str:
    """Build user message (legacy — used by tests)."""
    ctx = _build_shared_context(state, reviewer_feedback)
    return json.dumps(ctx, ensure_ascii=False, default=str)
