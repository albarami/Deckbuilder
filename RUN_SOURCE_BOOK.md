# Run Source Book Pipeline

This runner is generic and dynamic for any RFP. It is not tied to any client, proposal, BoQ, PDF, or validation dataset.

The runtime model is:

- `--docs-path` = folder containing the current RFP documents.
- `--evidence-docs-path` = folder containing the internal evidence corpus.
- `--evidence-cache-path` = folder containing the matching prebuilt evidence index/cache.

The RFP folder can contain any supported RFP documents. To run a different RFP, change only the RFP folder passed to `--docs-path` or `-RfpPath`.

## 1. Clone

```powershell
git clone https://github.com/albarami/Deckbuilder.git
cd Deckbuilder
git fetch origin
git checkout claude/sourcebook-runnable-generic
```

## 2. Python setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Alternative with `uv`:

```powershell
uv venv --python 3.12
.\.venv\Scripts\activate
uv pip install -r requirements.txt
```

## 3. Environment setup

Copy the example environment file and fill in your own keys:

```powershell
Copy-Item .env.example .env
```

Never commit `.env`. It must contain only your local runtime secrets and configuration.

## 4. Folder setup

You must provide these runtime assets locally:

- `.env` with your API keys and local configuration.
- An RFP folder containing the current RFP documents.
- An internal evidence corpus folder supplied separately.
- A matching prebuilt evidence cache/index folder.

Suggested local layout:

```text
sample_rfps/
  my_rfp/
    <place current RFP files here>
evidence_corpus/
  <place internal evidence files here>
state/index/
  embeddings.npy
  chunks.json
  manifest.json
  knowledge_graph.json
```

The evidence cache must match the evidence corpus. If the cache was built from a different corpus, evidence mode may be disabled or produce invalid retrieval results.

Private evidence files and index/cache files may be confidential. Do not commit private PDFs, DOCX, PPTX, XLSX, `.env`, generated outputs, or real `state/index` cache files to the public repository.

## 5. Run Source Book only

Use the helper script:

```powershell
.\scripts\run_source_book.ps1 `
  -RfpPath "sample_rfps\my_rfp" `
  -EvidenceDocsPath "evidence_corpus" `
  -EvidenceCachePath "state/index" `
  -Language ar
```

Equivalent direct command for `cmd.exe`:

```cmd
python scripts/source_book_only.py ^
  --language ar ^
  --docs-path "<RFP_FOLDER>" ^
  --evidence-docs-path "<INTERNAL_EVIDENCE_FOLDER>" ^
  --evidence-cache-path "<EVIDENCE_CACHE_FOLDER>" ^
  --max-summary-chars 12000
```

Example only for `cmd.exe`:

```cmd
python scripts/source_book_only.py ^
  --language ar ^
  --docs-path sample_rfps/my_rfp ^
  --evidence-docs-path ".\evidence_corpus" ^
  --evidence-cache-path state/index ^
  --max-summary-chars 12000
```

## 6. Expected output

Each run writes generated artifacts under:

```text
output/sb-ar-XXXXXXXXXX/
```

Expected artifacts include:

- `source_book.docx`
- `conformance_report.json`
- `evidence_ledger.json`
- `claim_registry.json`
- `routing_report.json`
- `evidence_coverage_report.json`
- `gate_decision.json`
- `slide_blueprint_from_source_book.json`
- `external_evidence_pack.json`
- `query_execution_log.json`
- `research_query_log.json`
- `research_results_raw.json`

Generated outputs are local artifacts and must not be committed.

## 7. Scope of this runner

This runner is Source Book only.

It does not:

- Generate a deck.
- Render slides.
- Create PPTX files.

It stops before deck assembly, slide rendering, and PPTX generation.

## 8. Validation

After setup, you can run the boundary/export tests without running the Source Book pipeline:

```powershell
python -m pytest tests/agents/test_engine1_engine2_boundary.py tests/services/test_engine2_pattern_and_export.py -q
```

Expected result:

```text
37 passed
```
