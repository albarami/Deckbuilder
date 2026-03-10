"""Re-run the 5-turn iterative builder from existing E2E pipeline output.

Loads post-Gate-3 state from step1_rfp_context.json and step4_research_report.json,
runs the iterative builder (5 turns), then renders the PPTX.

Usage:
    python scripts/run_builder_only.py
"""

import asyncio
import json
import logging
import shutil
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    base = Path(__file__).resolve().parent.parent
    output_dir = base / "output"

    # Load existing pipeline artifacts
    rfp_path = output_dir / "step1_rfp_context.json"
    report_path = output_dir / "step4_research_report.json"
    ref_index_path = output_dir / "step3_reference_index.json"
    template_path = base / "templates" / "Presentation6.pptx"

    logger.info("Loading RFP context from %s", rfp_path.name)
    with open(rfp_path, encoding="utf-8") as f:
        rfp_data = json.load(f)

    logger.info("Loading research report from %s", report_path.name)
    with open(report_path, encoding="utf-8") as f:
        report_data = json.load(f)

    # Build state
    from src.models.rfp import RFPContext
    from src.models.state import DeckForgeState

    state = DeckForgeState(
        rfp_context=RFPContext(**rfp_data),
        report_markdown=report_data.get("full_markdown", ""),
        output_language="en",
    )

    # Load reference index if available
    if ref_index_path.exists():
        from src.models.claims import ReferenceIndex
        with open(ref_index_path, encoding="utf-8") as f:
            ref_data = json.load(f)
        state.reference_index = ReferenceIndex(**ref_data)
        logger.info("Loaded reference index (%d claims)", len(state.reference_index.claims))

    logger.info("Report markdown: %d chars", len(state.report_markdown))
    logger.info("RFP: %s", rfp_data.get("rfp_name", {}).get("en", "?"))

    # Run iterative builder
    from src.agents.iterative.builder import run_iterative_build

    logger.info("\n" + "=" * 60)
    logger.info("Starting 5-turn iterative builder...")
    logger.info("=" * 60)

    state = await run_iterative_build(state)

    logger.info("Builder complete. Stage: %s", state.current_stage)
    logger.info("Evidence mode: %s", state.evidence_mode)
    logger.info("Deck drafts: %d", len(state.deck_drafts))
    logger.info("Deck reviews: %d", len(state.deck_reviews))
    logger.info("LLM calls: %d", state.session.total_llm_calls)
    logger.info(
        "Tokens: %d in / %d out",
        state.session.total_input_tokens,
        state.session.total_output_tokens,
    )

    if state.errors:
        logger.error("Errors encountered:")
        for err in state.errors:
            logger.error("  [%s] %s: %s", err.agent, err.error_type, err.message)

    if state.written_slides is None:
        logger.error("No written slides produced!")
        return

    slides = state.written_slides.slides
    logger.info("\nWritten slides: %d", len(slides))
    for i, s in enumerate(slides, 1):
        logger.info("  S%d: [%s] %s", i, s.layout_type, s.title)

    # Save intermediate outputs
    if state.deck_drafts:
        with open(output_dir / "step5_deck_drafts.json", "w", encoding="utf-8") as f:
            json.dump(state.deck_drafts, f, ensure_ascii=False, indent=2)
    if state.deck_reviews:
        with open(output_dir / "step5_deck_reviews.json", "w", encoding="utf-8") as f:
            json.dump(state.deck_reviews, f, ensure_ascii=False, indent=2)

    written_data = state.written_slides.model_dump(mode="json")
    with open(output_dir / "step5_written_slides.json", "w", encoding="utf-8") as f:
        json.dump(written_data, f, ensure_ascii=False, indent=2)
    logger.info("Saved step5 outputs")

    # Render PPTX
    from src.services.renderer import render_pptx

    pptx_out = str(output_dir / "deck_formatted.pptx")
    logger.info("\nRendering PPTX to %s...", pptx_out)
    result = await render_pptx(
        slides=slides,
        template_path=str(template_path),
        output_path=pptx_out,
    )
    logger.info("  -> %d slides rendered", result.slide_count)
    for entry in result.render_log:
        status = entry.get("status", "?")
        msg = entry.get("message", "")
        logger.info("    [%s] %s", status, msg)

    pptx_size = Path(pptx_out).stat().st_size
    logger.info("  -> File size: %.1f KB", pptx_size / 1024)

    # Copy to main output directory
    main_output = Path("C:/Projects/Deckbuilder/output")
    main_output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pptx_out, str(main_output / "deck.pptx"))
    logger.info("\nCopied -> %s", main_output / "deck.pptx")

    logger.info("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
