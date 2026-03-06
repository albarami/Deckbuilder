# DeckForge — M5 Phase 1 Agents Design

> **Scope:** Context Agent → Retrieval Planner → Retrieval Ranker → Analysis Agent → Research Agent
> **Depends on:** M1–M4 (enums, models, state, config, LLM wrapper) — all approved and pushed.
> **Pipeline coverage:** Steps 2–5, Gates 1–3

**Date:** 2026-03-06 (revised)
**Source of truth:** Architecture doc Sections 4–5, Prompt Library Agents 1–4, Scaffold doc Section 3

---

## 1. Execution Order

Each agent is built one at a time, in pipeline order, with its own review gate. No batching.

| Order | Agent | Files | Model (from MODEL_MAP) | Gate After |
|-------|-------|-------|----------------------|------------|
| 1 | Context Agent | `src/agents/context/agent.py`, `prompts.py` | `MODEL_MAP["context_agent"]` (GPT-5.4) | Gate 1 |
| 2 | Retrieval Planner | `src/agents/retrieval/planner.py`, `prompts.py` | `MODEL_MAP["retrieval_planner"]` (GPT-5.4) | — |
| 3 | Retrieval Ranker | `src/agents/retrieval/ranker.py`, `prompts.py` (shared) | `MODEL_MAP["retrieval_ranker"]` (GPT-5.4) | Gate 2 |
| 4 | Analysis Agent | `src/agents/analysis/agent.py`, `prompts.py` | `MODEL_MAP["analysis_agent"]` (Claude Opus 4.6) | — |
| 5 | Research Agent | `src/agents/research/agent.py`, `prompts.py` | `MODEL_MAP["research_agent"]` (Claude Opus 4.6) | Gate 3 |

---

## 2. Agent Specifications

### 2.1 Context Agent

**Pipeline step:** Step 2 — Context Understanding
**Prompt Library section:** Agent 1 (lines 26–244)

**Input state fields:**
- `state.ai_assist_summary` — raw text from BD Station
- `state.uploaded_documents` — list of `UploadedDocument` (filename, content_text, language)
- `state.user_notes` — optional strategic context

**Output state fields:**
- `state.rfp_context` — `RFPContext` (the full parsed RFP object)
- `state.current_stage` — set to `PipelineStage.CONTEXT_REVIEW`

**LLM call:**
- `response_model=RFPContext`
- System prompt: verbatim from Prompt Library Agent 1
- User message: JSON of `{ai_assist_summary, uploaded_documents, user_notes}`

**Failure behavior:**
- `LLMError` → populate `state.errors`, set `state.current_stage = PipelineStage.ERROR`
- Do not crash. Return state with error info.

**Gate interaction:** After Context Agent runs, pipeline pauses at Gate 1. User reviews `rfp_context`, selects output language. Gate logic is M7.

---

### 2.2 Retrieval Planner (Pass 1)

**Pipeline step:** Step 3 — SharePoint Knowledge Retrieval (query generation)
**Prompt Library section:** Agent 2, Pass 1 (lines 248–336)

**Input state fields:**
- `state.rfp_context` — the approved `RFPContext` from Gate 1
- `state.output_language` — selected at Gate 1

**Output state fields:**
- No direct state field for queries. The planner output is an intermediate artifact consumed by the search service and then the ranker.

**Retrieval schema requirement:**
The Prompt Library defines a JSON output schema for the planner (search queries with strategy, target_criterion, language, priority) that has no corresponding centralized Pydantic model in `src/models/`. Per `.cursorrules`, all Pydantic models belong in `src/models/`, not in agent files. **Prerequisite: a centralized `RetrievalQueries` model must be added to `src/models/` and approved before the Retrieval Planner can be implemented.** This will be proposed in the Retrieval Planner implementation plan.

**LLM call:**
- `response_model` — the pending centralized `RetrievalQueries` model
- System prompt: verbatim from Prompt Library Agent 2, Pass 1
- User message: JSON of `{rfp_context, output_language}`

**Failure behavior:**
- `LLMError` → populate `state.errors`, set `state.current_stage = PipelineStage.ERROR`

**Gate interaction:** None (planner feeds into ranker, not a gate).

---

### 2.3 Retrieval Ranker (Pass 2)

**Pipeline step:** Step 3 — SharePoint Knowledge Retrieval (source ranking)
**Prompt Library section:** Agent 2, Pass 2 (lines 338–401)

**Input state fields:**
- `state.rfp_context` — for relevance assessment
- Search results from Azure AI Search (production) or local search (local dev)

**Output state fields:**
- `state.retrieved_sources` — list of `RetrievedSource` (already exists in `src/models/state.py`)
- `state.current_stage` — set to `PipelineStage.SOURCE_REVIEW`

**Retrieval schema requirement:**
The ranker output schema includes `ranked_sources` (mappable to `RetrievedSource`, which already exists) and `excluded_documents` (which has no centralized model). **Prerequisite: a `RankedSourcesOutput` wrapper model must be added to `src/models/` to hold both `ranked_sources` and `excluded_documents`, subject to approval.** Alternatively, only `ranked_sources` is mapped to state and exclusions are logged.

**LLM call:**
- `response_model` — the pending centralized output wrapper
- System prompt: verbatim from Prompt Library Agent 2, Pass 2
- User message: JSON of `{rfp_context, search_results}`

**Failure behavior:**
- `LLMError` → populate `state.errors`, set `state.current_stage = PipelineStage.ERROR`

**Gate interaction:** After ranker runs, pipeline pauses at Gate 2. Gate logic is M7.

**Dependency note:** The ranker depends on a search service to execute queries. The search service is not part of the current approved path. It will be addressed in the Retrieval agent implementation plan.

---

### 2.4 Analysis Agent

**Pipeline step:** Step 4 — Deep Analysis & Knowledge Extraction
**Prompt Library section:** Agent 3 (lines 405–617)

**Input state fields:**
- `state.rfp_context` — for criterion matching
- `state.approved_source_ids` — DOC-NNN ids approved at Gate 2
- Source document content — full text of approved documents. **Open question:** `DeckForgeState` has `approved_source_ids` but not document content. The pipeline node must load content from search/storage using these IDs. This dependency will be addressed in the Analysis Agent implementation plan.

**Output state fields:**
- `state.reference_index` — `ReferenceIndex` (already exists in `src/models/claims.py`)
- `state.current_stage` — advance past analysis

**LLM call:**
- `response_model=ReferenceIndex`
- System prompt: verbatim from Prompt Library Agent 3
- User message: JSON of `{approved_sources, rfp_context, evaluation_criteria}`

**Failure behavior:**
- `LLMError` → populate `state.errors`, set `state.current_stage = PipelineStage.ERROR`
- Claude Opus 4.6 agent — may hit context limits with large document sets. Error handling must be robust.

**Gate interaction:** None between Analysis and Research.

---

### 2.5 Research Agent

**Pipeline step:** Step 5 — Research Report Generation
**Prompt Library section:** Agent 4 (lines 621–763)

**Input state fields:**
- `state.reference_index` — the full `ReferenceIndex` from Analysis Agent
- `state.rfp_context` — for report structuring
- `state.output_language` — for language selection
- `state.user_notes` — optional strategic positioning guidance

**Output state fields:**
- `state.research_report` — `ResearchReport` (already exists in `src/models/report.py`)
- `state.report_markdown` — the full report as a single markdown string
- `state.current_stage` — set to `PipelineStage.REPORT_REVIEW`

**LLM call:**
- `response_model=ResearchReport`
- System prompt: verbatim from Prompt Library Agent 4
- User message: JSON of `{reference_index, rfp_context, output_language, user_strategic_notes}`

**Failure behavior:**
- `LLMError` → populate `state.errors`, set `state.current_stage = PipelineStage.ERROR`
- Architecture doc Section 9: "Partial report saved. User notified. Can retry from last checkpoint."

**Gate interaction:** After Research Agent runs, pipeline pauses at Gate 3 (the most important gate). Gate logic is M7.

**Risk — output size:** `ResearchReport` may be large enough to challenge structured output token limits. This is an open question to be evaluated during implementation. No contract changes are proposed at this time.

---

## 3. Interface Gaps Identified

| Gap | Description | Resolution Path | When |
|-----|-------------|----------------|------|
| No state field for search queries | Retrieval Planner output has no `DeckForgeState` field | Keep as transient; pipeline node chains planner→search→ranker | Retrieval Planner impl plan |
| No centralized `RetrievalQueries` model | Planner output schema has no Python model in `src/models/` | Propose as prerequisite centralized model addition, subject to approval | Retrieval Planner impl plan |
| No centralized ranker output wrapper | Ranker output includes `excluded_documents` not in any model | Propose `RankedSourcesOutput` or map only `ranked_sources` to `RetrievedSource` | Retrieval Ranker impl plan |
| No document content in state | `approved_source_ids` exists but not full text | Pipeline node loads content from storage; addressed in Analysis Agent impl plan | Analysis Agent impl plan |
| Research Agent output size | May challenge structured output limits | Open question — evaluate during implementation, no contract changes proposed | Research Agent impl plan |

---

## 4. M5 vs M6/M7 Scope

### M5 builds (this milestone)

- Context Agent (agent.py + prompts.py + test)
- Retrieval Planner (planner.py + prompts.py + test) — after schema prerequisite approved
- Retrieval Ranker (ranker.py + prompts.py shared + test) — after schema prerequisite approved
- Analysis Agent (agent.py + prompts.py + test)
- Research Agent (agent.py + prompts.py + test)

### Not in M5 current approved path

- Search service (`src/services/search.py`) — deferred to Retrieval agent planning
- Pipeline wiring between agents
- Gate logic
- PPTX rendering
- SharePoint integration

### M6 builds (next milestone)

- Structure Agent, Content Agent, QA Agent, Conversation Manager

### M7 builds (later)

- LangGraph StateGraph, gate logic, pipeline orchestration, CLI runner

---

## 5. Common Agent Pattern (from .cursorrules)

Every M5 agent follows this exact structure:

```python
# src/agents/<name>/agent.py
from src.config.models import MODEL_MAP
from src.models.state import DeckForgeState
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT

async def run(state: DeckForgeState) -> DeckForgeState:
    """<Agent Name> — <one line description>."""
    # 1. Extract inputs from state
    # 2. Build user_message JSON from state data
    # 3. Call LLM: result = await call_llm(model=MODEL_MAP["<name>"], ...)
    # 4. Use result.parsed (LLMResponse.parsed), not raw return
    # 5. Update state with result.parsed
    # 6. Update state.current_stage
    # 7. On LLMError: populate state.errors, set stage to ERROR
    # 8. Return state
```

Every agent uses `result.parsed` from `LLMResponse[T]`, never assumes a direct model return.

---

*End of M5 Phase 1 Agents Design (revised) | DeckForge | 2026-03-06*
