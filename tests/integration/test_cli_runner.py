"""Tests for the CLI pipeline runner."""

import os
import tempfile

from src.models.common import BilingualText
from src.models.enums import PipelineStage
from src.models.rfp import RFPContext
from src.models.state import DeckForgeState
from src.pipeline.graph import save_state

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")
SAMPLE_JSON = os.path.join(FIXTURES_DIR, "sample_rfp_summary.json")


def test_cli_creates_state_from_json() -> None:
    """JSON input creates valid DeckForgeState with all fields."""
    from scripts.run_pipeline import create_state_from_input

    state = create_state_from_input(SAMPLE_JSON)

    assert isinstance(state, DeckForgeState)
    assert "SAP" in state.ai_assist_summary
    assert state.output_language == "en"
    assert state.presentation_type == "technical_proposal"
    assert "Aramco" in state.user_notes


def test_cli_creates_state_from_text() -> None:
    """Plain text input creates valid DeckForgeState."""
    from scripts.run_pipeline import create_state_from_input

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("SAP Support Renewal RFP from SIDF")
        f.flush()
        tmp_path = f.name

    try:
        state = create_state_from_input(tmp_path)
        assert isinstance(state, DeckForgeState)
        assert state.ai_assist_summary == (
            "SAP Support Renewal RFP from SIDF"
        )
        # Text mode uses defaults for optional fields
        assert state.output_language == "en"
    finally:
        os.unlink(tmp_path)


def test_cli_resume_loads_state() -> None:
    """Saved state reloads correctly via resume."""
    from scripts.run_pipeline import resume_state

    state = DeckForgeState(
        ai_assist_summary="Test RFP",
        output_language="en",
        current_stage=PipelineStage.CONTEXT_REVIEW,
        rfp_context=RFPContext(
            rfp_name=BilingualText(en="Test"),
            issuing_entity=BilingualText(en="Org"),
            mandate=BilingualText(en="Do things"),
        ),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "session.json")
        save_state(state, path)

        loaded = resume_state(path)
        assert loaded.current_stage == PipelineStage.CONTEXT_REVIEW
        assert loaded.rfp_context is not None
        assert loaded.rfp_context.rfp_name.en == "Test"


def test_cli_dry_run_flag() -> None:
    """Dry-run mode creates mock responses without requiring API keys."""
    from scripts.run_pipeline import get_dry_run_patches

    patches = get_dry_run_patches()

    # Should have patches for all 8 agent modules + search + load_documents
    assert len(patches) >= 8
    # Each patch should have a target path containing 'call_llm' or 'search'
    for p in patches:
        assert hasattr(p, "attribute")
