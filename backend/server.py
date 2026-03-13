"""
DeckForge Backend — FastAPI Application

Entry point for the backend API server. Wraps the LangGraph pipeline
and exposes REST + SSE endpoints for the frontend.

Start:
    PIPELINE_MODE=dry_run uvicorn backend.server:app --reload --port 8000

Environment:
    PIPELINE_MODE: "dry_run" (default) | "live"
        Controls whether the pipeline uses mock agents or real LLM calls.
        MUST be "dry_run" for all local development and CI.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import pipeline, gates, upload, slides, export
from backend.services.session_manager import SessionManager
from backend.services.sse_broadcaster import SSEBroadcaster


def get_pipeline_mode() -> str:
    """Read PIPELINE_MODE from environment. Defaults to dry_run."""
    return os.environ.get("PIPELINE_MODE", "dry_run")


# ── Shared services (singleton instances) ──────────────────────────

session_manager = SessionManager()
sse_broadcaster = SSEBroadcaster()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown."""
    # Startup
    session_manager.start_background_cleanup()
    yield
    # Shutdown
    session_manager.stop_background_cleanup()


# ── FastAPI App ────────────────────────────────────────────────────

app = FastAPI(
    title="DeckForge API",
    description="Backend bridge to the DeckForge LangGraph pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS (allow frontend dev server) ──────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Dependency injection — attach services to app state ───────────

app.state.session_manager = session_manager
app.state.sse_broadcaster = sse_broadcaster
app.state.pipeline_mode = get_pipeline_mode()

# ── Register routers ──────────────────────────────────────────────

app.include_router(pipeline.router)
app.include_router(gates.router)
app.include_router(upload.router)
app.include_router(slides.router)
app.include_router(export.router)


# ── Health check ──────────────────────────────────────────────────

@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint."""
    from backend.models.api_models import HealthResponse

    return HealthResponse(
        status="ok",
        pipeline_mode=app.state.pipeline_mode,
        active_sessions=session_manager.active_count,
        version="0.1.0",
    ).model_dump()
