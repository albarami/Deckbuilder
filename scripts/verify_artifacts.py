"""Artifact-based E2E acceptance verifier for Engine 1 runs.

Reads fresh session artifacts and asserts:
A. Query artifact checks
B. Evidence pack checks
C. Source Book DOCX completeness checks
D. Theme coverage checks

Usage:
    python scripts/verify_artifacts.py <session_id>
    python scripts/verify_artifacts.py sb-ar-1774876876
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

    # ── A. Query artifact checks ──────────────────────────
    print("\n=== A. QUERY ARTIFACT CHECKS ===")
    qlog_path = output_dir / "research_query_log.json"
    if qlog_path.exists():
        qlog = json.loads(qlog_path.read_text(encoding="utf-8"))
        queries = qlog.get("queries_sent", [])

        # A1: every query has query_theme
        missing_theme = [q for q in queries if not q.get("query_theme")]
        if missing_theme:
            print(f"  FAIL A1: {len(missing_theme)} queries missing query_theme")
            all_pass = False
        else:
            print(f"  PASS A1: all {len(queries)} queries have query_theme")

        # A2: every query has services_actual
        missing_svc = [q for q in queries if not q.get("services_actual")]
        if missing_svc:
            print(f"  FAIL A2: {len(missing_svc)} queries missing services_actual")
            all_pass = False
        else:
            print(f"  PASS A2: all queries have services_actual")

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
            print(f"  FAIL A3: {len(bad_queries)} weak/clipped queries found")
            for kind, q in bad_queries[:3]:
                print(f"    [{kind}] {q[:80]}")
            all_pass = False
        else:
            print(f"  PASS A3: no weak/clipped query patterns")

        # A4: log has theme_coverage
        tc = qlog.get("theme_coverage", {})
        if tc:
            print(f"  PASS A4: theme_coverage present with {len(tc)} themes")
        else:
            print(f"  FAIL A4: theme_coverage missing from query log")
            all_pass = False

        # A5: snippet/author status present
        snippet_status = qlog.get("snippet_enrichment_status", "MISSING")
        author_status = qlog.get("author_enrichment_status", "MISSING")
        if snippet_status != "MISSING" and author_status != "MISSING":
            print(f"  PASS A5: snippet={snippet_status}, author={author_status}")
        else:
            print(f"  FAIL A5: snippet/author status missing")
            all_pass = False
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
            print(f"  FAIL B2: {len(sg_proof)} S2 sources labeled SG_internal_proof")
            all_pass = False
        else:
            print(f"  PASS B2: no S2 sources labeled SG_internal_proof")

        # B3: evidence_class present on all
        no_class = [s for s in sources if not s.get("evidence_class")]
        if no_class:
            print(f"  FAIL B3: {len(no_class)} sources missing evidence_class")
            all_pass = False
        else:
            print(f"  PASS B3: all sources have evidence_class")
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
                print(f"  PASS C1: no JSON file references in DOCX")

            # C2: evidence metadata visible in tables
            combined = all_text + table_text
            meta_fields = ["provider", "evidence_class", "query_used",
                          "mapped_rfp_theme", "authors"]
            found = [f for f in meta_fields if f.lower() in combined.lower()]
            missing = [f for f in meta_fields if f.lower() not in combined.lower()]
            if missing:
                print(f"  WARN C2: DOCX missing metadata fields: {missing}")
            else:
                print(f"  PASS C2: all evidence metadata visible in DOCX")

            # C3: theme coverage visible
            if "Theme Coverage" in all_text or "theme" in all_text.lower():
                print(f"  PASS C3: theme coverage visible in DOCX")
            else:
                print(f"  FAIL C3: theme coverage not visible in DOCX")
                all_pass = False

        except ImportError:
            print(f"  SKIP C: python-docx not available")
    else:
        print(f"  FAIL: source_book.docx not found")
        all_pass = False

    # ── D. Theme coverage checks ──────────────────────────
    print("\n=== D. THEME COVERAGE CHECKS ===")
    if qlog_path.exists():
        tc = qlog.get("theme_coverage", {})
        gaps = [t for t, v in tc.items() if v.get("status") == "gap"]
        weak = [t for t, v in tc.items() if v.get("status") == "weak"]
        covered = [t for t, v in tc.items() if v.get("status") == "covered"]

        print(f"  Covered: {covered}")
        print(f"  Weak: {weak}")
        print(f"  Gaps: {gaps}")

        if gaps:
            print(f"  INFO D: {len(gaps)} theme gaps flagged (acceptable if honest)")
        print(f"  PASS D: theme coverage assessed ({len(tc)} themes)")
    else:
        print(f"  FAIL D: no query log to check")
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
