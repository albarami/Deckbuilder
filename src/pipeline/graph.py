"""LangGraph StateGraph — wires all 9 agents into the DeckForge pipeline.

Pipeline flow:
  START → context → gate_1 → retrieval → gate_2 → analysis → research
  → gate_3 → structure → gate_4 → content → qa → gate_5 → END

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
from src.agents.content import agent as content_agent
from src.agents.context import agent as context_agent
from src.agents.qa import agent as qa_agent
from src.agents.research import agent as research_agent
from src.agents.retrieval import planner as retrieval_planner
from src.agents.retrieval import ranker as retrieval_ranker
from src.agents.structure import agent as structure_agent
from src.models.enums import PipelineStage
from src.models.state import DeckForgeState, GateDecision
from src.services.search import load_documents, local_search

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

    return {gate_field: gate_decision}


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
    if state.report_markdown:
        length = len(state.report_markdown)
        return f"Research report ready ({length} chars)."
    return "No research report generated."


def _gate_4_summary(state: DeckForgeState) -> str:
    if state.slide_outline:
        count = len(state.slide_outline.slides)
        return f"Slide outline: {count} slides."
    return "No slide outline generated."


def _gate_5_summary(state: DeckForgeState) -> str:
    if state.qa_result:
        s = state.qa_result.deck_summary
        return (
            f"QA complete: {s.passed} passed, {s.failed} failed"
            f" | fail_close={s.fail_close}"
        )
    return "No QA result."


async def gate_1_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 1: User reviews RFP context."""
    return await gate_node(state, 1, _gate_1_summary)


async def gate_2_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 2: User reviews retrieved sources."""
    return await gate_node(state, 2, _gate_2_summary)


async def gate_3_node(state: DeckForgeState) -> dict[str, Any]:
    """Gate 3: User reviews research report (most important gate)."""
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

    # Step 2: Search
    search_results = await local_search(queries.search_queries)

    # Step 3: Rank
    result = await retrieval_ranker.run(state, search_results)
    return {
        "retrieved_sources": result.retrieved_sources,
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

    documents = await load_documents(approved_ids)
    result = await analysis_agent.run(state, documents)
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


async def structure_node(state: DeckForgeState) -> dict[str, Any]:
    """Structure Agent — convert report into slide outline."""
    result = await structure_agent.run(state)
    return {
        "slide_outline": result.slide_outline,
        "current_stage": result.current_stage,
        "session": result.session,
        "errors": result.errors,
        "last_error": result.last_error,
    }


async def content_node(state: DeckForgeState) -> dict[str, Any]:
    """Content Agent — write slide copy from outline + report."""
    result = await content_agent.run(state)
    return {
        "written_slides": result.written_slides,
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
    return _route_after_gate(state, "gate_3", "structure")


def route_after_gate_4(state: DeckForgeState) -> str:
    return _route_after_gate(state, "gate_4", "content")


def route_after_gate_5(state: DeckForgeState) -> str:
    return END


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
    graph.add_node("structure", structure_node)
    graph.add_node("gate_4", gate_4_node)
    graph.add_node("content", content_node)
    graph.add_node("qa", qa_node)
    graph.add_node("gate_5", gate_5_node)

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
        "gate_3", route_after_gate_3, ["structure", END]
    )
    graph.add_edge("structure", "gate_4")
    graph.add_conditional_edges(
        "gate_4", route_after_gate_4, ["content", END]
    )
    graph.add_edge("content", "qa")
    graph.add_edge("qa", "gate_5")
    graph.add_conditional_edges(
        "gate_5", route_after_gate_5, [END]
    )

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
