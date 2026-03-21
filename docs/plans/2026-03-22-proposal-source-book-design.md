# Proposal Source Book & Slide Blueprint Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce a Proposal Source Book (Word document) and Slide Blueprint (structured JSON) as a new upstream reasoning layer between RFP intake and slide generation, fixing the root cause of weak proposal quality.

**Architecture:** A 5-agent Proposal Cell produces a human-reviewable Word document (the Source Book) containing all proposal logic, evidence, and slide-by-slide blueprints. The approved Source Book is then mechanically extracted into a Slide Blueprint JSON that feeds the existing G1/G2/G3 slide generation infrastructure. Gate 3 shifts from reviewing assembly metadata to reviewing the full Source Book.

**Tech Stack:** Python 3.12, python-docx, Pydantic v2, Claude Opus (generation), GPT-5.4 (critique), existing LangGraph pipeline, existing Semantic Scholar + Perplexity services.

---

### Skills Used

| Skill | Purpose |
|-------|---------|
| `writing-plans` | Structured this design document with phased rollout |
| `verification-before-completion` | Verified every reuse claim against actual code paths -- corrected 4 false claims in v1 |
| `systematic-debugging` | Phase 1 root-cause investigation: traced dead `report_markdown` path + evidence truncation |
| `test-driven-development` | Defined validation approach for Source Book + Blueprint before implementation |
| `executing-plans` | Designed phased rollout with iteration gates |
| `docx` | Defined Word generation approach using python-docx (already a dependency) |
| `get-shit-done` | Audited existing code via repo search, git history, and actual code inspection -- no shallow assumptions |

---

## 1. Executive recommendation

**Decision: REFACTOR + EXTEND (not rebuild)**

The existing DeckForge pipeline has strong, tested infrastructure that must be preserved:
- G1 slide pattern library (template management, layout contracts)
- G2 filler output schemas (typed Pydantic models with bullet constraints)
- G3 quality gate (10 hard rules, 4 scored metrics)
- Assembly plan agent (deterministic selection scoring)
- Section fillers (5 working fillers with external enrichment)
- Template-v2 renderer (manifest-driven, zero-placeholder audit)

What is **missing** is the proposal reasoning layer between retrieval and slide generation. The old analysis + research agents exist in code but are **dead** -- disconnected from the graph. The iterative builder (draft/review/refine/final_review) consumes `report_markdown` but this field is **never populated** in the active pipeline. Additionally, the live evidence path is severely truncated: `_build_source_pack_from_state()` at `graph.py:596` uses `source.summary` (short ranker strings, ~50-200 words each), and the dead `load_documents()` at `search.py:639,643` takes only the first 3 docs truncated to 5k chars each. The system is starved of both reasoning and evidence.

**Action:** Resurrect and strengthen the analysis + research path as a 5-agent Proposal Cell that produces a Source Book. Build a new full-text document loader. Reconnect it to the existing infrastructure via a new Slide Blueprint extraction step. Preserve all G1/G2/G3 infrastructure unchanged.

---

## 2. Existing system audit

### 2.1 Active pipeline (currently wired into LangGraph)

| Node | File | What It Does | Salvageable? |
|------|------|-------------|-------------|
| `context` | `src/agents/context/agent.py` | Parses RFP into `RFPContext` via `MODEL_MAP["context_agent"]` (GPT-5.4) | YES -- keep as-is |
| `gate_1` | `src/pipeline/graph.py:267` | User approves RFP parse. Uses `interrupt()` inside `gate_node()`. | YES -- keep as-is |
| `retrieval` | `src/agents/retrieval/planner.py` + `ranker.py` | Planner (GPT) generates queries, `semantic_search()` runs against local index, Ranker (GPT) scores results into `retrieved_sources` with short `summary` strings | YES -- keep as-is |
| `gate_2` | `src/pipeline/graph.py:272` | User approves sources | YES -- keep as-is |
| `assembly_plan` | `src/agents/assembly_plan/agent.py` | Single Opus call produces metadata (geography, mode, phases, win_themes). Deterministic pipeline builds InclusionPolicy, MethodologyBlueprint, selects case studies/team, computes SlideBudget, builds ProposalManifest. | YES -- keep, but move after Source Book |
| `gate_3` | `src/pipeline/graph.py:275-277` | User reviews assembly plan summary via `interrupt()` | REFACTOR -- review Source Book instead |
| `submission_transform` | `src/agents/submission_transform/agent.py` | Single Opus call. Converts (non-existent) ResearchReport into SubmissionSourcePack (ContentUnit, EvidenceBundle, SlideAllocation, SlideBrief). Currently operates on empty input. | REPLACE -- see Section 8 |
| `section_fill` | `src/agents/section_fillers/orchestrator.py` | Concurrent Opus calls for 5 section fillers. Receives SourcePack built from `source.summary` (not full text). | YES -- keep, but fix SourcePack input |
| `build_slides` | `src/agents/iterative/builder.py` | 5-turn: Draft(Opus)->Review(GPT)->Refine(Opus)->FinalReview(GPT)->Presentation(Opus). All consume empty `report_markdown`. | YES -- keep, Source Book fixes input |
| `gate_4` | `src/pipeline/graph.py:280` | User reviews built slides | YES -- keep as-is |
| `qa` | `src/agents/qa/agent.py` | No Free Facts + constraint validation | YES -- keep as-is |
| `governance` | `src/agents/submission_qa/agent.py` | Density/lint/provenance checks (deterministic, no LLM) | YES -- keep as-is |
| `gate_5` | `src/pipeline/graph.py:285` | User reviews final QA | YES -- keep as-is |
| `render` | `src/pipeline/graph.py` + `renderer_v2.py` | Manifest-driven PPTX generation with zero-placeholder audit + quality gate | YES -- keep as-is |

### 2.2 Dead code (exists but disconnected from graph)

| Module | File | What It Does | Reusable? |
|--------|------|-------------|-----------|
| `analysis` | `src/agents/analysis/agent.py` | Extracts `ReferenceIndex` (atomic claims) from approved docs. Uses `load_documents()` which truncates to 3 docs x 5k chars. | YES -- agent logic reusable, but needs new full-text document loader |
| `research` | `src/agents/research/agent.py` | Generates `ResearchReport` from ReferenceIndex. Model: Opus, 16k tokens. | PARTIALLY -- report structure is good, but prompt needs strengthening for proposal strategy |
| `analysis_node` | `src/pipeline/graph.py:337` | Defined but never added to graph via `add_node()` | Reusable after re-wiring |
| `research_node` | `src/pipeline/graph.py:390` | Defined but never added to graph via `add_node()` | Reusable after re-wiring |

### 2.3 Evidence path -- actual live flow

**Critical finding: The live evidence path is severely truncated.**

```
retrieval_node
  -> ranker produces RetrievedSource objects with short .summary strings
  -> state.retrieved_sources populated

_build_source_pack_from_state() [graph.py:573-618]
  -> iterates state.retrieved_sources
  -> DocumentEvidence.content_text = source.summary or ""   [line 596]
  -> This is a SHORT RANKER SUMMARY, not full document text
  -> reference_index is always None (analysis agent not wired)
  -> people/projects lists are always empty

section_fill_node
  -> receives SourcePack with summary-only documents
  -> fillers must work from abbreviated evidence

load_documents() [search.py:630-660]  (DEAD -- only used by disconnected analysis_node)
  -> approved[:3]                    -- takes first 3 docs only
  -> max_chars_per_document = 5_000  -- truncates each to 5k chars
  -> Even if resurrected, this is too restrictive
```

### 2.4 Failure analysis of current architecture

The current active pipeline has this flow:

```
RFP -> context -> retrieval -> assembly_plan -> section_fill -> build_slides -> render
```

**Three compounding failures between `retrieval` and `section_fill`:**

1. **No document analysis.** The analysis agent (which extracts atomic claims from approved documents) exists in code but is NOT wired into the graph (`analysis_node` defined at `graph.py:337` but never added via `add_node()`). The `reference_index` field on state is always `None`.

2. **No research report.** The research agent (which synthesizes a report from claims) exists but is NOT wired into the graph (`research_node` defined at `graph.py:390` but never added). The `report_markdown` field is always empty.

3. **Evidence truncation at every layer.** Even if the above agents were resurrected:
   - `load_documents()` (`search.py:639`) takes only the first 3 approved documents
   - Each document is truncated to 5,000 characters (`search.py:643`)
   - `_build_source_pack_from_state()` (`graph.py:596`) uses `source.summary` (ranker summary, typically 50-200 words) as document content, not full text
   - Section fillers receive `DocumentEvidence` objects containing these short summaries
   - Total evidence available to any single agent: ~15k chars (3 x 5k) via legacy loader, or ~1-2k chars (ranker summaries) via live path

4. **No proposal strategy.** No agent interprets the RFP to identify evaluator priorities, scoring logic, or win themes beyond the assembly_plan's shallow metadata extraction (3-5 string `win_themes` with no evidence backing).

5. **No evidence critique.** No agent validates whether claims are supported, flags thin evidence, or detects fluff before slide generation.

**Consequence:** The iterative builder runs with:
- `approved_report`: empty string (no content to work from)
- `reference_index`: None (no claims to reference)
- `evidence_mode`: defaults to "general" (no evidence threshold met)

Section fillers receive a `SourcePack` with ranker summary strings instead of full document text. They must generate proposal content from ~200-word summaries per source.

**Result:** Slides contain generic consulting language, unsupported claims, repetitive content, and weak differentiation.

### 2.5 External services

| Service | File | Status | Reusable? |
|---------|------|--------|-----------|
| `semantic_scholar` | `src/services/semantic_scholar.py` | Active (methodology filler only) | YES -- extend to External Research Agent |
| `perplexity` | `src/services/perplexity.py` | Active (understanding + methodology fillers) | YES -- extend to External Research Agent |
| `source_pack` | `src/services/source_pack.py` | Active -- but `_build_source_pack_from_state()` uses summaries, not full text | REFACTOR -- dataclass is fine, construction function needs new full-text path |
| `search` | `src/services/search.py` | Active (retrieval node). `load_documents()` at line 630 is dead code. | YES -- keep search; replace `load_documents()` |

### 2.6 Key data models

| Model | File | Status |
|-------|------|--------|
| `ReferenceIndex` | `src/models/claims.py` | Defined, used by dead analysis agent. Schema is comprehensive. |
| `ResearchReport` | `src/models/report.py` | Defined, used by dead research agent + DOCX export |
| `DeckForgeState` | `src/models/state.py` | Active. Has `reference_index` (always None) and `report_markdown` (always empty). |
| `SourcePack` | `src/services/source_pack.py` | Active dataclass. `DocumentEvidence` allows full text but is populated with summaries. |
| `SubmissionSourcePack` | `src/models/submission.py` | Active. Contains `ContentUnit`, `EvidenceBundle`, `SlideAllocation`, `SlideBrief`. See Section 8 for overlap analysis. |
| `SlideBrief` | `src/models/submission.py:71-87` | Has `slide_position`, `objective`, `key_message`, `evidence_bundle_refs`, `content_unit_refs`, `prohibited_content`, `layout_type`. Partially overlaps with proposed `SlideBlueprintEntry`. |

### 2.7 DOCX generation

| Function | File | Status |
|----------|------|--------|
| `export_report_docx()` | `src/services/renderer.py:718` | Active -- exports ResearchReport as .docx with heading/section structure |
| `export_source_index_docx()` | `src/services/renderer.py:773` | Active -- 4-column table |
| `export_gap_report_docx()` | `src/services/renderer.py:813` | Active -- 5-column table |
| `render_markdown_to_docx()` | `src/services/formatting.py` | Active -- markdown-it-py to python-docx paragraph conversion |

**Key dependency:** `python-docx>=1.1.0` is already in `requirements.txt`.

---

## 3. Reuse plan

### What stays as-is (no changes needed)

| Component | File | Reason |
|-----------|------|--------|
| Context Agent | `src/agents/context/agent.py` | RFP parsing works correctly |
| Retrieval (planner + ranker) | `src/agents/retrieval/` | Source discovery works; summaries are fine for selection |
| G1 slide pattern library | Template management + layout contracts | Tested, render-proven |
| G2 filler output schemas | `src/agents/section_fillers/g2_schemas.py` | Typed bullet lists, validated, quality-gate-tested |
| G3 quality gate | `src/services/quality_gate.py` | 10 hard rules (R1-R10), 4 scored metrics |
| Template-v2 renderer | `src/services/renderer_v2.py` | Manifest-driven, zero-placeholder audit |
| Manifest builder | `src/services/manifest_builder.py` | Deterministic manifest from assembly plan |
| Selection policies | `src/services/selection_policies.py` | Case study + team scoring works |
| Slide budgeter | `src/services/slide_budgeter.py` | Deterministic budget computation |
| Semantic Scholar service | `src/services/semantic_scholar.py` | Graceful degradation, correct API |
| Perplexity service | `src/services/perplexity.py` | Graceful degradation, correct API |
| Gate infrastructure | `src/pipeline/graph.py:104-115` | `gate_node()` + `interrupt()` pattern works |
| Iterative builder orchestrator | `src/agents/iterative/builder.py` | 5-turn loop structure is sound |
| Draft/Review/Refine/FinalReview/Presentation agents | `src/agents/draft/`, `review/`, `refine/`, `final_review/`, `presentation/` | Working code, just starved of input |

### What needs refactoring

| Component | File | What Changes |
|-----------|------|-------------|
| `_build_source_pack_from_state()` | `graph.py:573-618` | Must load full document text, not `source.summary`. Needs new document loading path. |
| `load_documents()` | `search.py:630-660` | Replace with new full-text loader. Remove 3-doc limit and 5k char truncation. Use reasonable per-doc limit (50k chars) and support all approved docs. |
| Analysis agent prompt | `src/agents/analysis/prompts.py` | Tighten: reject vague claims, add confidence scoring, score evidence strength |
| `gate_3` summary | `graph.py:_gate_3_summary()` | Show Source Book stats instead of assembly plan metadata |
| Graph node ordering | `graph.py:build_graph()` | Insert new nodes, move assembly_plan after gate_3 |
| Section filler input | `src/agents/section_fillers/base.py` | Add `blueprint_entries` field to `SectionFillerInput` |

### What is newly built

| Component | Rationale |
|-----------|-----------|
| External Research Agent | No existing agent unifies Semantic Scholar + Perplexity |
| Proposal Strategist | No existing agent does evaluator-priority + win-theme analysis |
| Source Book Writer | No existing agent produces structured proposal narrative |
| Source Book Reviewer | Existing review pattern reused, but new instance needed for proposal-level critique |
| Source Book DOCX export | Existing export pattern extended, but new function needed |
| Slide Blueprint schema + extraction | New structured output that maps Source Book to G1 layouts |
| Full-text document loader | Replaces dead `load_documents()` with proper full-content loading |

The detailed file-backed build vs reuse decision table is in Appendix C. In summary: 2 agents reused (analysis agent, review pattern), 3 built new (external research, proposal strategist, source book writer), 1 replaced (submission_transform → slide architect), 2 refactored (SourcePack construction, pipeline wiring), 1 new loader.

---

## 4. New proposal architecture

### 4.1 Target pipeline flow

```
START
  -> context (parse RFP)
  -> gate_1 (approve RFP parse)
  -> retrieval (search + rank local docs)
  -> gate_2 (approve sources)
  -> evidence_curation (Internal Evidence Curator + External Research Agent)
  -> proposal_strategy (Proposal Strategist)
  -> source_book (Source Book generation -- iterative, up to 5 passes)
  -> gate_3 (human reviews Source Book DOCX -- approve/reject/edit)
  -> assembly_plan (metadata + deterministic selection -- NOW informed by Source Book)
  -> blueprint_extraction (Slide Architect extracts Blueprint from approved Source Book)
  -> section_fill (G2 fillers -- NOW fed by Blueprint)
  -> build_slides (5-turn iterative builder -- NOW fed by Source Book as report_markdown)
  -> gate_4 (approve built slides)
  -> qa + governance
  -> gate_5 (approve final QA)
  -> render (PPTX generation)
  -> END
```

### 4.2 5-agent Proposal Cell integration

```
┌─────────────────────────────────────────────────────────────┐
│                   PROPOSAL CELL (NEW)                       │
│                                                             │
│  ┌─────────────────┐    ┌──────────────────┐               │
│  │ 1. Internal      │    │ 2. External       │              │
│  │    Evidence      │    │    Research        │              │
│  │    Curator       │    │    Agent           │              │
│  │                  │    │                    │              │
│  │ REUSES:          │    │ BUILDS NEW using:  │              │
│  │ analysis/agent.py│    │ semantic_scholar.py│              │
│  │ claims.py schemas│    │ perplexity.py      │              │
│  │                  │    │                    │              │
│  │ NEEDS NEW:       │    │                    │              │
│  │ full-text loader │    │                    │              │
│  └────────┬─────────┘    └────────┬───────────┘              │
│           │                       │                          │
│           └───────────┬───────────┘                          │
│                       ▼                                      │
│           ┌───────────────────────┐                          │
│           │ 3. Proposal Strategist│                          │
│           │    (BUILD NEW)        │                          │
│           │                       │                          │
│           │ Reads: RFP + evidence │                          │
│           │ Outputs: thesis,      │                          │
│           │   win themes,         │                          │
│           │   evaluator priorities│                          │
│           └───────────┬───────────┘                          │
│                       ▼                                      │
│    ┌──────────────────────────────────┐                      │
│    │     SOURCE BOOK ITERATION LOOP   │                      │
│    │                                  │                      │
│    │  ┌────────────────┐  ┌────────┐ │                      │
│    │  │ Source Book     │◄►│5. Red  │ │                      │
│    │  │ Writer          │  │  Team  │ │                      │
│    │  │ (BUILD NEW)     │  │Reviewer│ │                      │
│    │  │                 │  │(REUSES │ │                      │
│    │  │                 │  │review  │ │                      │
│    │  │                 │  │pattern)│ │                      │
│    │  └────────────────┘  └────────┘ │                      │
│    └──────────────────────────────────┘                      │
│                       ▼                                      │
│           ┌───────────────────────┐                          │
│           │ 4. Slide Architect    │                          │
│           │    (REPLACES          │                          │
│           │    submission_xform)  │                          │
│           │                       │                          │
│           │ Extracts Blueprint    │                          │
│           │ from Source Book      │                          │
│           └───────────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              EXISTING DECKFORGE PIPELINE                     │
│                                                             │
│  assembly_plan -> section_fill -> build_slides -> render    │
│  (ALL EXISTING, now fed by Source Book + Blueprint)         │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Data flow between agents

```
                    RFP Context (from context agent)
                    Retrieved Sources (from retrieval)
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
          Internal Evidence        External Research
          Curator                  Agent
                    │                    │
                    ▼                    ▼
          ReferenceIndex         ExternalEvidencePack
          (state.reference_index) (state.external_evidence_pack)
                    │                    │
                    └─────────┬──────────┘
                              ▼
                    Proposal Strategist
                              │
                              ▼
                    ProposalStrategy
                    (state.proposal_strategy)
                              │
                              ▼
                    Source Book Writer + Reviewer
                    (iterative, up to 5 passes)
                              │
                              ▼
                    SourceBook -> DOCX + report_markdown
                    (state.report_markdown populated)
                              │
                         [GATE 3]
                              │
                              ▼
                    Assembly Plan (existing)
                    (now reads Source Book context)
                              │
                              ▼
                    Slide Architect
                              │
                              ▼
                    SlideBlueprint
                    (state.slide_blueprint)
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
            Section Fillers       Iterative Builder
            (receive Blueprint    (receives report_markdown
             entries per section)  = Source Book text)
```

### 4.4 Integration points with existing infrastructure

1. **`state.reference_index`** -- already defined on `DeckForgeState`. Internal Evidence Curator populates it (same as the dead analysis agent did).

2. **`state.report_markdown`** -- already defined on `DeckForgeState`. Source Book generation populates it with the full Source Book text. The iterative builder already consumes it.

3. **`state.research_report`** -- already defined on `DeckForgeState`. Can be populated with the structured Source Book data for DOCX export.

4. **`state.proposal_manifest`** -- built by assembly_plan + manifest_builder. Blueprint extraction produces injection_data that merges into the manifest (same pattern as current section_fill).

5. **Section fillers** -- receive `SourcePack` + `win_themes` + `methodology_blueprint`. Now ALSO receive blueprint entries per section.

6. **Quality gate** -- unchanged. Still validates b_variable slides for R1-R10 rules.

### 4.5 Pipeline node mapping

#### Current graph (from `build_graph()` in graph.py:1065)

```
START -> context -> gate_1 -> retrieval -> gate_2
     -> assembly_plan -> gate_3 -> submission_transform
     -> section_fill -> build_slides -> gate_4
     -> qa -> governance -> gate_5 -> render -> END
```

#### New graph

```
START -> context -> gate_1 -> retrieval -> gate_2
     -> evidence_curation -> proposal_strategy -> source_book
     -> gate_3 -> assembly_plan -> blueprint_extraction
     -> section_fill -> build_slides -> gate_4
     -> qa -> governance -> gate_5 -> render -> END
```

#### Node-by-node changes

| Node | Change Type | Details |
|------|-------------|---------|
| `context` | UNCHANGED | |
| `gate_1` | UNCHANGED | |
| `retrieval` | UNCHANGED | |
| `gate_2` | UNCHANGED | |
| `evidence_curation` | **NEW** | Runs Internal Evidence Curator + External Research Agent concurrently via `asyncio.gather()`. Populates `state.reference_index` and `state.external_evidence_pack`. |
| `proposal_strategy` | **NEW** | Runs Proposal Strategist. Populates `state.proposal_strategy`. |
| `source_book` | **NEW** | Runs Source Book Writer + Reviewer iteration loop (up to 5 passes). Populates `state.report_markdown` with Source Book text. Generates Source Book DOCX. |
| `gate_3` | **REFACTORED** | Shows Source Book stats instead of assembly plan metadata. Same `interrupt()` mechanism. |
| `assembly_plan` | **MOVED** (was before gate_3, now after) | Now reads Source Book context for better methodology/selection decisions. Assembly plan prompt updated to consume `state.proposal_strategy.recommended_methodology_approach`. |
| `blueprint_extraction` | **NEW** (replaces `submission_transform`) | Extracts SlideBlueprint from Source Book. |
| `section_fill` | **MODIFIED** | `SectionFillerInput` gains `blueprint_entries` field. `_build_source_pack_from_state()` refactored to use full document text. |
| `build_slides` | UNCHANGED | Now receives populated `report_markdown` automatically. |
| `gate_4` through `render` | UNCHANGED | |

#### New state fields

```python
class DeckForgeState(DeckForgeBaseModel):
    # ... existing fields ...

    # ─── Proposal Cell (new) ───
    external_evidence_pack: ExternalEvidencePack | None = None
    proposal_strategy: ProposalStrategy | None = None
    source_book: SourceBook | None = None
    source_book_docx_path: str | None = None
    slide_blueprint: SlideBlueprint | None = None
```

#### Removed nodes

| Node | Why Removed |
|------|-------------|
| `submission_transform` | Replaced by `blueprint_extraction`. See Section 8 for rationale. |

#### Gate rejection loops

| Gate | On Rejection | Loops Back To |
|------|-------------|---------------|
| gate_1 | Re-parse RFP | `context` |
| gate_2 | Re-search | `retrieval` |
| gate_3 | Rewrite Source Book with feedback | `source_book` |
| gate_4 | Re-build slides | `build_slides` |
| gate_5 | Re-run QA | `qa` |

---

## 5. Prompt architecture

### 5.1 Internal Evidence Curator

**Reuses:** `src/agents/analysis/agent.py` with tuned prompt and new document loader.

**Framework-level prompt purpose:** Extract ONLY verified, specific evidence from Strategic Gears internal documents. Reject vague claims. Every extracted claim must have a verifiable source span.

**Dynamic context inputs:**
- `rfp_context` (parsed RFP -- to focus extraction on relevant evidence)
- `approved_documents` (full document content -- NEW loader, not the 3-doc/5k-char `load_documents()`)
- `output_language`

**Output schema:** `ReferenceIndex` (existing, from `src/models/claims.py`)
- `ClaimObject` list (claim_id, claim_text, source_doc_id, evidence_span, confidence 0.6-1.0)
- `CaseStudy` list (project names, clients, outcomes)
- `TeamProfile` list (names, roles, certifications)
- `ComplianceEvidence` list
- `FrameworkReference` list
- `GapObject` list (identified evidence gaps)
- `Contradiction` list

**Prompt tuning (vs current analysis agent):**
- Add: "Reject any claim without a specific evidence span from the source document"
- Add: "Flag claims that use vague language: 'extensive experience', 'deep expertise', 'proven track record' -- these are NOT evidence"
- Add: "For each person, extract SPECIFIC certifications, years of experience, and named project roles"
- Add: "Confidence scoring: 1.0 = direct quote with context, 0.8 = clear paraphrase, 0.6 = reasonable inference"

**Document loading strategy:** New `load_full_documents()` function replaces `load_documents()`:
- No doc count limit (process ALL approved docs)
- Per-document truncation: 50,000 chars (matches analysis agent's internal cap)
- If total content exceeds LLM context, batch into multiple analysis calls and merge `ReferenceIndex` results
- Uses existing `extract_document()` from `src/utils/extractors.py`

**Failure conditions:**
- Zero claims extracted -> ERROR (documents may be empty or unreadable)
- All claims below 0.6 confidence -> WARNING (evidence quality too low)

### 5.2 External Research Agent

**New agent.** Reuses `semantic_scholar.py` and `perplexity.py` services.

**Framework-level prompt purpose:** Gather external evidence (academic papers, industry benchmarks, public-sector case studies, methodology frameworks) that supports the proposal thesis. External research provides EVIDENCE ONLY -- it does not write proposal content.

**Dynamic context inputs:**
- `rfp_context` (to generate targeted search queries)
- `sector` (from RFP context)
- `methodology_keywords` (extracted from RFP scope)

**Output schema:** New `ExternalEvidencePack` Pydantic model:
```python
class ExternalSource(DeckForgeBaseModel):
    source_id: str  # EXT-001, EXT-002, ...
    title: str
    source_type: Literal["academic_paper", "industry_report", "benchmark", "case_study", "framework"]
    year: int
    url: str = ""
    abstract: str  # max 200 words
    relevance_score: float  # 0.0-1.0
    relevance_reason: str
    key_findings: list[str]  # 3-5 bullet points

class ExternalEvidencePack(DeckForgeBaseModel):
    sources: list[ExternalSource]
    search_queries_used: list[str]
    coverage_assessment: str  # summary of what evidence was/wasn't found
```

**Implementation:** LLM generates search queries from RFP context, then:
1. Run 3-5 Semantic Scholar searches (academic rigor)
2. Run 2-3 Perplexity searches (industry trends, benchmarks)
3. LLM ranks and filters results by relevance
4. LLM extracts key findings per source

**Failure conditions:**
- Both services fail -> degrade gracefully (empty pack, log warning)
- Zero relevant results -> proceed with internal evidence only

### 5.3 Proposal Strategist

**New agent.**

**Framework-level prompt purpose:** Interpret the RFP through the lens of a senior bid manager. Identify what evaluators will prioritize, define a winning thesis, and map SG's verified capabilities to RFP requirements.

**Dynamic context inputs:**
- `rfp_context` (full parsed RFP)
- `reference_index` (Internal Evidence Curator output -- verified SG capabilities)
- `external_evidence_pack` (External Research Agent output)
- `output_language`

**Output schema:** New `ProposalStrategy` Pydantic model:
```python
class EvaluatorPriority(DeckForgeBaseModel):
    priority: str
    weight_estimate: float  # 0.0-1.0
    evidence_available: Literal["strong", "moderate", "weak", "none"]
    strategy_note: str

class WinTheme(DeckForgeBaseModel):
    theme: str
    supporting_evidence: list[str]  # claim_ids or ext source_ids
    differentiator_strength: Literal["unique", "strong", "moderate", "weak"]

class ProposalStrategy(DeckForgeBaseModel):
    rfp_interpretation: str  # 2-3 paragraphs
    unstated_evaluator_priorities: list[EvaluatorPriority]
    scoring_logic_assessment: str
    compliance_requirements: list[str]
    win_themes: list[WinTheme]  # 3-5, each with evidence backing
    proposal_thesis: str  # 1 paragraph -- the core argument
    risk_if_unchanged: str  # client's risk of not acting
    competitive_positioning: str  # how SG differentiates
    evidence_gaps: list[str]  # what we can't prove
    recommended_methodology_approach: str  # high-level, informs assembly plan
```

**Model:** Claude Opus (strategic reasoning requires strongest model)

**Failure conditions:**
- Zero win themes with "strong" or better evidence -> WARNING
- All evaluator priorities show "weak" or "none" evidence -> CRITICAL (proposal may not be competitive)

### 5.4 Source Book Writer

**New agent.**

**Framework-level prompt purpose:** Synthesize all upstream evidence and strategy into a comprehensive, human-readable Proposal Source Book. Every claim must cite its source (CLM-xxxx for internal, EXT-xxx for external). No unsupported assertions.

**Dynamic context inputs:**
- `reference_index` (verified internal evidence)
- `external_evidence_pack` (external research)
- `proposal_strategy` (thesis, win themes, evaluator priorities)
- `rfp_context`
- `output_language`
- `reviewer_feedback` (if rewriting after critique)

**Output schema:** New `SourceBook` Pydantic model (see Section 7 for full structure)

**Model:** Claude Opus (long-form structured writing with evidence integration)

### 5.5 Reviewer / Red Team

**Based on:** `src/agents/review/agent.py` critique pattern (1-5 scoring with issues/instructions).

**Framework-level prompt purpose:** Evaluate the Source Book draft as a tough evaluator would. Remove fluff, reject unsupported claims, detect repetition, assess competitive viability.

**Dynamic context inputs:**
- Source Book draft (current pass)
- `rfp_context`
- `reference_index` (to verify evidence backing)
- Previous review (if iterating)

**Output schema:** New `SourceBookReview` Pydantic model:
```python
class SectionCritique(DeckForgeBaseModel):
    section_id: str
    score: int  # 1-5
    issues: list[str]
    rewrite_instructions: list[str]
    unsupported_claims: list[str]  # claims without evidence backing
    fluff_detected: list[str]  # vague language to remove

class SourceBookReview(DeckForgeBaseModel):
    section_critiques: list[SectionCritique]
    overall_score: int  # 1-5
    coherence_issues: list[str]
    repetition_detected: list[str]
    competitive_viability: Literal["strong", "adequate", "weak", "not_competitive"]
    pass_threshold_met: bool  # True if overall >= 4 and no section < 3
    rewrite_required: bool
```

**Model:** GPT-5.4 (critique role, consistent with existing review/final_review pattern)

**Failure conditions:**
- Overall score 1-2 after 3 passes -> CRITICAL (proposal fundamentals are weak)
- `competitive_viability == "not_competitive"` -> flag for human review

---

## 6. Iteration design

### 6.1 Source Book iteration loop

```
Pass 1: Draft Source Book
  |-- Internal Evidence Curator output
  |-- External Evidence Pack
  |-- Proposal Strategy
  |-- Source Book Writer produces initial draft
  |
Pass 2: Evidence Critique
  |-- Reviewer checks evidence backing
  |-- Flags unsupported claims, thin logic
  |-- Score: if >= 4 overall and no section < 3, skip to Pass 5
  |
Pass 3: Proposal Logic Critique
  |-- Reviewer checks competitive viability
  |-- Detects repetition, weak differentiators
  |-- If pass_threshold_met: skip to Pass 5
  |
Pass 4: Rewrite
  |-- Source Book Writer rewrites weak sections
  |-- Uses rewrite_instructions from Passes 2-3
  |-- Reviewer validates improvements
  |
Pass 5: Final Review + Blueprint Extraction
  |-- Final Reviewer validates complete Source Book
  |-- If approved: extract Slide Blueprint
  |-- If not approved: return to Pass 4 (max 1 retry)
```

### 6.2 Gates between passes

| Gate | Condition | Action if Failed |
|------|-----------|-----------------|
| After Pass 1 | Source Book has all 7 sections populated | Retry Pass 1 (max 1 retry) |
| After Pass 2 | No section scored 1 (catastrophic) | Return to Pass 1 with evidence gaps flagged |
| After Pass 3 | `competitive_viability != "not_competitive"` | Flag for human intervention at Gate 3 |
| After Pass 4 | `overall_score >= 3` | Accept (human will review at Gate 3) |
| After Pass 5 | Blueprint extracted with `evidence_coverage >= 0.5` | Accept |

### 6.3 Early-stop criteria

- **After Pass 2:** If `overall_score >= 4` AND no section < 3 AND `competitive_viability` in ("strong", "adequate") -> skip directly to Pass 5.
- **After Pass 3:** If `pass_threshold_met == True` -> skip to Pass 5.
- **Maximum passes:** 5. If not converging, accept best-effort and present to human at Gate 3 with warnings.

### 6.4 Red-team thresholds

| Metric | Threshold | Consequence |
|--------|-----------|-------------|
| Unsupported claims per section | > 3 | Section must be rewritten |
| Fluff phrases detected (total) | > 10 | Rewrite pass required |
| Repetition instances | > 5 | Deduplication pass required |
| Evidence coverage | < 50% | WARNING at Gate 3 |
| Competitive viability | "not_competitive" | CRITICAL flag at Gate 3 |

---

## 7. Source Book design

### 7.1 Word document structure

```
PROPOSAL SOURCE BOOK
[Client Name] - [RFP Name]
Generated: [date] | Language: [en/ar]

TABLE OF CONTENTS (auto-generated)

1. RFP INTERPRETATION
   1.1 Objective & Scope
   1.2 Constraints & Compliance Requirements
   1.3 Unstated Evaluator Priorities
   1.4 Probable Scoring Logic
   1.5 Key Compliance Requirements

2. CLIENT PROBLEM FRAMING
   2.1 Current-State Challenge
   2.2 Why It Matters Now
   2.3 Transformation Logic
   2.4 Risk If Unchanged

3. WHY STRATEGIC GEARS
   3.1 Capability-to-RFP Mapping (table)
   3.2 Named Consultants & Role Relevance (table)
   3.3 Relevant Project Experience (table)
   3.4 Certifications & Compliance

4. EXTERNAL EVIDENCE
   4.1 Academic Studies (table: source, year, relevance, key finding)
   4.2 Industry Benchmarks (table)
   4.3 Public-Sector Case Studies (table)
   4.4 Methodology Frameworks (table)

5. PROPOSED SOLUTION
   5.1 Methodology Overview
   5.2 Phase Details (per phase: activities, deliverables, governance)
   5.3 Governance Framework
   5.4 Timeline Logic
   5.5 Value Case & Differentiation

6. SLIDE-BY-SLIDE BLUEPRINT
   For each b_variable slide:
   - Slide # | Section | Layout
   - Purpose (1 sentence)
   - Title (max 10 words)
   - Key Message (1 sentence)
   - Bullet Logic (2-6 bullets)
   - Proof Points (evidence references)
   - Visual Guidance
   - Must-Have Evidence
   - Forbidden Content

7. EVIDENCE LEDGER
   Table: Claim ID | Claim Text | Source Type | Source Reference |
          Confidence | Verifiability Status
```

### 7.2 Generation approach

Use **python-docx** (already installed, `python-docx>=1.1.0` in `requirements.txt`).

Extend the existing `export_report_docx()` pattern in `src/services/renderer.py`.

New function: `export_source_book_docx(source_book: SourceBook, output_path: str) -> str`

Implementation:
1. Create `Document()` with custom styles (heading fonts, table styles matching SG brand)
2. Add cover page with client name, RFP name, date
3. Iterate through 7 sections, rendering each with appropriate formatting:
   - Sections 1-2, 5: prose paragraphs rendered via existing `render_markdown_to_docx()` from `src/services/formatting.py`
   - Sections 3-4: structured tables using python-docx `Table` API (same pattern as `export_source_index_docx()`)
   - Section 6: one table per slide blueprint entry
   - Section 7: single large evidence ledger table (same pattern as `export_gap_report_docx()`)
4. Save to `output/{session_id}/source_book.docx`

### 7.3 Review/edit workflow

1. Pipeline generates Source Book DOCX and saves to `output/{session_id}/source_book.docx`
2. Gate 3 displays Source Book summary (section count, evidence coverage, competitive viability score)
3. User can:
   - **Approve** -> proceed to assembly plan + slide generation
   - **Reject with feedback** -> Source Book Writer rewrites based on feedback, re-presents at Gate 3
   - **Download and edit** -> user edits DOCX offline, re-uploads -> pipeline re-extracts and continues
4. Approved Source Book text is stored in `state.report_markdown` (feeds iterative builder)

---

## 8. Slide Blueprint design

### 8.1 Decision: REPLACE submission_transform (not refactor)

The existing `SubmissionSourcePack` (in `src/models/submission.py`) has structural overlap with the proposed Slide Blueprint:

| Existing `SlideBrief` field | Proposed `SlideBlueprintEntry` field | Compatible? |
|----------------------------|--------------------------------------|-------------|
| `slide_position` | `slide_number` | YES |
| `objective` | `slide_purpose` | YES |
| `key_message` | `key_message` | YES |
| `evidence_bundle_refs` | `proof_points` | PARTIAL -- refs vs IDs |
| `content_unit_refs` | (no equivalent) | NO -- Blueprint doesn't use content units |
| `prohibited_content` | `forbidden_content` | YES |
| `layout_type` | `semantic_layout_id` | NO -- LayoutType enum vs G1 semantic IDs |
| (no equivalent) | `title` | MISSING |
| (no equivalent) | `bullet_logic` | MISSING |
| (no equivalent) | `visual_guidance` | MISSING |
| (no equivalent) | `must_have_evidence` | MISSING |

**Why REPLACE, not REFACTOR:**

1. **Input source is different.** Submission_transform reads a ResearchReport (which doesn't exist in the active pipeline). The Slide Architect reads the Source Book. The prompt, context injection, and reasoning are fundamentally different.

2. **Output granularity is different.** `SlideBrief` is a routing/allocation tool (which content units go where). `SlideBlueprintEntry` is a content specification (what the slide must say, with exact bullet logic and evidence references). The Blueprint is more prescriptive.

3. **`ContentUnit` / `EvidenceBundle` abstraction is unnecessary.** The Source Book already contains structured, evidence-cited content. Re-extracting it into intermediate content units adds a layer of indirection without value. The Blueprint reads the Source Book directly.

4. **Layout mapping is incompatible.** `SlideBrief.layout_type` uses the `LayoutType` enum (CONTENT_1COL, CONTENT_2COL, etc.) which maps to legacy renderer layouts. The Blueprint uses `semantic_layout_id` strings that map to G1 template layout families. These are fundamentally different addressing schemes.

**What happens to existing submission code:**
- `src/agents/submission_transform/` -- retired (agent + prompts)
- `src/models/submission.py` -- `SubmissionSourcePack`, `ContentUnit`, `EvidenceBundle`, `SlideBrief`, `SlideAllocation` become dead code. `InternalNotePack`, `UnresolvedIssueRegistry`, and the QA-related models (`SubmissionQAResult`, etc.) are still used by the governance node and stay.
- `submission_transform_node` in graph.py -- replaced by `blueprint_extraction_node`

### 8.2 JSON structure

```json
{
  "blueprint_version": "1.0",
  "total_variable_slides": 12,
  "evidence_coverage": 0.85,
  "entries": [
    {
      "slide_number": 1,
      "section_id": "section_01",
      "semantic_layout_id": "layout_heading_and_two_content_with_tiltes",
      "slide_purpose": "Frame the client's strategic challenge and transformation need",
      "title": "Strategic Context & Challenge",
      "key_message": "Current legacy architecture is blocking digital transformation goals",
      "bullet_logic": [
        "Legacy systems limit service delivery modernization",
        "Data silos prevent cross-agency decision-making",
        "Rising citizen expectations demand digital-first services"
      ],
      "proof_points": ["CLM-0012", "CLM-0015", "EXT-003"],
      "visual_guidance": "Two-column: left=challenges, right=implications",
      "must_have_evidence": ["CLM-0012"],
      "forbidden_content": ["generic digital transformation claims", "unsupported statistics"]
    }
  ]
}
```

### 8.3 Mapping Blueprint to manifest and render pipeline

**Point 1: Blueprint -> Section Filler Input**

```python
class SectionFillerInput(DeckForgeBaseModel):
    # ... existing fields ...
    blueprint_entries: list[SlideBlueprintEntry] = Field(default_factory=list)  # NEW
```

Each filler uses blueprint entries as explicit content guidance:
- Title comes from `blueprint_entry.title`
- Bullet content guided by `blueprint_entry.bullet_logic`
- Evidence references from `blueprint_entry.proof_points`

**Point 2: Blueprint -> Iterative Builder**

`state.report_markdown` is populated with approved Source Book text. The iterative builder's Draft agent now has rich content to work from instead of an empty string. The Blueprint's `slide_purpose` and `key_message` fields can optionally be injected into the draft prompt for additional guidance.

**Point 3: Filler Output -> Manifest -> Renderer (unchanged)**

After fillers run, their `injection_data` (populated from G2 schemas) is merged into `ManifestEntry` objects. The render pipeline (`renderer_v2.py`) reads `ManifestEntry.injection_data` and injects into PPTX placeholders. This path is completely unchanged.

Blueprint `semantic_layout_id` values use the same G1 layout ID vocabulary as the existing manifest entries, ensuring compatibility.

---

## 9. Gate 3 redesign

### 9.1 What changes

| Aspect | Current | New |
|--------|---------|-----|
| **What is reviewed** | Assembly plan metadata (mode, geography, phase count, case study count) | Full Source Book DOCX (proposal content, evidence, strategy) |
| **Review artifact** | Terminal summary (5-6 lines) | Downloadable Word document + terminal summary |
| **Approval meaning** | "Template structure looks right" | "Proposal content and strategy are approved for slide generation" |
| **Rejection action** | Retry assembly plan (re-run LLM) | Rewrite Source Book with user feedback (iterative) |
| **Implementation** | `_gate_3_summary()` returns assembly stats | Updated `_gate_3_summary()` returns Source Book stats + DOCX path |
| **Interrupt mechanism** | `interrupt()` inside `gate_node()` (unchanged) | Same `interrupt()` pattern -- infrastructure stays |

### 9.2 What is reviewed

Gate 3 summary now includes:
1. Source Book statistics (section count, word count, evidence count)
2. Competitive viability score (from Red Team review)
3. Evidence coverage (% of claims with backing)
4. Evidence gaps flagged (count + summary)
5. Win themes with evidence strength ratings
6. Path to Source Book DOCX for download/review

### 9.3 What must be approved before slides are generated

1. **Source Book content** -- the full proposal logic, evidence, and strategy
2. **Slide-by-Slide Blueprint** (Section 6 of Source Book) -- what each slide will contain
3. **Evidence Ledger** (Section 7) -- verified claims and their sources

Only AFTER Gate 3 approval does the pipeline proceed to:
- Assembly plan (methodology phases, case study/team selection)
- Section fillers (G2 content generation)
- Iterative builder (slide text refinement)
- Render (PPTX generation)

---

## 10. Model recommendations

| Agent Role | Model | Justification |
|-----------|-------|---------------|
| **Internal Evidence Curator** | Claude Opus (`anthropic_model_opus`) | Complex document analysis, structured extraction, nuanced confidence scoring. Reuses existing analysis agent's model key (`MODEL_MAP["analysis_agent"]`). |
| **External Research Agent** | Claude Sonnet (`anthropic_model_sonnet`) | Search query generation + result ranking. Does not require Opus-level reasoning. The heavy lifting is done by Semantic Scholar/Perplexity APIs. Uses `MODEL_MAP["conversation_manager"]` key. |
| **Proposal Strategist** | Claude Opus | Highest-stakes reasoning: RFP interpretation, evaluator psychology, competitive positioning. Must be strongest model. New `MODEL_MAP["proposal_strategist"]` key. |
| **Source Book Writer** | Claude Opus | Long-form structured proposal writing with evidence integration. Needs strongest generation model. New `MODEL_MAP["source_book_writer"]` key. |
| **Reviewer / Red Team** | GPT-5.4 (`openai_model_gpt54`) | Critique role. Consistent with existing pattern (review agent uses `MODEL_MAP["qa_agent"]`, final_review uses same). Different model family provides genuine second opinion. |
| **Slide Architect (Blueprint Extraction)** | Claude Opus | Must understand both Source Book content and G1 template constraints. Complex mapping task. New `MODEL_MAP["slide_architect"]` key. |
| **Section Fillers** | Claude Opus | Keep existing. Already tuned and working. |
| **Iterative Builder (Draft/Refine/Presentation)** | Claude Opus via `MODEL_MAP["research_agent"]` | Keep existing model assignments. |
| **Iterative Builder (Review/FinalReview)** | GPT-5.4 via `MODEL_MAP["qa_agent"]` | Keep existing model assignments. |

**Cost note:** The Source Book iteration loop adds 3-5 Opus calls (writer) + 2-3 GPT calls (reviewer) per proposal. This is ~$5-15 additional cost per proposal but produces a dramatically better upstream signal that reduces downstream iteration waste.

**Where lighter models are acceptable:**
- External Research Agent (Sonnet) -- query generation is simple; API services do the heavy work
- Evidence Curator could potentially use Sonnet for shorter documents (<10k chars), but Opus is safer for complex multi-document extraction
- Red Team Reviewer uses GPT-5.4 which is cheaper than Opus and provides cross-family diversity

---

## 11. Implementation plan

### Phase 1: Evidence foundation (lowest risk, highest value)

**Goal:** Build the full-text document loader, resurrect the analysis agent, add external research. Populate `reference_index` and `external_evidence_pack` on state. Fix `_build_source_pack_from_state()` to use full document text.

**Tasks:**
1. Build `load_full_documents()` in `src/services/search.py` -- loads ALL approved docs, 50k chars per doc, uses `extract_document()` from `src/utils/extractors.py`
2. Refactor `_build_source_pack_from_state()` in `graph.py` to load full document text instead of `source.summary`
3. Re-wire `analysis_node` into the graph after `gate_2`, using new full-text loader
4. Tune analysis agent prompt (reject vague claims, add confidence scoring)
5. Build External Research Agent (new file: `src/agents/external_research/agent.py`)
6. Add `ExternalEvidencePack` schema to `src/models/`
7. Add `external_evidence_pack` field to `DeckForgeState`
8. Wire both into a concurrent `evidence_curation_node`
9. Tests: verify ReferenceIndex is populated with full-text claims, verify external evidence degrades gracefully, verify SourcePack contains full document text

### Phase 2: Proposal strategy

**Goal:** Add strategic reasoning between evidence curation and slide generation.

**Tasks:**
1. Build Proposal Strategist agent (`src/agents/proposal_strategy/agent.py`)
2. Add `ProposalStrategy` schema to `src/models/`
3. Add `proposal_strategy` field to `DeckForgeState`
4. Wire `proposal_strategy_node` into graph after `evidence_curation`
5. Tests: verify strategy output has win themes with evidence backing

### Phase 3: Source Book generation

**Goal:** Produce the Proposal Source Book (Word document) with iterative quality loop.

**Tasks:**
1. Define `SourceBook` Pydantic model (7 sections matching spec)
2. Build Source Book Writer agent (`src/agents/source_book/writer.py`)
3. Build Source Book Reviewer agent (`src/agents/source_book/reviewer.py`)
4. Build iteration orchestrator (`src/agents/source_book/orchestrator.py`)
5. Build DOCX export function (`export_source_book_docx()` in `src/services/renderer.py`)
6. Wire `source_book_node` into graph
7. Populate `state.report_markdown` from Source Book content
8. Tests: verify Source Book has all 7 sections, verify DOCX generates correctly, verify iteration loop converges within 5 passes

### Phase 4: Gate 3 redesign + pipeline reorder

**Goal:** Gate 3 reviews the Source Book. Assembly plan moves after Gate 3.

**Tasks:**
1. Update `_gate_3_summary()` in `graph.py` to show Source Book stats (word count, evidence count, viability score, DOCX path)
2. Move `assembly_plan_node` to AFTER gate_3 in `build_graph()`
3. Update assembly_plan prompt to consume `state.proposal_strategy.recommended_methodology_approach`
4. Tests: verify gate 3 shows Source Book info, verify pipeline order is correct, verify assembly plan still produces valid output

### Phase 5: Blueprint extraction + filler integration

**Goal:** Replace submission_transform with Blueprint Extraction. Feed blueprint to section fillers.

**Tasks:**
1. Define `SlideBlueprint` and `SlideBlueprintEntry` schemas in `src/models/`
2. Build Slide Architect agent (`src/agents/slide_architect/agent.py`) -- reads Source Book, outputs SlideBlueprint
3. Add `blueprint_entries` field to `SectionFillerInput` in `src/agents/section_fillers/base.py`
4. Update each filler to use blueprint guidance (title, bullet_logic, proof_points) when available
5. Replace `submission_transform_node` with `blueprint_extraction_node` in graph
6. Add `slide_blueprint` field to `DeckForgeState`
7. Tests: verify Blueprint aligns with manifest b_variable count, verify fillers use blueprint guidance, verify submission_transform models still importable (governance node uses some)

### Phase 6: E2E integration + quality validation

**Goal:** Full pipeline runs end-to-end with Source Book -> Blueprint -> Slides.

**Tasks:**
1. Run EN positive proof with Source Book layer
2. Run AR positive proof with Source Book layer
3. Compare output quality against Phase G Step 4 baselines
4. Tune prompts based on quality delta
5. Run full test suite (pytest + ruff + vitest)

### Prototyping priority

**Start with Phase 1** -- it's the lowest-risk, highest-value change:
- Fixes the evidence truncation problem immediately
- Populates `reference_index` which is already a state field
- Provides immediate signal improvement to downstream agents
- Can be tested independently without changing pipeline node order
- The full-text loader alone will improve section filler output quality

---

### Appendix A -- Verified reuse claims

| # | Claim | File/Path Checked | What Was Verified |
|---|-------|-------------------|-------------------|
| 1 | Analysis agent extracts ReferenceIndex from docs | `src/agents/analysis/agent.py` | Confirmed: `run(state, approved_sources)` -> `ReferenceIndex` via Opus structured output. Model: `claude-opus-4-6`, fallback `gpt-5.4`. Schemas in `src/models/claims.py`. |
| 2 | Research agent produces ResearchReport with sections | `src/agents/research/agent.py` | Confirmed: reads `reference_index` + `rfp_context`, produces `ResearchReport` with `sections: list[ReportSection]`, each with `content_markdown`, `claims_referenced`, `gaps_flagged`. Model: `claude-opus-4-6`, max_tokens 16000. |
| 3 | `report_markdown` is never populated in active pipeline | `src/pipeline/graph.py:173,395` | Confirmed: line 395 sets `report_markdown` only in `research_node` which is NOT added to graph. Line 173 reads it for gate_3 summary but it's always empty. |
| 4 | Iterative builder consumes `report_markdown` as `approved_report` | `src/agents/draft/agent.py:86`, `src/agents/review/agent.py:51` | Confirmed: both draft and review agents pass `state.report_markdown` as `approved_report` in user message. Currently empty. |
| 5 | python-docx is already a dependency | `requirements.txt` | Confirmed: `python-docx>=1.1.0` listed. |
| 6 | DOCX export functions exist and use `render_markdown_to_docx` | `src/services/renderer.py:718-828` | Confirmed: three async export functions, all using python-docx `Document()` + `render_markdown_to_docx()` from `formatting.py`. |
| 7 | Semantic Scholar service returns `ScholarResult` with title/abstract/citations | `src/services/semantic_scholar.py` | Confirmed: `search_papers(query) -> list[ScholarResult]`, graceful degradation on error. |
| 8 | Perplexity service returns `PerplexityResult` with content/citations | `src/services/perplexity.py` | Confirmed: `search_web(query) -> PerplexityResult | None`, graceful degradation. |
| 9 | `_build_source_pack_from_state()` uses `source.summary` (short ranker summary), NOT full document text | `src/pipeline/graph.py:591-598` | Confirmed at line 596: `content_text=source.summary or ""`. |
| 10 | `load_documents()` takes first 3 docs, truncates each to 5,000 chars | `src/services/search.py:630-660` | Confirmed at lines 639, 643: `approved[:3]` and `max_chars_per_document = 5_000`. |
| 11 | G2 schemas enforce typed bullet lists with 25-word max | `src/agents/section_fillers/g2_schemas.py` | Confirmed: `Bullets_2_3`, `Bullets_3_5` etc. with word-count validators. |
| 12 | Assembly plan produces MethodologyBlueprint deterministically | `src/agents/assembly_plan/agent.py:429-456` | Confirmed: LLM outputs phase specs, `build_methodology_blueprint()` constructs deterministic blueprint. |
| 13 | Quality gate is manifest-aware and checks only b_variable slides | `src/services/quality_gate.py` | Confirmed: R7, R10 filter on `entry_type == "b_variable"`. |
| 14 | Gate 3 uses `interrupt()` inside `gate_node()` | `src/pipeline/graph.py:104-115` | Confirmed at line 111: `decision = interrupt({...})`. All gates use this pattern. |

### Appendix B -- Rejected assumptions

| # | Assumption Considered | Why Rejected (code evidence) |
|---|----------------------|------------------------------|
| 1 | "The submission_transform agent can be reused as the Proposal Strategist" | Rejected: `submission_transform/prompts.py` is a content-unit extraction tool, not a strategy agent. It routes existing report content into slide buckets. It does not interpret the RFP, identify evaluator priorities, or define win themes. |
| 2 | "The iterative builder (5-turn) should be removed" | Rejected: The Draft/Review/Refine/FinalReview/Presentation cycle is sound architecture for slide text generation. The problem is upstream -- it's fed empty `report_markdown`. With a proper Source Book as input, the 5-turn builder becomes valuable again. |
| 3 | "The analysis agent needs a complete rewrite" | Rejected: `analysis/agent.py` already extracts structured `ClaimObject`, `CaseStudy`, `TeamProfile`, `ComplianceEvidence`, `FrameworkReference` from documents. Schema in `src/models/claims.py` is comprehensive. Needs prompt tuning AND a new document loader, not a rewrite of the agent itself. |
| 4 | "We need a new Word document library" | Rejected: `python-docx>=1.1.0` is already installed and used by three existing export functions. No new dependency needed. |
| 5 | "The knowledge graph should be rebuilt" | Rejected: `state/index/knowledge_graph.json` with `PersonProfile`, `ProjectRecord`, `ClientRecord` (defined in `src/models/knowledge.py`) is adequate. The gap is in how it's used, not in the data itself. |
| 6 | "SourcePack can be reused as-is for the new proposal cell" | Partially rejected. The `SourcePack` dataclass is well-designed. But `_build_source_pack_from_state()` in `graph.py:573-618` populates it with `source.summary` (short ranker strings), not full document text. The SourcePack builder needs a new construction path. |

### Appendix C -- File-backed build vs reuse decision table

| Component | Decision | File Evidence |
|-----------|----------|---------------|
| **Internal Evidence Curator** | REUSE agent + NEW loader | Agent: `src/agents/analysis/agent.py` (correct schema). Loader: `search.py:630` truncates to 3 docs x 5k chars -- must replace. |
| **External Research Agent** | BUILD NEW | No existing agent combines `semantic_scholar.py` + `perplexity.py`. Individual services reused. |
| **Proposal Strategist** | BUILD NEW | `assembly_plan/agent.py` does metadata only (geography, mode, phases). No evaluator-priority analysis. |
| **Slide Architect** | REPLACE `submission_transform` | `submission.py:71-87` `SlideBrief` uses `LayoutType` enum (legacy), not `semantic_layout_id` (G1). See Section 8.1. |
| **Reviewer / Red Team** | REUSE pattern from `review/agent.py` | 1-5 scoring + issues + instructions pattern is correct. New instance for proposal critique. |
| **Source Book DOCX** | EXTEND `renderer.py` | `export_report_docx()` at line 718 + `render_markdown_to_docx()` in `formatting.py` provide foundation. |
| **SourcePack construction** | REFACTOR | `graph.py:596` uses `source.summary`. Dataclass fine, construction function needs full-text path. |
| **Document loader** | BUILD NEW | `search.py:639,643`: `approved[:3]`, `5_000` chars. Must support all docs at 50k. |
| **Pipeline wiring** | REFACTOR `graph.py` | `analysis_node` defined at line 337, `research_node` at 390 -- both orphaned. Re-enable + add new nodes. |

---

*Design document v3 complete. Architecture unchanged from v2. Document structure cleaned to exactly 11 required primary sections + 3 appendices. No coding until approved.*
