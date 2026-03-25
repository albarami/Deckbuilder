# Codebase Cleanup & Consolidation Inventory

> **Generated**: 2026-03-26
> **Branch**: `claude/agitated-williamson` (reviewed branch)
> **Purpose**: Honest audit of what exists on this branch today.

---

# Section A: Current Reality (claude/agitated-williamson)

## 1. Branch State

| Property | Value |
|---|---|
| **Branch** | `claude/agitated-williamson` |
| **Working directory** | `c:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson` |
| **Upstream** | `origin/claude/agitated-williamson` |

### What this branch HAS

- **Real Source Book pipeline**: `evidence_curation_node`, `proposal_strategy_node`, `source_book_node`, `blueprint_extraction_node` in `graph.py`
- **Real Source Book Writer agent** (`src/agents/source_book/writer.py`) — calls LLM, produces `SourceBook` object
- **Real Source Book Reviewer agent** (`src/agents/source_book/reviewer.py`) — per-section scoring, red-team critique
- **Real Source Book orchestrator** (`src/agents/source_book/orchestrator.py`) — Writer→Reviewer loop (up to 5 passes)
- **Real Source Book evidence extractor** (`src/agents/source_book/evidence_extractor.py`)
- **Real `SourceBook` model** (`src/models/source_book.py`) — 7-section schema with evidence ledger
- **Real Source Book DOCX exporter** (`src/services/source_book_export.py`) — python-docx, structured output
- **Proposal strategy agent** (`src/agents/proposal_strategy/agent.py`) — win themes, evaluator priorities
- **External research agent** (`src/agents/external_research/agent.py`) — S2 + Perplexity integration
- **Template contract** (`src/models/template_contract.py`, `src/services/template_validator.py`)
- **SlideBlueprint** + `SlideBlueprintEntry` model (`src/models/slide_blueprint.py`)
- **ProposalManifest** + `HouseInclusionPolicy` model (`src/models/proposal_manifest.py`)
- **Template-locked structure agent** (`src/agents/slide_architect/structure/`)
- **Iterative builder** (draft → review → refine → final_review → presentation)
- **Renderer v2** (manifest-driven, template-locked)
- **Semantic Scholar client** with search + recommendations
- **Embedding-based search/retrieval**
- **Frontend Source Book awareness** — gate 3 review, export, progress tracking
- **Source Book-only runner** using the REAL pipeline path

---

## 2. Pipeline Nodes (`src/pipeline/graph.py`)

| Node | Exists? | Line | What it does |
|---|---|---|---|
| `context_node` | Yes | | Parses RFP intake into `RFPContext` |
| `gate_1_node` | Yes | | User reviews RFP context |
| `retrieval_node` | Yes | | Planner → Search → Ranker chain |
| `gate_2_node` | Yes | | User reviews retrieved sources |
| `evidence_curation_node` | **Yes** | 483 | Analysis + external evidence curation |
| `proposal_strategy_node` | **Yes** | 558 | Win themes, evaluator priorities, methodology |
| `source_book_node` | **Yes** | 603 | Writer/Reviewer loop (up to 5 passes), DOCX export |
| `gate_3_node` | Yes | | User reviews Source Book |
| `blueprint_extraction_node` | Yes | | Extracts `SlideBlueprint` from Source Book Section 6 |
| `assembly_plan_node` | Yes | | Assembly planning |
| `build_slides_node` | Yes | | 5-turn iterative builder |
| `qa_node` | Yes | | Validates slides against report and template |
| `render_node` | Yes | | Renders PPTX via renderer_v2 |

### Canonical pipeline path (Source Book-only)

```
context → gate_1 → retrieval → gate_2 → evidence_curation
→ proposal_strategy → source_book → gate_3 → STOP
```

### Full pipeline path

```
context → gate_1 → retrieval → gate_2 → evidence_curation
→ proposal_strategy → source_book → gate_3
→ blueprint_extraction → assembly_plan → build_slides → qa → render
```

---

## 3. Agents (`src/agents/`)

| Agent directory | Has real agent? | Notes |
|---|---|---|
| `source_book/writer.py` | **Yes** | LLM-driven, produces `SourceBook` with 7 sections |
| `source_book/reviewer.py` | **Yes** | Per-section scoring, red-team critique |
| `source_book/orchestrator.py` | **Yes** | Writer→Reviewer loop management |
| `source_book/evidence_extractor.py` | **Yes** | Evidence extraction from docs |
| `proposal_strategy/agent.py` | **Yes** | Win themes and strategy |
| `external_research/agent.py` | **Yes** | S2 + Perplexity research |
| `analysis/` | Yes | Claim extraction from docs |
| `context/` | Yes | RFP parsing |
| `draft/` | Yes | Turn 1 of iterative builder |
| `final_review/` | Yes | Turn 4 of iterative builder |
| `indexing/` | Yes | Document indexing + classification |
| `iterative/` | Yes | Iterative builder orchestration |
| `presentation/` | Yes | Turn 5 of iterative builder |
| `qa/` | Yes | Slide QA |
| `refine/` | Yes | Turn 3 of iterative builder |
| `research/` | Yes | Research report generation |
| `retrieval/` | Yes | Document retrieval |
| `review/` | Yes | Turn 2 of iterative builder |
| `slide_architect/` | Yes | Template-locked structure agent |
| `content/` | Yes (legacy) | Old content writer, superseded by iterative builder |

---

## 4. Models (`src/models/`)

| File | Key models | Status |
|---|---|---|
| `source_book.py` | `SourceBook`, `SourceBookReview`, `EvidenceLedger`, `RFPInterpretation`, `SlideBlueprintEntry` | **Present, canonical** |
| `state.py` | `DeckForgeState` | Has `source_book`, `source_book_review`, `external_evidence_pack` fields |
| `slide_blueprint.py` | `SlideBlueprint`, `SlideBlueprintEntry` | Present, canonical |
| `proposal_manifest.py` | `ProposalManifest`, `ManifestEntry`, `HouseInclusionPolicy` | Present, canonical |
| `template_contract.py` | `TEMPLATE_SECTION_ORDER`, `TemplateSectionSpec` | Present, canonical |
| `report.py` | `ResearchReport`, `ReportSection` | Present |

---

## 5. Runner Classification (honest)

| File | Label | Why |
|---|---|---|
| `scripts/source_book_only.py` | **CANONICAL** | Uses the REAL pipeline path: context → gate_1 → retrieval → gate_2 → evidence_curation → proposal_strategy → source_book → gate_3. Extracts real `SourceBook` from state. |
| `scripts/run_pipeline.py` | **Canonical (full)** | Runs the complete pipeline including render. |

---

## 6. Domain Bias Status

| Location | Status |
|---|---|
| `manifest_builder.py` `sector` default | **FIXED** — `sector: str = ""` |
| `manifest_builder.py` `_add_pool_clones` services/keywords | **FIXED** — extracted from RFP context |
| `source_book_only.py` DeckForgeState init | **FIXED** — no hardcoded geography/sector/proposal_mode |
| `graph.py` `analysis_node` KG loading | **FIXED** — uses only `DEFAULT_CACHE_PATH`, no fallback to shared `state/index/` |

---

## 7. Fallback Policy

### Indexing failure handling

`ensure_search_index()` returns `(cache_dir, status, reason)`:
- `"OK"` — indexing succeeded
- `"DEGRADED"` — indexing failed, empty backend saved, reason logged

### Run status reporting

The runner reports honest status in result JSON:
- `"SUCCESS"` — all checks pass, Source Book produced
- `"DEGRADED"` — Source Book produced but with issues (indexing failure, missing evidence, etc.)
- `"FAILED"` — Source Book not produced, critical failure

### Hard fail checks

- Evidence ledger has 0 entries
- Slide blueprint has < 8 entries
- Both S2 and Perplexity returned zero results
- All consultants are placeholders despite KG data
- Indexing failed

---

## 8. Canonical Artifact Package

| Artifact | Source | Notes |
|---|---|---|
| `source_book.docx` | `source_book_export.export_source_book_docx(source_book)` | From real `SourceBook` model |
| `evidence_ledger.json` | `source_book.evidence_ledger` | From real evidence curation |
| `slide_blueprint_from_source_book.json` | `source_book.slide_blueprints` | From Source Book Section 6 |
| `external_evidence_pack.json` | External research agent output | Real S2/Perplexity results |
| `research_query_log.json` | Research query metadata | |
| `research_results_raw.json` | Raw external results | |
| Result summary JSON | Run metadata with honest status | Includes `status`, `index_status`, `failures` |

---

# Section B: Remaining Work

## What this branch still needs

1. **S2 API fixes from master** — commits `47c8278`, `40443e7`, `f8533e8`, `fbf1003` contain Semantic Scholar API auth, probe, and rate limit fixes. Cherry-pick failed due to branch divergence; these should be applied surgically if S2 issues arise.
2. **Test coverage** — Source Book agents need targeted tests on this branch.
3. **Frontend reconciliation** — `claude/nostalgic-nash` has the M11 frontend/backend; this branch has Source Book frontend awareness. These need merging eventually.

## What is NOT needed

- No synthetic approximations — this branch has the real pipeline.
- No relabeling of research_report as source_book.docx — the real writer produces the real `SourceBook`.
- No separate structure agent call for blueprint — the Source Book already contains `slide_blueprints` in Section 6.
