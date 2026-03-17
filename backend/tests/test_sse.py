"""
Tests for SSE broadcaster and event streaming.

Tests the SSEBroadcaster service and the GET /api/pipeline/{id}/stream endpoint.
All tests run with PIPELINE_MODE=dry_run. Zero LLM calls.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.models.api_models import SSEEvent
from backend.services.sse_broadcaster import SSEBroadcaster

# ── Unit Tests: SSEBroadcaster ──────────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_creates_queue() -> None:
    """subscribe() returns an asyncio.Queue for the session."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe("session-1")
    assert queue is not None
    assert broadcaster.has_subscribers("session-1")


@pytest.mark.asyncio
async def test_unsubscribe_removes_queue() -> None:
    """unsubscribe() removes the subscriber queue."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe("session-1")
    broadcaster.unsubscribe("session-1", queue)
    assert not broadcaster.has_subscribers("session-1")


@pytest.mark.asyncio
async def test_broadcast_sends_to_subscriber() -> None:
    """broadcast() sends event to all session subscribers."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe("session-1")

    event = SSEEvent(
        type="stage_change",
        stage="source_research",
        timestamp="2024-01-01T00:00:00Z",
    )
    await broadcaster.broadcast("session-1", event)

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received is not None
    assert received.type == "stage_change"
    assert received.stage == "source_research"


@pytest.mark.asyncio
async def test_broadcast_multiple_subscribers() -> None:
    """broadcast() sends to all subscribers of a session."""
    broadcaster = SSEBroadcaster()
    q1 = broadcaster.subscribe("session-1")
    q2 = broadcaster.subscribe("session-1")

    event = SSEEvent(
        type="heartbeat",
        timestamp="2024-01-01T00:00:00Z",
    )
    await broadcaster.broadcast("session-1", event)

    r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert r1.type == "heartbeat"
    assert r2.type == "heartbeat"


@pytest.mark.asyncio
async def test_broadcast_isolated_sessions() -> None:
    """Events for one session don't leak to another."""
    broadcaster = SSEBroadcaster()
    q1 = broadcaster.subscribe("session-1")
    q2 = broadcaster.subscribe("session-2")

    event = SSEEvent(
        type="stage_change",
        stage="rendering",
        timestamp="2024-01-01T00:00:00Z",
    )
    await broadcaster.broadcast("session-1", event)

    # q1 should have the event
    r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    assert r1.type == "stage_change"

    # q2 should be empty
    assert q2.empty()


@pytest.mark.asyncio
async def test_close_session_sends_sentinel() -> None:
    """close_session() sends None sentinel to all subscribers."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe("session-1")

    await broadcaster.close_session("session-1")

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received is None


@pytest.mark.asyncio
async def test_event_generator_yields_sse_format() -> None:
    """event_generator() yields properly formatted SSE strings."""
    broadcaster = SSEBroadcaster()

    event = SSEEvent(
        type="stage_change",
        stage="context_analysis",
        timestamp="2024-01-01T00:00:00Z",
    )

    # Put event then close
    async def feed_events():
        await asyncio.sleep(0.1)
        await broadcaster.broadcast("session-1", event)
        await asyncio.sleep(0.1)
        await broadcaster.close_session("session-1")

    asyncio.create_task(feed_events())

    lines = []
    async for line in broadcaster.event_generator("session-1"):
        lines.append(line)

    assert len(lines) >= 1
    assert lines[0].startswith("data: ")
    assert lines[0].endswith("\n\n")
    assert "stage_change" in lines[0]


@pytest.mark.asyncio
async def test_broadcast_gate_pending_event() -> None:
    """SSE event for gate_pending is properly structured."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe("session-1")

    event = SSEEvent(
        type="gate_pending",
        gate_number=2,
        timestamp="2024-01-01T10:00:00Z",
    )
    await broadcaster.broadcast("session-1", event)

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received.type == "gate_pending"
    assert received.gate_number == 2


@pytest.mark.asyncio
async def test_broadcast_error_event() -> None:
    """SSE event for pipeline errors is properly structured."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe("session-1")

    event = SSEEvent(
        type="error",
        error="Render failed: template not found",
        agent="renderer",
        timestamp="2024-01-01T10:00:00Z",
    )
    await broadcaster.broadcast("session-1", event)

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received.type == "error"
    assert received.error is not None
    assert received.agent == "renderer"


@pytest.mark.asyncio
async def test_broadcast_complete_event() -> None:
    """SSE event for pipeline completion is properly structured."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe("session-1")

    event = SSEEvent(
        type="complete",
        slide_count=20,
        session_id="session-1",
        timestamp="2024-01-01T10:00:00Z",
    )
    await broadcaster.broadcast("session-1", event)

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received.type == "complete"
    assert received.slide_count == 20
    assert received.session_id == "session-1"


@pytest.mark.asyncio
async def test_has_subscribers_false_initially() -> None:
    """has_subscribers() returns False for unknown sessions."""
    broadcaster = SSEBroadcaster()
    assert not broadcaster.has_subscribers("nonexistent")


@pytest.mark.asyncio
async def test_unsubscribe_idempotent() -> None:
    """unsubscribe() with unknown queue is a no-op."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe("session-1")
    broadcaster.unsubscribe("session-1", queue)
    # Second unsubscribe should not raise
    broadcaster.unsubscribe("session-1", queue)
    assert not broadcaster.has_subscribers("session-1")
