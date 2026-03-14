"""
DeckForge Backend — SSE Broadcaster

Server-Sent Events streaming for real-time pipeline progress.
Each session maintains its own event queue. Clients subscribe
via GET /api/pipeline/{id}/stream.

Features:
- Per-session event queues (asyncio.Queue)
- Heartbeat every 15 seconds
- Auto-cleanup on client disconnect
- Multiple subscribers per session supported
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from backend.models.api_models import SSEEvent


class SSEBroadcaster:
    """
    Manages SSE event streams for pipeline sessions.

    Each session can have multiple subscribers. Events are broadcast
    to all active subscribers for a given session.
    """

    HEARTBEAT_INTERVAL_SECONDS = 15

    def __init__(self) -> None:
        # session_id → list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue[SSEEvent | None]]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue[SSEEvent | None]:
        """
        Create a new subscriber queue for a session.
        Returns a Queue that will receive SSEEvent objects.
        Send None to signal end-of-stream.
        """
        if session_id not in self._subscribers:
            self._subscribers[session_id] = []

        queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        return queue

    def unsubscribe(
        self, session_id: str, queue: asyncio.Queue[SSEEvent | None]
    ) -> None:
        """Remove a subscriber queue."""
        if session_id in self._subscribers:
            try:
                self._subscribers[session_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]

    async def broadcast(self, session_id: str, event: SSEEvent) -> None:
        """Send an event to all subscribers of a session."""
        if session_id in self._subscribers:
            for queue in self._subscribers[session_id]:
                await queue.put(event)

    async def close_session(self, session_id: str) -> None:
        """Signal end-of-stream to all subscribers of a session."""
        if session_id in self._subscribers:
            for queue in self._subscribers[session_id]:
                await queue.put(None)  # Sentinel for end

    def has_subscribers(self, session_id: str) -> bool:
        """Check if a session has any active subscribers."""
        return bool(self._subscribers.get(session_id))

    async def event_generator(
        self, session_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Async generator that yields SSE-formatted strings.
        Includes heartbeat every 15 seconds.

        Yields lines in SSE format:
            data: {json}\n\n
        """
        queue = self.subscribe(session_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=self.HEARTBEAT_INTERVAL_SECONDS,
                    )

                    if event is None:
                        # End-of-stream sentinel
                        return

                    yield f"data: {event.model_dump_json()}\n\n"

                except asyncio.TimeoutError:
                    # Send heartbeat
                    heartbeat = SSEEvent(
                        type="heartbeat",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                    yield f"data: {heartbeat.model_dump_json()}\n\n"
        finally:
            self.unsubscribe(session_id, queue)
