"""
DeckForge Backend — live pipeline runtime bridge.

Connects the FastAPI bridge layer to the real LangGraph pipeline. Sessions keep
their LangGraph thread ID and the latest DeckForgeState, allowing the backend
to resume from approval gates instead of replaying a fake progress simulation.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from langgraph.types import Command

from backend.models.api_models import (
    AgentRunInfo,
    AgentRunStatus,
    CaseStudySummary,
    DeliverableInfo,
    GapItem,
    Gate1ContextData,
    Gate2SourceReviewData,
    Gate3AssemblyPlanData,
    Gate3ReportReviewData,
    Gate3SourceBookData,
    Gate4SlideReviewData,
    Gate5QaReviewData,
    GatePayloadType,
    ManifestCompositionSummary,
    MethodologyPhaseSummary,
    ReadinessStatus,
    ReportSectionSummary,
    RfpBriefInput,
    SectionCritiqueSummary,
    SensitivitySummary,
    SlideBudgetSummary,
    SlidePreviewItem,
    SourceBookSummary,
    SourceIndexItem,
    SourceReviewItem,
    SSEEvent,
    TeamBioSummary,
    ThumbnailMode,
)
from backend.services.session_manager import PipelineSession, SessionManager
from backend.services.sse_broadcaster import SSEBroadcaster
from src.models.enums import Language, PipelineStage, RendererMode
from src.models.state import DeckForgeState, SessionMetadata, UploadedDocument
from src.pipeline.dry_run import get_dry_run_patches

FRONTEND_STAGE_MAP: dict[str, tuple[str, str, int | None]] = {
    PipelineStage.INTAKE.value: ("intake", "Intake", 1),
    PipelineStage.CONTEXT_REVIEW.value: ("context_analysis", "Context Understanding", 2),
    PipelineStage.SOURCE_REVIEW.value: ("source_research", "Knowledge Retrieval", 3),
    PipelineStage.ANALYSIS.value: ("analysis", "Deep Analysis", 4),
    PipelineStage.ASSEMBLY_PLAN_REVIEW.value: ("assembly_plan", "Assembly Plan Review", 4),
    PipelineStage.REPORT_REVIEW.value: ("report_generation", "Research Report Generation", 5),
    PipelineStage.SLIDE_BUILDING.value: ("slide_rendering", "Iterative Slide Builder", 6),
    PipelineStage.CONTENT_GENERATION.value: ("slide_rendering", "Iterative Slide Builder", 7),
    PipelineStage.QA.value: ("quality_assurance", "Quality Assurance", 8),
    PipelineStage.DECK_REVIEW.value: ("quality_assurance", "Deck Review", 9),
    # Source Book pipeline stages
    PipelineStage.EVIDENCE_CURATION.value: ("evidence_curation", "Evidence Curation", 4),
    PipelineStage.SOURCE_BOOK_GENERATION.value: ("source_book_generation", "Source Book Generation", 5),
    PipelineStage.SOURCE_BOOK_REVIEW.value: ("source_book_review", "Source Book Review", 6),
    # Terminal
    PipelineStage.FINALIZED.value: ("finalized", "Finalization & Export", 10),
    PipelineStage.ERROR.value: ("error", "Pipeline Error", None),
}

SEGMENT_AGENT_MAP: dict[int, list[str]] = {
    0: ["context_agent"],
    1: ["retrieval_planner", "retrieval_ranker"],
    2: ["analysis_agent", "research_agent"],
    3: [
        "draft_agent",
        "review_agent",
        "refine_agent",
        "final_review_agent",
        "presentation_agent",
    ],
    4: ["qa_agent"],
}


async def advance_pipeline_session(
    session_id: str,
    *,
    graph: Any,
    session_manager: SessionManager,
    broadcaster: SSEBroadcaster,
    pipeline_mode: str,
    resume_payload: dict[str, Any] | None = None,
) -> None:
    """Advance a pipeline session until the next gate or completion."""

    session = session_manager.get(session_id)
    if session is None:
        return

    config = {"configurable": {"thread_id": session.thread_id}}

    patches = []
    if pipeline_mode == "dry_run":
        patches = get_dry_run_patches()
        for patch in patches:
            patch.start()

    try:
        # Pre-invoke optimistic broadcast for immediate UI feedback after gate approval
        if resume_payload is not None and resume_payload.get("approved"):
            last_gate = session.completed_gates[-1] if session.completed_gates else None
            if last_gate:
                next_stage_key, next_stage_label, next_step = _optimistic_next_stage(
                    last_gate.gate_number
                )
                session_manager.update_stage(
                    session.session_id, next_stage_key,
                    stage_label=next_stage_label, step_number=next_step,
                )
                await broadcaster.broadcast(
                    session.session_id,
                    _build_event(
                        "stage_change",
                        session_id=session.session_id,
                        stage=next_stage_key,
                        stage_key=next_stage_key,
                        stage_label=next_stage_label,
                        step_number=next_step,
                        message=next_stage_label,
                    ),
                )

        if resume_payload is None:
            state = session.graph_state or _build_initial_state(session, session_manager)
            result = await graph.ainvoke(state, config)
        else:
            result = await graph.ainvoke(Command(resume=resume_payload), config)

        await _sync_session_from_result(
            session=session,
            result=result,
            session_manager=session_manager,
            broadcaster=broadcaster,
        )
    finally:
        for patch in patches:
            patch.stop()


async def advance_source_book_session(
    session_id: str,
    *,
    graph: Any,
    session_manager: SessionManager,
    broadcaster: SSEBroadcaster,
    pipeline_mode: str,
    resume_payload: dict[str, Any] | None = None,
) -> None:
    """Advance a Source Book pipeline session until the next gate or completion.

    Source Book pipeline flow:
      Phase 1: graph.ainvoke(state) → Gate 1 (context review)
      Phase 2: graph.ainvoke(Command(resume)) → Gate 2 (source review)
      Phase 3: graph.ainvoke(Command(resume)) → evidence curation + writer/reviewer → Gate 3
      Phase 4: After Gate 3 approval → extract artifacts, export files, mark complete
               (DO NOT resume graph — Gate 3 is terminal for source_book_only)
    """
    import logging

    logger = logging.getLogger(__name__)

    session = session_manager.get(session_id)
    if session is None:
        return

    config = {"configurable": {"thread_id": session.thread_id}}

    # Check if this is Gate 3 approval — terminal gate for source_book_only
    if resume_payload is not None and resume_payload.get("approved"):
        last_gate = session.completed_gates[-1] if session.completed_gates else None
        if last_gate and last_gate.gate_number == 3:
            # Gate 3 approved — extract artifacts and complete
            await _complete_source_book_session(
                session=session,
                session_manager=session_manager,
                broadcaster=broadcaster,
                logger=logger,
            )
            return

    # For Gate 3 rejection, we DO resume the graph (revision loop)
    # For all other cases (initial start, Gate 1/2 resume), advance normally

    patches = []
    if pipeline_mode == "dry_run":
        patches = get_dry_run_patches()
        for patch in patches:
            patch.start()

    try:
        # Pre-invoke optimistic broadcast for immediate UI feedback
        if resume_payload is not None and resume_payload.get("approved"):
            last_gate_num = session.completed_gates[-1].gate_number if session.completed_gates else 0
            if last_gate_num == 2:
                # Gate 2 approved -> evidence curation about to start
                _optimistic_stage = "evidence_curation"
                _optimistic_label = "Evidence Curation"
                _optimistic_runs = _derive_source_book_agent_runs(
                    session.graph_state or _build_initial_state(session, session_manager)
                )
                # Force evidence_curator to RUNNING
                for _r in _optimistic_runs:
                    if _r.agent_key == "evidence_curator" and _r.status == AgentRunStatus.WAITING:
                        _r.status = AgentRunStatus.RUNNING
                        _r.metric_value = "running"
                        break
                session_manager.update_stage(
                    session.session_id, _optimistic_stage,
                    stage_label=_optimistic_label, step_number=4,
                )
                await broadcaster.broadcast(
                    session.session_id,
                    _build_event(
                        "stage_change",
                        session_id=session.session_id,
                        stage=_optimistic_stage,
                        stage_key=_optimistic_stage,
                        stage_label=_optimistic_label,
                        step_number=4,
                        agent_runs=[_r.model_dump() for _r in _optimistic_runs],
                        message=_optimistic_label,
                    ),
                )
            elif last_gate_num == 1:
                # Gate 1 approved -> source research about to start
                session_manager.update_stage(
                    session.session_id, "source_research",
                    stage_label="Source Research", step_number=3,
                )
                await broadcaster.broadcast(
                    session.session_id,
                    _build_event(
                        "stage_change",
                        session_id=session.session_id,
                        stage="source_research",
                        stage_key="source_research",
                        stage_label="Source Research",
                        step_number=3,
                        message="Source Research",
                    ),
                )

        if resume_payload is None:
            state = session.graph_state or _build_initial_state(session, session_manager)
            result = await graph.ainvoke(state, config)
        else:
            result = await graph.ainvoke(Command(resume=resume_payload), config)

        await _sync_source_book_session(
            session=session,
            result=result,
            session_manager=session_manager,
            broadcaster=broadcaster,
        )
    finally:
        for patch in patches:
            patch.stop()


async def _sync_source_book_session(
    *,
    session: PipelineSession,
    result: dict[str, Any],
    session_manager: SessionManager,
    broadcaster: SSEBroadcaster,
) -> None:
    """Sync session state from graph result for Source Book pipeline.

    Similar to _sync_session_from_result but uses Source Book-specific
    gate payload logic and stage mapping.
    """
    interrupts = result.get("__interrupt__", [])
    state_payload = {key: value for key, value in result.items() if key != "__interrupt__"}
    state = DeckForgeState.model_validate(state_payload)

    session_manager.set_graph_state(
        session.session_id,
        graph_state=state,
        interrupt_info=interrupts[0].value if interrupts else None,
    )

    # Sync RFP brief from state
    if state.rfp_context:
        session.rfp_brief = RfpBriefInput(
            rfp_name={
                "en": state.rfp_context.rfp_name.en,
                "ar": state.rfp_context.rfp_name.ar or "",
            },
            issuing_entity=state.rfp_context.issuing_entity.en,
            procurement_platform=state.rfp_context.procurement_platform or "",
            mandate_summary=state.rfp_context.mandate.en,
            scope_requirements=[
                scope_item.description.en for scope_item in state.rfp_context.scope_items
            ],
            deliverables=[
                deliverable.description.en for deliverable in state.rfp_context.deliverables
            ],
            mandatory_compliance=[
                requirement.requirement.en
                for requirement in state.rfp_context.compliance_requirements
            ],
            key_dates={
                "inquiry_deadline": state.rfp_context.key_dates.inquiry_deadline or ""
                if state.rfp_context.key_dates
                else "",
                "submission_deadline": state.rfp_context.key_dates.submission_deadline or ""
                if state.rfp_context.key_dates
                else "",
                "opening_date": state.rfp_context.key_dates.bid_opening or ""
                if state.rfp_context.key_dates
                else "",
                "expected_award_date": state.rfp_context.key_dates.expected_award or ""
                if state.rfp_context.key_dates
                else "",
                "service_start_date": state.rfp_context.key_dates.service_start or ""
                if state.rfp_context.key_dates
                else "",
            },
            submission_format={
                "format": "Structured proposal submission",
                "delivery_method": "Client portal",
                "file_requirements": state.rfp_context.submission_format.additional_requirements
                if state.rfp_context.submission_format
                else [],
                "additional_instructions": "",
            },
        )

    stage_key, stage_label, step_number = _map_stage(state.current_stage)
    session_manager.update_stage(
        session.session_id,
        stage_key,
        stage_label=stage_label,
        step_number=step_number,
    )

    agent_runs = _derive_source_book_agent_runs(state)
    session_manager.set_agent_runs(session.session_id, agent_runs)

    # Set deliverables for SB mode (DOCX at minimum)
    deliverables = _derive_source_book_deliverables(session.session_id, state)
    session_manager.set_deliverables(session.session_id, deliverables)

    # Post-invoke broadcast with real agent state + session metadata
    _status_session = session_manager.get(session.session_id)
    _metadata_dict = None
    if _status_session:
        _sr = _status_session.to_status_response()
        _metadata_dict = _sr.session_metadata.model_dump() if _sr.session_metadata else None

    await broadcaster.broadcast(
        session.session_id,
        _build_event(
            "stage_change",
            session_id=session.session_id,
            stage=stage_key,
            stage_key=stage_key,
            stage_label=stage_label,
            step_number=step_number,
            agent_runs=[r.model_dump() for r in agent_runs],
            session_metadata=_metadata_dict,
            message=stage_label,
        ),
    )

    # Error handling
    if state.last_error:
        session_manager.set_error(
            session.session_id,
            state.last_error.agent,
            state.last_error.message,
        )
        await broadcaster.broadcast(
            session.session_id,
            _build_event(
                "pipeline_error",
                session_id=session.session_id,
                stage=stage_key,
                stage_key=stage_key,
                stage_label=stage_label,
                step_number=step_number,
                agent=state.last_error.agent,
                agent_key=state.last_error.agent,
                message=state.last_error.message,
                error=state.last_error.message,
            ),
        )
        await broadcaster.close_session(session.session_id)
        return

    # Gate interrupt handling
    if interrupts:
        gate_number = interrupts[0].value.get(
            "gate_number", _sb_gate_number_from_stage(state.current_stage)
        )
        payload_type, gate_data = _build_source_book_gate_payloads(
            session.session_id, state, gate_number
        )
        summary = interrupts[0].value.get("summary", _sb_default_gate_summary(gate_number))
        prompt = interrupts[0].value.get(
            "prompt",
            f"Gate {gate_number}: review, approve, or reject with feedback.",
        )

        session_manager.set_gate_pending(
            session.session_id,
            gate_number=gate_number,
            summary=summary,
            prompt=prompt,
            payload_type=payload_type,
            gate_data=gate_data,
        )

        await broadcaster.broadcast(
            session.session_id,
            _build_event(
                "gate_pending",
                session_id=session.session_id,
                stage=stage_key,
                stage_key=stage_key,
                stage_label=stage_label,
                step_number=step_number,
                gate_number=gate_number,
                gate_payload_type=payload_type,
                summary=summary,
                prompt=prompt,
                gate_data=gate_data.model_dump() if hasattr(gate_data, "model_dump") else gate_data,
                message=summary,
            ),
        )
        return

    # If we reach FINALIZED without gate interrupt, complete
    if state.current_stage == PipelineStage.FINALIZED:
        await _complete_source_book_session(
            session=session,
            session_manager=session_manager,
            broadcaster=broadcaster,
        )


async def _complete_source_book_session(
    *,
    session: PipelineSession,
    session_manager: SessionManager,
    broadcaster: SSEBroadcaster,
    logger: Any = None,
) -> None:
    """Finalize a Source Book session after Gate 3 approval.

    Extracts artifacts from graph state, writes JSON artifacts to disk,
    builds SourceBookSummary metrics, and marks session complete.
    """
    import json
    import logging
    from pathlib import Path

    if logger is None:
        logger = logging.getLogger(__name__)

    state = session.graph_state
    if state is None:
        session_manager.set_error(
            session.session_id, "pipeline", "No graph state available for completion."
        )
        await broadcaster.broadcast(
            session.session_id,
            _build_event(
                "pipeline_error",
                session_id=session.session_id,
                error="No graph state available.",
            ),
        )
        await broadcaster.close_session(session.session_id)
        return

    session_id = session.session_id
    output_dir = Path(f"output/{session_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Extract and write artifact JSONs ──

    # 1. Evidence Ledger
    if state.source_book and state.source_book.evidence_ledger:
        try:
            ledger_data = state.source_book.evidence_ledger.model_dump(mode="json")
            ledger_path = str(output_dir / "evidence_ledger.json")
            with open(ledger_path, "w", encoding="utf-8") as f:
                json.dump(ledger_data, f, indent=2, ensure_ascii=False)
            session.evidence_ledger_path = ledger_path
            session.outputs.evidence_ledger_ready = True
            logger.info("Evidence ledger exported: %s", ledger_path)
        except Exception as e:
            logger.error("Evidence ledger export failed: %s", e)

    # 2. Slide Blueprints — run through blueprint_transform for contract schema
    if state.source_book and state.source_book.slide_blueprints:
        try:
            from src.services.blueprint_transform import transform_to_contract_blueprint
            team_profiles = None
            if state.source_book.why_strategic_gears:
                team_profiles = getattr(
                    state.source_book.why_strategic_gears, "named_consultants", None
                )
            contract_entries, violations = transform_to_contract_blueprint(
                state.source_book.slide_blueprints,
                team_profiles=team_profiles,
            )
            bp_data = {
                "contract_entries": [
                    e.model_dump(mode="json") if hasattr(e, "model_dump") else e
                    for e in contract_entries
                ],
                "validation_violations": violations,
                "legacy_count": len(state.source_book.slide_blueprints),
                "contract_count": len(contract_entries),
            }
            bp_path = str(output_dir / "slide_blueprint.json")
            with open(bp_path, "w", encoding="utf-8") as f:
                json.dump(bp_data, f, indent=2, ensure_ascii=False)
            session.slide_blueprint_path = bp_path
            session.outputs.slide_blueprint_ready = True
            if violations:
                logger.warning(
                    "Slide blueprint exported with %d violations: %s",
                    len(violations), bp_path,
                )
            else:
                logger.info("Slide blueprint exported: %s", bp_path)
        except Exception as e:
            logger.error("Slide blueprint export failed: %s", e)

    # 3. External Evidence Pack
    if state.external_evidence_pack:
        try:
            ee_data = state.external_evidence_pack.model_dump(mode="json")
            ee_path = str(output_dir / "external_evidence.json")
            with open(ee_path, "w", encoding="utf-8") as f:
                json.dump(ee_data, f, indent=2, ensure_ascii=False)
            session.external_evidence_path = ee_path
            session.outputs.external_evidence_ready = True
            logger.info("External evidence exported: %s", ee_path)
        except Exception as e:
            logger.error("External evidence export failed: %s", e)

    # 4. Routing Report
    if state.routing_report:
        try:
            rr_data = state.routing_report if isinstance(state.routing_report, dict) else (
                state.routing_report.model_dump(mode="json")
                if hasattr(state.routing_report, "model_dump")
                else state.routing_report
            )
            rr_path = str(output_dir / "routing_report.json")
            with open(rr_path, "w", encoding="utf-8") as f:
                json.dump(rr_data, f, indent=2, ensure_ascii=False)
            session.routing_report_path = rr_path
            session.outputs.routing_report_ready = True
            logger.info("Routing report exported: %s", rr_path)
        except Exception as e:
            logger.error("Routing report export failed: %s", e)

    # 5. Research Query Log — built from session-safe captured data + evidence pack
    #    Uses the same logic as scripts/source_book_only.py::_collect_research_query_log
    #    but reads from graph state (captured_query_*) not process globals.
    try:
        query_log = _build_research_query_log(state)
        if query_log.get("queries_sent"):
            rql_path = str(output_dir / "research_query_log.json")
            with open(rql_path, "w", encoding="utf-8") as f:
                json.dump(query_log, f, indent=2, ensure_ascii=False)
            session.research_query_log_path = rql_path
            session.outputs.research_query_log_ready = True
            logger.info("Research query log exported: %s", rql_path)
    except Exception as e:
        logger.warning("Research query log export failed: %s", e)

    # 6. Query Execution Log — session-safe per-query telemetry from graph state
    try:
        captured_exec_log = getattr(state, "captured_query_execution_log", [])
        if captured_exec_log:
            qel_path = str(output_dir / "query_execution_log.json")
            with open(qel_path, "w", encoding="utf-8") as f:
                json.dump(captured_exec_log, f, indent=2, ensure_ascii=False)
            session.query_execution_log_path = qel_path
            session.outputs.query_execution_log_ready = True
            logger.info(
                "Query execution log exported: %s (%d entries)",
                qel_path, len(captured_exec_log),
            )
    except Exception as e:
        logger.warning("Query execution log export failed: %s", e)

    # 7. Source Book DOCX — already exported by source_book_node
    if state.report_docx_path:
        session.source_book_path = state.report_docx_path
        session.outputs.source_book_ready = True
        session.outputs.docx_ready = True
    elif state.source_book_docx_path:
        session.source_book_path = state.source_book_docx_path
        session.outputs.source_book_ready = True
        session.outputs.docx_ready = True

    # ── Build SourceBookSummary metrics ──
    summary = _build_source_book_summary(state)
    session.source_book_summary = summary

    # ── Build final deliverables list ──
    deliverables = _derive_source_book_deliverables(session_id, state)
    # Update deliverable readiness from session outputs
    for d in deliverables:
        if d.key == "source_book":
            d.ready = session.outputs.source_book_ready
            d.path = session.source_book_path
            d.download_url = f"/api/pipeline/{session_id}/export/source_book" if d.ready else None
        elif d.key == "evidence_ledger":
            d.ready = session.outputs.evidence_ledger_ready
            d.path = session.evidence_ledger_path
            d.download_url = f"/api/pipeline/{session_id}/export/evidence_ledger" if d.ready else None
        elif d.key == "slide_blueprint":
            d.ready = session.outputs.slide_blueprint_ready
            d.path = session.slide_blueprint_path
            d.download_url = f"/api/pipeline/{session_id}/export/slide_blueprint" if d.ready else None
        elif d.key == "external_evidence":
            d.ready = session.outputs.external_evidence_ready
            d.path = session.external_evidence_path
            d.download_url = f"/api/pipeline/{session_id}/export/external_evidence" if d.ready else None
        elif d.key == "routing_report":
            d.ready = session.outputs.routing_report_ready
            d.path = session.routing_report_path
            d.download_url = f"/api/pipeline/{session_id}/export/routing_report" if d.ready else None
        elif d.key == "research_query_log":
            d.ready = session.outputs.research_query_log_ready
            d.path = session.research_query_log_path
            d.download_url = f"/api/pipeline/{session_id}/export/research_query_log" if d.ready else None
        elif d.key == "query_execution_log":
            d.ready = session.outputs.query_execution_log_ready
            d.path = session.query_execution_log_path
            d.download_url = f"/api/pipeline/{session_id}/export/query_execution_log" if d.ready else None

    # ── Mark session complete ──
    session_manager.set_complete(session_id, slide_count=0, deliverables=deliverables)

    stage_key, stage_label, step_number = "finalized", "Finalization & Export", 10
    await broadcaster.broadcast(
        session_id,
        _build_event(
            "pipeline_complete",
            session_id=session_id,
            stage=stage_key,
            stage_key=stage_key,
            stage_label=stage_label,
            step_number=step_number,
            slide_count=0,
            message="Source Book pipeline complete. Artifacts are ready.",
        ),
    )
    await broadcaster.close_session(session_id)


def _build_source_book_summary(state: DeckForgeState) -> SourceBookSummary:
    """Extract Source Book metrics from graph state into typed summary."""
    sb = state.source_book
    review = state.source_book_review
    evidence_pack = state.external_evidence_pack

    word_count = 0
    evidence_ledger_entries = 0
    blueprint_entries = 0
    capability_mappings = 0
    consultant_count = 0
    real_consultant_names: list[str] = []
    project_count = 0

    if sb:
        # Real prose word count — extracts actual text fields, not JSON blobs
        word_count = _count_source_book_words(sb)
        evidence_ledger_entries = len(sb.evidence_ledger.entries) if sb.evidence_ledger else 0
        blueprint_entries = len(sb.slide_blueprints)

        # Why Strategic Gears section metrics — uses actual model fields:
        # WhyStrategicGears.named_consultants, .project_experience, .capability_mapping
        wsg = sb.why_strategic_gears
        if wsg:
            capability_mappings = len(getattr(wsg, "capability_mapping", []))
            consultants = getattr(wsg, "named_consultants", [])
            consultant_count = len(consultants)
            real_consultant_names = [
                getattr(c, "name", "") for c in consultants
                if getattr(c, "name", "")
            ]
            project_count = len(getattr(wsg, "project_experience", []))

    external_sources = 0
    if evidence_pack:
        sources = getattr(evidence_pack, "sources", [])
        external_sources = len(sources)

    return SourceBookSummary(
        word_count=word_count,
        reviewer_score=review.overall_score if review else 0,
        threshold_met=review.pass_threshold_met if review else False,
        competitive_viability=review.competitive_viability if review else "unknown",
        evidence_ledger_entries=evidence_ledger_entries,
        slide_blueprint_entries=blueprint_entries,
        external_sources=external_sources,
        capability_mappings=capability_mappings,
        consultant_count=consultant_count,
        real_consultant_names=real_consultant_names,
        project_count=project_count,
        pass_number=sb.pass_number if sb else 0,
    )


def _derive_source_book_agent_runs(state: DeckForgeState) -> list[AgentRunInfo]:
    """Build agent run cards for Source Book pipeline mode."""
    runs = {
        agent_key: AgentRunInfo(
            agent_key=agent_key,
            agent_label=agent_label,
            model=model,
            status=AgentRunStatus.WAITING,
            metric_label=metric_label,
            metric_value="pending",
            step_key=step_key,
            step_number=step_number,
        )
        for agent_key, agent_label, model, metric_label, step_key, step_number in [
            ("context_agent", "Context Agent", "GPT-5.4", "Context package", "context_understanding", 1),
            ("retrieval_planner", "Retrieval Planner", "GPT-5.4", "Search plan", "knowledge_retrieval", 2),
            ("retrieval_ranker", "Ranker Agent", "GPT-5.4", "Source shortlist", "knowledge_retrieval", 2),
            ("evidence_curator", "Evidence Curator", "Claude Opus 4.6", "Evidence pack", "evidence_curation", 3),
            ("routing_agent", "Routing Agent", "GPT-5.4", "Jurisdiction routing", "evidence_curation", 3),
            ("proposal_strategist", "Proposal Strategist", "Claude Opus 4.6", "Win themes", "evidence_curation", 3),
            ("sb_writer", "Source Book Writer", "Claude Opus 4.6", "Source book draft", "source_book_generation", 4),
            ("sb_reviewer", "Source Book Reviewer", "GPT-5.4", "Review score", "source_book_review", 5),
            ("sb_evidence_extractor", "Evidence Extractor", "Claude Opus 4.6", "Ledger entries", "source_book_generation", 4),
        ]
    }

    # Update status based on state
    if state.rfp_context:
        runs["context_agent"].status = AgentRunStatus.COMPLETE
        runs["context_agent"].metric_value = f"{state.rfp_context.completeness.top_level_fields_extracted}/10 fields"

    if state.retrieved_sources:
        runs["retrieval_planner"].status = AgentRunStatus.COMPLETE
        runs["retrieval_planner"].metric_value = "queries issued"
        runs["retrieval_ranker"].status = AgentRunStatus.COMPLETE
        runs["retrieval_ranker"].metric_value = f"{len(state.retrieved_sources)} sources"

    if state.external_evidence_pack:
        runs["evidence_curator"].status = AgentRunStatus.COMPLETE
        sources = getattr(state.external_evidence_pack, "sources", [])
        runs["evidence_curator"].metric_value = f"{len(sources)} evidence sources"

    if state.routing_report:
        runs["routing_agent"].status = AgentRunStatus.COMPLETE
        if isinstance(state.routing_report, dict):
            confidence = state.routing_report.get("routing_confidence", 0)
            runs["routing_agent"].metric_value = f"conf={confidence:.2f}"
        else:
            runs["routing_agent"].metric_value = "classified"

    if state.proposal_strategy:
        runs["proposal_strategist"].status = AgentRunStatus.COMPLETE
        win_themes = getattr(state.proposal_strategy, "win_themes", [])
        runs["proposal_strategist"].metric_value = f"{len(win_themes)} themes"

    if state.source_book:
        runs["sb_writer"].status = AgentRunStatus.COMPLETE
        bp_count = len(state.source_book.slide_blueprints)
        ledger_count = len(state.source_book.evidence_ledger.entries) if state.source_book.evidence_ledger else 0
        runs["sb_writer"].metric_value = f"{bp_count} blueprints, {ledger_count} evidence"

    if state.source_book_review:
        runs["sb_reviewer"].status = AgentRunStatus.COMPLETE
        runs["sb_reviewer"].metric_value = f"{state.source_book_review.overall_score}/5"

    if state.source_book and state.source_book.evidence_ledger and len(state.source_book.evidence_ledger.entries) > 0:
        runs["sb_evidence_extractor"].status = AgentRunStatus.COMPLETE
        runs["sb_evidence_extractor"].metric_value = f"{len(state.source_book.evidence_ledger.entries)} entries"

    # Mark currently running agent
    current_stage = state.current_stage.value if hasattr(state.current_stage, "value") else str(state.current_stage)
    stage_to_agents = {
        PipelineStage.CONTEXT_REVIEW.value: ["context_agent"],
        PipelineStage.SOURCE_REVIEW.value: ["retrieval_planner", "retrieval_ranker"],
        PipelineStage.EVIDENCE_CURATION.value: ["evidence_curator", "routing_agent", "proposal_strategist"],
        PipelineStage.SOURCE_BOOK_GENERATION.value: ["sb_writer", "sb_evidence_extractor"],
        PipelineStage.SOURCE_BOOK_REVIEW.value: ["sb_reviewer"],
    }
    active_agents = stage_to_agents.get(current_stage, [])
    for key in active_agents:
        if runs[key].status == AgentRunStatus.WAITING:
            runs[key].status = AgentRunStatus.RUNNING
            runs[key].metric_value = "running"
            break

    if state.last_error:
        failing = runs.get(state.last_error.agent)
        if failing:
            failing.status = AgentRunStatus.ERROR
            failing.metric_value = state.last_error.message

    return list(runs.values())


def _derive_source_book_deliverables(session_id: str, state: DeckForgeState) -> list[DeliverableInfo]:
    """Build deliverable list for Source Book pipeline mode."""
    return [
        DeliverableInfo(
            key="source_book",
            label="Source Book (DOCX)",
            ready=bool(state.report_docx_path or state.source_book_docx_path),
            filename=f"source_book_{session_id[:6]}.docx",
            download_url=f"/api/pipeline/{session_id}/export/source_book"
            if (state.report_docx_path or state.source_book_docx_path)
            else None,
            path=state.report_docx_path or state.source_book_docx_path,
        ),
        DeliverableInfo(
            key="evidence_ledger",
            label="Evidence Ledger (JSON)",
            ready=bool(state.evidence_ledger_path),
            filename=f"evidence_ledger_{session_id[:6]}.json",
            download_url=f"/api/pipeline/{session_id}/export/evidence_ledger"
            if state.evidence_ledger_path
            else None,
            path=state.evidence_ledger_path,
        ),
        DeliverableInfo(
            key="slide_blueprint",
            label="Slide Blueprint (JSON)",
            ready=bool(state.slide_blueprint_path),
            filename=f"slide_blueprint_{session_id[:6]}.json",
            download_url=f"/api/pipeline/{session_id}/export/slide_blueprint"
            if state.slide_blueprint_path
            else None,
            path=state.slide_blueprint_path,
        ),
        DeliverableInfo(
            key="external_evidence",
            label="External Evidence Pack (JSON)",
            ready=bool(state.external_evidence_path),
            filename=f"external_evidence_{session_id[:6]}.json",
            download_url=f"/api/pipeline/{session_id}/export/external_evidence"
            if state.external_evidence_path
            else None,
            path=state.external_evidence_path,
        ),
        DeliverableInfo(
            key="routing_report",
            label="Routing Report (JSON)",
            ready=bool(state.routing_report_path),
            filename=f"routing_report_{session_id[:6]}.json",
            download_url=f"/api/pipeline/{session_id}/export/routing_report"
            if state.routing_report_path
            else None,
            path=state.routing_report_path,
        ),
        DeliverableInfo(
            key="research_query_log",
            label="Research Query Log (JSON)",
            ready=bool(state.research_query_log_path),
            filename=f"research_query_log_{session_id[:6]}.json",
            download_url=f"/api/pipeline/{session_id}/export/research_query_log"
            if state.research_query_log_path
            else None,
            path=state.research_query_log_path,
        ),
        DeliverableInfo(
            key="query_execution_log",
            label="Query Execution Log (JSON)",
            ready=bool(state.query_execution_log_path),
            filename=f"query_execution_log_{session_id[:6]}.json",
            download_url=f"/api/pipeline/{session_id}/export/query_execution_log"
            if state.query_execution_log_path
            else None,
            path=state.query_execution_log_path,
        ),
    ]


def _build_source_book_gate_payloads(
    session_id: str,
    state: DeckForgeState,
    gate_number: int,
) -> tuple[GatePayloadType, Any]:
    """Build gate payload for Source Book pipeline mode."""
    if gate_number == 1:
        return GatePayloadType.CONTEXT_REVIEW, _build_gate1_payload(state)
    if gate_number == 2:
        return GatePayloadType.SOURCE_REVIEW, _build_gate2_payload(state)
    # Gate 3 in source_book_only = Source Book Review
    return GatePayloadType.SOURCE_BOOK_REVIEW, _build_gate3_source_book_payload(session_id, state)


def _build_gate3_source_book_payload(
    session_id: str,
    state: DeckForgeState,
) -> Gate3SourceBookData:
    """Build Gate 3 payload for Source Book review."""
    review = state.source_book_review
    sb = state.source_book

    # Word count estimate
    word_count = 0
    if sb:
        for section_name in [
            "rfp_interpretation", "client_problem_framing",
            "why_strategic_gears", "external_evidence", "proposed_solution",
        ]:
            section = getattr(sb, section_name, None)
            if section:
                section_text = str(section.model_dump(mode="json") if hasattr(section, "model_dump") else section)
                word_count += len(section_text.split())

    # Section critiques from reviewer
    critiques: list[SectionCritiqueSummary] = []
    if review and review.section_critiques:
        for sc in review.section_critiques:
            critiques.append(SectionCritiqueSummary(
                section_id=sc.section_id,
                score=sc.score,
                issues=list(sc.issues),
                rewrite_instructions=list(sc.rewrite_instructions),
            ))

    evidence_count = 0
    blueprint_count = 0
    if sb:
        evidence_count = len(sb.evidence_ledger.entries) if sb.evidence_ledger else 0
        blueprint_count = len(sb.slide_blueprints)

    docx_preview_url = ""
    if state.report_docx_path or state.source_book_docx_path:
        docx_preview_url = f"/api/pipeline/{session_id}/export/source_book"

    return Gate3SourceBookData(
        reviewer_score=review.overall_score if review else 0,
        threshold_met=review.pass_threshold_met if review else False,
        competitive_viability=review.competitive_viability if review else "unknown",
        pass_number=sb.pass_number if sb else 0,
        rewrite_required=review.rewrite_required if review else False,
        section_critiques=critiques,
        coherence_issues=list(review.coherence_issues) if review else [],
        word_count=word_count,
        evidence_count=evidence_count,
        blueprint_count=blueprint_count,
        docx_preview_url=docx_preview_url,
    )


def _sb_gate_number_from_stage(stage: Any) -> int | None:
    """Map pipeline stage to gate number for Source Book mode."""
    stage_value = stage.value if hasattr(stage, "value") else str(stage)
    return {
        PipelineStage.CONTEXT_REVIEW.value: 1,
        PipelineStage.SOURCE_REVIEW.value: 2,
        PipelineStage.SOURCE_BOOK_REVIEW.value: 3,
    }.get(stage_value)


def _sb_default_gate_summary(gate_number: int) -> str:
    return {
        1: "Context review is ready.",
        2: "Source review is ready.",
        3: "Source Book review is ready.",
    }.get(gate_number, "Review required.")


def _build_initial_state(
    session: PipelineSession,
    session_manager: SessionManager,
) -> DeckForgeState:
    uploaded_documents: list[UploadedDocument] = []
    for upload_id in session.upload_ids:
        metadata = session_manager.get_upload(upload_id)
        if metadata is None:
            continue
        uploaded_documents.append(
            UploadedDocument(
                filename=str(metadata.get("filename", "uploaded-document")),
                content_text=str(metadata.get("content_text", "")),
                language=_to_language(str(metadata.get("detected_language", session.language))),
            )
        )

    ai_summary = session.text_input or ""
    if not ai_summary and uploaded_documents:
        ai_summary = "\n\n---\n\n".join(
            f"[{doc.filename}]\n{doc.content_text[:5000]}"
            for doc in uploaded_documents
            if doc.content_text
        )

    return DeckForgeState(
        ai_assist_summary=ai_summary,
        uploaded_documents=uploaded_documents,
        user_notes=session.user_notes,
        output_language=_to_language(session.language),
        renderer_mode=RendererMode(session.renderer_mode) if session.renderer_mode else RendererMode.TEMPLATE_V2,
        proposal_mode=session.proposal_mode or "standard",
        sector=session.sector or "",
        geography=session.geography or "",
        session=SessionMetadata(session_id=session.session_id),
    )


async def _sync_session_from_result(
    *,
    session: PipelineSession,
    result: dict[str, Any],
    session_manager: SessionManager,
    broadcaster: SSEBroadcaster,
) -> None:
    interrupts = result.get("__interrupt__", [])
    state_payload = {key: value for key, value in result.items() if key != "__interrupt__"}
    state = DeckForgeState.model_validate(state_payload)

    session_manager.set_graph_state(
        session.session_id,
        graph_state=state,
        interrupt_info=interrupts[0].value if interrupts else None,
    )

    if state.rfp_context:
        session.rfp_brief = RfpBriefInput(
            rfp_name={
                "en": state.rfp_context.rfp_name.en,
                "ar": state.rfp_context.rfp_name.ar or "",
            },
            issuing_entity=state.rfp_context.issuing_entity.en,
            procurement_platform=state.rfp_context.procurement_platform or "",
            mandate_summary=state.rfp_context.mandate.en,
            scope_requirements=[
                scope_item.description.en for scope_item in state.rfp_context.scope_items
            ],
            deliverables=[
                deliverable.description.en for deliverable in state.rfp_context.deliverables
            ],
            mandatory_compliance=[
                requirement.requirement.en
                for requirement in state.rfp_context.compliance_requirements
            ],
            key_dates={
                "inquiry_deadline": state.rfp_context.key_dates.inquiry_deadline or ""
                if state.rfp_context.key_dates
                else "",
                "submission_deadline": state.rfp_context.key_dates.submission_deadline or ""
                if state.rfp_context.key_dates
                else "",
                "opening_date": state.rfp_context.key_dates.bid_opening or ""
                if state.rfp_context.key_dates
                else "",
                "expected_award_date": state.rfp_context.key_dates.expected_award or ""
                if state.rfp_context.key_dates
                else "",
                "service_start_date": state.rfp_context.key_dates.service_start or ""
                if state.rfp_context.key_dates
                else "",
            },
            submission_format={
                "format": "Structured proposal submission",
                "delivery_method": "Client portal",
                "file_requirements": state.rfp_context.submission_format.additional_requirements
                if state.rfp_context.submission_format
                else [],
                "additional_instructions": "",
            },
        )

    stage_key, stage_label, step_number = _map_stage(state.current_stage)
    session_manager.update_stage(
        session.session_id,
        stage_key,
        stage_label=stage_label,
        step_number=step_number,
    )

    agent_runs = _derive_agent_runs(state)
    session_manager.set_agent_runs(session.session_id, agent_runs)

    slides_data = _build_slide_preview_data(session.session_id, state)
    if slides_data:
        preview_kind = (
            ThumbnailMode.RENDERED
            if state.current_stage in (PipelineStage.QA, PipelineStage.DECK_REVIEW, PipelineStage.FINALIZED)
            else ThumbnailMode.DRAFT
        )
        session_manager.set_preview_assets(
            session.session_id,
            slides_data=slides_data,
            thumbnail_mode=ThumbnailMode.RENDERED,
            preview_kind=preview_kind,
        )

    deliverables = _derive_deliverables(session.session_id, state)
    session_manager.set_deliverables(session.session_id, deliverables)

    # Post-invoke broadcast with real agent state + session metadata
    _status_session = session_manager.get(session.session_id)
    _metadata_dict = None
    if _status_session:
        _sr = _status_session.to_status_response()
        _metadata_dict = _sr.session_metadata.model_dump() if _sr.session_metadata else None

    await broadcaster.broadcast(
        session.session_id,
        _build_event(
            "stage_change",
            session_id=session.session_id,
            stage=stage_key,
            stage_key=stage_key,
            stage_label=stage_label,
            step_number=step_number,
            agent_runs=[r.model_dump() for r in agent_runs],
            session_metadata=_metadata_dict,
            message=stage_label,
        ),
    )

    if state.last_error:
        session_manager.set_error(
            session.session_id,
            state.last_error.agent,
            state.last_error.message,
        )
        await broadcaster.broadcast(
            session.session_id,
            _build_event(
                "pipeline_error",
                session_id=session.session_id,
                stage=stage_key,
                stage_key=stage_key,
                stage_label=stage_label,
                step_number=step_number,
                agent=state.last_error.agent,
                agent_key=state.last_error.agent,
                message=state.last_error.message,
                error=state.last_error.message,
            ),
        )
        await broadcaster.close_session(session.session_id)
        return

    if interrupts:
        gate_number = interrupts[0].value.get("gate_number", _gate_number_from_stage(state.current_stage))
        payload_type, gate_data = _build_gate_payloads(session.session_id, state, gate_number)
        summary = interrupts[0].value.get("summary", _default_gate_summary(gate_number))
        prompt = interrupts[0].value.get(
            "prompt",
            f"Gate {gate_number}: review, approve, or reject with feedback.",
        )

        session_manager.set_gate_pending(
            session.session_id,
            gate_number=gate_number,
            summary=summary,
            prompt=prompt,
            payload_type=payload_type,
            gate_data=gate_data,
        )

        await broadcaster.broadcast(
            session.session_id,
            _build_event(
                "gate_pending",
                session_id=session.session_id,
                stage=stage_key,
                stage_key=stage_key,
                stage_label=stage_label,
                step_number=step_number,
                gate_number=gate_number,
                gate_payload_type=payload_type,
                summary=summary,
                prompt=prompt,
                gate_data=gate_data.model_dump() if hasattr(gate_data, "model_dump") else gate_data,
                message=summary,
            ),
        )
        return

    if state.current_stage == PipelineStage.FINALIZED:
        session_manager.set_complete(
            session.session_id,
            slide_count=len(state.final_slides or state.written_slides.slides if state.written_slides else []),
            deliverables=deliverables,
        )
        await broadcaster.broadcast(
            session.session_id,
            _build_event(
                "pipeline_complete",
                session_id=session.session_id,
                stage=stage_key,
                stage_key=stage_key,
                stage_label=stage_label,
                step_number=step_number,
                slide_count=session.outputs.slide_count,
                message="Pipeline complete. Deliverables are ready.",
            ),
        )
        await broadcaster.close_session(session.session_id)


def _derive_agent_runs(state: DeckForgeState) -> list[AgentRunInfo]:
    runs = {
        agent_key: AgentRunInfo(
            agent_key=agent_key,
            agent_label=agent_label,
            model=model,
            status=AgentRunStatus.WAITING,
            metric_label=metric_label,
            metric_value="pending",
            step_key=step_key,
            step_number=step_number,
        )
        for agent_key, agent_label, model, metric_label, step_key, step_number in [
            ("context_agent", "Context Agent", "GPT-5.4", "Context package", "context_understanding", 2),
            ("retrieval_planner", "Retrieval Planner", "GPT-5.4", "Search plan", "knowledge_retrieval", 3),
            ("retrieval_ranker", "Ranker Agent", "GPT-5.4", "Source shortlist", "knowledge_retrieval", 3),
            ("analysis_agent", "Analysis Agent", "Claude Opus 4.6", "Analysis memo", "deep_analysis", 4),
            ("research_agent", "Research Agent", "Claude Opus 4.6", "Research synthesis", "report_generation", 5),
            ("draft_agent", "Draft Agent", "Claude Opus 4.6", "Draft report", "slide_structure", 6),
            ("review_agent", "Review Agent", "GPT-5.4", "Review checks", "slide_content_review", 7),
            ("refine_agent", "Refine Agent", "Claude Opus 4.6", "Revision pass", "slide_refinement", 8),
            ("final_review_agent", "Final Review Agent", "GPT-5.4", "Final coherence check", "final_slide_review", 9),
            ("presentation_agent", "Presentation Agent", "Claude Opus 4.6",
             "Slide package", "presentation_package", 10),
            ("qa_agent", "QA Agent", "GPT-5.4", "Submission QA", "quality_assurance", 8),
        ]
    }

    if state.rfp_context:
        runs["context_agent"].status = AgentRunStatus.COMPLETE
        runs["context_agent"].metric_value = f"{state.rfp_context.completeness.top_level_fields_extracted}/10 fields"

    if state.retrieved_sources:
        runs["retrieval_planner"].status = AgentRunStatus.COMPLETE
        runs["retrieval_planner"].metric_value = "queries issued"
        runs["retrieval_ranker"].status = AgentRunStatus.COMPLETE
        runs["retrieval_ranker"].metric_value = f"{len(state.retrieved_sources)} sources"

    if state.reference_index:
        runs["analysis_agent"].status = AgentRunStatus.COMPLETE
        runs["analysis_agent"].metric_value = f"{len(state.reference_index.claims)} claims"

    if state.research_report:
        runs["research_agent"].status = AgentRunStatus.COMPLETE
        runs["research_agent"].metric_value = f"{len(state.research_report.sections)} sections"

    if state.deck_drafts:
        runs["draft_agent"].status = AgentRunStatus.COMPLETE
        runs["draft_agent"].metric_value = f"{len(state.deck_drafts[0].get('slides', []))} slides"
    if state.deck_reviews:
        runs["review_agent"].status = AgentRunStatus.COMPLETE
        runs["review_agent"].metric_value = f"{len(state.deck_reviews[0].get('critiques', []))} critiques"
    if len(state.deck_drafts) > 1:
        runs["refine_agent"].status = AgentRunStatus.COMPLETE
        runs["refine_agent"].metric_value = f"{len(state.deck_drafts[1].get('slides', []))} refined"
    if len(state.deck_reviews) > 1:
        runs["final_review_agent"].status = AgentRunStatus.COMPLETE
        runs["final_review_agent"].metric_value = f"{state.deck_reviews[1].get('overall_score', 0)}/5"
    if state.written_slides:
        runs["presentation_agent"].status = AgentRunStatus.COMPLETE
        runs["presentation_agent"].metric_value = f"{len(state.written_slides.slides)} written"

    if state.qa_result:
        runs["qa_agent"].status = AgentRunStatus.COMPLETE
        runs["qa_agent"].metric_value = (
            f"{state.qa_result.deck_summary.passed} pass"
            f" / {state.qa_result.deck_summary.failed} fail"
        )

    current_stage = state.current_stage.value if hasattr(state.current_stage, "value") else str(state.current_stage)
    gate_number = _gate_number_from_stage(state.current_stage)
    active_segment = {
        PipelineStage.CONTEXT_REVIEW.value: 0,
        PipelineStage.SOURCE_REVIEW.value: 1,
        PipelineStage.ANALYSIS.value: 2,
        PipelineStage.REPORT_REVIEW.value: 2,
        PipelineStage.SLIDE_BUILDING.value: 3,
        PipelineStage.CONTENT_GENERATION.value: 3,
        PipelineStage.QA.value: 4,
        PipelineStage.DECK_REVIEW.value: 4,
    }.get(current_stage)

    if active_segment is not None and not state.last_error and gate_number is None:
        for key in SEGMENT_AGENT_MAP.get(active_segment, []):
            if runs[key].status == AgentRunStatus.WAITING:
                runs[key].status = AgentRunStatus.RUNNING
                runs[key].metric_value = "running"
                break

    if gate_number is not None:
        for key in SEGMENT_AGENT_MAP.get(gate_number - 1, []):
            if runs[key].status == AgentRunStatus.WAITING:
                runs[key].status = AgentRunStatus.COMPLETE
                runs[key].metric_value = runs[key].metric_value if runs[key].metric_value != "pending" else "completed"

    if state.last_error:
        failing = runs.get(state.last_error.agent)
        if failing:
            failing.status = AgentRunStatus.ERROR
            failing.metric_value = state.last_error.message

    return list(runs.values())


def _build_slide_preview_data(session_id: str, state: DeckForgeState) -> list[dict[str, Any]]:
    slides = state.final_slides or (state.written_slides.slides if state.written_slides else [])
    payload: list[dict[str, Any]] = []

    for index, slide in enumerate(slides, start=1):
        body_preview = slide.body_content.text_elements[:3] if slide.body_content else []
        payload.append(
            {
                "slide_id": slide.slide_id,
                "slide_number": index,
                "entry_type": "content" if index > 1 else "title",
                "asset_id": slide.slide_id.lower(),
                "semantic_layout_id": slide.layout_type,
                "section_id": slide.report_section_ref or f"Section {((index - 1) // 3) + 1}",
                "title": slide.title,
                "key_message": slide.key_message,
                "layout_type": slide.layout_type,
                "body_content_preview": body_preview,
                "source_claims": slide.source_claims,
                "source_refs": slide.source_refs,
                "shape_count": len(body_preview) + 2,
                "fonts": ["IBM Plex Sans"],
                "text_preview": " • ".join(body_preview) if body_preview else slide.title,
                "thumbnail_url": f"/api/pipeline/{session_id}/slides/{index}/thumbnail.png?preview_kind=draft",
                "report_section_ref": slide.report_section_ref,
                "rfp_criterion_ref": slide.rfp_criterion_ref,
                "speaker_notes_preview": slide.speaker_notes[:180],
                "sensitivity_tags": [str(tag) for tag in slide.sensitivity_tags],
                "content_guidance": slide.content_guidance,
                "change_history_count": len(slide.change_history),
            }
        )

    return payload


def _derive_deliverables(session_id: str, state: DeckForgeState) -> list[DeliverableInfo]:
    return [
        DeliverableInfo(
            key="pptx",
            label="Presentation deck",
            ready=bool(state.pptx_path),
            filename=state.pptx_path.split("\\")[-1] if state.pptx_path else f"proposal_{session_id[:6]}_en.pptx",
            download_url=f"/api/pipeline/{session_id}/export/pptx" if state.pptx_path else None,
            path=state.pptx_path,
        ),
        DeliverableInfo(
            key="docx",
            label="Research report",
            ready=bool(state.report_docx_path),
            filename=(
                state.report_docx_path.split("\\")[-1]
                if state.report_docx_path
                else f"research_report_{session_id[:6]}_en.docx"
            ),
            download_url=f"/api/pipeline/{session_id}/export/docx" if state.report_docx_path else None,
            path=state.report_docx_path,
        ),
        DeliverableInfo(
            key="source_index",
            label="Source index",
            ready=bool(getattr(state, "source_index_path", None)),
            filename=f"source_index_{session_id[:6]}.docx",
            download_url=(
                f"/api/pipeline/{session_id}/export/source_index"
                if getattr(state, "source_index_path", None)
                else None
            ),
            path=getattr(state, "source_index_path", None),
        ),
        DeliverableInfo(
            key="gap_report",
            label="Gap report",
            ready=bool(getattr(state, "gap_report_path", None)),
            filename=f"gap_report_{session_id[:6]}.docx",
            download_url=(
                f"/api/pipeline/{session_id}/export/gap_report"
                if getattr(state, "gap_report_path", None)
                else None
            ),
            path=getattr(state, "gap_report_path", None),
        ),
    ]


def _build_gate_payloads(
    session_id: str,
    state: DeckForgeState,
    gate_number: int,
) -> tuple[GatePayloadType, Any]:
    if gate_number == 1:
        return GatePayloadType.CONTEXT_REVIEW, _build_gate1_payload(state)
    if gate_number == 2:
        return GatePayloadType.SOURCE_REVIEW, _build_gate2_payload(state)
    if gate_number == 3:
        if state.assembly_plan is not None:
            return GatePayloadType.ASSEMBLY_PLAN_REVIEW, _build_gate3_assembly_plan_payload(state)
        return GatePayloadType.REPORT_REVIEW, _build_gate3_payload(state)
    if gate_number == 4:
        return GatePayloadType.SLIDE_REVIEW, _build_gate4_payload(session_id, state)
    return GatePayloadType.QA_REVIEW, _build_gate5_payload(session_id, state)


def _build_gate1_payload(state: DeckForgeState) -> Gate1ContextData:
    context = state.rfp_context
    if context is None:
        return Gate1ContextData(
            rfp_brief=RfpBriefInput(),
            missing_fields=["rfp_context"],
            selected_output_language=str(state.output_language),
            user_notes=state.user_notes,
            evaluation_highlights=[],
        )

    technical_weight = (
        context.evaluation_criteria.technical.weight_pct
        if context.evaluation_criteria and context.evaluation_criteria.technical
        else None
    )
    financial_weight = (
        context.evaluation_criteria.financial.weight_pct
        if context.evaluation_criteria and context.evaluation_criteria.financial
        else None
    )

    return Gate1ContextData(
        rfp_brief=RfpBriefInput(
            rfp_name={"en": context.rfp_name.en, "ar": context.rfp_name.ar or ""},
            issuing_entity=context.issuing_entity.en,
            procurement_platform=context.procurement_platform or "",
            mandate_summary=context.mandate.en,
            scope_requirements=[item.description.en for item in context.scope_items],
            deliverables=[item.description.en for item in context.deliverables],
            technical_evaluation=[],
            financial_evaluation=[],
            mandatory_compliance=[req.requirement.en for req in context.compliance_requirements],
            key_dates={
                "inquiry_deadline": context.key_dates.inquiry_deadline or "" if context.key_dates else "",
                "submission_deadline": context.key_dates.submission_deadline or "" if context.key_dates else "",
                "opening_date": context.key_dates.bid_opening or "" if context.key_dates else "",
                "expected_award_date": context.key_dates.expected_award or "" if context.key_dates else "",
                "service_start_date": context.key_dates.service_start or "" if context.key_dates else "",
            },
            submission_format={
                "format": "Structured proposal submission",
                "delivery_method": "Client portal",
                "file_requirements": (
                    context.submission_format.additional_requirements
                    if context.submission_format
                    else []
                ),
                "additional_instructions": "",
            },
        ),
        missing_fields=context.completeness.top_level_missing,
        selected_output_language=str(state.output_language),
        user_notes=state.user_notes,
        evaluation_highlights=[
            (
                f"Technical evaluation weight: {technical_weight}%"
                if technical_weight is not None
                else "Technical evaluation weight not specified"
            ),
            (
                f"Financial evaluation weight: {financial_weight}%"
                if financial_weight is not None
                else "Financial evaluation weight not specified"
            ),
            f"{len(context.compliance_requirements)} compliance requirements identified",
        ],
    )


def _build_gate2_payload(state: DeckForgeState) -> Gate2SourceReviewData:
    return Gate2SourceReviewData(
        sources=[
            SourceReviewItem(
                source_id=source.doc_id,
                title=source.title,
                relevance_score=(
                    float(source.relevance_score) / 100
                    if source.relevance_score > 1
                    else float(source.relevance_score)
                ),
                snippet=source.summary,
                matched_criteria=list(source.matched_criteria),
                selected=source.recommendation == "include",
            )
            for source in state.retrieved_sources
        ],
        retrieval_strategies=["retrieval_planner", "retrieval_ranker"],
        source_count=len(state.retrieved_sources),
    )


def _build_gate3_payload(state: DeckForgeState) -> Gate3ReportReviewData:
    report = state.research_report
    reference_index = state.reference_index

    sensitivity_counts = Counter()
    if reference_index:
        for claim in reference_index.claims:
            sensitivity_counts[str(claim.sensitivity_tag)] += 1

    return Gate3ReportReviewData(
        report_markdown=state.report_markdown,
        sections=[
            ReportSectionSummary(
                section_id=section.section_id,
                title=section.heading,
                claim_count=len(section.claims_referenced),
                gap_count=len(section.gaps_flagged),
            )
            for section in (report.sections if report else [])
        ],
        gaps=[
            GapItem(
                gap_id=gap.gap_id,
                label=gap.rfp_criterion,
                description=gap.description,
                severity=str(gap.severity),
                status="open",
            )
            for gap in (report.all_gaps if report else [])
        ],
        sensitivity_summary=[
            SensitivitySummary(tag=tag, count=count)
            for tag, count in sensitivity_counts.items()
        ],
        source_index=[
            SourceIndexItem(
                source_id=entry.claim_id,
                title=entry.document_title,
                location=entry.date or "",
                url=entry.sharepoint_path,
            )
            for entry in (report.source_index if report else [])
        ],
    )


def _safe_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Get attribute from object or dict, with fallback."""
    val = getattr(obj, key, None)
    if val is not None:
        return val
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _build_gate3_assembly_plan_payload(
    state: DeckForgeState,
) -> Gate3AssemblyPlanData:
    """Build Gate 3 payload from assembly plan (template-first path)."""
    plan = state.assembly_plan
    if plan is None:
        return Gate3AssemblyPlanData()

    llm_output = _safe_attr(plan, "llm_output")
    case_result = _safe_attr(plan, "case_study_result")
    team_result = _safe_attr(plan, "team_result")
    budget = _safe_attr(plan, "slide_budget")

    # Methodology phases
    phases: list[MethodologyPhaseSummary] = []
    if llm_output:
        raw_phases = _safe_attr(llm_output, "methodology_phases", [])
        for phase in (raw_phases or []):
            phases.append(MethodologyPhaseSummary(
                phase_name=_safe_attr(phase, "phase_name_en", ""),
                activities_count=len(
                    _safe_attr(phase, "activities", []) or []
                ),
                deliverables_count=len(
                    _safe_attr(phase, "deliverables", []) or []
                ),
            ))

    # Case studies
    case_studies: list[CaseStudySummary] = []
    if case_result:
        for cs in (_safe_attr(case_result, "selected", []) or []):
            case_studies.append(CaseStudySummary(
                asset_id=_safe_attr(cs, "asset_id", ""),
                score=float(_safe_attr(cs, "score", 0.0) or 0),
            ))

    # Team bios
    team_bios: list[TeamBioSummary] = []
    if team_result:
        for tb in (_safe_attr(team_result, "selected", []) or []):
            team_bios.append(TeamBioSummary(
                asset_id=_safe_attr(tb, "asset_id", ""),
                score=float(_safe_attr(tb, "score", 0.0) or 0),
            ))

    # Slide budget
    budget_summary = SlideBudgetSummary()
    if budget:
        budget_summary = SlideBudgetSummary(
            a1_clone=int(_safe_attr(budget, "a1_clone", 0) or 0),
            a2_shell=int(_safe_attr(budget, "a2_shell", 0) or 0),
            b_variable=int(_safe_attr(budget, "b_variable", 0) or 0),
            pool_clone=int(_safe_attr(budget, "pool_clone", 0) or 0),
            total=int(_safe_attr(budget, "total_slides", 0) or 0),
        )

    # Service divider — from service_divider_result or state field
    svc_result = _safe_attr(plan, "service_divider_result")
    service_divider = ""
    if svc_result:
        service_divider = str(
            _safe_attr(svc_result, "selected_service_divider", "")
            or ""
        )
    if not service_divider:
        # Fallback: read from state-level field
        service_divider = str(
            getattr(state, "selected_service_divider", "") or ""
        )

    # Manifest composition
    manifest = state.proposal_manifest
    manifest_comp = ManifestCompositionSummary()
    if manifest:
        entries = _safe_attr(manifest, "entries", []) or []
        type_counts: dict[str, int] = {}
        for entry in entries:
            etype = str(_safe_attr(entry, "entry_type", "") or "")
            type_counts[etype] = type_counts.get(etype, 0) + 1
        manifest_comp = ManifestCompositionSummary(
            total_entries=len(entries),
            entry_type_counts=type_counts,
        )

    # Win themes
    win_themes: list[str] = []
    if llm_output:
        raw = _safe_attr(llm_output, "win_themes", [])
        win_themes = list(raw or [])

    mode = _safe_attr(llm_output, "proposal_mode", "standard")
    geo = _safe_attr(llm_output, "geography", "")
    sector = _safe_attr(llm_output, "sector", "")

    return Gate3AssemblyPlanData(
        proposal_mode=str(mode) if mode else "standard",
        geography=str(geo) if geo else "",
        sector=str(sector) if sector else "",
        methodology_phases=phases,
        slide_budget=budget_summary,
        case_studies=case_studies,
        team_bios=team_bios,
        selected_service_divider=service_divider,
        manifest_composition=manifest_comp,
        win_themes=win_themes,
    )


def _build_gate4_payload(
    session_id: str,
    state: DeckForgeState,
) -> Gate4SlideReviewData:
    slides = _build_slide_preview_data(session_id, state)
    return Gate4SlideReviewData(
        slides=[SlidePreviewItem.model_validate(slide) for slide in slides],
        slide_count=len(slides),
        thumbnail_mode=ThumbnailMode.RENDERED if slides else ThumbnailMode.METADATA_ONLY,
        preview_ready=bool(slides),
    )


def _build_gate5_payload(
    session_id: str,
    state: DeckForgeState,
) -> Gate5QaReviewData:
    qa = state.qa_result
    if qa is None:
        return Gate5QaReviewData(
            submission_readiness=ReadinessStatus.REVIEW,
            fail_close=False,
            critical_gaps=[],
            lint_status=ReadinessStatus.REVIEW,
            density_status=ReadinessStatus.REVIEW,
            template_compliance=ReadinessStatus.REVIEW,
            language_status=ReadinessStatus.REVIEW,
            coverage_status=ReadinessStatus.REVIEW,
            waivers=[],
            results=[],
            deliverables=_derive_deliverables(session_id, state),
        )

    summary = qa.deck_summary
    readiness = (
        ReadinessStatus.BLOCKED
        if summary.fail_close
        else (ReadinessStatus.NEEDS_FIXES if summary.failed > 0 else ReadinessStatus.READY)
    )
    review_status = ReadinessStatus.READY if summary.failed == 0 else ReadinessStatus.NEEDS_FIXES

    return Gate5QaReviewData(
        submission_readiness=readiness,
        fail_close=summary.fail_close,
        critical_gaps=[
            GapItem(
                gap_id=f"GAP-{index+1:03d}",
                label="Critical gap",
                description=summary.fail_close_reason,
                severity="critical",
                status="open",
            )
            for index in range(summary.critical_gaps_remaining)
        ],
        lint_status=review_status,
        density_status=ReadinessStatus.REVIEW if summary.warnings > 0 else ReadinessStatus.READY,
        template_compliance=review_status,
        language_status=ReadinessStatus.READY,
        coverage_status=ReadinessStatus.READY if not summary.uncovered_criteria else ReadinessStatus.NEEDS_FIXES,
        waivers=[],
        results=[
            {
                "slide_index": index + 1,
                "check": validation.slide_id,
                "status": str(validation.status).lower(),
                "details": "; ".join(issue.explanation for issue in validation.issues) or "No issues found.",
            }
            for index, validation in enumerate(qa.slide_validations)
        ],
        deliverables=_derive_deliverables(session_id, state),
    )


def _map_stage(stage: Any) -> tuple[str, str, int | None]:
    stage_value = stage.value if hasattr(stage, "value") else str(stage)
    return FRONTEND_STAGE_MAP.get(
        stage_value,
        (stage_value, stage_value.replace("_", " ").title(), None),
    )


def _optimistic_next_stage(gate_number: int) -> tuple[str, str, int]:
    """Return (stage_key, stage_label, step_number) for the stage after a gate approval."""
    return {
        1: ("source_research", "Knowledge Retrieval", 3),
        2: ("analysis", "Deep Analysis", 4),
        3: ("slide_rendering", "Iterative Slide Builder", 6),
        4: ("quality_assurance", "Quality Assurance", 8),
        5: ("finalized", "Finalization & Export", 10),
    }.get(gate_number, ("running", "Processing", 0))


def _gate_number_from_stage(stage: Any) -> int | None:
    stage_value = stage.value if hasattr(stage, "value") else str(stage)
    return {
        PipelineStage.CONTEXT_REVIEW.value: 1,
        PipelineStage.SOURCE_REVIEW.value: 2,
        PipelineStage.ASSEMBLY_PLAN_REVIEW.value: 3,
        PipelineStage.REPORT_REVIEW.value: 3,
        PipelineStage.CONTENT_GENERATION.value: 4,
        PipelineStage.QA.value: 5,
        PipelineStage.DECK_REVIEW.value: 5,
    }.get(stage_value)


def _default_gate_summary(gate_number: int) -> str:
    return {
        1: "Context review is ready.",
        2: "Source review is ready.",
        3: "Research report review is ready.",
        4: "Slide review is ready.",
        5: "QA review is ready.",
    }.get(gate_number, "Review required.")




def _to_language(value: str) -> Language:
    try:
        return Language(value)
    except ValueError:
        return Language.EN


def _build_research_query_log(state: DeckForgeState) -> dict[str, Any]:
    """Build research query log from session-safe captured data + evidence pack.

    Mirrors scripts/source_book_only.py::_collect_research_query_log but reads
    from graph state (captured_query_*) not process globals, making it safe for
    concurrent multi-session servers.
    """
    import time

    captured_exec_log = getattr(state, "captured_query_execution_log", [])
    captured_theme_map = getattr(state, "captured_query_theme_map", {})
    ext_evidence = state.external_evidence_pack

    log: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "queries_sent": [],
        "theme_coverage": {},
        "snippet_enrichment_status": "available_but_not_invoked",
        "author_enrichment_status": "available_but_not_invoked",
    }
    if not ext_evidence:
        return log

    queries = getattr(ext_evidence, "search_queries_used", [])
    sources = getattr(ext_evidence, "sources", [])
    query_service_map = getattr(ext_evidence, "query_service_map", {}) or {}

    # Build execution truth from captured (session-safe) execution log
    exec_services_invoked: dict[str, set[str]] = {}
    for entry in captured_exec_log:
        q = entry.get("query", "")
        svc = entry.get("service_invoked", "")
        if q and svc:
            exec_services_invoked.setdefault(q, set()).add(svc)

    # Count retained sources per query
    retained_by_query: dict[str, int] = {}
    for src in sources:
        qused = getattr(src, "query_used", "")
        if qused:
            retained_by_query[qused] = retained_by_query.get(qused, 0) + 1

    # Build per-query entries
    theme_source_counts: dict[str, int] = {}
    for q in queries:
        theme = captured_theme_map.get(q, "unclassified")

        # services_requested from the query_service_map (set at generation time)
        services_requested = query_service_map.get(q, [])
        if not services_requested:
            services_requested = ["unknown"]

        # services_actual from EXECUTION LOG TRUTH
        services_actual = sorted(exec_services_invoked.get(q, set()))

        # retained_sources_count from actual retained sources
        retained = retained_by_query.get(q, 0)
        theme_source_counts[theme] = theme_source_counts.get(theme, 0) + retained

        log["queries_sent"].append({
            "query": q,
            "query_theme": theme,
            "services_requested": services_requested,
            "services_actual": services_actual,
            "retained_sources_count": retained,
        })

    # Build theme coverage
    _ALL_THEMES = [
        "needs_assessment", "service_portfolio_design", "institutional_framework",
        "strategic_support", "methodology", "institutional_model", "evaluation",
        "analogical_domain", "pack_curated", "local_public_context",
    ]
    for theme in _ALL_THEMES:
        count = theme_source_counts.get(theme, 0)
        status = "covered" if count >= 3 else "weak" if count >= 1 else "gap"
        log["theme_coverage"][theme] = {
            "retained_sources": count,
            "status": status,
        }

    log["coverage_assessment"] = getattr(ext_evidence, "coverage_assessment", "")
    return log


def _count_source_book_words(sb: Any) -> int:
    """Count real prose words from Source Book section fields.

    Extracts actual prose text from structured section fields,
    not JSON-serialized blobs. Mirrors scripts/source_book_only.py logic.
    """
    if sb is None:
        return 0

    def _wc(text: str | None) -> int:
        return len(text.split()) if text else 0

    prose_parts: list[str | None] = []

    # Section 1: RFP Interpretation
    rfp = sb.rfp_interpretation
    if rfp:
        prose_parts.extend([
            getattr(rfp, "objective_and_scope", None),
            getattr(rfp, "constraints_and_compliance", None),
            getattr(rfp, "unstated_evaluator_priorities", None),
            getattr(rfp, "probable_scoring_logic", None),
        ])

    # Section 2: Client Problem Framing
    cpf = sb.client_problem_framing
    if cpf:
        prose_parts.extend([
            getattr(cpf, "current_state_challenge", None),
            getattr(cpf, "why_it_matters_now", None),
            getattr(cpf, "transformation_logic", None),
            getattr(cpf, "risk_if_unchanged", None),
        ])

    # Section 3: Why Strategic Gears — consultant profiles, project outcomes
    wsg = sb.why_strategic_gears
    if wsg:
        for nc in getattr(wsg, "named_consultants", []):
            prose_parts.extend([
                getattr(nc, "relevance", None),
                getattr(nc, "justification", None),
            ])
        for pe in getattr(wsg, "project_experience", []):
            prose_parts.append(getattr(pe, "outcomes", None))
        for cm in getattr(wsg, "capability_mapping", []):
            prose_parts.append(getattr(cm, "sg_capability", None))
        certs = getattr(wsg, "certifications_and_compliance", None)
        if certs:
            prose_parts.append(" ".join(certs))

    # Section 4: External Evidence
    ext = sb.external_evidence
    if ext:
        prose_parts.append(getattr(ext, "coverage_assessment", None))
        for ee in getattr(ext, "entries", []):
            prose_parts.extend([
                getattr(ee, "relevance", None),
                getattr(ee, "key_finding", None),
            ])

    # Section 5: Proposed Solution
    ps = sb.proposed_solution
    if ps:
        prose_parts.extend([
            getattr(ps, "methodology_overview", None),
            getattr(ps, "governance_framework", None),
            getattr(ps, "timeline_logic", None),
            getattr(ps, "value_case_and_differentiation", None),
        ])
        for phase in getattr(ps, "phase_details", []):
            prose_parts.extend(getattr(phase, "activities", []))
            prose_parts.extend(getattr(phase, "deliverables", []))
            prose_parts.append(getattr(phase, "governance", None))

    return sum(_wc(p) for p in prose_parts)


def _build_event(event_type: str, **kwargs: Any) -> SSEEvent:
    return SSEEvent(type=event_type, **kwargs)
