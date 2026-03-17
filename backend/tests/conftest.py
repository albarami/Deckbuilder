"""
DeckForge Backend — Test Configuration

Sets PIPELINE_MODE=dry_run for all tests.
Provides shared fixtures for the FastAPI test client and session manager.
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

# ── MANDATORY: Set dry_run BEFORE any import of server ─────────────
os.environ["PIPELINE_MODE"] = "dry_run"

from backend.server import app, session_manager, sse_broadcaster
from backend.services.session_manager import SessionManager


@pytest.fixture(autouse=True)
def _enforce_dry_run() -> None:
    """Ensure PIPELINE_MODE is always dry_run in tests."""
    assert os.environ.get("PIPELINE_MODE") == "dry_run", (
        "Tests MUST run with PIPELINE_MODE=dry_run"
    )
    assert app.state.pipeline_mode == "dry_run"


@pytest.fixture(autouse=True)
def _clean_sessions() -> None:
    """Reset session manager state between tests."""
    session_manager._sessions.clear()
    session_manager._thread_map.clear()
    session_manager._upload_store.clear()
    sse_broadcaster._subscribers.clear()


@pytest.fixture
def sm() -> SessionManager:
    """Provide the session manager instance."""
    return session_manager


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
