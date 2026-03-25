"""LangGraph StateGraph — wires the DeckForge pipeline.

Pipeline flow (M10 — iterative builder):
  START → context → gate_1 → retrieval → gate_2 → analysis → research
  → gate_3 → build_slides → gate_4 → qa → gate_5 → render → END

build_slides replaces the old structure + content nodes with a 5-turn
iterative builder (Draft → Review → Refine → Final Review → Presentation).

Gate nodes use LangGraph's interrupt() for human-in-the-loop approval.
The CLI runner resumes with Command(resume={"approved": True/False, ...}).
"""

from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from src.agents.analysis import agent as analysis_agent
from src.agents.context import agent as context_agent
from src.agents.iterative.builder import run_iterative_build
from src.agents.qa import agent as qa_agent
from src.agents.research import agent as research_agent
from src.agents.retrieval import planner as retrieval_planner
from src.agents.retrieval import ranker as retrieval_ranker
from src.config.settings import get_settings
from src.models.enums import PipelineStage, RendererMode
from src.models.state import DeckForgeState, ErrorInfo, GateDecision
from src.services.renderer import (
    export_gap_report_docx,
    export_report_docx,
    export_source_index_docx,
    render_pptx,
)
from src.services.scorer_profiles import ScorerProfile
from src.services.search import load_documents, semantic_search
from src.services.semantic_scholar import (
    SemanticScholarAPIError,
    gather_external_evidence,
    normalize_semantic_scholar_api_key,
)

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
    mode_prefix = f"Mode: {state.deck_mode}"
    manifest = state.proposal_manifest
    if manifest is not None:
        total = manifest.total_slides
        sections = manifest.section_ids
        return (
            f"{mode_prefix} | Assembly plan ready: {total} slides across "
            f"{len(sections)} sections ({', '.join(sections)})."
        )
    if state.report_markdown:
        length = len(state.report_markdown)
        return f"{mode_prefix} | Research report ready ({length} chars)."
    if state.research_report and state.research_report.sections:
        return f"{mode_prefix} | Research report ready ({len(state.research_report.sections)} sections)."
    return f"{mode_prefix} | No assembly plan or research report generated."


def _gate_4_summary(state: DeckForgeState) -> str:
    mode_prefix = f"Mode: {state.deck_mode}"
    blocker_suffix = ""
    if state.unresolved_issues and state.unresolved_issues.has_blockers:
        unresolved_count = sum(1 for issue in state.unresolved_issues.issues if not issue.resolved)
        blocker_suffix = f" | Unresolved blockers: {unresolved_count}"

    if state.written_slides:
        count = len(state.written_slides.slides)
        mode = state.evidence_mode
        drafts = len(state.deck_drafts)
        reviews = len(state.deck_reviews)
        return (
            f"{mode_prefix} | Built slides: {count} slides ({mode} mode)"
            f" | {drafts} drafts, {reviews} reviews"
            f"{blocker_suffix}"
        )
    if state.slide_outline:
        count = len(state.slide_outline.slides)
        return f"{mode_prefix} | Slide outline: {count} slides.{blocker_suffix}"
    return f"{mode_prefix} | No slides built.{blocker_suffix}"


def _gate_5_summary(state: DeckForgeState) -> str:
    mode_prefix = f"Mode: {state.deck_mode}"
    if state.submission_qa_result:
        submission = state.submission_qa_result
        parts = [
            mode_prefix,
            f"Submission QA: {submission.status}",
        ]
        if submission.summary:
            parts.append(submission.summary)

        if submission.density_result:
            density = submission.density_result
            density_blockers = []
            for score in density.slide_scores:
                has_blocker = any(v.severity == "blocker" for v in score.violations)
                if has_blocker:
                    density_blockers.append(score.slide_id)
            density_blockers = sorted(dict.fromkeys(density_blockers))
            if density.blocker_count > 0:
                blocker_text = ", ".join(density_blockers) if density_blockers else "none listed"
                parts.append(
                    f"Density: {density.blocker_count} blockers ({blocker_text})"
                )

        if submission.evidence_provenance:
            provenance = submission.evidence_provenance
            if provenance.blocker_count > 0:
                provenance_ids = sorted(
                    dict.fromkeys(issue.slide_id for issue in provenance.issues)
                )
                parts.append(
                    f"Provenance: {provenance.blocker_count} blockers "
                    f"({', '.join(provenance_ids)})"
                )

        return " | ".join(parts)

    if state.qa_result:
        s = state.qa_result.deck_summary
        return (
            f"{mode_prefix} | QA complete: {s.passed} passed, {s.failed} failed"
            f" | fail_close={s.fail_close}"
        )
    return f"{mode_prefix} | No QA result."


async def gate_1_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 1: User reviews RFP context."""
    return await gate_node(state, 1, _gate_1_summary)


async def gate_2_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 2: User reviews retrieved sources."""
    return await gate_node(state, 2, _gate_2_summary)


async def gate_3_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 3: User reviews assembly plan (methodology, budget, selections)."""
    return await gate_node(state, 3, _gate_3_summary)


async def gate_4_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 4: User reviews slide outline."""
    return await gate_node(state, 4, _gate_4_summary)


async def gate_5_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 5: User reviews final QA results."""
    return await gate_node(state, 5, _gate_5_summary)


def _merge_local_and_s2(local: list[dict], s2: list[dict]) -> list[dict]:
    """Prefer local knowledge hits first, then Semantic Scholar rows (deduped by doc_id)."""
    seen: set[str] = set()
    out: list[dict] = []
    for row in local:
        did = str(row.get("doc_id", ""))
        if did and did not in seen:
            seen.add(did)
            out.append(row)
    for row in s2:
        did = str(row.get("doc_id", ""))
        if did and did not in seen:
            seen.add(did)
            out.append(row)
    return out


async def retrieval_node(state: DeckForgeState) -> dict[str, Any]:
    """Retrieval chain: Planner → Search → Ranker (single node).

    1. Call planner — get transient search queries
    2. Pass queries to local search + optional Semantic Scholar (key probed; public tier if key rejected)
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

    # Step 2: Search — local index + optional S2 (x-api-key when accepted, else public API).
    query_strings = [q.query for q in queries.search_queries if q.query.strip()]
    if not query_strings:
        search_results = []
        s2_registry: dict[str, dict] = {}
    else:
        local_results = await semantic_search(query_strings, top_k=10)
        api_key = normalize_semantic_scholar_api_key(
            get_settings().semantic_scholar_api_key.get_secret_value(),
        )
        if api_key:
            try:
                s2_results, s2_registry = await gather_external_evidence(
                    query_strings,
                    api_key=api_key,
                )
            except SemanticScholarAPIError as e:
                err = ErrorInfo(
                    agent="semantic_scholar",
                    error_type=type(e).__name__,
                    message=str(e),
                )
                errors = [*state.errors, err]
                return {
                    "current_stage": PipelineStage.ERROR,
                    "session": state.session,
                    "errors": errors,
                    "last_error": err,
                    "semantic_scholar_papers": {},
                }
        else:
            s2_results, s2_registry = [], {}

        search_results = _merge_local_and_s2(local_results, s2_results)

    # Step 3: Rank
    result = await retrieval_ranker.run(state, search_results)
    return {
        "retrieved_sources": result.retrieved_sources,
        "semantic_scholar_papers": s2_registry,
        "current_stage": result.current_stage,
        "session": result.session,
        "errors": result.errors,
        "last_error": result.last_error,
    }


async def analysis_node(state: DeckForgeState) -> dict[str, Any]:
    """Analysis Agent — load approved docs and extract claims.

    Gate 2 sets approved_source_ids.  For local dev, we auto-approve
    all retrieved sources if no explicit IDs were set.
    """
    approved_ids = state.approved_source_ids
    if not approved_ids:
        # Auto-approve all retrieved sources for local dev
        approved_ids = [s.doc_id for s in state.retrieved_sources]

    documents = await load_documents(
        approved_ids,
        external_papers=state.semantic_scholar_papers,
    )
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


async def build_slides_node(state: DeckForgeState) -> dict[str, Any]:
    """5-turn iterative slide builder — replaces structure + content agents.

    Runs Draft → Review → Refine → Final Review → Presentation in sequence.
    Gate 4 now shows complete built slides (not just an outline).
    """
    result = await run_iterative_build(state)
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
    based on ``state.renderer_mode``.  Default is LEGACY.

    Legacy path: uses final_slides + templates/Presentation6.pptx.
    Template-v2 path: uses ProposalManifest + official .potx template
    + catalog lock.

    Scorer profile is dispatched by renderer mode.
    """
    mode = state.renderer_mode

    if mode == RendererMode.TEMPLATE_V2:
        return await _render_template_v2(state)

    # ── Legacy path (default, unchanged) ──────────────────────
    return await _render_legacy(state)


async def _render_legacy(state: DeckForgeState) -> dict[str, Any]:
    """Legacy renderer — unchanged from pre-v2 behavior."""
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

    # Resolve paths
    template_path = "templates/Presentation6.pptx"
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

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
    pipeline phase (assembly plan node).  Fails closed if the manifest
    is absent — no fallback rebuild from slides is permitted.

    The scorer profile for composition QA is dispatched by renderer mode.
    """
    import logging

    _logger = logging.getLogger(__name__)

    manifest = state.proposal_manifest
    if manifest is None:
        _logger.error(
            "render_v2: proposal_manifest is None — fail closed. "
            "The assembly plan must populate the manifest before rendering."
        )
        return {
            "current_stage": PipelineStage.ERROR,
            "last_error": ErrorInfo(
                agent="render_v2",
                error_type="MissingManifest",
                message=(
                    "proposal_manifest is missing. Template-first mode requires "
                    "the assembly plan to build the manifest before rendering. "
                    "No fallback rebuild from slides is permitted."
                ),
            ),
        }

    _logger.info(
        "render_v2: manifest present with %d entries, rendering via template-v2",
        manifest.total_slides,
    )

    from src.services.renderer_v2 import render_v2
    from src.services.template_manager import TemplateManager

    output_dir = Path("output")
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

    # Initialize TemplateManager from template path
    try:
        template_path = data_dir / f"template_{lang_suffix}.potx"
        if not template_path.exists():
            template_path = Path("templates") / f"PROPOSAL_TEMPLATE_{lang_suffix.upper()}.potx"
        if not template_path.exists():
            # Fallback to PROPOSAL_TEMPLATE directory
            if lang_suffix == "ar":
                template_path = Path("PROPOSAL_TEMPLATE") / "Arabic_Proposal_Template.potx"
            else:
                template_path = Path("PROPOSAL_TEMPLATE") / "PROPOSAL_TEMPLATE EN.potx"

        _logger.info("render_v2: resolved template path = %s", template_path)
        tm = TemplateManager(str(template_path), catalog_lock_path)
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
        _logger.info(
            "render_v2: calling render_v2() with %d manifest entries, "
            "catalog_lock=%s, output=%s",
            manifest.total_slides,
            catalog_lock_path,
            pptx_path,
        )
        v2_result = render_v2(manifest, tm, catalog_lock_path, pptx_path)

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
) -> str:
    """Route after a gate: continue if approved, end if rejected."""
    gate = getattr(state, gate_field, None)
    if gate and gate.approved:
        return next_node
    return END


def route_after_gate_1(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_1", "retrieval")


def route_after_gate_2(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_2", "analysis")


def route_after_gate_3(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_3", "build_slides")


def route_after_gate_4(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_4", "qa")


def route_after_gate_5(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_5", "render")


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
    graph.add_node("analysis", analysis_node)
    graph.add_node("research", research_node)
    graph.add_node("gate_3", gate_3_node)
    graph.add_node("build_slides", build_slides_node)
    graph.add_node("gate_4", gate_4_node)
    graph.add_node("qa", qa_node)
    graph.add_node("gate_5", gate_5_node)
    graph.add_node("render", render_node)

    # Linear edges
    graph.add_edge(START, "context")
    graph.add_edge("context", "gate_1")

    # Conditional edges after gates
    graph.add_conditional_edges(
        "gate_1", route_after_gate_1, ["retrieval", END]
    )
    graph.add_edge("retrieval", "gate_2")
    graph.add_conditional_edges(
        "gate_2", route_after_gate_2, ["analysis", END]
    )
    graph.add_edge("analysis", "research")
    graph.add_edge("research", "gate_3")
    graph.add_conditional_edges(
        "gate_3", route_after_gate_3, ["build_slides", END]
    )
    graph.add_edge("build_slides", "gate_4")
    graph.add_conditional_edges(
        "gate_4", route_after_gate_4, ["qa", END]
    )
    graph.add_edge("qa", "gate_5")
    graph.add_conditional_edges(
        "gate_5", route_after_gate_5, ["render", END]
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
