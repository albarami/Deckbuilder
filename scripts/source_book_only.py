"""
Source Book Only — runs the pipeline ONLY through Source Book generation.

Stops BEFORE assembly_plan / blueprint_extraction / section_fill / build_slides / render.
Produces Source Book artifacts only: DOCX, evidence ledger, slide blueprints,
external evidence pack, research logs.

NO PPTX. NO DECK. NO RENDER. NO PROOF CLASSIFICATION.

Usage:
    python scripts/source_book_only.py --language en
    python scripts/source_book_only.py --language ar
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

# Force UTF-8 on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s %(levelname)s: %(message)s",
)

from langgraph.types import Command  # noqa: E402

# Increase retry budget for LLM calls
import src.services.llm as _llm_mod  # noqa: E402
from src.models.enums import RendererMode  # noqa: E402
from src.models.state import DeckForgeState, SessionMetadata  # noqa: E402
from src.pipeline.graph import build_graph  # noqa: E402
from src.services.search import _ensure_local_backend  # noqa: E402

_llm_mod._RETRY_DELAYS = [10, 20, 40, 60, 90, 120]

_orig_get_anthropic = _llm_mod._get_anthropic_client


def _patched_get_anthropic():
    if not getattr(_llm_mod, "_anthropic_client", None):
        settings = _llm_mod.get_settings()
        _llm_mod._anthropic_client = _llm_mod.anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            max_retries=5,
            timeout=1200.0,
        )
    return _llm_mod._anthropic_client


_llm_mod._get_anthropic_client = _patched_get_anthropic

BRIEF_POSITIVE = (
    "Digital Transformation Consulting Services RFP -- "
    "The Ministry of Communications and Information Technology (MCIT) of the "
    "Kingdom of Saudi Arabia seeks a consulting firm to provide digital "
    "transformation advisory, enterprise architecture assessment, and "
    "automation strategy services. "
    "Strategic Gears proposes a phased consulting engagement leveraging its "
    "proven KSA government advisory experience, certified team, and "
    "structured delivery methodology. "
    "Evaluation Criteria: Technical Approach and Methodology (30%), "
    "Team Qualifications and Experience (25%), Past Performance and "
    "Project References (25%), Compliance and Certifications (10%), "
    "Project Management and Governance (10%)."
)


async def ensure_search_index(docs_path: str) -> str:
    """Index the local knowledge source."""
    import src.services.search as _search_mod

    cache_dir = "state/index_positive/"
    _search_mod._backend = None
    _search_mod.DEFAULT_DOCS_PATH = docs_path
    _search_mod.DEFAULT_CACHE_PATH = cache_dir
    print(f"[INDEX] Overriding search defaults: docs={docs_path}")

    cache_path = Path(cache_dir)
    embeddings = cache_path / "embeddings.npy"
    if embeddings.exists():
        print(f"[INDEX] Using cached index at {cache_path}")
    else:
        print(f"[INDEX] Indexing documents from {docs_path} ...")
    await _ensure_local_backend(docs_path, str(cache_dir))
    print(f"[INDEX] Search backend ready (docs={docs_path})")
    return str(cache_dir)


def _count_words(text: str | None) -> int:
    return len(text.split()) if text else 0


async def run_source_book_only(
    language: str,
    docs_path: str = "data_positive_proof",
) -> dict[str, Any]:
    """Run pipeline through Source Book only. No PPT. No render."""
    lang_suffix = "ar" if language == "ar" else "en"

    print(f"\n{'=' * 80}")
    print(f"  SOURCE BOOK ONLY: language={language}")
    print("  Stops at: source_book (before assembly_plan)")
    print("  NO PPTX. NO DECK. NO RENDER.")
    print(f"{'=' * 80}\n")

    await ensure_search_index(docs_path=docs_path)

    # Build graph
    print("\n[BUILD] Building production pipeline graph...")
    graph = build_graph()
    print("[BUILD] Graph ready")

    session_id = f"sb-{lang_suffix}-{int(time.time())}"
    state = DeckForgeState(
        ai_assist_summary=BRIEF_POSITIVE,
        output_language=language,
        renderer_mode=RendererMode.TEMPLATE_V2,
        geography="ksa",
        proposal_mode="standard",
        sector="technology",
        session=SessionMetadata(session_id=session_id),
    )
    config = {"configurable": {"thread_id": session_id}}

    print(f"[SESSION] ID: {session_id}")
    stages: list[tuple[str, float]] = []

    # ── PHASE 1: context → gate_1 ──
    print(f"\n{'-' * 80}")
    print("  PHASE 1: START → context → gate_1 (interrupt)")
    print(f"{'-' * 80}")
    t0 = time.time()
    result = await graph.ainvoke(state, config)
    t1 = time.time()
    print(f"  Time: {t1 - t0:.1f}s | Stage: {result.get('current_stage')}")
    ctx = result.get("rfp_context")
    if ctx:
        print(f"  rfp_name: {getattr(ctx, 'rfp_name', 'N/A')}")
    stages.append(("context → gate_1", t1 - t0))

    # ── PHASE 2: gate_1 approve → retrieval → gate_2 ──
    print(f"\n{'-' * 80}")
    print("  PHASE 2: gate_1 approve → retrieval → gate_2 (interrupt)")
    print(f"{'-' * 80}")
    t0 = time.time()
    result = await graph.ainvoke(Command(resume={"approved": True}), config)
    t1 = time.time()
    sources = result.get("retrieved_sources", [])
    print(f"  Time: {t1 - t0:.1f}s | Sources: {len(sources)}")
    stages.append(("retrieval → gate_2", t1 - t0))

    # ── PHASE 3: gate_2 approve → evidence_curation → proposal_strategy
    #             → source_book → gate_3 (interrupt) ──
    # This is where the Source Book is produced. We STOP here.
    print(f"\n{'-' * 80}")
    print("  PHASE 3: gate_2 approve → evidence_curation →")
    print("           proposal_strategy → source_book → gate_3")
    print(f"{'-' * 80}")
    t0 = time.time()
    result = await graph.ainvoke(Command(resume={"approved": True}), config)
    t1 = time.time()
    print(f"  Time: {t1 - t0:.1f}s | Stage: {result.get('current_stage')}")
    stages.append(("evidence → strategy → source_book → gate_3", t1 - t0))

    # ── Extract all Source Book data ──
    source_book = result.get("source_book")
    source_book_review = result.get("source_book_review")
    ext_evidence = result.get("external_evidence_pack")
    knowledge_graph = result.get("knowledge_graph")
    docx_path = result.get("report_docx_path")

    # ── Persist artifacts ──
    output_dir = Path("output") / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. source_book.docx — already persisted by pipeline
    print(f"\n  Source Book DOCX: {docx_path}")

    # 2. evidence_ledger.json
    ledger_path = None
    ledger_count = 0
    if source_book:
        ledger_data = source_book.evidence_ledger.model_dump(mode="json")
        ledger_count = len(ledger_data.get("entries", []))
        ledger_path = str(output_dir / "evidence_ledger.json")
        Path(ledger_path).write_text(
            json.dumps(ledger_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  Evidence ledger: {ledger_path} ({ledger_count} entries)")

    # 3. slide_blueprint_from_source_book.json
    blueprint_path = None
    blueprint_count = 0
    if source_book:
        bp_data = [bp.model_dump(mode="json") for bp in source_book.slide_blueprints]
        blueprint_count = len(bp_data)
        blueprint_path = str(output_dir / "slide_blueprint_from_source_book.json")
        Path(blueprint_path).write_text(
            json.dumps(bp_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  Slide blueprints: {blueprint_path} ({blueprint_count} entries)")

    # 4. external_evidence_pack.json
    ext_path = None
    ext_source_count = 0
    if ext_evidence:
        ext_data = ext_evidence.model_dump(mode="json")
        ext_source_count = len(ext_data.get("sources", []))
        ext_path = str(output_dir / "external_evidence_pack.json")
        Path(ext_path).write_text(
            json.dumps(ext_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  External evidence: {ext_path} ({ext_source_count} sources)")

    # 5. research_query_log.json — from external research agent's log
    query_log = _collect_research_query_log(ext_evidence)
    query_log_path = str(output_dir / "research_query_log.json")
    Path(query_log_path).write_text(
        json.dumps(query_log, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Research query log: {query_log_path}")

    # 6. research_results_raw.json — raw results from S2 + Perplexity
    raw_results = _collect_raw_research_results(ext_evidence)
    raw_path = str(output_dir / "research_results_raw.json")
    Path(raw_path).write_text(
        json.dumps(raw_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Research results raw: {raw_path}")

    # ── Compute metrics ──
    sb_word_count = 0
    cap_count = 0
    consultant_count = 0
    project_count = 0
    consultant_names: list[str] = []
    project_names: list[str] = []
    pass_number = 0
    review_score = 0

    if source_book:
        prose_parts = [
            source_book.rfp_interpretation.objective_and_scope,
            source_book.rfp_interpretation.constraints_and_compliance,
            source_book.rfp_interpretation.unstated_evaluator_priorities,
            source_book.rfp_interpretation.probable_scoring_logic,
            source_book.client_problem_framing.current_state_challenge,
            source_book.client_problem_framing.why_it_matters_now,
            source_book.client_problem_framing.transformation_logic,
            source_book.client_problem_framing.risk_if_unchanged,
            source_book.proposed_solution.methodology_overview,
            source_book.proposed_solution.governance_framework,
            source_book.proposed_solution.timeline_logic,
            source_book.proposed_solution.value_case_and_differentiation,
        ]
        # Add certifications (now list[str])
        if source_book.why_strategic_gears.certifications_and_compliance:
            prose_parts.append(
                " ".join(source_book.why_strategic_gears.certifications_and_compliance)
            )
        sb_word_count = sum(_count_words(p) for p in prose_parts)

        cap_count = len(source_book.why_strategic_gears.capability_mapping)

        wsg = source_book.why_strategic_gears
        consultant_count = len(wsg.named_consultants)
        consultant_names = [c.name for c in wsg.named_consultants]
        project_count = len(wsg.project_experience)
        project_names = [p.project_name for p in wsg.project_experience]
        pass_number = source_book.pass_number

    if source_book_review:
        review_score = source_book_review.overall_score

    # ── Check Perplexity + Semantic Scholar status ──
    s2_status = "NOT CALLED"
    pplx_status = "NOT CALLED"
    s2_result_count = 0
    pplx_result_count = 0
    if ext_evidence:
        coverage = getattr(ext_evidence, "coverage_assessment", "")
        sources_list = getattr(ext_evidence, "sources", [])
        for src in sources_list:
            st = getattr(src, "source_type", "")
            if "academic" in st or "scholar" in st:
                s2_result_count += 1
            elif "web" in st or "perplexity" in st or "report" in st:
                pplx_result_count += 1

        if s2_result_count > 0:
            s2_status = f"WORKING ({s2_result_count} results)"
        elif "Semantic Scholar" in coverage or "no results" in coverage.lower():
            s2_status = f"FAILED (coverage says: {coverage[:100]})"
        else:
            s2_status = "ZERO RESULTS (no academic sources in pack)"

        if pplx_result_count > 0:
            pplx_status = f"WORKING ({pplx_result_count} results)"
        elif "Perplexity" in coverage:
            pplx_status = f"FAILED (coverage says: {coverage[:100]})"
        else:
            pplx_status = "ZERO RESULTS (no web sources in pack)"

    # ── KG diagnostic ──
    kg_people_count = 0
    kg_project_count = 0
    if knowledge_graph:
        kg_people = getattr(knowledge_graph, "people", [])
        kg_projects = getattr(knowledge_graph, "projects", [])
        kg_people_count = len([
            p for p in kg_people
            if getattr(p, "person_type", "") == "internal_team"
        ])
        kg_project_count = len(kg_projects)

    # Placeholder detection
    placeholder_names = [
        n for n in consultant_names
        if any(p in n.lower() for p in [
            "placeholder", "[", "tbd", "tbc", "name",
            "consultant 1", "consultant 2", "to be",
        ])
    ]
    real_names = [n for n in consultant_names if n not in placeholder_names]

    # ── HARD FAIL checks ──
    failures: list[str] = []
    if ledger_count == 0:
        failures.append("Evidence ledger (Section 7) has 0 entries")
    if blueprint_count < 8:
        failures.append(
            f"Slide blueprint (Section 6) has {blueprint_count} entries (need >= 8)"
        )
    if s2_result_count == 0 and pplx_result_count == 0:
        failures.append("Both Semantic Scholar AND Perplexity returned zero results")
    if (
        kg_people_count > 0
        and len(real_names) == 0
        and consultant_count > 0
    ):
        failures.append(
            "All named consultants are placeholders despite KG having "
            f"{kg_people_count} internal team members"
        )

    status = "FAILURE" if failures else "SUCCESS"

    # ── Print summary ──
    total_time = sum(s[1] for s in stages)
    print(f"\n{'=' * 80}")
    print(f"  SOURCE BOOK SUMMARY — Session: {session_id}")
    print(f"{'=' * 80}")
    print(f"\n  Status: {status}")
    if failures:
        print("  HARD FAIL REASONS:")
        for f in failures:
            print(f"    ✗ {f}")

    print("\n  --- Content Metrics ---")
    print(f"  Word count (prose sections):     {sb_word_count}")
    print(f"  Evidence ledger entries:         {ledger_count}")
    print(f"  Slide blueprint entries:         {blueprint_count}")
    print(f"  External evidence sources:       {ext_source_count}")
    print(f"    Semantic Scholar:              {s2_result_count}")
    print(f"    Perplexity:                    {pplx_result_count}")
    print(f"  Capability mappings:             {cap_count}")
    print(f"  Named consultants:               {consultant_count}")
    print(f"    Real names:                    {len(real_names)}")
    print(f"    Placeholder names:             {len(placeholder_names)}")
    print(f"  Prior projects:                  {project_count}")

    print("\n  --- Writer/Reviewer ---")
    print(f"  Writer pass count:               {pass_number}")
    print(f"  Final review score:              {review_score}/5")
    if source_book_review:
        print(
            f"  Competitive viability:           "
            f"{source_book_review.competitive_viability}"
        )
        print(
            f"  Pass threshold met:              "
            f"{source_book_review.pass_threshold_met}"
        )

    print("\n  --- External Research Status ---")
    print(f"  Semantic Scholar:                {s2_status}")
    print(f"  Perplexity:                      {pplx_status}")

    print("\n  --- Knowledge Graph ---")
    print(f"  KG internal team members:        {kg_people_count}")
    print(f"  KG projects:                     {kg_project_count}")

    print("\n  --- Named Consultants ---")
    for name in consultant_names[:10]:
        marker = "✓" if name in real_names else "✗ PLACEHOLDER"
        print(f"    {marker}  {name}")

    print("\n  --- Prior Projects ---")
    for name in project_names[:10]:
        print(f"    • {name}")

    print("\n  --- Artifacts ---")
    artifacts = [
        ("Source Book DOCX", docx_path),
        ("Evidence Ledger JSON", ledger_path),
        ("Slide Blueprint JSON", blueprint_path),
        ("External Evidence Pack", ext_path),
        ("Research Query Log", query_log_path),
        ("Research Results Raw", raw_path),
    ]
    for label, path in artifacts:
        if path and Path(path).exists():
            size = Path(path).stat().st_size
            print(f"    {label}: {path} ({size:,} bytes)")
        elif path:
            print(f"    {label}: {path} (NOT FOUND)")
        else:
            print(f"    {label}: (not generated)")

    print("\n  --- Timing ---")
    for label, elapsed in stages:
        print(f"    {elapsed:7.1f}s  {label}")
    print(f"    {total_time:7.1f}s  TOTAL")

    print(f"\n{'=' * 80}")
    print(f"  FINAL STATUS: {status}")
    print(f"{'=' * 80}\n")

    return {
        "status": status,
        "session_id": session_id,
        "failures": failures,
        "word_count": sb_word_count,
        "evidence_ledger_entries": ledger_count,
        "slide_blueprint_entries": blueprint_count,
        "external_sources": ext_source_count,
        "s2_status": s2_status,
        "pplx_status": pplx_status,
        "capability_mappings": cap_count,
        "consultant_count": consultant_count,
        "real_consultant_names": real_names,
        "project_count": project_count,
        "project_names": project_names,
        "pass_number": pass_number,
        "review_score": review_score,
        "total_time": total_time,
        "docx_path": docx_path,
        "artifacts": {k: v for k, v in artifacts},
    }


def _collect_research_query_log(ext_evidence) -> dict:
    """Build research query log from available data."""
    log: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "queries_sent": [],
    }
    if ext_evidence:
        queries = getattr(ext_evidence, "search_queries_used", [])
        for q in queries:
            log["queries_sent"].append({
                "query": q,
                "services": ["semantic_scholar", "perplexity"],
            })
        log["coverage_assessment"] = getattr(
            ext_evidence, "coverage_assessment", "",
        )
    return log


def _collect_raw_research_results(ext_evidence) -> dict:
    """Build raw research results from available data."""
    results: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "semantic_scholar_results": [],
        "perplexity_results": [],
    }
    if ext_evidence:
        sources = getattr(ext_evidence, "sources", [])
        for src in sources:
            entry = {
                "source_id": getattr(src, "source_id", ""),
                "title": getattr(src, "title", ""),
                "source_type": getattr(src, "source_type", ""),
                "year": getattr(src, "year", 0),
                "url": getattr(src, "url", ""),
                "relevance_score": getattr(src, "relevance_score", 0),
                "relevance_reason": getattr(src, "relevance_reason", ""),
            }
            st = getattr(src, "source_type", "")
            if "academic" in st or "scholar" in st:
                results["semantic_scholar_results"].append(entry)
            else:
                results["perplexity_results"].append(entry)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Source Book Only — no PPT, no render",
    )
    parser.add_argument(
        "--language", choices=["en", "ar"], default="en",
    )
    parser.add_argument(
        "--docs-path", default="data_positive_proof",
        help="Path to curated data directory",
    )
    args = parser.parse_args()

    result = asyncio.run(
        run_source_book_only(args.language, args.docs_path),
    )

    # Write result JSON
    out = Path(f"source_book_only_{args.language}_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str, ensure_ascii=False)
    print(f"Results written to: {out}")
