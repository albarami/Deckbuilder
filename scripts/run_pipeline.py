"""CLI runner for the DeckForge pipeline.

Usage:
    python -m scripts.run_pipeline --input rfp_summary.json [--docs ./test_docs] [--dry-run]
    python -m scripts.run_pipeline --resume ./state/session.json
    python -m scripts.run_pipeline --index --docs-path "./data test/"
"""

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

from src.config.settings import get_settings
from src.models.enums import RendererMode
from src.models.state import DeckForgeState
from src.pipeline.dry_run import get_dry_run_patches
from src.pipeline.graph import build_graph, load_state, save_state

# ──────────────────────────────────────────────────────────────
# Input handling — JSON or plain text → DeckForgeState
# ──────────────────────────────────────────────────────────────


def _renderer_mode_from_settings() -> RendererMode:
    """Read renderer_mode from Settings and convert to RendererMode enum.

    Returns RendererMode.LEGACY if the value is unrecognised.
    """
    raw = get_settings().renderer_mode
    try:
        return RendererMode(raw)
    except ValueError:
        return RendererMode.LEGACY


def create_state_from_input(path: str) -> DeckForgeState:
    """Create a DeckForgeState from a JSON or plain text file.

    JSON files (.json) are parsed and fields are mapped directly
    to DeckForgeState fields. Plain text files read the entire
    content as ai_assist_summary with default values for other fields.

    ``renderer_mode`` is always populated from Settings unless the
    JSON input already contains an explicit ``renderer_mode`` key.
    """
    filepath = Path(path)
    content = filepath.read_text(encoding="utf-8")
    mode = _renderer_mode_from_settings()

    if filepath.suffix.lower() == ".json":
        data = json.loads(content)
        # Only inject settings value when JSON doesn't provide its own
        data.setdefault("renderer_mode", mode.value)
        return DeckForgeState(**data)

    # Plain text — content becomes the AI summary
    return DeckForgeState(
        ai_assist_summary=content.strip(),
        renderer_mode=mode,
    )


def resume_state(path: str) -> DeckForgeState:
    """Load a previously saved DeckForgeState from JSON."""
    return load_state(path)


# ──────────────────────────────────────────────────────────────
# Gate interaction — Rich-powered human-in-the-loop
# ──────────────────────────────────────────────────────────────


def _display_gate(gate_info: dict) -> bool:
    """Display gate info and prompt for approval.

    Uses rich if available, falls back to plain text.
    """
    try:
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        gate_num = gate_info.get("gate_number", "?")
        summary = gate_info.get("summary", "No summary available.")
        prompt = gate_info.get("prompt", "Approve?")

        console.print()
        console.print(Panel(
            summary,
            title=f"[bold cyan]Gate {gate_num}[/bold cyan]",
            border_style="cyan",
        ))
        console.print(f"  [bold]{prompt}[/bold]")
    except ImportError:
        gate_num = gate_info.get("gate_number", "?")
        summary = gate_info.get("summary", "No summary available.")
        prompt = gate_info.get("prompt", "Approve?")
        print(f"\n{'='*60}")
        print(f"  Gate {gate_num}: {summary}")
        print(f"  {prompt}")
        print(f"{'='*60}")

    response = input("  > ").strip().lower()
    return response in ("y", "yes", "")


# ──────────────────────────────────────────────────────────────
# Main pipeline runner
# ──────────────────────────────────────────────────────────────


async def run_pipeline(args: argparse.Namespace) -> None:
    """Execute the DeckForge pipeline with CLI arguments."""
    from langgraph.types import Command

    # Load or create state
    if args.resume:
        state = resume_state(args.resume)
        print(f"Resumed state from {args.resume}")
        print(f"  Stage: {state.current_stage}")
    else:
        state = create_state_from_input(args.input)
        print(f"Created state from {args.input}")
        print(f"  Summary: {state.ai_assist_summary[:80]}...")

    # Apply dry-run patches if requested
    patches = []
    if args.dry_run:
        patches = get_dry_run_patches()
        for p in patches:
            p.start()
        print("[dry-run] All LLM calls mocked.")

    try:
        graph = build_graph()
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        # First invocation
        result = await graph.ainvoke(state, config)  # type: ignore[arg-type]

        # Gate loop — keep resuming until pipeline completes
        max_gates = 5
        for gate_idx in range(max_gates):
            if "__interrupt__" not in result:
                break

            # Extract gate info from interrupt
            interrupts = result["__interrupt__"]
            if not interrupts:
                break

            gate_info = interrupts[0].value if hasattr(interrupts[0], "value") else {}
            approved = _display_gate(gate_info)

            if not approved:
                print("Pipeline stopped by user.")
                break

            result = await graph.ainvoke(
                Command(resume={"approved": True}), config  # type: ignore[arg-type]
            )

        # Save state
        state_path = Path(args.state_dir) / "session.json"
        final_state = DeckForgeState.model_validate(result)
        save_state(final_state, str(state_path))
        print(f"\nState saved to {state_path}")
        print(f"  Stage: {final_state.current_stage}")

        if final_state.qa_result:
            s = final_state.qa_result.deck_summary
            print(f"  QA: {s.passed} passed, {s.failed} failed")

        if final_state.pptx_path:
            print(f"  PPTX: {final_state.pptx_path}")
        if final_state.report_docx_path:
            print(f"  DOCX: {final_state.report_docx_path}")

    finally:
        for p in patches:
            p.stop()


async def run_index(args: argparse.Namespace) -> None:
    """Run the full indexing pipeline on a document directory."""
    import logging

    from src.services.search import index_documents

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    docs_path = args.docs_path
    cache_path = args.cache_path
    skip_entities = args.skip_entities

    print(f"{'=' * 70}")
    print("DeckForge Indexing Pipeline")
    print(f"  Docs path:    {docs_path}")
    print(f"  Cache path:   {cache_path}")
    print(f"  Skip entities: {skip_entities}")
    print(f"{'=' * 70}\n")

    start_time = time.perf_counter()
    manifest = await index_documents(
        docs_path=docs_path,
        cache_path=cache_path,
        skip_entities=skip_entities,
    )
    total_time = time.perf_counter() - start_time

    # Display results
    print(f"\n{'=' * 70}")
    print(f"INDEXING COMPLETE ({total_time:.1f}s)")
    print(f"{'=' * 70}")
    print(f"  Total documents:        {manifest['total_documents']}")
    print(f"  Unique documents:       {manifest.get('unique_documents', '?')}")
    print(f"  Duplicates skipped:     {manifest['duplicates_skipped']}")
    print(f"  Near-duplicates flagged: {manifest['near_duplicates_flagged']}")
    print(f"  Total chunks:           {manifest['total_chunks']}")

    # Classifications
    print("\n  Classifications:")
    for doc_type, count in sorted(manifest.get("classifications", {}).items()):
        print(f"    {doc_type}: {count}")

    # Knowledge graph
    kg = manifest.get("knowledge_graph_summary", {})
    print("\n  Knowledge Graph:")
    print(f"    People:        {kg.get('people', 0)}")
    print(f"    Internal team: {kg.get('internal_team', 0)}")
    print(f"    Projects:      {kg.get('projects', 0)}")
    print(f"    Clients:       {kg.get('clients', 0)}")

    # Timings
    print("\n  Step Timings:")
    for step, secs in manifest.get("timings_seconds", {}).items():
        print(f"    {step}: {secs}s")

    print(f"\n  Embedding model: {manifest.get('embedding_model', '?')}")
    print(f"  Dimensions:      {manifest.get('embedding_dimensions', '?')}")
    print(f"  Manifest saved:  {cache_path}/manifest.json")
    print(f"{'=' * 70}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="run_pipeline",
        description="DeckForge — RFP-to-Deck pipeline runner",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input", "-i",
        help="Path to RFP input file (JSON or plain text)",
    )
    input_group.add_argument(
        "--resume", "-r",
        help="Path to saved state JSON to resume from",
    )
    input_group.add_argument(
        "--index",
        action="store_true",
        help="Run the indexing pipeline on a document directory",
    )

    parser.add_argument(
        "--docs", "-d",
        default="./test_docs",
        help="Path to local documents directory (default: ./test_docs)",
    )
    parser.add_argument(
        "--docs-path",
        default="./data test/",
        help="Path to document directory for indexing (default: ./data test/)",
    )
    parser.add_argument(
        "--cache-path",
        default="./state/index/",
        help="Path to save index artifacts (default: ./state/index/)",
    )
    parser.add_argument(
        "--skip-entities",
        action="store_true",
        help="Skip entity extraction during indexing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mock all LLM calls for offline testing",
    )
    parser.add_argument(
        "--output", "-o",
        default="./output",
        help="Directory for rendered PPTX and DOCX files (default: ./output)",
    )
    parser.add_argument(
        "--state-dir",
        default="./state",
        help="Directory to save pipeline state (default: ./state)",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the CLI runner."""
    args = parse_args(argv)

    # Index mode
    if args.index:
        if not Path(args.docs_path).exists():
            print(
                f"Error: Docs directory not found: {args.docs_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        asyncio.run(run_index(args))
        return

    # Validate input file exists
    if args.input and not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if args.resume and not Path(args.resume).exists():
        print(f"Error: State file not found: {args.resume}", file=sys.stderr)
        sys.exit(1)

    # Validate docs directory
    if args.input and not Path(args.docs).exists():
        print(f"Warning: Docs directory not found: {args.docs}", file=sys.stderr)

    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
