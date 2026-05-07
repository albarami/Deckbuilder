param(
  [Parameter(Mandatory=$true)]
  [string]$RfpPath,

  [Parameter(Mandatory=$true)]
  [string]$EvidenceDocsPath,

  [string]$EvidenceCachePath = "state/index",

  [string]$Language = "ar",

  [int]$MaxSummaryChars = 12000
)

$env:PYTHONIOENCODING="utf-8"

python scripts/source_book_only.py `
  --language $Language `
  --docs-path $RfpPath `
  --evidence-docs-path $EvidenceDocsPath `
  --evidence-cache-path $EvidenceCachePath `
  --max-summary-chars $MaxSummaryChars
