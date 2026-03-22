"""LangGraph StateGraph — wires the DeckForge pipeline.

Pipeline flow (template-first assembly with Source Book pipeline):
  START → context → gate_1 → retrieval → gate_2 → evidence_curation
  → proposal_strategy → source_book → assembly_plan → gate_3
  → submission_transform → section_fill → build_slides → gate_4
  → qa → governance → gate_5 → render → END

evidence_curation runs the Internal Evidence Curator (analysis agent)
and External Research Agent concurrently to populate reference_index
and external_evidence_pack.  proposal_strategy produces win themes,
evaluator priorities, and methodology recommendation.  source_book
runs the Writer → Reviewer iteration loop to produce the Proposal
Source Book (DOCX) and populates report_markdown for downstream agents.

Gate nodes use LangGraph's interrupt() for human-in-the-loop approval.
The CLI runner resumes with Command(resume={"approved": True/False, ...}).
"""

import logging
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from src.agents.analysis import agent as analysis_agent
from src.agents.assembly_plan import agent as assembly_plan_agent
from src.agents.context import agent as context_agent
from src.agents.iterative.builder import run_iterative_build
from src.agents.qa import agent as qa_agent
from src.agents.research import agent as research_agent
from src.agents.retrieval import planner as retrieval_planner
from src.agents.retrieval import ranker as retrieval_ranker
from src.agents.submission_qa import agent as submission_qa_agent
from src.agents.submission_transform import agent as submission_transform_agent
from src.models.enums import PipelineStage, RendererMode
from src.models.state import DeckForgeState, ErrorInfo, GateDecision
from src.services.renderer import (
    export_gap_report_docx,
    export_report_docx,
    export_source_index_docx,
    render_pptx,
)
from src.services.scorer_profiles import ScorerProfile
from src.services.search import semantic_search

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Pipeline nodes — thin wrappers that call agents and return
# partial state dicts for LangGraph to merge.
# ──────────────────────────────────────────────────────────────


async def context_node(state: DeckForgeState) -> dict[str, Any]:
    """Run Context Agent — parse RFP intake into structured context."""
    result = await context_agent.run(state)
    return {
        "rfp_context": result.rfp_context,
        "current_stage": result.current_stage,
        "session": result.session,
        "errors": result.errors,
        "last_error": result.last_error,
    }


def _resolve_gate_2_approved_source_ids(
    state: DeckForgeState,
    decision: dict[str, Any],
) -> list[str]:
    """Resolve Gate 2 reviewer selections into persisted approved source IDs."""
    available_ids = [source.doc_id for source in state.retrieved_sources]
    modifications = decision.get("modifications") or {}

    included_ids = [
        source_id
        for source_id in modifications.get("included_sources", [])
        if source_id in available_ids
    ]
    excluded_ids = {
        source_id
        for source_id in modifications.get("excluded_sources", [])
        if source_id in available_ids
    }
    prioritized_ids = [
        source_id
        for source_id in modifications.get("prioritized_sources", [])
        if source_id in available_ids
    ]

    approved_ids = included_ids or list(available_ids)
    approved_ids = [
        source_id for source_id in approved_ids if source_id not in excluded_ids
    ]

    if not prioritized_ids:
        return approved_ids

    prioritized_set = set(prioritized_ids)
    prioritized = [source_id for source_id in prioritized_ids if source_id in approved_ids]
    remaining = [source_id for source_id in approved_ids if source_id not in prioritized_set]
    return prioritized + remaining


async def gate_node(
    state: DeckForgeState,
    gate_number: int,
    summary_fn: Any,
) -> dict[str, Any]:
    """Generic gate — interrupt for human approval."""
    summary = summary_fn(state)
    decision = interrupt({
        "gate_number": gate_number,
        "summary": summary,
        "prompt": f"Gate {gate_number}: Approve (y), reject with feedback (n), or quit (q)?",
    })

    gate_field = f"gate_{gate_number}"
    if decision.get("approved", False):
        gate_decision = GateDecision(
            gate_number=gate_number,
            approved=True,
            feedback=decision.get("feedback", ""),
        )
    else:
        gate_decision = GateDecision(
            gate_number=gate_number,
            approved=False,
            feedback=decision.get("feedback", "Rejected by user"),
        )

    updates: dict[str, Any] = {gate_field: gate_decision}
    if gate_number == 2 and gate_decision.approved:
        updates["approved_source_ids"] = _resolve_gate_2_approved_source_ids(state, decision)

    return updates


def _gate_1_summary(state: DeckForgeState) -> str:
    if state.rfp_context:
        name = state.rfp_context.rfp_name.en or "N/A"
        entity = state.rfp_context.issuing_entity.en or "N/A"
        return f"RFP: {name} | Entity: {entity}"
    return "No RFP context extracted."


def _gate_2_summary(state: DeckForgeState) -> str:
    count = len(state.retrieved_sources)
    return f"Retrieved {count} sources for review."


def _gate_3_summary(state: DeckForgeState) -> str:
    parts: list[str] = []

    # Assembly plan info (template-first pipeline)
    if state.assembly_plan:
        ap = state.assembly_plan
        llm = ap.llm_output
        parts.append(
            f"Assembly Plan: {llm.proposal_mode} mode, "
            f"{llm.geography} geography, sector={llm.sector}"
        )
        parts.append(f"Methodology: {len(llm.methodology_phases)} phases")
        parts.append(
            f"Case studies: {len(ap.case_study_result.selected)} selected, "
            f"{len(ap.case_study_result.excluded)} excluded"
        )
        parts.append(
            f"Team: {len(ap.team_result.selected)} selected, "
            f"{len(ap.team_result.excluded)} excluded"
        )
        parts.append(f"Total slides: {ap.slide_budget.total_slides}")
        parts.append(f"Win themes: {', '.join(llm.win_themes[:3])}")
    elif state.report_markdown:
        # Legacy fallback — research report path
        length = len(state.report_markdown)
        parts.append(f"Research report ready ({length} chars).")
    elif state.research_report and state.research_report.sections:
        parts.append(f"Research report ready ({len(state.research_report.sections)} sections).")
    else:
        parts.append("No assembly plan or research report generated.")

    parts.append(f"Mode: {state.deck_mode}")
    return " ".join(parts)


def _gate_4_summary(state: DeckForgeState) -> str:
    parts: list[str] = []
    if state.written_slides:
        count = len(state.written_slides.slides)
        mode = state.evidence_mode
        drafts = len(state.deck_drafts)
        reviews = len(state.deck_reviews)
        parts.append(
            f"Built slides: {count} slides ({mode} mode)"
            f" | {drafts} drafts, {reviews} reviews"
        )
    elif state.slide_outline:
        count = len(state.slide_outline.slides)
        parts.append(f"Slide outline: {count} slides.")
    else:
        parts.append("No slides built.")
    parts.append(f"Mode: {state.deck_mode}")
    # Show unresolved blockers if present
    if state.unresolved_issues and state.unresolved_issues.has_blockers:
        unresolved = [i for i in state.unresolved_issues.issues if not i.resolved]
        if unresolved:
            parts.append(f"Unresolved blockers: {len(unresolved)}")
    return " ".join(parts)


def _gate_5_summary(state: DeckForgeState) -> str:
    parts: list[str] = []
    if state.qa_result:
        s = state.qa_result.deck_summary
        parts.append(
            f"QA complete: {s.passed} passed, {s.failed} failed"
            f" | fail_close={s.fail_close}"
        )
    else:
        parts.append("No QA result.")
    parts.append(f"Mode: {state.deck_mode}")
    # Submission Transform status
    if state.submission_source_pack:
        cu = len(state.submission_source_pack.content_units)
        eb = len(state.submission_source_pack.evidence_bundles)
        sb = len(state.submission_source_pack.slide_briefs)
        parts.append(f"Transform: {cu} units, {eb} bundles, {sb} briefs")
    else:
        # Check if transform failed (error in errors list)
        xform_err = [
            e for e in (state.errors or [])
            if getattr(e, "agent", "") == "submission_transform_agent"
        ]
        if xform_err:
            parts.append("Transform: FAILED (submission_source_pack empty)")
        else:
            parts.append("Transform: not run")
    # Submission QA status
    if state.submission_qa_result:
        parts.append(f"Submission QA: {state.submission_qa_result.status}")
    # Density details
    if state.submission_qa_result and state.submission_qa_result.density_result:
        dr = state.submission_qa_result.density_result
        blocker_ids = sorted(
            s.slide_id for s in dr.slide_scores if not s.passes
        )
        if blocker_ids:
            parts.append(f"Density: {dr.blocker_count} blockers [{', '.join(blocker_ids)}]")
            split_ids = sorted(
                s.split_suggestion.source_slide_id
                for s in dr.slide_scores
                if s.split_suggestion is not None
            )
            if split_ids:
                parts.append(f"Split suggestions: [{', '.join(split_ids)}]")
    # Provenance details
    if state.submission_qa_result and state.submission_qa_result.evidence_provenance:
        ep = state.submission_qa_result.evidence_provenance
        if ep.issues:
            issue_ids = sorted(i.slide_id for i in ep.issues)
            parts.append(f"Provenance: {ep.blocker_count} blockers [{', '.join(issue_ids)}]")
    return " ".join(parts)


async def gate_1_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 1: User reviews RFP context."""
    return await gate_node(state, 1, _gate_1_summary)


async def gate_2_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 2: User reviews retrieved sources."""
    return await gate_node(state, 2, _gate_2_summary)


async def gate_3_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 3: User reviews assembly plan or research report."""
    return await gate_node(state, 3, _gate_3_summary)


async def gate_4_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 4: User reviews slide outline."""
    return await gate_node(state, 4, _gate_4_summary)


async def gate_5_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 5: User reviews final QA results."""
    return await gate_node(state, 5, _gate_5_summary)


async def retrieval_node(state: DeckForgeState) -> dict[str, Any]:
    """Retrieval chain: Planner → Search → Ranker (single node).

    1. Call planner — get transient search queries
    2. Pass queries to local search service
    3. Pass search results to ranker — populates retrieved_sources
    """
    # Step 1: Plan
    state, queries = await retrieval_planner.plan(state)
    if state.current_stage == PipelineStage.ERROR or queries is None:
        return {
            "current_stage": state.current_stage,
            "session": state.session,
            "errors": state.errors,
            "last_error": state.last_error,
        }

    # Step 2: Search — extract query strings and call semantic_search directly.
    # Empty queries fall back to an empty result set (the planner always
    # produces at least one query, so this is a safety net only).
    query_strings = [q.query for q in queries.search_queries if q.query.strip()]
    if not query_strings:
        search_results: list[dict] = []
    else:
        search_results = await semantic_search(query_strings, top_k=10)

    # Step 3: Rank
    result = await retrieval_ranker.run(state, search_results)
    return {
        "retrieved_sources": result.retrieved_sources,
        "current_stage": result.current_stage,
        "session": result.session,
        "errors": result.errors,
        "last_error": result.last_error,
    }


async def assembly_plan_node(state: DeckForgeState) -> dict[str, Any]:
    """Assembly Plan Agent — template-first assembly plan.

    Produces: inclusion policy, methodology blueprint, case study & team
    selection, slide budget.  All downstream rendering is driven by this
    assembly plan — not by a generic 5-turn iterative builder.
    """
    return await assembly_plan_agent.run(state)


async def analysis_node(state: DeckForgeState) -> dict[str, Any]:
    """Internal Evidence Curator — load approved docs (full text) and extract claims.

    Uses load_full_documents() to load ALL approved documents at up to
    50k chars each (no 3-doc limit, no 5k truncation). Gate 2 sets
    approved_source_ids.  For local dev, we auto-approve all retrieved
    sources if no explicit IDs were set.
    """
    from src.services.search import load_full_documents

    approved_ids = state.approved_source_ids
    if not approved_ids:
        # Auto-approve all retrieved sources for local dev
        approved_ids = [s.doc_id for s in state.retrieved_sources]

    documents = await load_full_documents(approved_ids)
    result = state
    merged_index = None

    for document in documents:
        result = await analysis_agent.run(result, [document])
        if result.current_stage == PipelineStage.ERROR:
            return {
                "reference_index": result.reference_index,
                "approved_source_ids": approved_ids,
                "current_stage": result.current_stage,
                "session": result.session,
                "errors": result.errors,
                "last_error": result.last_error,
            }

        if result.reference_index:
            if merged_index is None:
                merged_index = result.reference_index.model_copy(deep=True)
            else:
                merged_index.claims.extend(result.reference_index.claims)
                merged_index.case_studies.extend(result.reference_index.case_studies)
                merged_index.team_profiles.extend(result.reference_index.team_profiles)
                merged_index.compliance_evidence.extend(result.reference_index.compliance_evidence)
                merged_index.frameworks.extend(result.reference_index.frameworks)
                merged_index.gaps.extend(result.reference_index.gaps)
                merged_index.contradictions.extend(result.reference_index.contradictions)
                merged_index.source_manifest.extend(result.reference_index.source_manifest)

    if merged_index is not None:
        result.reference_index = merged_index

    return {
        "reference_index": result.reference_index,
        "approved_source_ids": approved_ids,
        "full_text_documents": documents,
        "current_stage": result.current_stage,
        "session": result.session,
        "errors": result.errors,
        "last_error": result.last_error,
    }


async def research_node(state: DeckForgeState) -> dict[str, Any]:
    """Research Agent — generate research report from reference index."""
    result = await research_agent.run(state)
    return {
        "research_report": result.research_report,
        "report_markdown": result.report_markdown,
        "current_stage": result.current_stage,
        "session": result.session,
        "errors": result.errors,
        "last_error": result.last_error,
    }


async def evidence_curation_node(state: DeckForgeState) -> dict[str, Any]:
    """Evidence Curation — runs Internal Evidence Curator + External Research concurrently.

    Phase 1 of the Proposal Source Book pipeline. Populates:
    - state.reference_index (from analysis agent)
    - state.external_evidence_pack (from external research agent)
    - state.full_text_documents (from analysis agent's loader)

    Session accounting is accumulated (summed), not clobbered.
    """
    import asyncio

    from src.agents.external_research import agent as external_research_agent

    # Run both agents concurrently
    analysis_task = asyncio.create_task(analysis_node(state))
    external_task = asyncio.create_task(external_research_agent.run(state))

    analysis_result, external_result = await asyncio.gather(
        analysis_task, external_task, return_exceptions=True,
    )

    # Merge results — session accounting must be accumulated, not clobbered
    updates: dict[str, Any] = {}

    if isinstance(analysis_result, Exception):
        logger.error("Analysis agent failed: %s", analysis_result)
        updates["reference_index"] = None
    else:
        updates.update(analysis_result)

    if isinstance(external_result, Exception):
        logger.error("External research agent failed: %s", external_result)
        from src.models.external_evidence import ExternalEvidencePack
        updates["external_evidence_pack"] = ExternalEvidencePack(
            coverage_assessment=f"External research failed: {external_result}",
        )
    else:
        # Merge non-session fields from external result
        for key, value in external_result.items():
            if key != "session":
                updates[key] = value

        # Accumulate session accounting from both branches
        if "session" in updates and "session" in external_result:
            analysis_session = updates["session"]
            external_session = external_result["session"]
            merged_session = analysis_session.model_copy(deep=True)
            merged_session.total_llm_calls = (
                analysis_session.total_llm_calls
                + external_session.total_llm_calls
                - state.session.total_llm_calls  # subtract base (counted twice)
            )
            merged_session.total_input_tokens = (
                analysis_session.total_input_tokens
                + external_session.total_input_tokens
                - state.session.total_input_tokens
            )
            merged_session.total_output_tokens = (
                analysis_session.total_output_tokens
                + external_session.total_output_tokens
                - state.session.total_output_tokens
            )
            merged_session.total_cost_usd = (
                analysis_session.total_cost_usd
                + external_session.total_cost_usd
                - state.session.total_cost_usd
            )
            updates["session"] = merged_session
        elif "session" in external_result:
            updates["session"] = external_result["session"]

    return updates


async def proposal_strategy_node(state: DeckForgeState) -> dict[str, Any]:
    """Proposal Strategist — strategic reasoning between evidence and content.

    Reads reference_index, external_evidence_pack, and rfp_context.
    Produces ProposalStrategy with win themes, evaluator priorities,
    and methodology recommendation.
    """
    from src.agents.proposal_strategy import agent as proposal_strategy_agent

    return await proposal_strategy_agent.run(state)


async def source_book_node(state: DeckForgeState) -> dict[str, Any]:
    """Source Book — iterative Writer/Reviewer loop producing Source Book DOCX.

    Runs the Source Book Writer, then Reviewer, iterating up to 3 passes
    until the review threshold is met. Exports DOCX and populates
    report_markdown from the approved Source Book content.
    """
    from src.agents.source_book import orchestrator, reviewer, writer
    from src.services.source_book_export import export_source_book_docx

    max_passes = 5
    current_state = state

    for pass_num in range(1, max_passes + 1):
        # Writer pass
        reviewer_feedback = ""
        if pass_num > 1 and current_state.source_book_review:
            reviewer_feedback = orchestrator.build_reviewer_feedback(
                current_state.source_book_review
            )

        writer_result = await writer.run(current_state, reviewer_feedback=reviewer_feedback)

        # Update state with writer result
        updates = dict(writer_result)
        source_book = updates.get("source_book")

        if not source_book or "errors" in updates:
            logger.error("Source Book Writer failed on pass %d", pass_num)
            return updates

        # Temporarily update state for reviewer
        current_state = state.model_copy(
            update={
                "source_book": source_book,
                "session": updates.get("session", state.session),
            },
        )

        # Reviewer pass
        review_result = await reviewer.run(current_state)
        review = review_result.get("source_book_review")

        if not review:
            logger.warning("Source Book Reviewer returned no review on pass %d", pass_num)
            break

        # Update state for next iteration
        current_state = current_state.model_copy(
            update={
                "source_book_review": review,
                "session": review_result.get("session", current_state.session),
            },
        )

        logger.info(
            "Source Book pass %d: score=%d, threshold=%s, viability=%s",
            pass_num,
            review.overall_score,
            review.pass_threshold_met,
            review.competitive_viability,
        )

        # Check if we should stop
        if not orchestrator.should_continue_iteration(
            review, current_pass=pass_num, max_passes=max_passes
        ):
            break

    # Export DOCX — persist path in state and surface failures
    session_id = current_state.session.session_id or "default"
    docx_path = f"output/{session_id}/source_book.docx"
    exported_docx_path: str | None = None
    export_error: ErrorInfo | None = None

    try:
        await export_source_book_docx(current_state.source_book, docx_path)
        exported_docx_path = docx_path
        logger.info("Source Book DOCX exported: %s", docx_path)
    except Exception as e:
        logger.error("Source Book DOCX export failed: %s", e)
        export_error = ErrorInfo(
            agent="source_book",
            error_type="DocxExportError",
            message=f"Source Book DOCX export failed: {e}",
        )

    # Populate report_markdown from Source Book
    report_md = orchestrator.source_book_to_markdown(current_state.source_book)

    result: dict[str, Any] = {
        "source_book": current_state.source_book,
        "source_book_review": current_state.source_book_review,
        "report_markdown": report_md,
        "report_docx_path": exported_docx_path,
        "session": current_state.session,
    }

    # Surface export failure structurally
    if export_error:
        result["errors"] = state.errors + [export_error]
        result["last_error"] = export_error

    return result


async def submission_transform_node(state: DeckForgeState) -> dict[str, Any]:
    """Submission Transform — converts Research Report to SubmissionSourcePack.

    Runs between gate_3 and build_slides (CLIENT_SUBMISSION mode only).
    Produces content_units, evidence_bundles, slide_allocation, and briefs
    that feed into evidence_provenance checks in the governance node.
    """
    result = await submission_transform_agent.run(state)
    return {
        "submission_source_pack": result.submission_source_pack,
        "internal_notes": result.internal_notes,
        "unresolved_issues": result.unresolved_issues,
        "current_stage": result.current_stage,
        "session": result.session,
        "errors": result.errors,
        "last_error": result.last_error,
    }


async def section_fill_node(state: DeckForgeState) -> dict[str, Any]:
    """Section Fill — runs LLM fillers for variable sections.

    Reads the proposal_manifest (built by assembly_plan), runs section
    fillers to generate content for b_variable entries, and merges
    injection_data back into the manifest.

    Wired between submission_transform and build_slides.
    """
    from src.agents.section_fillers.orchestrator import run_section_fillers

    manifest = state.proposal_manifest
    budget = state.slide_budget
    if manifest is None or budget is None:
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="section_fill",
                error_type="MissingInputs",
                message=(
                    "section_fill requires proposal_manifest and "
                    "slide_budget from assembly_plan."
                ),
            ),
        }

    # Build SourcePack from available state data — use full-text docs when available
    full_text_docs = state.full_text_documents if state.full_text_documents else None
    source_pack = _build_source_pack_from_state(state, full_text_docs=full_text_docs)

    # Extract win_themes from assembly plan
    win_themes: list[str] = []
    if state.assembly_plan and hasattr(state.assembly_plan, "llm_output"):
        llm_out = state.assembly_plan.llm_output
        if hasattr(llm_out, "win_themes"):
            win_themes = llm_out.win_themes or []

    # Run all section fillers concurrently
    orch_result = await run_section_fillers(
        budget,
        rfp_context=state.rfp_context,
        source_pack=source_pack,
        win_themes=win_themes,
        output_language=state.output_language,
        methodology_blueprint=state.methodology_blueprint,
    )

    # Merge filler injection_data into existing manifest entries.
    # ManifestEntry is frozen, so we build a new entry list.
    from src.models.proposal_manifest import ManifestEntry, ProposalManifest

    filler_entries_by_section: dict[str, list[ManifestEntry]] = (
        orch_result.entries_by_section
    )

    new_entries: list[ManifestEntry] = []
    section_filler_idx: dict[str, int] = {}  # track which filler entry to use next

    for entry in manifest.entries:
        if (
            entry.entry_type == "b_variable"
            and entry.section_id in filler_entries_by_section
        ):
            section_id = entry.section_id
            idx = section_filler_idx.get(section_id, 0)
            filler_list = filler_entries_by_section[section_id]
            if idx < len(filler_list):
                # Replace with filler entry (has injection_data + possibly new layout)
                new_entries.append(filler_list[idx])
                section_filler_idx[section_id] = idx + 1
            else:
                # More manifest entries than filler produced — keep original
                new_entries.append(entry)
        else:
            new_entries.append(entry)

    updated_manifest = ProposalManifest(
        entries=new_entries,
        inclusion_policy=manifest.inclusion_policy,
    )

    # ── Validate rebuilt manifest ──────────────────────────────────
    from src.models.proposal_manifest import validate_manifest

    manifest_errors = validate_manifest(updated_manifest)
    if manifest_errors:
        logger.error(
            "section_fill: manifest validation failed: %s",
            manifest_errors,
        )
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="section_fill",
                error_type="ManifestValidationFailed",
                message=(
                    f"Rebuilt manifest failed validation with "
                    f"{len(manifest_errors)} error(s): "
                    + "; ".join(manifest_errors[:5])
                ),
            ),
        }

    # Budget invariant: manifest slide count must equal the approved budget
    if len(updated_manifest.entries) != budget.total_slides:
        logger.error(
            "section_fill: manifest/budget mismatch — manifest=%d, budget=%d",
            len(updated_manifest.entries),
            budget.total_slides,
        )
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="section_fill",
                error_type="ManifestBudgetMismatch",
                message=(
                    f"Rebuilt manifest has {len(updated_manifest.entries)} entries "
                    f"but approved budget is {budget.total_slides} — "
                    f"budget invariant violated"
                ),
            ),
        }

    # Count filled entries for logging
    filled_count = sum(
        1 for e in updated_manifest.entries
        if e.entry_type == "b_variable" and e.injection_data
    )

    logger.info(
        "section_fill: %d entries filled, %d errors, "
        "manifest total=%d",
        filled_count,
        len(orch_result.errors),
        len(updated_manifest.entries),
    )

    result: dict[str, Any] = {
        "proposal_manifest": updated_manifest,
        "filler_outputs": orch_result.filler_outputs,
    }

    if orch_result.errors:
        logger.warning(
            "section_fill had %d filler errors: %s",
            len(orch_result.errors),
            orch_result.errors,
        )

    return result


def _build_source_pack_from_state(
    state: DeckForgeState,
    full_text_docs: list[dict] | None = None,
) -> Any:
    """Build a SourcePack from pipeline state data.

    Uses retrieved_sources for document evidence and reference_index
    for people/project data when available.

    If `full_text_docs` is provided (from load_full_documents), uses
    full document text instead of short ranker summaries. This is the
    primary evidence path for the Proposal Source Book pipeline.
    """
    from src.services.source_pack import (
        DocumentEvidence,
        PersonSummary,
        ProjectSummary,
        SourcePack,
    )

    documents: list[DocumentEvidence] = []
    people: list[PersonSummary] = []
    projects: list[ProjectSummary] = []

    # Build a lookup of full-text content by doc_id
    full_text_lookup: dict[str, dict] = {}
    if full_text_docs:
        for doc in full_text_docs:
            full_text_lookup[doc["doc_id"]] = doc

    # Documents from retrieved_sources — use full text when available
    for source in state.retrieved_sources:
        if source.recommendation == "include":
            if source.doc_id in full_text_lookup:
                # Full-text path (Proposal Source Book pipeline)
                ftd = full_text_lookup[source.doc_id]
                content = ftd["content_text"]
            else:
                # Fallback to ranker summary (legacy path)
                content = source.summary or ""

            documents.append(DocumentEvidence(
                doc_id=source.doc_id,
                title=source.title,
                content_text=content,
                char_count=len(content),
            ))

    # People and projects from reference_index
    if state.reference_index:
        for tp in state.reference_index.team_profiles:
            people.append(PersonSummary(
                person_id=tp.person_id if hasattr(tp, "person_id") else "",
                name=tp.name if hasattr(tp, "name") else "",
                current_role=tp.role if hasattr(tp, "role") else "",
            ))

    if not documents and not people:
        return None

    return SourcePack(
        total_people=len(people),
        total_projects=len(projects),
        people=people,
        projects=projects,
        documents=documents,
    )


async def build_slides_node(state: DeckForgeState) -> dict[str, Any]:
    """5-turn iterative slide builder — replaces structure + content agents.

    Runs Draft → Review → Refine → Final Review → Presentation in sequence.
    Gate 4 now shows complete built slides (not just an outline).

    After building, stamps each slide with its manifest b_variable entry's
    asset_id for provenance tracking (QA uses this to filter).
    """
    result = await run_iterative_build(state)

    # ── Manifest provenance stamping ──────────────────────────────
    # The iterative builder produces written_slides for NON-methodology
    # sections only (understanding, timeline, governance).  Methodology
    # slides are filled by the section filler directly into manifest
    # injection_data and rendered by the renderer — they are NOT in
    # written_slides.
    #
    # We stamp iterative-builder slides against the non-methodology
    # b_variable entries (matching by position within that filtered list).
    # Then we synthesize WrittenSlide stubs for methodology entries from
    # their injection_data so QA can validate ALL b_variable content.
    _FILLER_ONLY_SECTIONS = frozenset({"section_03"})  # methodology

    ws = result.written_slides
    if (
        ws
        and state.renderer_mode == RendererMode.TEMPLATE_V2
        and state.proposal_manifest
    ):
        # Split b_variable entries into iterative-builder vs filler-only
        builder_entries = [
            e for e in state.proposal_manifest.entries
            if e.entry_type == "b_variable"
            and e.section_id not in _FILLER_ONLY_SECTIONS
        ]
        filler_entries = [
            e for e in state.proposal_manifest.entries
            if e.entry_type == "b_variable"
            and e.section_id in _FILLER_ONLY_SECTIONS
        ]

        # Stamp iterative-builder slides against builder_entries (1:1)
        for i, slide in enumerate(ws.slides):
            if i < len(builder_entries):
                slide.manifest_asset_id = builder_entries[i].asset_id
            else:
                slide.manifest_asset_id = f"_unmatched_{i}"

        # Synthesize WrittenSlide stubs for filler-only entries so QA
        # covers methodology content too.
        from src.models.enums import LayoutType
        from src.models.slides import BodyContent, SlideObject

        for entry in filler_entries:
            if entry.injection_data is None:
                continue
            data = entry.injection_data
            # Extract title and body text from injection_data
            title = data.get("title", entry.asset_id)
            body_parts: list[str] = []
            bc = data.get("body_contents")
            if isinstance(bc, dict):
                body_parts = [str(v) for v in bc.values() if v]
            elif data.get("body"):
                body_parts = [str(data["body"])]
            stub = SlideObject(
                slide_id=f"METH-{entry.asset_id}",
                title=title,
                layout_type=LayoutType.CONTENT_1COL,
                body_content=BodyContent(
                    text_elements=body_parts,
                ),
                manifest_asset_id=entry.asset_id,
            )
            ws.slides.append(stub)

        logger.info(
            "build_slides: stamped %d builder slides + %d methodology "
            "stubs (%d total b_variable entries)",
            len(builder_entries),
            len(filler_entries),
            len(builder_entries) + len(filler_entries),
        )

    return {
        "written_slides": result.written_slides,
        "deck_drafts": result.deck_drafts,
        "deck_reviews": result.deck_reviews,
        "evidence_mode": result.evidence_mode,
        "current_stage": result.current_stage,
        "session": result.session,
        "errors": result.errors,
        "last_error": result.last_error,
    }


async def qa_node(state: DeckForgeState) -> dict[str, Any]:
    """QA Agent — validate slides against report and template rules."""
    result = await qa_agent.run(state)
    return {
        "qa_result": result.qa_result,
        "current_stage": result.current_stage,
        "session": result.session,
        "errors": result.errors,
        "last_error": result.last_error,
    }


async def governance_node(state: DeckForgeState) -> dict[str, Any]:
    """Governance checks — deterministic density, lint, provenance (no LLM).

    Runs density_scorer, language_linter, and evidence_provenance via
    the submission_qa agent. Populates submission_qa_result on state.
    """
    result = await submission_qa_agent.run(state)
    return {
        "submission_qa_result": result.submission_qa_result,
    }


def get_scorer_profile(mode: RendererMode) -> ScorerProfile:
    """Map RendererMode to the corresponding ScorerProfile.

    Legacy renderer uses legacy scorer profile.
    Template-v2 renderer uses official_template_v2 scorer profile.
    """
    if mode == RendererMode.TEMPLATE_V2:
        return ScorerProfile.OFFICIAL_TEMPLATE_V2
    return ScorerProfile.LEGACY


async def render_node(state: DeckForgeState) -> dict[str, Any]:
    """Design Agent — render PPTX and export DOCX (deterministic, no LLM).

    Dispatches to legacy render_pptx() or renderer_v2.render_v2()
    based on ``state.renderer_mode``.  Default is TEMPLATE_V2.

    Both paths use templates from PROPOSAL_TEMPLATE/ directory.
    Template-v2 path: uses ProposalManifest + official .potx template
    + catalog lock (production default).

    Fail-close enforcement: if QA flagged fail_close=True and no
    waivers cover the critical gaps, rendering is BLOCKED.
    """
    # ── Fail-close enforcement ──
    if state.qa_result and state.qa_result.deck_summary.fail_close:
        waived_gaps = {w.gap_id for w in state.waivers} if state.waivers else set()
        critical_gaps = state.qa_result.deck_summary.critical_gaps or []
        unwaived = [g for g in critical_gaps if g not in waived_gaps]
        if unwaived:
            return {
                "current_stage": PipelineStage.ERROR,
                "last_error": ErrorInfo(
                    agent="render",
                    error_type="FailCloseBlocked",
                    message=(
                        f"Rendering blocked: {len(unwaived)} critical gap(s) "
                        f"unresolved and unwaived. Gaps: {', '.join(unwaived[:5])}"
                    ),
                ),
            }

    # ── Lint-blocker enforcement (governance layer) ──
    if (
        state.submission_qa_result
        and state.submission_qa_result.language_lint.blocker_count > 0
    ):
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="render",
                error_type="LintBlocked",
                message=(
                    f"Rendering blocked: "
                    f"{state.submission_qa_result.language_lint.blocker_count} "
                    f"lint blocker(s) in client-facing text."
                ),
            ),
        }

    mode = state.renderer_mode

    if mode == RendererMode.TEMPLATE_V2:
        return await _render_template_v2(state)

    # ── Legacy path (default, unchanged) ──────────────────────
    return await _render_legacy(state)


async def _render_legacy(state: DeckForgeState) -> dict[str, Any]:
    """Legacy renderer — uses PROPOSAL_TEMPLATE .potx via python-pptx."""
    # Determine slides to render
    slides = state.final_slides
    if not slides and state.written_slides:
        slides = state.written_slides.slides

    if not slides:
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="render",
                error_type="NoSlides",
                message="No slides available for rendering.",
            ),
        }

    # Resolve paths — session-scoped output directory
    session_id = state.session.session_id if state.session else "default"
    output_dir = Path("output") / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve template from PROPOSAL_TEMPLATE directory
    language = state.output_language
    lang_val = language.value if hasattr(language, "value") else str(language)
    if lang_val == "ar":
        template_path = str(Path("PROPOSAL_TEMPLATE") / "Arabic_Proposal_Template.potx")
    else:
        template_path = str(Path("PROPOSAL_TEMPLATE") / "PROPOSAL_TEMPLATE EN.potx")

    pptx_path = str(output_dir / "deck.pptx")
    docx_path = str(output_dir / "report.docx")

    language = state.output_language

    # Render PPTX
    render_result = await render_pptx(slides, template_path, pptx_path, language)

    result: dict[str, Any] = {
        "pptx_path": render_result.pptx_path,
        "final_slides": slides,
        "current_stage": PipelineStage.FINALIZED,
    }

    # Export DOCX if research report exists
    if state.research_report:
        await export_report_docx(state.research_report, docx_path, language)
        result["report_docx_path"] = docx_path

    # Export source index if data exists
    if state.research_report and state.research_report.source_index:
        source_index_path = str(output_dir / "source_index.docx")
        await export_source_index_docx(state.research_report, source_index_path, language)
        result["source_index_path"] = source_index_path

    # Export gap report if data exists
    if state.research_report and state.research_report.all_gaps:
        gap_report_path = str(output_dir / "gap_report.docx")
        await export_gap_report_docx(state.research_report, gap_report_path, language)
        result["gap_report_path"] = gap_report_path

    return result


async def _render_template_v2(state: DeckForgeState) -> dict[str, Any]:
    """Template-v2 renderer — manifest-driven, template-anchored.

    Requires ``state.proposal_manifest`` to be populated by an earlier
    pipeline phase.  Fails closed if the manifest is absent — no empty
    stub is ever constructed here.

    The scorer profile for composition QA is dispatched by renderer mode.
    """
    # ── Fail closed: manifest MUST be populated by assembly plan ──
    manifest = state.proposal_manifest
    if manifest is None:
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="render_v2",
                error_type="MissingManifest",
                message=(
                    "proposal_manifest is None at render time. "
                    "The assembly plan agent must populate it "
                    "before the render node runs."
                ),
            ),
        }

    from src.services.renderer_v2 import render_v2
    from src.services.template_manager import TemplateManager

    # Session-scoped output directory
    session_id = state.session.session_id if state.session else "default"
    output_dir = Path("output") / session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = output_dir / "deck.pptx"
    docx_path = str(output_dir / "report.docx")

    language = state.output_language
    lang_val = language.value if hasattr(language, "value") else str(language)
    lang_suffix = "ar" if lang_val == "ar" else "en"

    # Resolve catalog lock path
    data_dir = Path("src/data")
    catalog_lock_path = data_dir / f"catalog_lock_{lang_suffix}.json"

    if not catalog_lock_path.exists():
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="render_v2",
                error_type="MissingCatalogLock",
                message=(
                    f"Catalog lock not found at {catalog_lock_path}.  "
                    f"Run template auditor (PHASE 0) first."
                ),
            ),
        }

    # Initialize TemplateManager from PROPOSAL_TEMPLATE directory (production source of truth)
    try:
        proposal_template_dir = Path("PROPOSAL_TEMPLATE")
        if lang_suffix == "ar":
            template_path = proposal_template_dir / "Arabic_Proposal_Template.potx"
        else:
            template_path = proposal_template_dir / "PROPOSAL_TEMPLATE EN.potx"
        # Fallback: check src/data for locally cached .potx
        if not template_path.exists():
            template_path = data_dir / f"template_{lang_suffix}.potx"

        tm = TemplateManager(str(template_path), catalog_lock_path)

        logger.info(
            "renderer_v2 dispatch: template=%s, "
            "catalog_lock=%s, manifest_entries=%d",
            template_path, catalog_lock_path, len(manifest.entries),
        )
    except Exception as exc:
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="render_v2",
                error_type="TemplateManagerError",
                message=f"Failed to initialize TemplateManager: {exc}",
            ),
        }

    # Render via renderer_v2
    try:
        v2_result = render_v2(
            manifest, tm, catalog_lock_path, pptx_path,
            filler_outputs=state.filler_outputs,
            language=lang_val,
        )

        result: dict[str, Any] = {
            "pptx_path": str(pptx_path) if v2_result.success else None,
            "current_stage": PipelineStage.FINALIZED if v2_result.success else PipelineStage.ERROR,
        }

        if not v2_result.success:
            errors = v2_result.manifest_errors + v2_result.render_errors
            result["last_error"] = ErrorInfo(
                agent="render_v2",
                error_type="RenderV2Error",
                message="; ".join(errors) if errors else "Unknown v2 render error",
            )

        # Export DOCX if research report exists
        if state.research_report and v2_result.success:
            await export_report_docx(state.research_report, docx_path, language)
            result["report_docx_path"] = docx_path

            # Export source index if data exists
            if state.research_report.source_index:
                source_index_path = str(output_dir / "source_index.docx")
                await export_source_index_docx(state.research_report, source_index_path, language)
                result["source_index_path"] = source_index_path

            # Export gap report if data exists
            if state.research_report.all_gaps:
                gap_report_path = str(output_dir / "gap_report.docx")
                await export_gap_report_docx(state.research_report, gap_report_path, language)
                result["gap_report_path"] = gap_report_path

        return result

    except Exception as exc:
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="render_v2",
                error_type="RenderV2Exception",
                message=f"Template-v2 render failed: {exc}",
            ),
        }


# ──────────────────────────────────────────────────────────────
# Conditional routing — skip remaining pipeline on error
# ──────────────────────────────────────────────────────────────


def _route_after_gate(
    state: DeckForgeState,
    gate_field: str,
    next_node: str,
    retry_node: str | None = None,
) -> str:
    """Route after a gate: continue if approved, loop back if rejected.

    When rejected, routes to ``retry_node`` (the preceding agent) so the
    pipeline can re-run that stage with the reviewer's feedback incorporated.
    Falls back to ``next_node`` if no retry_node is specified.
    """
    gate = getattr(state, gate_field, None)
    if gate and gate.approved:
        return next_node
    # Rejection → re-run the preceding stage so feedback can be incorporated
    return retry_node or next_node


def route_after_gate_1(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_1", "retrieval", retry_node="context")


def route_after_gate_2(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_2", "evidence_curation", retry_node="retrieval")


def route_after_gate_3(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_3", "submission_transform", retry_node="assembly_plan")


def route_after_gate_4(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_4", "qa", retry_node="build_slides")


def route_after_gate_5(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_5", "render", retry_node="qa")


# ──────────────────────────────────────────────────────────────
# Graph construction
# ──────────────────────────────────────────────────────────────


def build_graph() -> CompiledStateGraph:
    """Build and compile the DeckForge pipeline graph.

    Returns a compiled LangGraph StateGraph with MemorySaver
    checkpointer for interrupt/resume at gates.
    """
    graph = StateGraph(DeckForgeState)

    # Add nodes
    graph.add_node("context", context_node)
    graph.add_node("gate_1", gate_1_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("gate_2", gate_2_node)
    graph.add_node("evidence_curation", evidence_curation_node)
    graph.add_node("proposal_strategy", proposal_strategy_node)
    graph.add_node("source_book", source_book_node)
    graph.add_node("assembly_plan", assembly_plan_node)
    graph.add_node("gate_3", gate_3_node)
    graph.add_node("submission_transform", submission_transform_node)
    graph.add_node("section_fill", section_fill_node)
    graph.add_node("build_slides", build_slides_node)
    graph.add_node("gate_4", gate_4_node)
    graph.add_node("qa", qa_node)
    graph.add_node("governance", governance_node)
    graph.add_node("gate_5", gate_5_node)
    graph.add_node("render", render_node)

    # Linear edges
    graph.add_edge(START, "context")
    graph.add_edge("context", "gate_1")

    # Conditional edges after gates — rejection loops back to preceding agent
    graph.add_conditional_edges(
        "gate_1", route_after_gate_1, ["retrieval", "context"]
    )
    graph.add_edge("retrieval", "gate_2")
    graph.add_conditional_edges(
        "gate_2", route_after_gate_2, ["evidence_curation", "retrieval"]
    )
    graph.add_edge("evidence_curation", "proposal_strategy")
    graph.add_edge("proposal_strategy", "source_book")
    graph.add_edge("source_book", "assembly_plan")
    graph.add_edge("assembly_plan", "gate_3")
    graph.add_conditional_edges(
        "gate_3", route_after_gate_3, ["submission_transform", "assembly_plan"]
    )
    graph.add_edge("submission_transform", "section_fill")
    graph.add_edge("section_fill", "build_slides")
    graph.add_edge("build_slides", "gate_4")
    graph.add_conditional_edges(
        "gate_4", route_after_gate_4, ["qa", "build_slides"]
    )
    graph.add_edge("qa", "governance")
    graph.add_edge("governance", "gate_5")
    graph.add_conditional_edges(
        "gate_5", route_after_gate_5, ["render", "qa"]
    )
    graph.add_edge("render", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# ──────────────────────────────────────────────────────────────
# State persistence — JSON save/load for crash recovery
# ──────────────────────────────────────────────────────────────


def save_state(state: DeckForgeState, path: str = "./state/session.json") -> None:
    """Serialize DeckForgeState to JSON file."""
    filepath = Path(path)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(
        state.model_dump_json(indent=2),
        encoding="utf-8",
    )


def load_state(path: str = "./state/session.json") -> DeckForgeState:
    """Deserialize DeckForgeState from JSON file."""
    filepath = Path(path)
    data = filepath.read_text(encoding="utf-8")
    return DeckForgeState.model_validate_json(data)
