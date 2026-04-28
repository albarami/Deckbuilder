"""End-to-end real pipeline test — SIDF SAP Renewal RFP.

Runs the full 10-step DeckForge pipeline with real LLM calls against
the indexed knowledge base. Auto-approves all gates and captures
every intermediate output for review.

Usage:
    python -m scripts.e2e_real_test
"""

import asyncio
import json
import logging
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)  # Override empty system env vars with .env values

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("e2e_real_test")


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# Main E2E Runner
# ──────────────────────────────────────────────────────────────

async def run_e2e() -> None:
    """Execute full pipeline step-by-step with real LLM calls."""
    from src.agents.analysis import agent as analysis_agent
    from src.agents.context import agent as context_agent
    from src.agents.iterative.builder import run_iterative_build
    from src.agents.qa import agent as qa_agent
    from src.agents.research import agent as research_agent
    from src.agents.retrieval import planner as retrieval_planner
    from src.agents.retrieval import ranker as retrieval_ranker
    from src.models.iterative import DeckDraft, DeckReview
    from src.models.state import (
        DeckForgeState,
        GateDecision,
        SessionMetadata,
    )
    from src.services.renderer import export_report_docx, render_pptx
    from src.services.search import _get_backend, semantic_search

    timings: dict[str, float] = {}
    pipeline_start = time.perf_counter()
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load RFP input ──────────────────────────────────────
    _separator("STEP 0: LOAD RFP INPUT")
    rfp_path = "tests/fixtures/sample_rfp_summary.txt"
    rfp_text = Path(rfp_path).read_text(encoding="utf-8")
    print(f"RFP Input ({len(rfp_text)} chars):")
    print(rfp_text)

    user_notes = (
        "Focus on SAP HANA experience. "
        "Highlight SIDF relationship. "
        "Emphasize Saudization percentage."
    )

    state = DeckForgeState(
        ai_assist_summary=rfp_text,
        user_notes=user_notes,
        output_language="en",
        session=SessionMetadata(session_id=str(uuid.uuid4())),
    )

    # ── Load search index ────────────────────────────────────
    _separator("STEP 0b: LOAD SEARCH INDEX")
    backend = _get_backend()
    backend.load("./state/index/")
    print(f"Loaded search index: {len(backend._chunks)} chunks")

    # ── STEP 1: Context Agent ────────────────────────────────
    _separator("STEP 1: CONTEXT AGENT (GPT-5.4)")
    t0 = time.perf_counter()
    state = await context_agent.run(state)
    timings["1_context"] = time.perf_counter() - t0

    if state.last_error:
        print(f"ERROR: {state.last_error.message}")
        return

    ctx = state.rfp_context
    print(f"Time: {timings['1_context']:.1f}s")
    print(f"Stage: {state.current_stage}")
    print(f"RFP Name (EN): {ctx.rfp_name.en}")
    print(f"RFP Name (AR): {ctx.rfp_name.ar}")
    print(f"Issuing Entity (EN): {ctx.issuing_entity.en}")
    print(f"Mandate: {ctx.mandate.en[:200]}...")

    # Evaluation Criteria (single object, not list)
    if ctx.evaluation_criteria:
        ec = ctx.evaluation_criteria
        print("Evaluation Criteria:")
        if ec.technical:
            print(f"  Technical: weight={ec.technical.weight_pct}%")
            for sub in ec.technical.sub_criteria:
                print(f"    - {sub.name}: weight={sub.weight_pct}%")
        if ec.financial:
            print(f"  Financial: weight={ec.financial.weight_pct}%")
        print(f"  Passing Score: {ec.passing_score}")
        if hasattr(ec, "award_mechanism"):
            print(f"  Award Mechanism: {ec.award_mechanism}")
        if hasattr(ec, "technical_passing_threshold") and ec.technical_passing_threshold:
            print(f"  Technical Passing Threshold: {ec.technical_passing_threshold}")
    else:
        print("Evaluation Criteria: Not specified in RFP")

    print(f"Compliance Requirements: {len(ctx.compliance_requirements)}")
    for cr in ctx.compliance_requirements[:5]:
        print(f"  - [{cr.id}] {cr.requirement.en}")

    # Key Dates (single object, not list)
    if ctx.key_dates:
        kd = ctx.key_dates
        print("Key Dates:")
        if kd.submission_deadline:
            print(f"  Submission: {kd.submission_deadline}")
        if kd.service_start:
            print(f"  Service Start: {kd.service_start}")
        if kd.inquiry_deadline:
            print(f"  Inquiry: {kd.inquiry_deadline}")
    else:
        print("Key Dates: Not specified")

    print(f"Scope Items: {len(ctx.scope_items)}")
    for si in ctx.scope_items[:5]:
        print(f"  - [{si.id}] {si.description.en}")

    print(f"Gaps: {len(ctx.gaps)}")
    for g in ctx.gaps:
        print(f"  - [{g.severity}] {g.field}: {g.description}")
    print(f"\nTokens: in={state.session.total_input_tokens}, out={state.session.total_output_tokens}")

    _save_json(ctx, "output/step1_rfp_context.json")

    # ── GATE 1 ──────────────────────────────────────────────
    _separator("GATE 1: RFP CONTEXT REVIEW")
    print(f"RFP: {ctx.rfp_name.en}")
    print(f"Entity: {ctx.issuing_entity.en}")
    print(">> AUTO-APPROVED (output_language=en)")
    state.gate_1 = GateDecision(gate_number=1, approved=True)

    # ── STEP 2: Retrieval ────────────────────────────────────
    _separator("STEP 2: RETRIEVAL (Planner → Search → Ranker)")

    # Step 2a: Planner
    t0 = time.perf_counter()
    state, queries = await retrieval_planner.plan(state)
    t_plan = time.perf_counter() - t0

    if queries is None:
        print(f"ERROR: Planner failed: {state.last_error}")
        return

    print(f"Planner ({t_plan:.1f}s): {len(queries.search_queries)} queries generated")
    for i, sq in enumerate(queries.search_queries):
        print(f"  Q{i+1}: [{sq.strategy}|{sq.priority}] {sq.query}")

    # Step 2b: Vector search against real index
    t0 = time.perf_counter()
    query_strings = [sq.query for sq in queries.search_queries]
    search_results = await semantic_search(query_strings, top_k=15)
    t_search = time.perf_counter() - t0

    print(f"\nSearch ({t_search:.1f}s): {len(search_results)} results")
    for i, r in enumerate(search_results[:10]):
        print(f"  {i+1}. [{r['doc_id']}] {r['title']} (score={r['search_score']:.4f})")

    # Step 2c: Ranker
    t0 = time.perf_counter()
    state = await retrieval_ranker.run(state, search_results)
    t_rank = time.perf_counter() - t0

    timings["2_retrieval"] = t_plan + t_search + t_rank
    print(f"\nRanker ({t_rank:.1f}s): {len(state.retrieved_sources)} ranked sources")
    for rs in state.retrieved_sources:
        print(f"  [{rs.doc_id}] {rs.title} — score={rs.relevance_score}, rec={rs.recommendation}")

    print(f"\nTotal Retrieval: {timings['2_retrieval']:.1f}s")
    print(f"Tokens: in={state.session.total_input_tokens}, out={state.session.total_output_tokens}")

    _save_json({"queries": [q.model_dump() for q in queries.search_queries],
                "search_results": search_results,
                "ranked_sources": [s.model_dump() for s in state.retrieved_sources]},
               "output/step2_retrieval.json")

    # ── GATE 2 ──────────────────────────────────────────────
    _separator("GATE 2: SOURCE REVIEW")
    # Force-include ALL retrieved sources to demonstrate full pipeline
    # (knowledge base has no SAP-specific docs, ranker correctly excluded
    # them, but we want to show the pipeline producing output)
    approved_ids = [s.doc_id for s in state.retrieved_sources]
    if not approved_ids:
        # Fallback: use the search result doc_ids directly
        approved_ids = list({r["doc_id"] for r in search_results})
    print(f"Force-approved {len(approved_ids)} sources: {approved_ids}")
    print(">> AUTO-APPROVED (force-including all sources for E2E demo)")
    state.gate_2 = GateDecision(gate_number=2, approved=True)
    state.approved_source_ids = approved_ids

    # ── STEP 3: Analysis Agent ───────────────────────────────
    _separator("STEP 3: ANALYSIS AGENT (Claude Opus 4.6)")

    # Load document content from chunk index for approved docs
    chunk_data = json.loads(
        Path("./state/index/chunks.json").read_text(encoding="utf-8")
    )
    # Group chunks by doc_id, build document content
    from collections import defaultdict
    doc_chunks: dict[str, list] = defaultdict(list)
    for chunk in chunk_data:
        if chunk.get("doc_id") in approved_ids:
            doc_chunks[chunk["doc_id"]].append(chunk)

    documents: list[dict] = []
    for doc_id in approved_ids:
        chunks_for_doc = doc_chunks.get(doc_id, [])
        # Sort by level and chunk_id for coherent ordering
        chunks_for_doc.sort(key=lambda c: (c.get("level", 0), c.get("chunk_id", "")))
        content_parts = [c.get("text", "") for c in chunks_for_doc]
        title = chunks_for_doc[0].get("doc_title", doc_id) if chunks_for_doc else doc_id
        documents.append({
            "doc_id": doc_id,
            "title": title,
            "content_text": "\n\n".join(content_parts)[:30000],  # Truncate for LLM context
            "metadata": {
                "filename": chunks_for_doc[0].get("doc_title", "") if chunks_for_doc else "",
                "chunk_count": len(chunks_for_doc),
            },
        })

    print(f"Loaded {len(documents)} documents from chunk index")
    for d in documents:
        print(f"  [{d['doc_id']}] {d['title']} — {len(d['content_text'])} chars, {d['metadata']['chunk_count']} chunks")

    t0 = time.perf_counter()
    state = await analysis_agent.run(state, documents)
    timings["3_analysis"] = time.perf_counter() - t0

    if state.last_error:
        print(f"ERROR: {state.last_error.message}")
        # Continue anyway — some errors are recoverable
        print("Continuing despite error...")

    ref_idx = state.reference_index
    if ref_idx:
        print(f"\nAnalysis ({timings['3_analysis']:.1f}s):")
        print(f"  Claims: {len(ref_idx.claims)}")
        print(f"  Gaps: {len(ref_idx.gaps)}")
        print(f"  Contradictions: {len(ref_idx.contradictions)}")
        print("\nSample Claims (first 5):")
        for cl in ref_idx.claims[:5]:
            print(f"  [{cl.claim_id}] {cl.claim_text[:120]}...")
            print(f"    Source: {cl.source_doc_id} | Type: {cl.claim_type}")
        if ref_idx.gaps:
            print("\nGaps:")
            for g in ref_idx.gaps[:5]:
                print(f"  [{g.gap_id}] {g.description[:120]}...")
    else:
        print(f"No reference index produced (time={timings['3_analysis']:.1f}s)")

    print(f"\nTokens: in={state.session.total_input_tokens}, out={state.session.total_output_tokens}")
    if ref_idx:
        _save_json(ref_idx, "output/step3_reference_index.json")

    # ── STEP 4: Research Agent ───────────────────────────────
    _separator("STEP 4: RESEARCH AGENT (Claude Opus 4.6)")
    t0 = time.perf_counter()
    state = await research_agent.run(state)
    timings["4_research"] = time.perf_counter() - t0

    if state.last_error:
        print(f"ERROR: {state.last_error.message}")
        print("Continuing despite error...")

    report = state.research_report
    md = state.report_markdown
    if report:
        print(f"Research Report ({timings['4_research']:.1f}s):")
        print(f"  Title: {report.title}")
        print(f"  Sections: {len(report.sections)}")
        for sec in report.sections:
            ref_count = sec.content_markdown.count("[Ref:")
            print(f"    - {sec.heading} ({len(sec.content_markdown)} chars, {ref_count} refs)")
        if md:
            print(f"  Markdown: {len(md)} chars")
            # Count total refs
            import re
            all_refs = re.findall(r"\[Ref:\s*CLM-\d+\]", md)
            print(f"  Total [Ref: CLM-xxxx] citations: {len(all_refs)}")
            all_gaps = re.findall(r"\[GAP", md)
            print(f"  Total GAP flags: {len(all_gaps)}")
    else:
        print(f"No research report produced (time={timings['4_research']:.1f}s)")

    print(f"\nTokens: in={state.session.total_input_tokens}, out={state.session.total_output_tokens}")
    if report:
        _save_json(report, "output/step4_research_report.json")
    if md:
        Path("output/step4_report.md").write_text(md, encoding="utf-8")

    # ── GATE 3 ──────────────────────────────────────────────
    _separator("GATE 3: RESEARCH REPORT REVIEW (MOST IMPORTANT)")
    if md and report:
        # Show first 2000 chars of each section
        for sec in report.sections:
            print(f"\n--- {sec.heading} ---")
            print(sec.content_markdown[:2000])
            if len(sec.content_markdown) > 2000:
                print(f"  ... [{len(sec.content_markdown) - 2000} more chars]")
    print("\n>> AUTO-APPROVED")
    state.gate_3 = GateDecision(gate_number=3, approved=True)

    # ── STEP 5: 5-Turn Iterative Slide Builder (M10) ─────────
    _separator("STEP 5: 5-TURN ITERATIVE SLIDE BUILDER")
    tokens_before = (state.session.total_input_tokens, state.session.total_output_tokens)
    calls_before = state.session.total_llm_calls

    t0 = time.perf_counter()
    state = await run_iterative_build(state)
    timings["5_iterative_builder"] = time.perf_counter() - t0

    if state.last_error:
        print(f"ERROR: {state.last_error.message}")
        print("Continuing despite error...")

    print(f"Evidence Mode: {state.evidence_mode}")
    print(f"Total Time: {timings['5_iterative_builder']:.1f}s")
    calls_used = state.session.total_llm_calls - calls_before
    tokens_in_used = state.session.total_input_tokens - tokens_before[0]
    tokens_out_used = state.session.total_output_tokens - tokens_before[1]
    print(f"LLM Calls: {calls_used} | Tokens: in={tokens_in_used:,}, out={tokens_out_used:,}")

    # Show Turn 1: Draft
    print(f"\n  --- Turn 1: Draft Agent (Opus) ---")
    if state.deck_drafts:
        draft_1 = DeckDraft(**state.deck_drafts[0])
        print(f"  Slides: {len(draft_1.slides)} | Mode: {draft_1.mode}")
        for sl in draft_1.slides[:5]:
            evidence = f" [{sl.evidence_level}]" if sl.evidence_level else ""
            print(f"    S{sl.slide_number}: {sl.title}{evidence}")
            for b in sl.bullets[:2]:
                print(f"      - {b[:120]}...")
        if len(draft_1.slides) > 5:
            print(f"    ... and {len(draft_1.slides) - 5} more slides")
    else:
        print("  (No draft produced)")

    # Show Turn 2: Review
    print(f"\n  --- Turn 2: Review Agent (GPT) ---")
    if state.deck_reviews:
        review_1 = DeckReview(**state.deck_reviews[0])
        print(f"  Overall Score: {review_1.overall_score}/5")
        if review_1.coherence_issues:
            print(f"  Coherence Issues: {len(review_1.coherence_issues)}")
            for issue in review_1.coherence_issues[:3]:
                print(f"    ! {issue[:120]}...")
        for cr in review_1.critiques[:5]:
            issues_text = ", ".join(cr.issues[:2]) if cr.issues else "OK"
            print(f"    S{cr.slide_number}: score={cr.score}/5 | {issues_text[:120]}")
        if len(review_1.critiques) > 5:
            print(f"    ... and {len(review_1.critiques) - 5} more critiques")
    else:
        print("  (No review produced)")

    # Show Turn 3: Refine
    print(f"\n  --- Turn 3: Refine Agent (Opus) ---")
    if len(state.deck_drafts) >= 2:
        draft_2 = DeckDraft(**state.deck_drafts[1])
        print(f"  Slides: {len(draft_2.slides)} | Mode: {draft_2.mode}")
        for sl in draft_2.slides[:5]:
            evidence = f" [{sl.evidence_level}]" if sl.evidence_level else ""
            print(f"    S{sl.slide_number}: {sl.title}{evidence}")
            for b in sl.bullets[:2]:
                print(f"      - {b[:120]}...")
        if len(draft_2.slides) > 5:
            print(f"    ... and {len(draft_2.slides) - 5} more slides")
    else:
        print("  (No refined draft produced)")

    # Show Turn 4: Final Review
    print(f"\n  --- Turn 4: Final Review Agent (GPT) ---")
    if len(state.deck_reviews) >= 2:
        review_2 = DeckReview(**state.deck_reviews[1])
        print(f"  Overall Score: {review_2.overall_score}/5")
        if review_2.coherence_issues:
            print(f"  Coherence Issues: {len(review_2.coherence_issues)}")
            for issue in review_2.coherence_issues[:3]:
                print(f"    ! {issue[:120]}...")
        for cr in review_2.critiques[:5]:
            issues_text = ", ".join(cr.issues[:2]) if cr.issues else "OK"
            print(f"    S{cr.slide_number}: score={cr.score}/5 | {issues_text[:120]}")
        if len(review_2.critiques) > 5:
            print(f"    ... and {len(review_2.critiques) - 5} more critiques")
    else:
        print("  (No final review produced)")

    # Show Turn 5: Presentation (Final Slides)
    print(f"\n  --- Turn 5: Presentation Agent (Opus) ---")
    written = state.written_slides
    if written:
        print(f"  Final Slides: {len(written.slides)} slides")
        for sl in written.slides[:5]:
            print(f"\n    Slide: {sl.title} [{sl.layout_type}]")
            if sl.body_content and sl.body_content.text_elements:
                body_preview = " | ".join(sl.body_content.text_elements[:3])
                print(f"    Body ({len(sl.body_content.text_elements)} elements): {body_preview[:200]}...")
            else:
                print("    Body: (empty)")
            print(f"    Speaker Notes: {(sl.speaker_notes or 'N/A')[:150]}...")
            print(f"    Source Refs: {sl.source_refs}")
        if len(written.slides) > 5:
            print(f"\n    ... and {len(written.slides) - 5} more slides")
    else:
        print("  (No written slides produced)")

    print(f"\nTokens: in={state.session.total_input_tokens}, out={state.session.total_output_tokens}")
    if written:
        _save_json(written, "output/step5_written_slides.json")
    if state.deck_drafts:
        _save_json(state.deck_drafts, "output/step5_deck_drafts.json")
    if state.deck_reviews:
        _save_json(state.deck_reviews, "output/step5_deck_reviews.json")

    # ── GATE 4 ──────────────────────────────────────────────
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

    # ── STEP 7: QA Agent ─────────────────────────────────────
    _separator("STEP 7: QA AGENT (GPT-5.4)")
    t0 = time.perf_counter()
    state = await qa_agent.run(state)
    timings["7_qa"] = time.perf_counter() - t0

    if state.last_error:
        print(f"ERROR: {state.last_error.message}")
        print("Continuing despite error...")

    qa = state.qa_result
    if qa:
        print(f"QA Result ({timings['7_qa']:.1f}s):")
        print(f"  Total Slides: {qa.deck_summary.total_slides}")
        print(f"  Passed: {qa.deck_summary.passed}")
        print(f"  Failed: {qa.deck_summary.failed}")
        print(f"  Warnings: {qa.deck_summary.warnings}")
        print(f"  Ungrounded Claims: {qa.deck_summary.ungrounded_claims}")
        print(f"  Fail Close: {qa.deck_summary.fail_close}")
        if qa.deck_summary.fail_close:
            print(f"  Fail Close Reason: {qa.deck_summary.fail_close_reason}")
        if qa.slide_validations:
            print("\n  Per-Slide Results:")
            for sv in qa.slide_validations[:10]:
                status = sv.status
                issue_count = len(sv.issues)
                issues_text = ", ".join(f"{i.type}" for i in sv.issues[:3]) if sv.issues else "OK"
                print(f"    [{status}] {sv.slide_id}: {issues_text} ({issue_count} issues)")
    else:
        print(f"No QA result produced (time={timings['7_qa']:.1f}s)")

    print(f"\nTokens: in={state.session.total_input_tokens}, out={state.session.total_output_tokens}")
    if qa:
        _save_json(qa, "output/step7_qa_result.json")

    # ── GATE 5 ──────────────────────────────────────────────
    _separator("GATE 5: FINAL DECK REVIEW")
    if qa:
        print(f"QA: {qa.deck_summary.passed} passed, {qa.deck_summary.failed} failed")
        print(f"Fail Close: {qa.deck_summary.fail_close}")
    print(">> AUTO-APPROVED")
    state.gate_5 = GateDecision(gate_number=5, approved=True)

    # ── STEP 8: PPTX Rendering ───────────────────────────────
    _separator("STEP 8: PPTX RENDERING")
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
    timings["8_render_pptx"] = time.perf_counter() - t0

    print(f"PPTX Rendered ({timings['8_render_pptx']:.1f}s):")
    print(f"  Path: {render_result.pptx_path}")
    print(f"  Slides: {render_result.slide_count}")
    pptx_size = Path(render_result.pptx_path).stat().st_size
    print(f"  Size: {pptx_size / 1024:.1f} KB")

    state.pptx_path = render_result.pptx_path

    # ── STEP 9: DOCX Export ──────────────────────────────────
    _separator("STEP 9: DOCX EXPORT")
    if state.research_report:
        t0 = time.perf_counter()
        docx_path = str(output_dir / "report.docx")
        await export_report_docx(state.research_report, docx_path, state.output_language)
        timings["9_export_docx"] = time.perf_counter() - t0

        docx_size = Path(docx_path).stat().st_size
        print(f"DOCX Exported ({timings['9_export_docx']:.1f}s):")
        print(f"  Path: {docx_path}")
        print(f"  Size: {docx_size / 1024:.1f} KB")
        state.report_docx_path = docx_path
    else:
        print("No research report — skipping DOCX export")

    # ── STEP 10: Save state + pipeline log ───────────────────
    _separator("STEP 10: SAVE ALL OUTPUTS")
    total_time = time.perf_counter() - pipeline_start

    # Save final state
    from src.pipeline.graph import save_state
    save_state(state, "./state/session.json")
    print("Saved state: ./state/session.json")

    # Calculate costs
    session = state.session
    # GPT-5.4 pricing: ~$2/1M input, ~$8/1M output (estimated)
    # Claude Opus 4.6: ~$15/1M input, ~$75/1M output (estimated)
    # Rough estimate — we don't have per-model token breakdown
    total_in = session.total_input_tokens
    total_out = session.total_output_tokens
    # Conservative estimate: blend of GPT-5.4 and Claude costs
    est_cost = (total_in / 1_000_000 * 5) + (total_out / 1_000_000 * 20)

    pipeline_log = {
        "session_id": session.session_id,
        "started_at": datetime.now(UTC).isoformat(),
        "total_time_seconds": round(total_time, 1),
        "timings_seconds": {k: round(v, 1) for k, v in timings.items()},
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_llm_calls": session.total_llm_calls,
        "estimated_cost_usd": round(est_cost, 2),
        "pptx_path": state.pptx_path,
        "docx_path": state.report_docx_path,
        "slides_count": render_result.slide_count if render_result else 0,
        "qa_passed": qa.deck_summary.passed if qa else 0,
        "qa_failed": qa.deck_summary.failed if qa else 0,
        "qa_fail_close": qa.deck_summary.fail_close if qa else None,
        "errors": [e.model_dump() for e in state.errors],
    }
    _save_json(pipeline_log, "output/pipeline_run_log.json")

    # ── FINAL SUMMARY ────────────────────────────────────────
    _separator("PIPELINE COMPLETE")
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


if __name__ == "__main__":
    asyncio.run(run_e2e())
