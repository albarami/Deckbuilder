"""E2E test for the M10 iterative slide builder only.

Loads existing state from prior E2E run (Steps 1-4 outputs),
then runs just Step 5 (5-turn iterative builder) + Step 6 (QA)
+ Step 7 (Render).

Usage:
    python -m scripts.e2e_iterative_test
"""

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)  # override empty system vars

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("e2e_iterative_test")


def _separator(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def _save_json(data: object, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if hasattr(data, "model_dump_json"):
            f.write(data.model_dump_json(indent=2))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)


async def run_iterative_e2e() -> None:
    """Load state from prior run, execute iterative builder + QA + render."""
    from src.agents.iterative.builder import run_iterative_build
    from src.agents.qa import agent as qa_agent
    from src.models.claims import ReferenceIndex
    from src.models.iterative import DeckDraft, DeckReview
    from src.models.report import ResearchReport
    from src.models.rfp import RFPContext
    from src.models.state import (
        DeckForgeState,
        GateDecision,
        RetrievedSource,
        SessionMetadata,
    )
    from src.services.renderer import export_report_docx, render_pptx

    output_dir = Path("output")
    timings: dict[str, float] = {}
    pipeline_start = time.perf_counter()

    # ── Load prior state from E2E outputs ────────────────────
    _separator("LOADING PRIOR E2E STATE (Steps 1-4)")

    # Load RFP context
    rfp_data = json.loads((output_dir / "step1_rfp_context.json").read_text(encoding="utf-8"))
    rfp_context = RFPContext(**rfp_data)
    print(f"RFP: {rfp_context.rfp_name.en}")

    # Load reference index
    ref_data = json.loads((output_dir / "step3_reference_index.json").read_text(encoding="utf-8"))
    reference_index = ReferenceIndex(**ref_data)
    print(f"Claims: {len(reference_index.claims)} | Gaps: {len(reference_index.gaps)}")

    # Load research report
    report_data = json.loads((output_dir / "step4_research_report.json").read_text(encoding="utf-8"))
    research_report = ResearchReport(**report_data)
    report_md = (output_dir / "step4_report.md").read_text(encoding="utf-8")
    print(f"Report: {research_report.title} ({len(report_md)} chars)")

    # Load retrieval results
    retrieval_data = json.loads((output_dir / "step2_retrieval.json").read_text(encoding="utf-8"))
    ranked_sources = [RetrievedSource(**s) for s in retrieval_data.get("ranked_sources", [])]
    print(f"Retrieved Sources: {len(ranked_sources)}")
    for rs in ranked_sources:
        print(f"  [{rs.doc_id}] {rs.title} score={rs.relevance_score} rec={rs.recommendation}")

    # Build state
    state = DeckForgeState(
        ai_assist_summary="SAP Support Renewal RFP from SIDF",
        output_language="en",
        session=SessionMetadata(session_id=str(uuid.uuid4())),
        rfp_context=rfp_context,
        reference_index=reference_index,
        research_report=research_report,
        report_markdown=report_md,
        retrieved_sources=ranked_sources,
        approved_source_ids=[s.doc_id for s in ranked_sources],
        gate_1=GateDecision(gate_number=1, approved=True),
        gate_2=GateDecision(gate_number=2, approved=True),
        gate_3=GateDecision(gate_number=3, approved=True),
    )

    print(f"\nState loaded. Starting iterative builder...")

    # ── STEP 5: 5-Turn Iterative Slide Builder ─────────────
    _separator("STEP 5: 5-TURN ITERATIVE SLIDE BUILDER")
    t0 = time.perf_counter()
    state = await run_iterative_build(state)
    timings["5_iterative_builder"] = time.perf_counter() - t0

    if state.last_error:
        print(f"ERROR: {state.last_error.message}")
        print("Continuing despite error...")

    print(f"Evidence Mode: {state.evidence_mode}")
    print(f"Total Time: {timings['5_iterative_builder']:.1f}s")
    print(f"LLM Calls: {state.session.total_llm_calls}")
    print(f"Tokens: in={state.session.total_input_tokens:,}, out={state.session.total_output_tokens:,}")

    # Show Turn 1: Draft
    print(f"\n  --- Turn 1: Draft Agent (Opus) ---")
    if state.deck_drafts:
        draft_1 = DeckDraft(**state.deck_drafts[0])
        print(f"  Slides: {len(draft_1.slides)} | Mode: {draft_1.mode}")
        for sl in draft_1.slides[:8]:
            evidence = f" [{sl.evidence_level}]" if sl.evidence_level else ""
            print(f"    S{sl.slide_number}: {sl.title}{evidence}")
            for b in sl.bullets[:2]:
                print(f"      - {b[:150]}")
        if len(draft_1.slides) > 8:
            print(f"    ... and {len(draft_1.slides) - 8} more slides")
    else:
        print("  (No draft produced)")

    # Show Turn 2: Review
    print(f"\n  --- Turn 2: Review Agent (GPT) ---")
    if state.deck_reviews:
        review_1 = DeckReview(**state.deck_reviews[0])
        print(f"  Overall Score: {review_1.overall_score}/5")
        if review_1.coherence_issues:
            print(f"  Coherence Issues:")
            for issue in review_1.coherence_issues[:5]:
                print(f"    ! {issue[:150]}")
        for cr in review_1.critiques[:8]:
            issues_text = "; ".join(cr.issues[:2]) if cr.issues else "OK"
            print(f"    S{cr.slide_number}: score={cr.score}/5 | {issues_text[:150]}")
        if len(review_1.critiques) > 8:
            print(f"    ... and {len(review_1.critiques) - 8} more critiques")
    else:
        print("  (No review produced)")

    # Show Turn 3: Refine
    print(f"\n  --- Turn 3: Refine Agent (Opus) ---")
    if len(state.deck_drafts) >= 2:
        draft_2 = DeckDraft(**state.deck_drafts[1])
        print(f"  Slides: {len(draft_2.slides)} | Mode: {draft_2.mode}")
        for sl in draft_2.slides[:8]:
            evidence = f" [{sl.evidence_level}]" if sl.evidence_level else ""
            print(f"    S{sl.slide_number}: {sl.title}{evidence}")
            for b in sl.bullets[:2]:
                print(f"      - {b[:150]}")
        if len(draft_2.slides) > 8:
            print(f"    ... and {len(draft_2.slides) - 8} more slides")
    else:
        print("  (No refined draft produced)")

    # Show Turn 4: Final Review
    print(f"\n  --- Turn 4: Final Review Agent (GPT) ---")
    if len(state.deck_reviews) >= 2:
        review_2 = DeckReview(**state.deck_reviews[1])
        print(f"  Overall Score: {review_2.overall_score}/5")
        if review_2.coherence_issues:
            print(f"  Coherence Issues:")
            for issue in review_2.coherence_issues[:5]:
                print(f"    ! {issue[:150]}")
        for cr in review_2.critiques[:8]:
            issues_text = "; ".join(cr.issues[:2]) if cr.issues else "OK"
            print(f"    S{cr.slide_number}: score={cr.score}/5 | {issues_text[:150]}")
        if len(review_2.critiques) > 8:
            print(f"    ... and {len(review_2.critiques) - 8} more critiques")
    else:
        print("  (No final review produced)")

    # Show Turn 5: Presentation (Final Slides)
    print(f"\n  --- Turn 5: Presentation Agent (Opus) ---")
    written = state.written_slides
    if written:
        print(f"  Final Slides: {len(written.slides)} slides")
        for sl in written.slides:
            print(f"\n    [{sl.layout_type}] {sl.title}")
            if sl.body_content and sl.body_content.text_elements:
                for elem in sl.body_content.text_elements[:4]:
                    print(f"      - {elem[:150]}")
                if len(sl.body_content.text_elements) > 4:
                    print(f"      ... +{len(sl.body_content.text_elements) - 4} more")
            if sl.speaker_notes:
                print(f"      Notes: {sl.speaker_notes[:120]}...")
            if sl.source_refs:
                print(f"      Refs: {sl.source_refs}")
    else:
        print("  (No written slides produced)")

    # Save iterative builder outputs
    if written:
        _save_json(written, "output/step5_written_slides.json")
    if state.deck_drafts:
        _save_json(state.deck_drafts, "output/step5_deck_drafts.json")
    if state.deck_reviews:
        _save_json(state.deck_reviews, "output/step5_deck_reviews.json")

    # ── GATE 4: AUTO-APPROVE ─────────────────────────────────
    _separator("GATE 4: BUILT SLIDES REVIEW")
    if written:
        print(f"Evidence Mode: {state.evidence_mode}")
        print(f"Total Slides: {len(written.slides)}")
        print(f"Drafts: {len(state.deck_drafts)} | Reviews: {len(state.deck_reviews)}")
        for i, sl in enumerate(written.slides):
            refs = f" refs={sl.source_refs}" if sl.source_refs else ""
            print(f"  Slide {i+1}: [{sl.layout_type}] {sl.title}{refs}")
    print("\n>> AUTO-APPROVED")
    state.gate_4 = GateDecision(gate_number=4, approved=True)

    # ── STEP 6: QA Agent ──────────────────────────────────────
    _separator("STEP 6: QA AGENT (GPT)")
    t0 = time.perf_counter()
    state = await qa_agent.run(state)
    timings["6_qa"] = time.perf_counter() - t0

    if state.last_error:
        print(f"ERROR: {state.last_error.message}")
        print("Continuing despite error...")

    qa = state.qa_result
    if qa:
        print(f"QA Result ({timings['6_qa']:.1f}s):")
        print(f"  Total Slides: {qa.deck_summary.total_slides}")
        print(f"  Passed: {qa.deck_summary.passed}")
        print(f"  Failed: {qa.deck_summary.failed}")
        print(f"  Warnings: {qa.deck_summary.warnings}")
        print(f"  Ungrounded Claims: {qa.deck_summary.ungrounded_claims}")
        print(f"  Fail Close: {qa.deck_summary.fail_close}")
        if qa.slide_validations:
            print("\n  Per-Slide Results:")
            for sv in qa.slide_validations[:15]:
                status = sv.status
                issue_count = len(sv.issues)
                issues_text = ", ".join(f"{i.type}" for i in sv.issues[:3]) if sv.issues else "OK"
                print(f"    [{status}] {sv.slide_id}: {issues_text} ({issue_count} issues)")
        _save_json(qa, "output/step6_qa_result.json")
    else:
        print("No QA result produced")

    # ── GATE 5: AUTO-APPROVE ─────────────────────────────────
    _separator("GATE 5: FINAL DECK REVIEW")
    if qa:
        print(f"QA: {qa.deck_summary.passed} passed, {qa.deck_summary.failed} failed")
    print(">> AUTO-APPROVED")
    state.gate_5 = GateDecision(gate_number=5, approved=True)

    # ── STEP 7: PPTX + DOCX Rendering ─────────────────────────
    _separator("STEP 7: RENDER PPTX + DOCX")
    slides = state.final_slides
    if not slides and state.written_slides:
        slides = state.written_slides.slides

    if not slides:
        print("ERROR: No slides available for rendering!")
        return

    t0 = time.perf_counter()
    template_path = "templates/Presentation6.pptx"
    pptx_path = str(output_dir / "deck.pptx")

    render_result = await render_pptx(slides, template_path, pptx_path, state.output_language)
    timings["7_render_pptx"] = time.perf_counter() - t0

    print(f"PPTX Rendered ({timings['7_render_pptx']:.1f}s):")
    print(f"  Path: {render_result.pptx_path}")
    print(f"  Slides: {render_result.slide_count}")
    pptx_size = Path(render_result.pptx_path).stat().st_size
    print(f"  Size: {pptx_size / 1024:.1f} KB")

    # DOCX
    if state.research_report:
        t0 = time.perf_counter()
        docx_path = str(output_dir / "report.docx")
        await export_report_docx(state.research_report, docx_path, state.output_language)
        timings["7_export_docx"] = time.perf_counter() - t0
        docx_size = Path(docx_path).stat().st_size
        print(f"\nDOCX Exported ({timings['7_export_docx']:.1f}s):")
        print(f"  Path: {docx_path}")
        print(f"  Size: {docx_size / 1024:.1f} KB")

    # ── FINAL SUMMARY ───────────────────────────────────────
    _separator("PIPELINE COMPLETE")
    total_time = time.perf_counter() - pipeline_start
    session = state.session
    total_in = session.total_input_tokens
    total_out = session.total_output_tokens
    est_cost = (total_in / 1_000_000 * 5) + (total_out / 1_000_000 * 20)

    print(f"Total Time:    {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"LLM Calls:     {session.total_llm_calls}")
    print(f"Input Tokens:  {total_in:,}")
    print(f"Output Tokens: {total_out:,}")
    print(f"Est. Cost:     ${est_cost:.2f}")
    print()
    print("Step Timings:")
    for step, secs in timings.items():
        print(f"  {step}: {secs:.1f}s")
    print()
    print("Output Files:")
    for f in sorted(output_dir.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name}: {size / 1024:.1f} KB")
    print()
    if state.errors:
        print(f"Errors ({len(state.errors)}):")
        for e in state.errors:
            print(f"  [{e.agent}] {e.error_type}: {e.message}")
    else:
        print("No errors.")

    # Copy to main output
    import shutil
    main_output = Path("C:/Projects/Deckbuilder/output")
    main_output.mkdir(parents=True, exist_ok=True)
    if Path(pptx_path).exists():
        shutil.copy2(pptx_path, str(main_output / "deck.pptx"))
        print(f"\nCopied deck.pptx -> {main_output / 'deck.pptx'}")
    docx_out = output_dir / "report.docx"
    if docx_out.exists():
        shutil.copy2(str(docx_out), str(main_output / "report.docx"))
        print(f"Copied report.docx -> {main_output / 'report.docx'}")


if __name__ == "__main__":
    asyncio.run(run_iterative_e2e())
