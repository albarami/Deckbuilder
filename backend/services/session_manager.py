"""
DeckForge Backend — In-Memory Session Manager

Manages pipeline session lifecycle per the Session Resume Contract.
In M11, all sessions are stored in-memory (lost on restart).
Redis persistence is added in M13.

Timeout / Cleanup Policy:
- Idle session: 2 hours
- Gate pending: 24 hours
- Complete/error: 4 hours after completion
- Cleanup interval: 30 minutes
- Max concurrent sessions: 50
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.models.api_models import (
    GateInfo,
    GateRecord,
    PipelineOutputs,
    PipelineStatus,
    PipelineStatusResponse,
    SessionMetadataInfo,
    SSEEvent,
)


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
    ) -> None:
        self.session_id = session_id
        self.language = language
        self.proposal_mode = proposal_mode
        self.sector = sector
        self.geography = geography
        self.renderer_mode = renderer_mode

        # Lifecycle
        self.status: PipelineStatus = PipelineStatus.RUNNING
        self.current_stage: str = "intake"
        self.created_at: datetime = datetime.now(timezone.utc)
        self.last_activity: datetime = datetime.now(timezone.utc)
        self.completed_at: datetime | None = None

        # Pipeline execution
        self.thread_id: str = str(uuid.uuid4())
        self.current_gate: GateInfo | None = None
        self.completed_gates: list[GateRecord] = []
        self.error_info: dict[str, str] | None = None

        # Outputs
        self.outputs: PipelineOutputs = PipelineOutputs()
        self.pptx_path: str | None = None
        self.docx_path: str | None = None

        # Metadata
        self.metadata: SessionMetadataInfo = SessionMetadataInfo()

        # SSE events queue
        self.sse_events: list[SSEEvent] = []

        # Uploaded document refs
        self.upload_ids: list[str] = []
        self.text_input: str | None = None

        # Slide data cache
        self.slides_data: list[dict[str, Any]] = []
        self.thumbnail_mode: str = "metadata_only"

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)

    @property
    def elapsed_ms(self) -> int:
        """Milliseconds since session started."""
        delta = datetime.now(timezone.utc) - self.created_at
        return int(delta.total_seconds() * 1000)

    def to_status_response(self) -> PipelineStatusResponse:
        """Convert to API status response."""
        return PipelineStatusResponse(
            session_id=self.session_id,
            status=self.status,
            current_stage=self.current_stage,
            current_gate=self.current_gate,
            completed_gates=self.completed_gates,
            started_at=self.created_at.isoformat(),
            elapsed_ms=self.elapsed_ms,
            error=self.error_info,
            outputs=self.outputs,
            session_metadata=self.metadata,
        )

    def is_expired(self) -> bool:
        """Check if session should be cleaned up."""
        now = datetime.now(timezone.utc)

        if self.status == PipelineStatus.GATE_PENDING:
            # Keep gate-pending sessions alive for 24h
            return (now - self.last_activity) > timedelta(hours=24)
        elif self.status in (PipelineStatus.COMPLETE, PipelineStatus.ERROR):
            # Completed/errored sessions expire 4h after completion
            if self.completed_at:
                return (now - self.completed_at) > timedelta(hours=4)
            return (now - self.last_activity) > timedelta(hours=4)
        else:
            # Running sessions expire after 2h idle
            return (now - self.last_activity) > timedelta(hours=2)


class SessionManager:
    """
    In-memory session store (M11). Redis backend added in M13.

    Thread-safe via asyncio (single-threaded event loop).
    """

    MAX_CONCURRENT_SESSIONS = 50
    CLEANUP_INTERVAL_SECONDS = 1800  # 30 minutes

    def __init__(self) -> None:
        self._sessions: dict[str, PipelineSession] = {}
        self._thread_map: dict[str, str] = {}  # thread_id → session_id
        self._upload_store: dict[str, dict[str, Any]] = {}  # upload_id → file metadata
        self._cleanup_task: asyncio.Task[None] | None = None

    # ── Session CRUD ───────────────────────────────────────────────

    def create(
        self,
        language: str,
        proposal_mode: str,
        sector: str,
        geography: str,
        renderer_mode: str,
    ) -> PipelineSession:
        """Create a new pipeline session. Raises ValueError if at capacity."""
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
        )
        self._sessions[session_id] = session
        self._thread_map[session.thread_id] = session_id
        return session

    def get(self, session_id: str) -> PipelineSession | None:
        """Get session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def get_by_thread(self, thread_id: str) -> PipelineSession | None:
        """Get session by LangGraph thread ID."""
        session_id = self._thread_map.get(thread_id)
        if session_id:
            return self._sessions.get(session_id)
        return None

    @property
    def active_count(self) -> int:
        """Number of active (non-expired) sessions."""
        return len(self._sessions)

    # ── State Updates ──────────────────────────────────────────────

    def update_stage(self, session_id: str, stage: str) -> None:
        """Update the pipeline stage for a session."""
        session = self._sessions.get(session_id)
        if session:
            session.current_stage = stage
            session.touch()

    def set_gate_pending(
        self,
        session_id: str,
        gate_number: int,
        summary: str,
        prompt: str,
        gate_data: Any = None,
    ) -> None:
        """Mark session as waiting at a gate."""
        session = self._sessions.get(session_id)
        if session:
            session.status = PipelineStatus.GATE_PENDING
            session.current_gate = GateInfo(
                gate_number=gate_number,
                summary=summary,
                prompt=prompt,
                gate_data=gate_data,
            )
            session.touch()

    def record_gate_decision(
        self,
        session_id: str,
        gate_number: int,
        approved: bool,
        feedback: str = "",
    ) -> None:
        """Record a gate decision and resume running."""
        session = self._sessions.get(session_id)
        if session:
            session.completed_gates.append(
                GateRecord(
                    gate_number=gate_number,
                    approved=approved,
                    feedback=feedback,
                    decided_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            session.current_gate = None
            session.status = PipelineStatus.RUNNING
            session.touch()

    def set_complete(
        self,
        session_id: str,
        pptx_path: str | None = None,
        docx_path: str | None = None,
        slide_count: int = 0,
    ) -> None:
        """Mark session as complete."""
        session = self._sessions.get(session_id)
        if session:
            session.status = PipelineStatus.COMPLETE
            session.current_stage = "finalized"
            session.completed_at = datetime.now(timezone.utc)
            session.pptx_path = pptx_path
            session.docx_path = docx_path
            session.outputs = PipelineOutputs(
                pptx_ready=pptx_path is not None,
                docx_ready=docx_path is not None,
                slide_count=slide_count,
            )
            session.touch()

    def set_error(
        self, session_id: str, agent: str, message: str
    ) -> None:
        """Mark session as errored."""
        session = self._sessions.get(session_id)
        if session:
            session.status = PipelineStatus.ERROR
            session.current_stage = "error"
            session.error_info = {"agent": agent, "message": message}
            session.completed_at = datetime.now(timezone.utc)
            session.touch()

    # ── SSE Events ─────────────────────────────────────────────────

    def push_event(self, session_id: str, event: SSEEvent) -> None:
        """Append an SSE event to the session's event log."""
        session = self._sessions.get(session_id)
        if session:
            session.sse_events.append(event)

    def get_events_since(
        self, session_id: str, after_index: int
    ) -> list[SSEEvent]:
        """Get SSE events after a given index."""
        session = self._sessions.get(session_id)
        if session:
            return session.sse_events[after_index:]
        return []

    # ── Upload Store ───────────────────────────────────────────────

    def store_upload(self, upload_id: str, metadata: dict[str, Any]) -> None:
        """Store uploaded file metadata."""
        self._upload_store[upload_id] = metadata

    def get_upload(self, upload_id: str) -> dict[str, Any] | None:
        """Get upload metadata by ID."""
        return self._upload_store.get(upload_id)

    # ── Cleanup ────────────────────────────────────────────────────

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        expired_ids = [
            sid for sid, session in self._sessions.items()
            if session.is_expired()
        ]
        for sid in expired_ids:
            session = self._sessions.pop(sid, None)
            if session:
                self._thread_map.pop(session.thread_id, None)
        return len(expired_ids)

    async def start_cleanup_loop(self) -> None:
        """Background task to periodically clean up expired sessions."""
        while True:
            await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
            self.cleanup_expired()

    def start_background_cleanup(self) -> None:
        """Start the cleanup loop as a background task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self.start_cleanup_loop())

    def stop_background_cleanup(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
