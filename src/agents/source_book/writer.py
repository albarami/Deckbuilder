"""Source Book Writer agent — synthesizes evidence and strategy into Source Book.

Consumes reference_index, external_evidence_pack, proposal_strategy, and
rfp_context to produce a structured SourceBook with 7 sections. Every claim
must cite its source (CLM-xxxx for internal, EXT-xxx for external).
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
    SourceBookSection6,
    SourceBookSection7,
)
from src.models.state import DeckForgeState
from src.services.llm import call_llm

from .prompts import STAGE2A_BLUEPRINTS_PROMPT, STAGE2B_EVIDENCE_LEDGER_PROMPT
from .prompts import WRITER_SYSTEM_PROMPT as SYSTEM_PROMPT

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


def _scan_for_hedges(source_book: SourceBook) -> list[str]:
    """Scan all text fields for banned hedge phrases. Returns matches.

    Uses word-boundary regex to avoid false positives from substrings
    (e.g., "pending" inside "spending" or "impending").
    """
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
    """Remove EXT-xxx citations that don't exist in the external evidence pack.

    Scans all text fields for EXT-xxx references and strips any that are not
    in the actual evidence pack. This prevents hallucinated citations from
    appearing in the final document.
    """
    valid_ext_ids: set[str] = set()
    if state.external_evidence_pack:
        for src in getattr(state.external_evidence_pack, "sources", []):
            sid = getattr(src, "source_id", "")
            if sid:
                valid_ext_ids.add(sid)

    if not valid_ext_ids:
        # No evidence pack at all — strip ALL EXT citations
        pass

    # Serialize to find all EXT references
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

    # Strip dangling EXT-xxx references from all string fields
    dangling_pattern = re.compile(
        r"\s*\[?(" + "|".join(re.escape(d) for d in dangling) + r")\]?\s*"
    )

    def _clean_str(val: str) -> str:
        return dangling_pattern.sub(" ", val).strip()

    def _clean_list(items: list[str]) -> list[str]:
        return [_clean_str(s) for s in items if _clean_str(s)]

    # Clean evidence_ids in slide blueprints
    for bp in source_book.slide_blueprints:
        if bp.proof_points:
            bp.proof_points = [p for p in bp.proof_points if p not in dangling]
        if bp.must_have_evidence:
            bp.must_have_evidence = [m for m in bp.must_have_evidence if m not in dangling]
        if bp.bullet_logic:
            bp.bullet_logic = _clean_list(bp.bullet_logic)

    # Clean evidence ledger — remove entries for dangling IDs
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
        "contains hedging language that must be removed. You MUST "
        "rewrite every sentence containing a banned word. Replace "
        "hedged language with direct, confident statements. Do NOT "
        "preserve any instance of: "
        f"{hedge_list}. "
        "Example rewrites:\n"
        '- "Timeline is pending baseline" → "The engagement delivers '
        'across 72 weeks in five phases"\n'
        '- "Subject to stakeholder approval" → "The steering committee '
        'approves at each phase gate"\n'
        '- "This could be adjusted" → "This adapts to client '
        'requirements at each phase gate"\n'
        "Do NOT change any other content. Output the full corrected "
        "SourceBook JSON."
    )

    user_msg = json.dumps(
        source_book.model_dump(mode="json"),
        ensure_ascii=False,
        default=str,
    )

    model = MODEL_MAP.get(
        "source_book_writer",
        MODEL_MAP.get("analysis_agent"),
    )

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
        # Preserve blueprints and evidence ledger — hedge rewrite LLM
        # often truncates these complex fields
        if not cleaned.slide_blueprints and source_book.slide_blueprints:
            cleaned.slide_blueprints = source_book.slide_blueprints
            logger.info(
                "Hedge rewrite: preserved %d slide blueprints",
                len(cleaned.slide_blueprints),
            )
        if (
            not cleaned.evidence_ledger.entries
            and source_book.evidence_ledger.entries
        ):
            cleaned.evidence_ledger = source_book.evidence_ledger
            logger.info(
                "Hedge rewrite: preserved %d evidence entries",
                len(cleaned.evidence_ledger.entries),
            )
        logger.info(
            "Hedge rewrite complete — removed %d hedge patterns",
            len(hedges_found),
        )
        return cleaned
    except Exception as e:
        logger.warning("Hedge rewrite failed: %s — keeping original", e)
        return source_book


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

    # Extract explicit timeline + team requirements for the Writer
    rfp_timeline_dump = None
    rfp_team_requirements_dump = None
    if state.rfp_context:
        if state.rfp_context.project_timeline:
            rfp_timeline_dump = state.rfp_context.project_timeline.model_dump(mode="json")
        if state.rfp_context.team_requirements:
            rfp_team_requirements_dump = [
                tr.model_dump(mode="json") for tr in state.rfp_context.team_requirements
            ]

    # Build explicit constraints block so the LLM cannot ignore them
    mandatory_constraints: list[str] = []
    if rfp_timeline_dump:
        dur = rfp_timeline_dump.get("total_duration", "")
        months = rfp_timeline_dump.get("total_duration_months")
        if dur or months:
            constraint = (
                f"MANDATORY TIMELINE: The RFP states the project duration is "
                f"{dur or str(months) + ' months'}. "
                f"You MUST use this exact duration in Section 5 timeline_logic "
                f"and all slide blueprints. Do NOT invent a different duration."
            )
            mandatory_constraints.append(constraint)
        sched = rfp_timeline_dump.get("deliverable_schedule", [])
        if sched:
            milestones = "; ".join(
                f"{s.get('milestone', '?')} due {s.get('due_date', '?')}"
                for s in sched
            )
            mandatory_constraints.append(
                f"MANDATORY MILESTONES: {milestones}"
            )
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

    # Build available EXT IDs so the Writer knows what exists
    available_ext_ids: list[str] = []
    if state.external_evidence_pack:
        for src in getattr(state.external_evidence_pack, "sources", []):
            sid = getattr(src, "source_id", "")
            if sid:
                available_ext_ids.append(sid)

    payload = {
        "mandatory_constraints": mandatory_constraints or None,
        "available_ext_ids": available_ext_ids or None,
        "rfp_context": rfp_dump,
        "rfp_project_timeline": rfp_timeline_dump,
        "rfp_team_requirements": rfp_team_requirements_dump,
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


async def _generate_blueprints(
    source_book: SourceBook,
    model: str,
) -> SourceBookSection6:
    """Stage 2a: Dedicated LLM call for slide blueprints only.

    Args:
        source_book: Completed Sections 1-5 from Stage 1.
        model: LLM model identifier.

    Returns:
        SourceBookSection6 with slide_blueprints.
    """
    context = _dump_sections_15(source_book)
    logger.info("Stage 2a (blueprints): input chars=%d", len(context))

    result = await call_llm(
        model=model,
        system_prompt=STAGE2A_BLUEPRINTS_PROMPT,
        user_message=context,
        response_model=SourceBookSection6,
        max_tokens=32000,
        temperature=0.1,
    )

    section6 = result.parsed
    logger.info("Stage 2a produced: %d blueprints", len(section6.slide_blueprints))
    return section6


async def _generate_evidence_ledger(
    source_book: SourceBook,
    model: str,
) -> SourceBookSection7:
    """Stage 2b: Dedicated LLM call for evidence ledger only.

    Args:
        source_book: Completed Sections 1-5 from Stage 1 (with blueprints
            already merged from Stage 2a).
        model: LLM model identifier.

    Returns:
        SourceBookSection7 with evidence_ledger.
    """
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
    """Run the Source Book Writer agent (three-stage architecture).

    Stage 1:  Sections 1-5 (prose content) — full token budget for depth.
    Stage 2a: Section 6 (slide blueprints) — dedicated call with Sections 1-5.
    Stage 2b: Section 7 (evidence ledger) — dedicated call with Sections 1-6.

    Each stage gets its own LLM call and token budget so Arabic output
    never truncates before completing the section.

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

    # Track fallback usage per pass for honest reporting
    fallback_events: list[str] = []

    try:
        # ── Stage 1: Sections 1-5 ────────────────────────────
        try:
            llm_result = await call_llm(
                model=model,
                system_prompt=SYSTEM_PROMPT,
                user_message=user_message,
                response_model=SourceBook,
                max_tokens=32000,
                temperature=0.1,
            )
            source_book = llm_result.parsed
        except Exception as stage1_err:
            if state.source_book and state.source_book.pass_number >= 1:
                logger.warning(
                    "Stage 1 validation failed on rewrite pass — "
                    "preserving previous pass result: %s",
                    stage1_err,
                )
                source_book = state.source_book.model_copy(deep=True)
                fallback_events.append("stage1_preserved_previous")
            else:
                raise

        # Set pass number
        current_pass = 1
        if state.source_book:
            current_pass = state.source_book.pass_number + 1
        source_book.pass_number = current_pass

        # Deduplicate projects by case-insensitive name
        if source_book.why_strategic_gears.project_experience:
            seen: dict[str, bool] = {}
            unique_projects = []
            for proj in source_book.why_strategic_gears.project_experience:
                key = proj.project_name.strip().lower()
                if key not in seen:
                    seen[key] = True
                    unique_projects.append(proj)
            if len(unique_projects) < len(
                source_book.why_strategic_gears.project_experience
            ):
                logger.info(
                    "Deduped projects: %d → %d",
                    len(source_book.why_strategic_gears.project_experience),
                    len(unique_projects),
                )
            source_book.why_strategic_gears.project_experience = (
                unique_projects
            )

        logger.info(
            "Stage 1 complete: pass=%d, capabilities=%d",
            current_pass,
            len(source_book.why_strategic_gears.capability_mapping),
        )

        # ── Stage 2a: Section 6 (blueprints) ──────────────────
        section6 = await _generate_blueprints(source_book, model)
        source_book.slide_blueprints = section6.slide_blueprints

        # Fallback for blueprints (safety net only)
        if not source_book.slide_blueprints:
            if state.source_book and state.source_book.slide_blueprints:
                source_book.slide_blueprints = (
                    state.source_book.slide_blueprints
                )
                fallback_events.append(
                    f"stage2a_blueprints_preserved_from_previous_pass"
                )
                logger.warning(
                    "Stage 2a produced 0 blueprints on pass %d "
                    "— preserved %d from previous pass (fallback)",
                    current_pass,
                    len(source_book.slide_blueprints),
                )
            else:
                logger.error(
                    "Stage 2a produced 0 slide blueprints and no "
                    "previous pass to fall back to — hard failure"
                )

        # ── Stage 2b: Section 7 (evidence ledger) ─────────────
        section7 = await _generate_evidence_ledger(source_book, model)
        source_book.evidence_ledger = section7.evidence_ledger

        # Fallback for evidence ledger (safety net only)
        if not source_book.evidence_ledger.entries:
            logger.warning(
                "Stage 2b produced empty evidence ledger — "
                "building from citations (fallback)"
            )
            source_book.evidence_ledger = _build_evidence_ledger_from_citations(
                source_book,
            )
            fallback_events.append("stage2b_evidence_ledger_from_citations")
            if source_book.evidence_ledger.entries:
                logger.info(
                    "Evidence ledger populated from citations (fallback): "
                    "%d entries",
                    len(source_book.evidence_ledger.entries),
                )

        # ── EXT citation coherence check ─────────────────────────
        source_book = _strip_dangling_ext_citations(source_book, state)

        # ── D9: Hedge scanner ──────────────────────────────────
        hedges = _scan_for_hedges(source_book)
        if hedges:
            logger.warning(
                "Hedge scanner found %d banned phrases: %s",
                len(hedges),
                ", ".join(hedges),
            )
            source_book = await _rewrite_hedges(source_book, hedges)
            remaining = _scan_for_hedges(source_book)
            if remaining:
                logger.warning(
                    "Hedge rewrite pass 1: %d phrases remain: %s — "
                    "running targeted second pass",
                    len(remaining),
                    ", ".join(remaining),
                )
                source_book = await _rewrite_hedges(
                    source_book, remaining,
                )
                final_check = _scan_for_hedges(source_book)
                if final_check:
                    logger.warning(
                        "Hedge rewrite pass 2: %d still remain: %s",
                        len(final_check),
                        ", ".join(final_check),
                    )
                else:
                    logger.info(
                        "Hedge rewrite pass 2: all phrases removed",
                    )
            else:
                logger.info("Hedge rewrite: all banned phrases removed")
        else:
            logger.info("Hedge scanner: zero banned phrases found")

        logger.info(
            "Source Book written: pass=%d, blueprints=%d, "
            "evidence_entries=%d, capabilities=%d",
            current_pass,
            len(source_book.slide_blueprints),
            len(source_book.evidence_ledger.entries),
            len(source_book.why_strategic_gears.capability_mapping),
        )

        # Update session accounting (3 stages: Stage 1 + Stage 2a + Stage 2b)
        session = state.session.model_copy(deep=True)
        session.total_llm_calls += 3

        return {
            "source_book": source_book,
            "session": session,
            "fallback_events": fallback_events,
        }

    except Exception as e:
        logger.error("Source Book Writer failed: %s", e)
        from src.models.state import ErrorInfo

        # On rewrite passes, preserve the previous good result
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
