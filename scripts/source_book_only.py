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
import re
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

# D3: Key-source diagnostic BEFORE load_dotenv merges .env into process env
from src.services.key_audit import print_key_diagnostic  # noqa: E402

print_key_diagnostic()

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s %(levelname)s: %(message)s",
)

from langgraph.types import Command  # noqa: E402

# Increase retry budget for LLM calls
import src.services.llm as _llm_mod  # noqa: E402
from src.models.enums import RendererMode  # noqa: E402
from src.models.state import DeckForgeState, SessionMetadata, UploadedDocument  # noqa: E402
from src.pipeline.graph import build_graph  # noqa: E402
from src.services.search import _ensure_local_backend  # noqa: E402
from src.utils.extractors import extract_directory  # noqa: E402

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

async def ensure_search_index(docs_path: str) -> tuple[str, str, str]:
    """Index the local knowledge source. Returns (cache_dir, status, reason).

    Status is one of: "OK", "DEGRADED".
    """
    import src.services.search as _search_mod

    docs_label = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(docs_path).name).strip("_")
    if not docs_label:
        docs_label = "default"
    cache_dir = f"state/index_source_book_{docs_label}/"
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
    try:
        await _ensure_local_backend(docs_path, str(cache_dir))
        print(f"[INDEX] Search backend ready (docs={docs_path})")
        return str(cache_dir), "OK", ""
    except Exception as exc:
        reason = str(exc)
        logger = logging.getLogger(__name__)
        logger.error(
            "INDEXING FAILED: Domain-specific index at %s could not be built. "
            "Reason: %s. The run will be marked DEGRADED.",
            cache_dir,
            reason,
        )
        _search_mod._backend = None
        backend = _search_mod._get_backend()
        backend.save(cache_dir)
        return str(cache_dir), "DEGRADED", reason


def _count_words(text: str | None) -> int:
    return len(text.split()) if text else 0


def _build_domain_agnostic_input(
    docs_path: str,
    language: str,
    max_summary_chars: int = 12_000,
) -> tuple[str, list[UploadedDocument]]:
    """Build DeckForge input from uploaded docs (no hardcoded domain brief)."""
    extracted_docs = extract_directory(docs_path)
    if not extracted_docs:
        msg = f"No supported documents found in docs path: {docs_path}"
        raise ValueError(msg)

    uploaded_documents: list[UploadedDocument] = []
    summary_parts: list[str] = []
    for doc in extracted_docs:
        text = (doc.full_text or "").strip()
        if not text:
            continue

        uploaded_documents.append(
            UploadedDocument(
                filename=doc.filename,
                content_text=text,
                language=language,
            )
        )
        summary_parts.append(f"[{doc.filename}]\n{text[:max_summary_chars]}")

    if not uploaded_documents:
        msg = (
            "Documents were found but text extraction returned empty content "
            f"for all files in: {docs_path}"
        )
        raise ValueError(msg)

    ai_summary = "\n\n".join(summary_parts)[:max_summary_chars]
    return ai_summary, uploaded_documents


async def run_source_book_only(
    language: str,
    docs_path: str = "data_positive_proof",
    max_summary_chars: int = 12_000,
    evidence_docs_path: str | None = None,
    evidence_cache_path: str | None = None,
) -> dict[str, Any]:
    """Run pipeline through Source Book only. No PPT. No render."""
    from src.services.llm import get_cost_summary, reset_cost_tracker

    reset_cost_tracker()
    lang_suffix = "ar" if language == "ar" else "en"

    print(f"\n{'=' * 80}")
    print(f"  SOURCE BOOK ONLY: language={language}")
    print("  Stops at: source_book (before assembly_plan)")
    print("  NO PPTX. NO DECK. NO RENDER.")
    if evidence_cache_path:
        print(f"  Evidence cache: {evidence_cache_path}")
    if evidence_docs_path:
        print(f"  Evidence docs:  {evidence_docs_path}")
    print(f"{'=' * 80}\n")

    # ── Step 1: Build RFP input from --docs-path (RFP only) ──
    ai_summary, uploaded_documents = _build_domain_agnostic_input(
        docs_path,
        language,
        max_summary_chars=max_summary_chars,
    )

    # ── Step 2: Build RFP-only index (resets _backend, overrides DEFAULT_CACHE_PATH) ──
    _cache_path, index_status, index_reason = await ensure_search_index(docs_path=docs_path)

    # ── Step 3: Validate + load evidence (AFTER RFP index) ──
    import src.services.search as _search_mod

    evidence_status = "OK"
    evidence_reason = ""
    evidence_consistent = True
    evidence_enabled = False
    evidence_manifest_docs = 0
    evidence_kg_people = 0
    evidence_kg_projects = 0
    evidence_kg_clients = 0

    if evidence_cache_path:
        if evidence_docs_path:
            # ── Step 3a: Validate cache/docs consistency BEFORE loading ──
            consistent, msg = _search_mod.validate_evidence_cache_consistency(
                evidence_cache_path, evidence_docs_path,
            )
            print(f"  [EVIDENCE] {msg}")
            evidence_consistent = consistent

            if not consistent:
                # FAIL CLOSED: do NOT load evidence backend, docs path, or KG.
                # Wrong evidence is worse than no evidence.
                evidence_status = "DEGRADED"
                evidence_reason = msg
                print(f"  [EVIDENCE] ⚠ MISMATCH — evidence mode DISABLED entirely")
                print(f"  [EVIDENCE]   Pipeline will run in RFP-only mode")
            else:
                # ── Step 3b: Consistency passed — load everything ──
                _search_mod.load_evidence_backend_from_cache(evidence_cache_path)
                _search_mod.set_evidence_docs_path(evidence_docs_path)
                _search_mod.EVIDENCE_KG_PATH = f"{evidence_cache_path}/knowledge_graph.json"
                evidence_enabled = True

                # Read manifest doc count for provenance
                manifest_path = Path(evidence_cache_path) / "manifest.json"
                if manifest_path.exists():
                    import json as _json
                    manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
                    evidence_manifest_docs = manifest.get("total_documents", 0)
        else:
            # Cache provided without docs path — retrieval/KG only mode
            print("  [EVIDENCE] ⚠ --evidence-cache-path set without --evidence-docs-path")
            print("  [EVIDENCE]   Loading retrieval backend + KG only")
            print("  [EVIDENCE]   Full-doc evidence loading NOT available")
            _search_mod.load_evidence_backend_from_cache(evidence_cache_path)
            _search_mod.EVIDENCE_KG_PATH = f"{evidence_cache_path}/knowledge_graph.json"
            evidence_enabled = True  # partial: retrieval + KG, no full-doc

    # Build graph
    print("\n[BUILD] Building production pipeline graph...")
    graph = build_graph()
    print("[BUILD] Graph ready")

    session_id = f"sb-{lang_suffix}-{int(time.time())}"
    state = DeckForgeState(
        ai_assist_summary=ai_summary,
        uploaded_documents=uploaded_documents,
        output_language=language,
        renderer_mode=RendererMode.TEMPLATE_V2,
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

    # ── DIAGNOSTIC: Print rfp_context fields ──
    if ctx:
        pt = getattr(ctx, "project_timeline", None)
        tr = getattr(ctx, "team_requirements", None)
        print("\n  [DIAG] rfp_context.project_timeline:")
        if pt:
            print(f"    total_duration: {getattr(pt, 'total_duration', 'N/A')}")
            print(f"    total_duration_months: {getattr(pt, 'total_duration_months', 'N/A')}")
            sched = getattr(pt, "deliverable_schedule", [])
            print(f"    deliverable_schedule: {len(sched)} items")
            for ds in sched[:5]:
                print(f"      - {getattr(ds, 'milestone', '?')}: {getattr(ds, 'due_date', '?')}")
            print(f"    notes: {getattr(pt, 'notes', 'N/A')}")
        else:
            print("    *** NOT POPULATED (None) ***")
        print("  [DIAG] rfp_context.team_requirements:")
        if tr:
            print(f"    {len(tr)} requirements:")
            for t_req in tr[:6]:
                rt = getattr(t_req, "role_title", None)
                title_str = ""
                if rt:
                    title_str = getattr(rt, "en", "") or getattr(rt, "ar", "") or str(rt)
                print(f"      - {title_str}: edu={getattr(t_req, 'education', '?')}, "
                      f"certs={getattr(t_req, 'certifications', [])}, "
                      f"yrs={getattr(t_req, 'min_years_experience', '?')}")
        else:
            print("    *** NOT POPULATED (empty) ***")
        # Also check scope_items for English translations
        si = getattr(ctx, "scope_items", [])
        print(f"  [DIAG] rfp_context.scope_items: {len(si)} items")
        for s_item in si[:3]:
            desc = getattr(s_item, "description", None)
            if desc:
                en_txt = getattr(desc, "en", "") or ""
                ar_txt = getattr(desc, "ar", "") or ""
                print(f"      en: {en_txt[:80]}")
                print(f"      ar: {ar_txt[:80]}")

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
    conformance_report = result.get("conformance_report")
    ext_evidence = result.get("external_evidence_pack")
    knowledge_graph = result.get("knowledge_graph")
    docx_path = result.get("report_docx_path")
    fallback_events = result.get("fallback_events", [])
    routing_report = result.get("routing_report", {})

    # Populate evidence KG counts for provenance reporting
    if knowledge_graph:
        evidence_kg_people = len(getattr(knowledge_graph, "people", []) or [])
        evidence_kg_projects = len(getattr(knowledge_graph, "projects", []) or [])
        evidence_kg_clients = len(getattr(knowledge_graph, "clients", []) or [])

    # Print routing report
    if routing_report:
        cls = routing_report.get("classification", {})
        print(f"\n  --- Routing Report ---")
        print(f"  Jurisdiction:     {cls.get('jurisdiction', 'unknown')}")
        print(f"  Sector:           {cls.get('sector', 'unknown')}")
        print(f"  Domain:           {cls.get('domain', '')}")
        print(f"  Client type:      {cls.get('client_type', '')}")
        print(f"  Confidence:       {routing_report.get('routing_confidence', 0):.2f}")
        print(f"  Selected packs:   {routing_report.get('selected_packs', [])}")
        print(f"  Fallback packs:   {routing_report.get('fallback_packs_used', [])}")
        warnings = routing_report.get("warnings", [])
        if warnings:
            for w in warnings:
                print(f"  ⚠ {w}")

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

    # 3. slide_blueprint_from_source_book.json — template-contract format
    blueprint_path = None
    blueprint_count = 0
    blueprint_violations: list[str] = []
    if source_book:
        from src.services.blueprint_transform import transform_to_contract_blueprint

        contract_entries, blueprint_violations = transform_to_contract_blueprint(
            source_book.slide_blueprints,
            team_profiles=list(source_book.why_strategic_gears.named_consultants),
        )
        bp_data = [e.model_dump(mode="json") for e in contract_entries]
        blueprint_count = len(bp_data)
        blueprint_path = str(output_dir / "slide_blueprint_from_source_book.json")
        Path(blueprint_path).write_text(
            json.dumps(bp_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  Slide blueprints: {blueprint_path} ({blueprint_count} entries)")
        if blueprint_violations:
            print(f"    Validator violations: {len(blueprint_violations)}")
            for v in blueprint_violations[:5]:
                print(f"      - {v}")

    # 4. conformance_report.json
    conformance_path = None
    conformance_status = "not_run"
    if conformance_report:
        cr_data = conformance_report.model_dump(mode="json")
        conformance_status = cr_data.get("conformance_status", "unknown")
        conformance_path = str(output_dir / "conformance_report.json")
        Path(conformance_path).write_text(
            json.dumps(cr_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  Conformance report: {conformance_path} (status={conformance_status})")

    # 5. external_evidence_pack.json
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

    # 6a. query_execution_log.json — real execution truth
    from src.agents.external_research.agent import _QUERY_EXECUTION_LOG
    exec_log_path = str(output_dir / "query_execution_log.json")
    Path(exec_log_path).write_text(
        json.dumps(_QUERY_EXECUTION_LOG, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Query execution log: {exec_log_path} ({len(_QUERY_EXECUTION_LOG)} entries)")

    # 6b. research_results_raw.json — raw results from S2 + Perplexity
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
    reviewer_passed = False
    reviewer_threshold_met = False
    competitive_viability = "unknown"

    if source_book:
        prose_parts = [
            # Section 1: RFP Interpretation
            source_book.rfp_interpretation.objective_and_scope,
            source_book.rfp_interpretation.constraints_and_compliance,
            source_book.rfp_interpretation.unstated_evaluator_priorities,
            source_book.rfp_interpretation.probable_scoring_logic,
            # Section 2: Client Problem Framing
            source_book.client_problem_framing.current_state_challenge,
            source_book.client_problem_framing.why_it_matters_now,
            source_book.client_problem_framing.transformation_logic,
            source_book.client_problem_framing.risk_if_unchanged,
            # Section 5: Proposed Solution
            source_book.proposed_solution.methodology_overview,
            source_book.proposed_solution.governance_framework,
            source_book.proposed_solution.timeline_logic,
            source_book.proposed_solution.value_case_and_differentiation,
        ]
        # Section 3: consultant profiles, project outcomes, capability descriptions
        for nc in source_book.why_strategic_gears.named_consultants:
            prose_parts.extend([nc.relevance, nc.justification])
        for pe in source_book.why_strategic_gears.project_experience:
            prose_parts.append(pe.outcomes)
        for cm in source_book.why_strategic_gears.capability_mapping:
            prose_parts.append(cm.sg_capability)
        # Section 3: certifications
        if source_book.why_strategic_gears.certifications_and_compliance:
            prose_parts.append(
                " ".join(source_book.why_strategic_gears.certifications_and_compliance)
            )
        # Section 4: external evidence
        if source_book.external_evidence.coverage_assessment:
            prose_parts.append(source_book.external_evidence.coverage_assessment)
        for ee in source_book.external_evidence.entries:
            prose_parts.extend([ee.relevance, ee.key_finding])
        # Section 5: phase activities and deliverables
        for phase in source_book.proposed_solution.phase_details:
            prose_parts.extend(phase.activities)
            prose_parts.extend(phase.deliverables)
            prose_parts.append(phase.governance)
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
        reviewer_threshold_met = source_book_review.pass_threshold_met
        reviewer_passed = reviewer_threshold_met
        competitive_viability = source_book_review.competitive_viability

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

    # Engine 1/Engine 2 name classification:
    # A "real" consultant name must be:
    # 1. Non-empty and not an open-role marker
    # 2. staffing_status == "recommended_candidate" (not open_role_profile)
    # 3. Actually exists in the KG (the Engine 1 guard ensures this)
    _OPEN_MARKERS = [
        "placeholder", "[", "tbd", "tbc", "name",
        "consultant 1", "consultant 2", "to be",
        "(open)", "open role", "يُحدَّد", "يحدد لاحقاً",
    ]

    def _is_real_name(name: str) -> bool:
        """A name is real only if non-empty and not an open-role marker."""
        stripped = name.strip()
        if not stripped:
            return False
        lower = stripped.lower()
        return not any(marker in lower for marker in _OPEN_MARKERS)

    # Only count names that survived the Engine 1 guard
    # (recommended_candidate with a non-empty name = KG-verified)
    real_names: list[str] = []
    placeholder_names: list[str] = []
    if source_book:
        for nc in source_book.why_strategic_gears.named_consultants:
            if (
                nc.staffing_status == "recommended_candidate"
                and _is_real_name(nc.name)
            ):
                real_names.append(nc.name)
            else:
                placeholder_names.append(nc.name or "(open)")

    # ── HARD FAIL checks ──
    failures: list[str] = []
    if index_status == "DEGRADED":
        failures.append(f"Indexing failed: {index_reason}")
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
    if source_book_review and not reviewer_threshold_met:
        failures.append(
            f"Reviewer threshold not met "
            f"(final score={review_score}/5, threshold_met={reviewer_threshold_met}, "
            f"viability={competitive_viability})"
        )
    if conformance_report and conformance_status == "fail":
        critical_count = sum(
            1 for f in conformance_report.missing_required_commitments
            if f.severity == "critical"
        )
        forbidden_count = len(conformance_report.forbidden_claims)
        failures.append(
            f"Conformance validation failed: {conformance_report.hard_requirements_failed} "
            f"requirements failed ({critical_count} critical, {forbidden_count} forbidden claims). "
            f"Decision: {conformance_report.final_acceptance_decision}"
        )
    elif conformance_report and conformance_status == "blocked":
        blocked_inputs = [
            mi.input_name for mi in conformance_report.missing_inputs
            if mi.severity == "critical" and mi.validation_scope == "source_book"
        ]
        failures.append(
            f"Conformance blocked by missing inputs: {', '.join(blocked_inputs) or 'unknown'}. "
            f"Decision: {conformance_report.final_acceptance_decision}"
        )

    if index_status == "DEGRADED" and not source_book:
        status = "FAILED"
    elif failures:
        status = "DEGRADED" if source_book else "FAILED"
    else:
        status = "SUCCESS"

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
    print(f"  Reviewer threshold met:          {reviewer_threshold_met}")
    print(f"  Reviewer passed:                 {reviewer_passed}")
    print(f"  Competitive viability:           {competitive_viability}")
    if source_book_review and source_book_review.rewrite_required:
        print(f"  Rewrite still required:          True")

    print("\n  --- Conformance ---")
    print(f"  Conformance status:              {conformance_status}")
    if conformance_report:
        print(f"  Requirements checked:            {conformance_report.hard_requirements_checked}")
        print(f"  Requirements passed:             {conformance_report.hard_requirements_passed}")
        print(f"  Requirements failed:             {conformance_report.hard_requirements_failed}")
        print(f"  Forbidden claims:                {len(conformance_report.forbidden_claims)}")
        print(f"  Missing inputs:                  {len(conformance_report.missing_inputs)}")
        print(f"  Final acceptance:                {conformance_report.final_acceptance_decision}")

    print("\n  --- Fallback Usage ---")
    if fallback_events:
        for fe in fallback_events:
            print(f"    Pass {fe['pass']}: {', '.join(fe['events'])}")
    else:
        print("    No fallbacks — all passes used primary path")

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
        ("Conformance Report JSON", conformance_path),
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

    # ── Provider Usage (D2) ──
    from src.services.perplexity import get_perplexity_usage
    from src.services.semantic_scholar import get_s2_usage

    perplexity_usage = get_perplexity_usage()
    s2_usage = get_s2_usage()

    # ── API Cost Summary ──
    cost_data = get_cost_summary()
    print("\n  --- API Cost ---")
    print(f"  Total LLM calls:                {cost_data['total_calls']}")
    print(f"  Total input tokens:             {cost_data['total_input_tokens']:,}")
    print(f"  Total output tokens:            {cost_data['total_output_tokens']:,}")
    print(f"  Total tokens:                   {cost_data['total_tokens']:,}")
    print(f"  Total cost (USD):               ${cost_data['total_cost_usd']:.4f}")
    print(f"  Total LLM latency:              {cost_data['total_latency_s']:.1f}s")
    if cost_data["by_model"]:
        print("\n  --- Cost by Model ---")
        for model_name, model_data in cost_data["by_model"].items():
            print(
                f"    {model_name}: {model_data['calls']} calls, "
                f"{model_data['input_tokens']:,} in / "
                f"{model_data['output_tokens']:,} out, "
                f"${model_data['cost_usd']:.4f}"
            )
    if cost_data["calls"]:
        print("\n  --- Per-Call Breakdown ---")
        for i, call in enumerate(cost_data["calls"], 1):
            print(
                f"    {i:2d}. {call['caller']:30s} "
                f"{call['model']:25s} "
                f"{call['input_tokens']:>7,} in / "
                f"{call['output_tokens']:>7,} out  "
                f"${call['cost_usd']:.4f}  "
                f"({call['latency_s']:.1f}s)"
            )

    print(f"\n{'=' * 80}")
    print(f"  FINAL STATUS: {status}")
    print(f"{'=' * 80}\n")

    return {
        "status": status,
        "index_status": index_status,
        "index_reason": index_reason,
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
        "reviewer_passed": reviewer_passed,
        "reviewer_final_score": review_score,
        "reviewer_threshold_met": reviewer_threshold_met,
        "competitive_viability": competitive_viability,
        "conformance_status": conformance_status,
        "conformance_decision": conformance_report.final_acceptance_decision if conformance_report else "not_run",
        "conformance_checked": conformance_report.hard_requirements_checked if conformance_report else 0,
        "conformance_passed": conformance_report.hard_requirements_passed if conformance_report else 0,
        "conformance_failed": conformance_report.hard_requirements_failed if conformance_report else 0,
        "conformance_forbidden_claims": len(conformance_report.forbidden_claims) if conformance_report else 0,
        "fallback_events": fallback_events,
        "routing_report": routing_report,
        "total_time": total_time,
        "docx_path": docx_path,
        "artifacts": {k: v for k, v in artifacts},
        "cost": cost_data,
        "provider_usage": {
            **cost_data.get("provider_breakdown", {}),
            "perplexity": perplexity_usage,
            "semantic_scholar": s2_usage,
        },
        # Evidence provenance
        "rfp_docs_path": docs_path,
        "rfp_cache_path": _cache_path,
        "evidence_docs_path": evidence_docs_path or "(not provided)",
        "evidence_cache_path": evidence_cache_path or "(not provided)",
        "evidence_cache_consistent": evidence_consistent if evidence_cache_path else None,
        "evidence_enabled": evidence_enabled,
        "evidence_manifest_doc_count": evidence_manifest_docs,
        "evidence_kg_people": evidence_kg_people,
        "evidence_kg_projects": evidence_kg_projects,
        "evidence_kg_clients": evidence_kg_clients,
    }


def _collect_research_query_log(ext_evidence) -> dict:
    """Build research query log from EXECUTION TRUTH, not retained source inference."""
    from src.agents.external_research.agent import _QUERY_EXECUTION_LOG, _QUERY_THEME_MAP

    log: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "queries_sent": [],
        "theme_coverage": {},
        "snippet_enrichment_status": "available_but_not_invoked",
        "author_enrichment_status": "available_but_not_invoked",
    }
    if not ext_evidence:
        return log

    queries = getattr(ext_evidence, "search_queries_used", [])
    sources = getattr(ext_evidence, "sources", [])
    query_service_map = getattr(ext_evidence, "query_service_map", {}) or {}

    # Build execution truth from the REAL execution log — not from retained sources
    # This records which services were ACTUALLY invoked per query
    exec_services_invoked: dict[str, set[str]] = {}
    for entry in _QUERY_EXECUTION_LOG:
        q = entry.get("query", "")
        svc = entry.get("service_invoked", "")
        if q and svc:
            exec_services_invoked.setdefault(q, set()).add(svc)

    # Count retained sources per query (for reporting, NOT for services_actual)
    retained_by_query: dict[str, int] = {}
    for src in sources:
        qused = getattr(src, "query_used", "")
        if qused:
            retained_by_query[qused] = retained_by_query.get(qused, 0) + 1

    # Build per-query entries
    theme_source_counts: dict[str, int] = {}
    for q in queries:
        theme = _QUERY_THEME_MAP.get(q, "unclassified")

        # services_requested from the query_service_map (set at generation time)
        services_requested = query_service_map.get(q, [])
        if not services_requested:
            services_requested = ["unknown"]

        # services_actual from EXECUTION LOG TRUTH — not from retained source attribution
        services_actual = sorted(exec_services_invoked.get(q, set()))

        # retained_sources_count from actual retained sources
        retained = retained_by_query.get(q, 0)
        theme_source_counts[theme] = theme_source_counts.get(theme, 0) + retained

        log["queries_sent"].append({
            "query": q,
            "query_theme": theme,
            "services_requested": services_requested,
            "services_actual": services_actual,
            "retained_sources_count": retained,
        })

    # Build theme coverage — include all themes from both Perplexity and S2
    _ALL_THEMES = [
        "needs_assessment", "service_portfolio_design", "institutional_framework",
        "strategic_support", "methodology", "institutional_model", "evaluation",
        "analogical_domain", "pack_curated", "local_public_context",
    ]
    for theme in _ALL_THEMES:
        count = theme_source_counts.get(theme, 0)
        if count >= 3:
            status = "covered"
        elif count >= 1:
            status = "weak"
        else:
            status = "gap"
        log["theme_coverage"][theme] = {
            "retained_sources": count,
            "status": status,
        }

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
            # Use the ACTUAL provider field, not inference from source_type
            provider = getattr(src, "provider", "")
            if provider == "semantic_scholar":
                results["semantic_scholar_results"].append(entry)
            elif provider == "perplexity":
                results["perplexity_results"].append(entry)
            else:
                # Fallback: unknown provider
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
        help="Path to RFP input documents (RFP only)",
    )
    parser.add_argument(
        "--evidence-docs-path", default=None,
        help="Path to internal evidence corpus (original files). "
             "Used for full-document loading after retrieval.",
    )
    parser.add_argument(
        "--evidence-cache-path", default=None,
        help="Path to pre-built internal evidence index (embeddings, KG). "
             "Used for retrieval search and knowledge graph loading.",
    )
    parser.add_argument(
        "--max-summary-chars",
        type=int,
        default=12_000,
        help="Max chars to include in extracted ai_assist_summary",
    )
    args = parser.parse_args()

    result = asyncio.run(
        run_source_book_only(
            args.language,
            args.docs_path,
            max_summary_chars=args.max_summary_chars,
            evidence_docs_path=args.evidence_docs_path,
            evidence_cache_path=args.evidence_cache_path,
        ),
    )

    # Write result JSON
    out = Path(f"source_book_only_{args.language}_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str, ensure_ascii=False)
    print(f"Results written to: {out}")
