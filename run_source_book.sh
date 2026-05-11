#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  DeckForge — Source Book Pipeline Runner
#  Branch: claude/claim-provenance-on-source-base
# ─────────────────────────────────────────────────────────────
#
#  SETUP (one-time):
#    git clone https://github.com/albarami/Deckbuilder.git
#    cd Deckbuilder
#    git checkout claude/claim-provenance-on-source-base
#    python -m venv .venv
#    source .venv/bin/activate        # Linux/Mac
#    pip install -r requirements.txt
#
#    # Create .env with your API keys:
#    cat > .env << 'ENVEOF'
#    OPENAI_API_KEY=sk-YOUR_KEY
#    ANTHROPIC_API_KEY=sk-ant-YOUR_KEY
#    PERPLEXITY_API_KEY=pplx-YOUR_KEY
#    LOG_LEVEL=INFO
#    ENVEOF
#
#  USAGE:
#    # Put your RFP PDF(s) in a folder, then run:
#    ./run_source_book.sh ar path/to/rfp_folder
#    ./run_source_book.sh ar path/to/rfp_folder path/to/evidence_corpus
#    ./run_source_book.sh en path/to/rfp_folder
#
#  EXAMPLES:
#    ./run_source_book.sh ar data_sdaia_unesco
#    ./run_source_book.sh ar data_sdaia_unesco "data test"
#
#  OUTPUT:
#    output/sb-{lang}-{session_id}/
#      source_book.docx                  — the Source Book
#      evidence_ledger.json              — claim evidence tracking
#      slide_blueprint_from_source_book.json — 30+ slide designs
#      conformance_report.json           — hard requirement validation
#      claim_registry.json               — claim provenance registry
#      external_evidence_pack.json       — S2 + Perplexity research
#      routing_report.json               — domain/pack classification
#      evidence_coverage_report.json     — methodology coverage
#      gate_decision.json                — acceptance gate result
#
#  NOTES:
#    - Pipeline takes ~60-120 min, costs ~$10-28 per run (mostly Claude Opus)
#    - RFP PDF can be scanned (OCR fallback built in) or text-based
#    - PERPLEXITY_API_KEY is optional but gives richer web evidence
#    - No Azure keys needed for local Source Book runs
#    - Does NOT generate a deck/PPTX — Source Book only
# ─────────────────────────────────────────────────────────────

set -euo pipefail

LANG="${1:-ar}"
DOCS_PATH="${2:-}"
EVIDENCE_PATH="${3:-}"

if [ -z "$DOCS_PATH" ]; then
    echo "Usage: ./run_source_book.sh <ar|en> <rfp_docs_path> [evidence_docs_path]"
    echo ""
    echo "Examples:"
    echo "  ./run_source_book.sh ar data_sdaia_unesco"
    echo "  ./run_source_book.sh ar data_sdaia_unesco \"data test\""
    exit 1
fi

CMD="python scripts/source_book_only.py --language $LANG --docs-path \"$DOCS_PATH\""

if [ -n "$EVIDENCE_PATH" ]; then
    CMD="$CMD --evidence-docs-path \"$EVIDENCE_PATH\""
fi

echo "Running: $CMD"
eval "$CMD"
