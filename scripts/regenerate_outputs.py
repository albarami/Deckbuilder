"""Regenerate PPTX and DOCX from existing E2E pipeline data.

Uses step5_written_slides.json (from iterative builder)
and step4_research_report.json to re-render with updated formatting.
"""

import asyncio
import json
import shutil
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.report import ResearchReport
from src.models.slides import SlideObject
from src.services.renderer import export_report_docx, render_pptx


async def main():
    base = Path(__file__).resolve().parent.parent
    output_dir = base / "output"

    # Try step5 first (iterative builder), fall back to step6 (old pipeline)
    slides_path = output_dir / "step5_written_slides.json"
    if not slides_path.exists():
        slides_path = output_dir / "step6_written_slides.json"

    report_path = output_dir / "step4_research_report.json"
    template_path = base / "templates" / "Presentation6.pptx"

    print(f"Loading slides from {slides_path.name}...")
    with open(slides_path, encoding="utf-8") as f:
        slides_data = json.load(f)

    print(f"Loading report from {report_path.name}...")
    with open(report_path, encoding="utf-8") as f:
        report_data = json.load(f)

    # Parse slide objects
    if "slides" in slides_data:
        slides = [SlideObject(**s) for s in slides_data["slides"]]
    else:
        slides = [SlideObject(**slides_data)]
    print(f"Parsed {len(slides)} slides")

    for i, s in enumerate(slides):
        print(f"  S{i+1}: [{s.layout_type}] {s.title}")

    # Parse report
    report = ResearchReport(**report_data)
    print(f"Parsed report: {report.title} ({len(report.sections)} sections)")

    # Render PPTX
    pptx_out = str(output_dir / "deck_formatted.pptx")
    print(f"\nRendering PPTX to {pptx_out}...")
    result = await render_pptx(
        slides=slides,
        template_path=str(template_path),
        output_path=pptx_out,
    )
    print(f"  -> {result.slide_count} slides rendered")
    for entry in result.render_log:
        status = entry.get("status", "?")
        msg = entry.get("message", "")
        print(f"    [{status}] {msg}")

    pptx_size = Path(pptx_out).stat().st_size
    print(f"  -> File size: {pptx_size / 1024:.1f} KB")

    # Export DOCX
    docx_out = str(output_dir / "report_formatted.docx")
    print(f"\nExporting DOCX to {docx_out}...")
    result_path = await export_report_docx(
        report=report,
        output_path=docx_out,
    )
    print(f"  -> Saved to {result_path}")

    # Copy to main output directory
    main_output = Path("C:/Projects/Deckbuilder/output")
    main_output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pptx_out, str(main_output / "deck.pptx"))
    print(f"\nCopied -> {main_output / 'deck.pptx'}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
