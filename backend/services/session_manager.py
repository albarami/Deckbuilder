"""
DeckForge Backend — In-memory session manager.

The M11 backend keeps frontend-facing pipeline sessions in memory. This module
stores enough structured state to drive the production UI contract:
gate-specific payloads, agent runtime cards, deliverables, slide previews, and
history listings.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.models.api_models import (
    AgentRunInfo,
    DeliverableInfo,
    GateInfo,
    GatePayloadType,
    GateRecord,
    PipelineOutputs,
    PipelineStatus,
    PipelineStatusResponse,
    RfpBriefInput,
    SessionHistoryItem,
    SessionHistoryResponse,
    SessionMetadataInfo,
    SSEEvent,
    ThumbnailMode,
)
from src.models.state import DeckForgeState


class PipelineSession:
    """Represents an active pipeline session."""

    def __init__(
        self,
        session_id: str,
        language: str,
        proposal_mode: str,
        sector: str,
        geography: str,
        renderer_mode: str,
        rfp_brief: RfpBriefInput | None = None,
        user_notes: str = "",
        text_input: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.language = language
        self.proposal_mode = proposal_mode
        self.sector = sector
        self.geography = geography
        self.renderer_mode = renderer_mode
        self.rfp_brief = rfp_brief
        self.user_notes = user_notes
        self.text_input = text_input

        self.status: PipelineStatus = PipelineStatus.RUNNING
        self.current_stage: str = "intake"
        self.current_stage_label: str = "Intake"
        self.current_step_number: int | None = 1
        self.created_at: datetime = datetime.now(UTC)
        self.last_activity: datetime = datetime.now(UTC)
        self.completed_at: datetime | None = None

        self.thread_id: str = str(uuid.uuid4())
        self.current_gate: GateInfo | None = None
        self.completed_gates: list[GateRecord] = []
        self.error_info: dict[str, str] | None = None

        self.outputs: PipelineOutputs = PipelineOutputs()
        self.pptx_path: str | None = None
        self.docx_path: str | None = None
        self.source_index_path: str | None = None
        self.gap_report_path: str | None = None
        self.deliverables: list[DeliverableInfo] = []

        self.metadata: SessionMetadataInfo = SessionMetadataInfo(
            updated_at=datetime.now(UTC).isoformat()
        )
        self.agent_runs: list[AgentRunInfo] = []

        self.sse_events: list[SSEEvent] = []
        self.upload_ids: list[str] = []

        self.slides_data: list[dict[str, Any]] = []
        self.thumbnail_mode: ThumbnailMode = ThumbnailMode.METADATA_ONLY
        self.preview_kind: ThumbnailMode = ThumbnailMode.METADATA_ONLY

        self.pending_rejection: dict[str, Any] | None = None
        self.graph_state: DeckForgeState | None = None
        self.last_interrupt: dict[str, Any] | None = None

    def touch(self) -> None:
        """Update timestamps for recent activity."""

        now = datetime.now(UTC)
        self.last_activity = now
        self.metadata.updated_at = now.isoformat()

    @property
    def elapsed_ms(self) -> int:
        delta = datetime.now(UTC) - self.created_at
        return int(delta.total_seconds() * 1000)

    @property
    def rfp_name(self) -> str:
        if self.graph_state and self.graph_state.rfp_context:
            return self.graph_state.rfp_context.rfp_name.en
        if self.rfp_brief and self.rfp_brief.rfp_name.en:
            return self.rfp_brief.rfp_name.en
        return "Untitled RFP"

    @property
    def issuing_entity(self) -> str:
        if self.graph_state and self.graph_state.rfp_context:
            return self.graph_state.rfp_context.issuing_entity.en
        if self.rfp_brief and self.rfp_brief.issuing_entity:
            return self.rfp_brief.issuing_entity
        return ""

    def to_status_response(self) -> PipelineStatusResponse:
        return PipelineStatusResponse(
            session_id=self.session_id,
            status=self.status,
            current_stage=self.current_stage,
            current_stage_label=self.current_stage_label,
            current_step_number=self.current_step_number,
            current_gate_number=self.current_gate.gate_number if self.current_gate else None,
            current_gate=self.current_gate,
            completed_gates=self.completed_gates,
            started_at=self.created_at.isoformat(),
            elapsed_ms=self.elapsed_ms,
            error=self.error_info,
            outputs=self.outputs,
            session_metadata=self.metadata,
            agent_runs=self.agent_runs,
            deliverables=self.deliverables,
            rfp_name=self.rfp_name,
            issuing_entity=self.issuing_entity,
        )

    def to_history_item(self) -> SessionHistoryItem:
        return SessionHistoryItem(
            session_id=self.session_id,
            rfp_name=self.rfp_name,
            issuing_entity=self.issuing_entity,
            language=self.language,
            status=self.status,
            current_stage=self.current_stage_label or self.current_stage,
            current_gate_number=self.current_gate.gate_number if self.current_gate else None,
            started_at=self.created_at.isoformat(),
            updated_at=self.metadata.updated_at or self.created_at.isoformat(),
            elapsed_ms=self.elapsed_ms,
            slide_count=self.outputs.slide_count,
            llm_calls=self.metadata.total_llm_calls,
            cost_usd=self.metadata.total_cost_usd,
            deliverables=self.deliverables,
        )

    def is_expired(self) -> bool:
        now = datetime.now(UTC)

        if self.status == PipelineStatus.GATE_PENDING:
            return (now - self.last_activity) > timedelta(hours=24)
        if self.status in (PipelineStatus.COMPLETE, PipelineStatus.ERROR):
            if self.completed_at:
                return (now - self.completed_at) > timedelta(hours=4)
            return (now - self.last_activity) > timedelta(hours=4)
        return (now - self.last_activity) > timedelta(hours=2)


class SessionManager:
    """In-memory session store for the M11 bridge backend."""

    MAX_CONCURRENT_SESSIONS = 50
    CLEANUP_INTERVAL_SECONDS = 1800

    def __init__(self) -> None:
        self._sessions: dict[str, PipelineSession] = {}
        self._thread_map: dict[str, str] = {}
        self._upload_store: dict[str, dict[str, Any]] = {}
        self._cleanup_task: asyncio.Task[None] | None = None

    def create(
        self,
        language: str,
        proposal_mode: str,
        sector: str,
        geography: str,
        renderer_mode: str,
        rfp_brief: RfpBriefInput | None = None,
        user_notes: str = "",
        text_input: str | None = None,
    ) -> PipelineSession:
        if len(self._sessions) >= self.MAX_CONCURRENT_SESSIONS:
            raise ValueError("Maximum concurrent sessions reached")

        session_id = str(uuid.uuid4())
        session = PipelineSession(
            session_id=session_id,
            language=language,
            proposal_mode=proposal_mode,
            sector=sector,
            geography=geography,
            renderer_mode=renderer_mode,
            rfp_brief=rfp_brief,
            user_notes=user_notes,
            text_input=text_input,
        )
        self._sessions[session_id] = session
        self._thread_map[session.thread_id] = session_id
        return session

    def get(self, session_id: str) -> PipelineSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> SessionHistoryResponse:
        sessions = [
            session.to_history_item()
            for session in sorted(
                self._sessions.values(),
                key=lambda current: current.created_at,
                reverse=True,
            )
        ]
        return SessionHistoryResponse(sessions=sessions)

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def update_stage(
        self,
        session_id: str,
        stage: str,
        *,
        stage_label: str | None = None,
        step_number: int | None = None,
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        session.current_stage = stage
        session.current_stage_label = stage_label or stage.replace("_", " ").title()
        session.current_step_number = step_number
        session.touch()

    def set_gate_pending(
        self,
        session_id: str,
        gate_number: int,
        summary: str,
        prompt: str,
        *,
        payload_type: GatePayloadType,
        gate_data: Any = None,
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        session.status = PipelineStatus.GATE_PENDING
        session.current_gate = GateInfo(
            gate_number=gate_number,
            summary=summary,
            prompt=prompt,
            payload_type=payload_type,
            gate_data=gate_data,
        )
        session.touch()

    def record_gate_decision(
        self,
        session_id: str,
        gate_number: int,
        approved: bool,
        feedback: str = "",
        modifications: Any = None,
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        payload_type = session.current_gate.payload_type if session.current_gate else None
        session.completed_gates.append(
            GateRecord(
                gate_number=gate_number,
                approved=approved,
                feedback=feedback,
                decided_at=datetime.now(UTC).isoformat(),
                payload_type=payload_type,
            )
        )
        session.current_gate = None
        session.pending_rejection = (
            {
                "gate_number": gate_number,
                "feedback": feedback,
                "modifications": modifications,
            }
            if not approved
            else None
        )
        session.status = PipelineStatus.RUNNING
        session.touch()

    def set_agent_runs(self, session_id: str, runs: list[AgentRunInfo]) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        session.agent_runs = runs
        session.touch()

    def set_graph_state(
        self,
        session_id: str,
        *,
        graph_state: DeckForgeState,
        interrupt_info: dict[str, Any] | None = None,
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        session.graph_state = graph_state
        session.last_interrupt = interrupt_info
        session.metadata.total_llm_calls = graph_state.session.total_llm_calls
        session.metadata.total_input_tokens = graph_state.session.total_input_tokens
        session.metadata.total_output_tokens = graph_state.session.total_output_tokens
        session.metadata.total_cost_usd = graph_state.session.total_cost_usd
        session.touch()

    def set_preview_assets(
        self,
        session_id: str,
        *,
        slides_data: list[dict[str, Any]],
        thumbnail_mode: ThumbnailMode,
        preview_kind: ThumbnailMode,
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        session.slides_data = slides_data
        session.thumbnail_mode = thumbnail_mode
        session.preview_kind = preview_kind
        session.outputs.preview_ready = True
        session.outputs.slide_count = len(slides_data)
        session.touch()

    def set_deliverables(
        self,
        session_id: str,
        deliverables: list[DeliverableInfo],
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        session.deliverables = deliverables
        session.outputs.deliverables = deliverables
        for deliverable in deliverables:
            real_path = deliverable.path or deliverable.filename
            if deliverable.key == "pptx":
                session.outputs.pptx_ready = deliverable.ready
                session.pptx_path = real_path
            elif deliverable.key == "docx":
                session.outputs.docx_ready = deliverable.ready
                session.docx_path = real_path
            elif deliverable.key == "source_index":
                session.outputs.source_index_ready = deliverable.ready
                session.source_index_path = real_path
            elif deliverable.key == "gap_report":
                session.outputs.gap_report_ready = deliverable.ready
                session.gap_report_path = real_path
        session.touch()

    def set_complete(
        self,
        session_id: str,
        *,
        slide_count: int = 0,
        deliverables: list[DeliverableInfo] | None = None,
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        session.status = PipelineStatus.COMPLETE
        session.current_stage = "finalized"
        session.current_stage_label = "Finalization & Export"
        session.current_step_number = 10
        session.completed_at = datetime.now(UTC)
        session.outputs.slide_count = slide_count
        if deliverables is not None:
            self.set_deliverables(session_id, deliverables)
        session.touch()

    def set_error(self, session_id: str, agent: str, message: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        session.status = PipelineStatus.ERROR
        session.current_stage = "error"
        session.current_stage_label = "Pipeline Error"
        session.error_info = {"agent": agent, "message": message}
        session.completed_at = datetime.now(UTC)
        session.touch()

    def push_event(self, session_id: str, event: SSEEvent) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        session.sse_events.append(event)

    def store_upload(self, upload_id: str, metadata: dict[str, Any]) -> None:
        self._upload_store[upload_id] = metadata

    def get_upload(self, upload_id: str) -> dict[str, Any] | None:
        return self._upload_store.get(upload_id)

    def cleanup_expired(self) -> int:
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.is_expired()
        ]
        for session_id in expired_ids:
            session = self._sessions.pop(session_id, None)
            if session:
                self._thread_map.pop(session.thread_id, None)
        return len(expired_ids)

    async def start_cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
            self.cleanup_expired()

    def start_background_cleanup(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self.start_cleanup_loop())

    def stop_background_cleanup(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
