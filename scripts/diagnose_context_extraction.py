"""
Diagnose context_agent RFP extraction in isolation.

Runs ONLY the context_agent on the RFP — no retrieval, no Source Book,
no LLM calls beyond the single context-extraction call. Prints the full
RFPContext output with explicit per-field null/populated/empty status,
plus the LLM-reported `gaps` array.

Cost: ~$0.10, time: ~30s-2min.

Usage:
    python scripts/diagnose_context_extraction.py --docs-path sample_rfps/my_rfp
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv  # noqa: E402

from src.services.key_audit import print_key_diagnostic  # noqa: E402

print_key_diagnostic()
load_dotenv(override=True)


def _field_status(value) -> str:
    """Return a compact status label for a field value."""
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return f"populated ({len(value)} chars)" if value else "EMPTY STRING"
    if isinstance(value, list):
        return f"populated ({len(value)} items)" if value else "EMPTY LIST"
    if isinstance(value, dict):
        if not value:
            return "EMPTY DICT"
        # For bilingual {en, ar}:
        if "en" in value or "ar" in value:
            en = value.get("en") or ""
            ar = value.get("ar") or ""
            parts = []
            if en:
                parts.append(f"en={len(en)} chars")
            else:
                parts.append("en=NULL/empty")
            if ar:
                parts.append(f"ar={len(ar)} chars")
            else:
                parts.append("ar=NULL/empty")
            return f"populated ({', '.join(parts)})"
        return f"populated (dict, {len(value)} keys)"
    return f"populated ({type(value).__name__})"


def _show_value(value, max_chars=200) -> str:
    s = str(value)
    return s[:max_chars] + ("..." if len(s) > max_chars else "")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-path", required=True)
    parser.add_argument("--max-summary-chars", type=int, default=12_000)
    parser.add_argument(
        "--language", choices=["ar", "en"], default="ar",
        help="Language hint for UploadedDocument (default: ar)",
    )
    args = parser.parse_args()

    print("=" * 78)
    print("  CONTEXT AGENT EXTRACTION DIAGNOSTIC")
    print(f"  --docs-path: {args.docs_path}")
    print(f"  --max-summary-chars: {args.max_summary_chars}")
    print("=" * 78)

    # ── Extract RFP text ──
    from src.utils.extractors import extract_directory

    docs = extract_directory(args.docs_path)
    if not docs:
        print(f"[ERROR] No documents in {args.docs_path}")
        return 1

    print(f"\n[1/4] Extracted {len(docs)} document(s) from {args.docs_path}:")
    for d in docs:
        text_len = len(d.full_text or "")
        print(f"  - {d.filename}: {text_len:,} chars (~{text_len // 4:,} tokens)")

    # ── Build inputs in the same shape source_book_only.py uses ──
    from src.models.state import DeckForgeState, SessionMetadata, UploadedDocument
    from src.models.enums import RendererMode

    summary_parts = []
    uploaded_documents = []
    for d in docs:
        text = (d.full_text or "").strip()
        if not text:
            continue
        uploaded_documents.append(
            UploadedDocument(filename=d.filename, content_text=text, language=args.language)
        )
        summary_parts.append(f"[{d.filename}]\n{text[:args.max_summary_chars]}")

    ai_summary = "\n\n".join(summary_parts)[: args.max_summary_chars]

    print(f"\n[2/4] Built inputs for context_agent:")
    print(f"  ai_assist_summary: {len(ai_summary):,} chars")
    print(f"  uploaded_documents: {len(uploaded_documents)} doc(s), "
          f"total {sum(len(u.content_text) for u in uploaded_documents):,} chars of content_text")

    state = DeckForgeState(
        ai_assist_summary=ai_summary,
        uploaded_documents=uploaded_documents,
        output_language=args.language,
        renderer_mode=RendererMode.TEMPLATE_V2,
        session=SessionMetadata(session_id="diagnose-context"),
    )

    # ── Run JUST the context_agent ──
    from src.services.llm import get_cost_summary, reset_cost_tracker
    from src.agents.context import agent as context_agent

    reset_cost_tracker()

    print(f"\n[3/4] Running context_agent.run() — single LLM call...")
    t0 = time.time()
    result_state = await context_agent.run(state)
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s")

    if result_state.last_error:
        print(f"\n[ERROR] context_agent failed: {result_state.last_error.error_type}")
        print(f"  Message: {result_state.last_error.message}")
        return 1

    rfp = result_state.rfp_context
    if rfp is None:
        print("\n[ERROR] context_agent returned without populating rfp_context")
        return 1

    # ── Per-field status report ──
    print(f"\n[4/4] RFPContext field-by-field status")
    print("=" * 78)

    field_names = [
        "rfp_name", "issuing_entity", "procurement_platform", "mandate",
        "scope_items", "deliverables", "evaluation_criteria",
        "compliance_requirements", "key_dates", "submission_format",
        "project_timeline", "team_requirements",
    ]

    for fname in field_names:
        value = getattr(rfp, fname, "ATTR_MISSING")
        if value == "ATTR_MISSING":
            print(f"  ✗ {fname}: ATTRIBUTE NOT PRESENT IN MODEL")
            continue
        status = _field_status(value)
        is_empty = status in {"NULL", "EMPTY STRING", "EMPTY LIST", "EMPTY DICT"}
        marker = "✗" if is_empty else "✓"
        print(f"  {marker} {fname:30s} → {status}")
        # Show actual content for top critical fields
        if fname in {"rfp_name", "mandate", "issuing_entity"} and value:
            if hasattr(value, "model_dump"):
                v_dict = value.model_dump()
            elif isinstance(value, dict):
                v_dict = value
            else:
                v_dict = {"value": value}
            for k, v in v_dict.items():
                print(f"      .{k}: {_show_value(v)}")

    print()
    print("─" * 78)

    # Gaps array (per prompt rule #1)
    gaps = getattr(rfp, "gaps", None)
    if gaps:
        print(f"\n  LLM-reported gaps ({len(gaps)} items):")
        for g in gaps[:20]:
            print(f"    - {_show_value(g, 250)}")
        if len(gaps) > 20:
            print(f"    ... ({len(gaps) - 20} more)")
    else:
        print("\n  LLM reported NO gaps (or `gaps` field absent from model).")

    # ── Cost summary ──
    cost = get_cost_summary()
    print()
    print("=" * 78)
    print(f"  Total LLM cost:     ${cost.get('total_cost_usd', 0):.4f}")
    print(f"  Total LLM calls:    {cost.get('total_calls', 0)}")
    print(f"  Total input tokens: {cost.get('total_input_tokens', 0):,}")
    print(f"  Total output tokens:{cost.get('total_output_tokens', 0):,}")
    print(f"  Wall time:          {elapsed:.1f}s")
    print("=" * 78)

    # Save full dump for follow-up
    out_path = project_root / "diagnose_context_result.json"
    try:
        dump = rfp.model_dump() if hasattr(rfp, "model_dump") else dict(rfp)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2, default=str, ensure_ascii=False)
        print(f"\nFull RFPContext dumped to: {out_path}")
    except Exception as e:
        print(f"\n[WARN] Could not dump rfp_context to disk: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
