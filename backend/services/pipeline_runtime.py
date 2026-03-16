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
    DeliverableInfo,
    Gate1ContextData,
    Gate2SourceReviewData,
    Gate3ReportReviewData,
    Gate4SlideReviewData,
    Gate5QaReviewData,
    GateInfo,
    GatePayloadType,
    GapItem,
    PipelineStatus,
    ReadinessStatus,
    ReportSectionSummary,
    RfpBriefInput,
    SSEEvent,
    SensitivitySummary,
    SlidePreviewItem,
    SourceIndexItem,
    SourceReviewItem,
    ThumbnailMode,
)
from backend.services.session_manager import PipelineSession, SessionManager
from backend.services.sse_broadcaster import SSEBroadcaster
from src.models.enums import Language, PipelineStage, RendererMode
from src.models.state import DeckForgeState, UploadedDocument
from src.pipeline.dry_run import get_dry_run_patches
from src.utils.extractors import extract_document


FRONTEND_STAGE_MAP: dict[str, tuple[str, str, int | None]] = {
    PipelineStage.INTAKE.value: ("intake", "Intake", 1),
    PipelineStage.CONTEXT_REVIEW.value: ("context_analysis", "Context Understanding", 2),
    PipelineStage.SOURCE_REVIEW.value: ("source_research", "Knowledge Retrieval", 3),
    PipelineStage.ANALYSIS.value: ("analysis", "Deep Analysis", 4),
    PipelineStage.REPORT_REVIEW.value: ("report_generation", "Research Report Generation", 5),
    PipelineStage.SLIDE_BUILDING.value: ("slide_rendering", "Iterative Slide Builder", 6),
    PipelineStage.CONTENT_GENERATION.value: ("slide_rendering", "Iterative Slide Builder", 7),
    PipelineStage.QA.value: ("quality_assurance", "Quality Assurance", 8),
    PipelineStage.DECK_REVIEW.value: ("quality_assurance", "Deck Review", 9),
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

    ai_summary = session.text_input or _brief_to_summary(session.rfp_brief)

    return DeckForgeState(
        ai_assist_summary=ai_summary,
        uploaded_documents=uploaded_documents,
        user_notes=session.user_notes,
        output_language=_to_language(session.language),
        renderer_mode=RendererMode.TEMPLATE_V2,
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
            ("presentation_agent", "Presentation Agent", "Claude Opus 4.6", "Slide package", "presentation_package", 10),
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
        runs["qa_agent"].metric_value = f"{state.qa_result.deck_summary.passed} pass / {state.qa_result.deck_summary.failed} fail"

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
    slide_count = len(state.final_slides or (state.written_slides.slides if state.written_slides else []))
    return [
        DeliverableInfo(
            key="pptx",
            label="Presentation deck",
            ready=bool(state.pptx_path),
            filename=state.pptx_path.split("\\")[-1] if state.pptx_path else f"proposal_{session_id[:6]}_en.pptx",
            download_url=f"/api/pipeline/{session_id}/export/pptx" if state.pptx_path else None,
        ),
        DeliverableInfo(
            key="docx",
            label="Research report",
            ready=bool(state.report_docx_path),
            filename=state.report_docx_path.split("\\")[-1] if state.report_docx_path else f"research_report_{session_id[:6]}_en.docx",
            download_url=f"/api/pipeline/{session_id}/export/docx" if state.report_docx_path else None,
        ),
        DeliverableInfo(
            key="source_index",
            label="Source index",
            ready=bool(getattr(state, "source_index_path", None)),
            filename=f"source_index_{session_id[:6]}.docx",
            download_url=f"/api/pipeline/{session_id}/export/source_index" if getattr(state, "source_index_path", None) else None,
        ),
        DeliverableInfo(
            key="gap_report",
            label="Gap report",
            ready=bool(getattr(state, "gap_report_path", None)),
            filename=f"gap_report_{session_id[:6]}.docx",
            download_url=f"/api/pipeline/{session_id}/export/gap_report" if getattr(state, "gap_report_path", None) else None,
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
                "file_requirements": context.submission_format.additional_requirements if context.submission_format else [],
                "additional_instructions": "",
            },
        ),
        missing_fields=context.completeness.top_level_missing,
        selected_output_language=str(state.output_language),
        user_notes=state.user_notes,
        evaluation_highlights=[
            f"Technical evaluation weight: {technical_weight}%" if technical_weight is not None else "Technical evaluation weight not specified",
            f"Financial evaluation weight: {financial_weight}%" if financial_weight is not None else "Financial evaluation weight not specified",
            f"{len(context.compliance_requirements)} compliance requirements identified",
        ],
    )


def _build_gate2_payload(state: DeckForgeState) -> Gate2SourceReviewData:
    return Gate2SourceReviewData(
        sources=[
            SourceReviewItem(
                source_id=source.doc_id,
                title=source.title,
                relevance_score=float(source.relevance_score) / 100 if source.relevance_score > 1 else float(source.relevance_score),
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
    readiness = ReadinessStatus.BLOCKED if summary.fail_close else (ReadinessStatus.NEEDS_FIXES if summary.failed > 0 else ReadinessStatus.READY)
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


def _gate_number_from_stage(stage: Any) -> int | None:
    stage_value = stage.value if hasattr(stage, "value") else str(stage)
    return {
        PipelineStage.CONTEXT_REVIEW.value: 1,
        PipelineStage.SOURCE_REVIEW.value: 2,
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


def _brief_to_summary(brief: RfpBriefInput | None) -> str:
    if brief is None:
        return ""
    summary_parts = [
        brief.rfp_name.en,
        brief.issuing_entity,
        brief.mandate_summary,
        "Scope: " + "; ".join(brief.scope_requirements[:5]) if brief.scope_requirements else "",
        "Deliverables: " + "; ".join(brief.deliverables[:5]) if brief.deliverables else "",
    ]
    return "\n".join(part for part in summary_parts if part)


def _to_language(value: str) -> Language:
    try:
        return Language(value)
    except ValueError:
        return Language.EN


def _build_event(event_type: str, **kwargs: Any) -> SSEEvent:
    return SSEEvent(type=event_type, **kwargs)
