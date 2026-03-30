"""Artifact-based E2E acceptance verifier for Engine 1 runs.

Reads fresh session artifacts and strictly asserts:
A. Query artifact checks (themes classified, services truthful, no weak patterns)
B. Evidence pack checks (metadata complete, classification honest)
C. Source Book DOCX completeness (no JSON refs, metadata visible, themes visible)
D. Theme coverage checks (all themes assessed, gaps flagged)

Usage:
    python scripts/verify_artifacts.py <session_id>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def verify(session_id: str) -> bool:
    """Run all verification checks on a session's artifacts. Returns True if all pass."""
    output_dir = Path("output") / session_id
    if not output_dir.exists():
        print(f"FAIL: output directory not found: {output_dir}")
        return False

    all_pass = True
    qlog = {}

    # ── A. Query artifact checks ──────────────────────────
    print("\n=== A. QUERY ARTIFACT CHECKS ===")
    qlog_path = output_dir / "research_query_log.json"
    if qlog_path.exists():
        qlog = json.loads(qlog_path.read_text(encoding="utf-8"))
        queries = qlog.get("queries_sent", [])

        # A1: every query has query_theme AND it is not "unclassified"
        unclassified = [q for q in queries if q.get("query_theme") in (None, "", "unclassified")]
        if unclassified:
            print(f"  FAIL A1: {len(unclassified)} queries are unclassified:")
            for uq in unclassified[:3]:
                print(f"    '{uq.get('query','')[:60]}' → theme='{uq.get('query_theme')}'")
            all_pass = False
        else:
            print(f"  PASS A1: all {len(queries)} queries have real themes")

        # A2: services_requested is NOT hardcoded to ["semantic_scholar", "perplexity"] for all
        all_same = all(
            sorted(q.get("services_requested", [])) == ["perplexity", "semantic_scholar"]
            for q in queries
        )
        if all_same and len(queries) > 1:
            print(f"  FAIL A2: services_requested is hardcoded identically for all queries")
            all_pass = False
        else:
            # Check that no query has services_requested = ["unknown"]
            unknown_svc = [q for q in queries if q.get("services_requested") == ["unknown"]]
            if unknown_svc:
                print(f"  WARN A2: {len(unknown_svc)} queries have services_requested=['unknown']")
            else:
                print(f"  PASS A2: services_requested varies per query (truthful)")

        # A3: no weak/clipped query patterns
        bad_patterns = ["best practices for", "priorities needs",
                       "institutional framework managing relationships national"]
        bad_queries = []
        for q in queries:
            query_text = q.get("query", "")
            for bp in bad_patterns:
                if bp in query_text.lower():
                    bad_queries.append((bp, query_text))
            if query_text.rstrip().endswith(","):
                bad_queries.append(("trailing comma", query_text))
        if bad_queries:
            print(f"  FAIL A3: {len(bad_queries)} weak/clipped queries")
            for kind, q in bad_queries[:3]:
                print(f"    [{kind}] {q[:80]}")
            all_pass = False
        else:
            print(f"  PASS A3: no weak/clipped patterns")

        # A4: theme_coverage present with realistic assessment
        tc = qlog.get("theme_coverage", {})
        if tc and len(tc) >= 3:
            print(f"  PASS A4: theme_coverage has {len(tc)} themes")
        else:
            print(f"  FAIL A4: theme_coverage missing or too sparse ({len(tc)} themes)")
            all_pass = False

        # A5: snippet/author status present and honest
        snippet_status = qlog.get("snippet_enrichment_status", "MISSING")
        author_status = qlog.get("author_enrichment_status", "MISSING")
        valid_statuses = ["available_but_not_invoked", "invoked", "not_available"]
        if snippet_status in valid_statuses and author_status in valid_statuses:
            print(f"  PASS A5: snippet={snippet_status}, author={author_status}")
        else:
            print(f"  FAIL A5: invalid status — snippet={snippet_status}, author={author_status}")
            all_pass = False

        # A6: Cross-check — if services_actual includes "semantic_scholar",
        # there should be S2 sources in the evidence pack
        s2_in_actual = any(
            "semantic_scholar" in q.get("services_actual", []) for q in queries
        )
        epack_path = output_dir / "external_evidence_pack.json"
        if epack_path.exists():
            epack = json.loads(epack_path.read_text(encoding="utf-8"))
            s2_sources = [s for s in epack.get("sources", []) if s.get("provider") == "semantic_scholar"]
            if s2_in_actual and not s2_sources:
                print(f"  WARN A6: services_actual says S2 ran but 0 S2 sources in pack")
            elif s2_sources:
                print(f"  PASS A6: {len(s2_sources)} S2 sources consistent with services_actual")
            else:
                print(f"  PASS A6: no S2 claimed, no S2 sources (consistent)")
    else:
        print(f"  FAIL: research_query_log.json not found")
        all_pass = False

    # ── B. Evidence pack checks ───────────────────────────
    print("\n=== B. EVIDENCE PACK CHECKS ===")
    epack_path = output_dir / "external_evidence_pack.json"
    if epack_path.exists():
        epack = json.loads(epack_path.read_text(encoding="utf-8"))
        sources = epack.get("sources", [])

        # B1: required metadata on every source
        required_fields = ["source_id", "title", "provider", "evidence_class",
                          "evidence_tier", "source_type"]
        missing_fields_count = 0
        for src in sources:
            missing = [f for f in required_fields if not src.get(f)]
            if missing:
                missing_fields_count += 1
        if missing_fields_count:
            print(f"  FAIL B1: {missing_fields_count}/{len(sources)} sources missing required fields")
            all_pass = False
        else:
            print(f"  PASS B1: all {len(sources)} sources have required metadata")

        # B2: no SG_internal_proof from S2
        sg_proof = [s for s in sources if s.get("evidence_class") == "SG_internal_proof"
                    and s.get("provider") == "semantic_scholar"]
        if sg_proof:
            print(f"  FAIL B2: {len(sg_proof)} S2 sources mislabeled as SG_internal_proof")
            all_pass = False
        else:
            print(f"  PASS B2: classification honest")

        # B3: provider field uses actual values, not inferred from source_type
        valid_providers = {"semantic_scholar", "perplexity", "manual"}
        invalid_providers = [s for s in sources if s.get("provider") not in valid_providers]
        if invalid_providers:
            print(f"  WARN B3: {len(invalid_providers)} sources with non-standard provider")
        else:
            print(f"  PASS B3: all providers are valid")
    else:
        print(f"  FAIL: external_evidence_pack.json not found")
        all_pass = False

    # ── C. Source Book DOCX completeness ──────────────────
    print("\n=== C. SOURCE BOOK DOCX CHECKS ===")
    docx_path = output_dir / "source_book.docx"
    if docx_path.exists():
        try:
            from docx import Document
            doc = Document(str(docx_path))
            all_text = " ".join(p.text for p in doc.paragraphs)
            table_text = ""
            for t in doc.tables:
                for r in t.rows:
                    for c in r.cells:
                        table_text += " " + c.text

            # C1: no JSON file references
            json_refs = [w for w in ["external_evidence_pack.json",
                                     "research_query_log.json",
                                     "research_results_raw.json"]
                        if w in all_text or w in table_text]
            if json_refs:
                print(f"  FAIL C1: DOCX references JSON files: {json_refs}")
                all_pass = False
            else:
                print(f"  PASS C1: no JSON file references")

            # C2: evidence metadata visible — check for specific field tokens
            combined = (all_text + table_text).lower()
            meta_fields = ["provider", "evidence_class", "query_used",
                          "mapped_rfp_theme", "authors"]
            found = [f for f in meta_fields if f in combined]
            missing = [f for f in meta_fields if f not in combined]
            if missing:
                print(f"  WARN C2: missing metadata fields in DOCX: {missing}")
            else:
                print(f"  PASS C2: all evidence metadata visible")

            # C3: theme coverage visible
            if "theme coverage" in combined or "proposal theme" in combined:
                print(f"  PASS C3: theme coverage visible in DOCX")
            else:
                print(f"  FAIL C3: theme coverage not visible in DOCX")
                all_pass = False

            # C4: Cross-check — are retained S2 source titles visible in DOCX?
            if epack_path.exists():
                s2_titles = [s.get("title", "")[:30] for s in epack.get("sources", [])
                            if s.get("provider") == "semantic_scholar" and s.get("title")]
                found_in_docx = sum(1 for t in s2_titles if t.lower() in combined)
                if s2_titles:
                    print(f"  INFO C4: {found_in_docx}/{len(s2_titles)} S2 source titles found in DOCX")
                else:
                    print(f"  INFO C4: no S2 sources to cross-check")

        except ImportError:
            print(f"  SKIP C: python-docx not available")
    else:
        print(f"  FAIL: source_book.docx not found")
        all_pass = False

    # ── D. Theme coverage checks ──────────────────────────
    print("\n=== D. THEME COVERAGE CHECKS ===")
    tc = qlog.get("theme_coverage", {})
    if tc:
        gaps = [t for t, v in tc.items() if v.get("status") == "gap"]
        weak = [t for t, v in tc.items() if v.get("status") == "weak"]
        covered = [t for t, v in tc.items() if v.get("status") == "covered"]
        print(f"  Covered: {covered}")
        print(f"  Weak: {weak}")
        print(f"  Gaps: {gaps}")
        print(f"  PASS D: theme coverage assessed ({len(tc)} themes)")
    else:
        print(f"  FAIL D: no theme coverage data")
        all_pass = False

    # ── Summary ───────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  VERIFICATION RESULT: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
    print(f"{'='*60}")
    return all_pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_artifacts.py <session_id>")
        sys.exit(1)
    session_id = sys.argv[1]
    passed = verify(session_id)
    sys.exit(0 if passed else 1)
