# ─────────────────────────────────────────────────────────────
#  DeckForge — Source Book Pipeline Runner (Windows)
#  Branch: claude/claim-provenance-on-source-base
# ─────────────────────────────────────────────────────────────
#
#  SETUP (one-time):
#    git clone https://github.com/albarami/Deckbuilder.git
#    cd Deckbuilder
#    git checkout claude/claim-provenance-on-source-base
#    python -m venv .venv
#    .venv\Scripts\Activate.ps1
#    pip install -r requirements.txt
#
#    # Create .env with your API keys:
#    @"
#    OPENAI_API_KEY=sk-YOUR_KEY
#    ANTHROPIC_API_KEY=sk-ant-YOUR_KEY
#    PERPLEXITY_API_KEY=pplx-YOUR_KEY
#    LOG_LEVEL=INFO
#    "@ | Set-Content .env -Encoding utf8
#
#  USAGE:
#    .\run_source_book.ps1 -Lang ar -DocsPath path\to\rfp_folder
#    .\run_source_book.ps1 -Lang ar -DocsPath path\to\rfp_folder -EvidencePath "path\to\evidence"
#
#  EXAMPLES:
#    .\run_source_book.ps1 -Lang ar -DocsPath data_sdaia_unesco
#    .\run_source_book.ps1 -Lang ar -DocsPath data_sdaia_unesco -EvidencePath "C:\Projects\Deckbuilder\data test"
#
# ─────────────────────────────────────────────────────────────

param(
    [ValidateSet("ar","en")]
    [string]$Lang = "ar",

    [Parameter(Mandatory=$true)]
    [string]$DocsPath,

    [string]$EvidencePath = ""
)

$args_list = @("scripts/source_book_only.py", "--language", $Lang, "--docs-path", $DocsPath)

if ($EvidencePath -ne "") {
    $args_list += @("--evidence-docs-path", $EvidencePath)
}

Write-Host "Running: python $($args_list -join ' ')" -ForegroundColor Cyan
& python @args_list
