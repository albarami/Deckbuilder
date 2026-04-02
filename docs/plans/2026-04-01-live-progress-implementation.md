# Source Book Live Progress — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Source Book pipeline session visibly alive during long waits — accurate agent grid, live stage updates, true end-to-end cost.

**Architecture:** Enrich existing `stage_change` SSE events with `agent_runs` + `session_metadata` payload. Add pre-invoke optimistic broadcast for immediate feedback after Gate 2. Shared cost helper replaces scattered inline accounting. Frontend hydrates agent state from SSE, not just /status polling.

**Tech Stack:** FastAPI + LangGraph (backend), React 18 + TypeScript + Zustand + next-intl (frontend), Vitest

---

## Task 1: LLMResponse.cost_usd + shared accounting helper

**Files:**
- Modify: `src/services/llm.py:144-151`
- Create: `src/services/session_accounting.py`
- Create: `src/services/test_session_accounting.py`

**Step 1: Add cost_usd to LLMResponse**

In `src/services/llm.py`, add `cost_usd: float = 0.0` to the `LLMResponse` dataclass (after line 151). In `call_llm()` (around line 382), after computing `cost = _compute_cost(...)`, set it on the response object.

The dataclass becomes:
```python
class LLMResponse(Generic[T]):
    """Wrapper holding the parsed model, token counts, and metadata."""
    parsed: T
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: float
    cost_usd: float = 0.0
```

In `call_llm()`, after line 382 where `cost` is computed, before the `_call_log.append(...)`:
```python
# Set cost on the response object so callers can propagate it
response.cost_usd = cost
```

Where `response` is the `LLMResponse` object being returned.

**Step 2: Create session_accounting.py**

Create `src/services/session_accounting.py`:
```python
"""Shared session accounting helpers.

Single source of truth for updating SessionMetadata from LLM call results.
Replaces scattered inline session mutation across agent files.
"""

from __future__ import annotations

from src.models.state import SessionMetadata
from src.services.llm import LLMResponse


def update_session_from_llm(
    session: SessionMetadata,
    llm_result: LLMResponse,
) -> SessionMetadata:
    """Increment session accounting from a call_llm() result.

    Returns a new SessionMetadata copy. Does not mutate the input.
    """
    updated = session.model_copy(deep=True)
    updated.total_llm_calls += 1
    updated.total_input_tokens += llm_result.input_tokens
    updated.total_output_tokens += llm_result.output_tokens
    updated.total_cost_usd += llm_result.cost_usd
    return updated


def update_session_from_raw(
    session: SessionMetadata,
    *,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> SessionMetadata:
    """Increment session accounting from raw values.

    For agents that call the Anthropic client directly (not via call_llm).
    Returns a new SessionMetadata copy. Does not mutate the input.
    """
    updated = session.model_copy(deep=True)
    updated.total_llm_calls += 1
    updated.total_input_tokens += input_tokens
    updated.total_output_tokens += output_tokens
    updated.total_cost_usd += cost_usd
    return updated
```

**Step 3: Write test**

Create `src/services/test_session_accounting.py`:
```python
"""Tests for session accounting helpers."""

from src.models.state import SessionMetadata
from src.services.session_accounting import update_session_from_llm, update_session_from_raw


class _FakeLLMResponse:
    input_tokens = 1000
    output_tokens = 500
    cost_usd = 0.025


def test_update_session_from_llm():
    session = SessionMetadata(session_id="test")
    result = update_session_from_llm(session, _FakeLLMResponse())
    assert result.total_llm_calls == 1
    assert result.total_input_tokens == 1000
    assert result.total_output_tokens == 500
    assert result.total_cost_usd == 0.025
    # Original unchanged
    assert session.total_llm_calls == 0


def test_update_session_from_llm_accumulates():
    session = SessionMetadata(session_id="test", total_llm_calls=2, total_cost_usd=0.05)
    result = update_session_from_llm(session, _FakeLLMResponse())
    assert result.total_llm_calls == 3
    assert result.total_cost_usd == 0.075


def test_update_session_from_raw():
    session = SessionMetadata(session_id="test")
    result = update_session_from_raw(session, input_tokens=800, output_tokens=300, cost_usd=0.018)
    assert result.total_llm_calls == 1
    assert result.total_input_tokens == 800
    assert result.total_output_tokens == 300
    assert result.total_cost_usd == 0.018
```

**Step 4: Verify**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -c "from src.services.session_accounting import update_session_from_llm, update_session_from_raw; print('OK')"`

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -m pytest src/services/test_session_accounting.py -v`

**Step 5: Commit**

```
git add src/services/llm.py src/services/session_accounting.py src/services/test_session_accounting.py
git commit -m "feat: add LLMResponse.cost_usd and shared session accounting helpers"
```

---

## Task 2: Source Book agent cost propagation

**Files:**
- Modify: `src/agents/source_book/writer.py:1564-1571`
- Modify: `src/agents/source_book/reviewer.py` (session update area)
- Modify: `src/agents/source_book/evidence_extractor.py:195-367`
- Modify: `src/pipeline/graph.py` (~line 750, evidence extractor caller)

**Step 1: Writer accumulator**

In `src/agents/source_book/writer.py`, replace the coarse session update (lines 1564-1567):
```python
# OLD:
session = state.session.model_copy(deep=True)
session.total_llm_calls += 8
```

With accumulator pattern. At the start of `run()`, initialize:
```python
from src.services.session_accounting import update_session_from_llm
accumulated_session = state.session.model_copy(deep=True)
```

After each of the 8 internal `call_llm()` calls (Section 1, Section 2, Section 3, Section 4, Section 5 methodology, Section 5 governance, Section 6, Section 7), add:
```python
accumulated_session = update_session_from_llm(accumulated_session, stage_result)
```

At return, use `accumulated_session` instead of the manual `session`:
```python
return {"source_book": source_book, "session": accumulated_session, "fallback_events": fallback_events}
```

**Step 2: Reviewer helper**

In `src/agents/source_book/reviewer.py`, find the inline session mutation (similar pattern: `session.total_llm_calls += 1`, etc.). Replace with:
```python
from src.services.session_accounting import update_session_from_llm
session = update_session_from_llm(state.session, llm_result)
```

**Step 3: Evidence extractor usage info**

In `src/agents/source_book/evidence_extractor.py`, change `extract_evidence_ledger()` return to include usage. After the `response = await client.messages.create(...)` call (line 224), extract usage:

```python
usage_info = None
if hasattr(response, "usage") and response.usage:
    from src.services.llm import _compute_cost
    ext_input = response.usage.input_tokens
    ext_output = response.usage.output_tokens
    ext_cost = _compute_cost("claude-sonnet-4-20250514", ext_input, ext_output)
    usage_info = {"input_tokens": ext_input, "output_tokens": ext_output, "cost_usd": ext_cost}
```

Change the return statements to return tuples:
- Success: `return filtered, usage_info`
- JSON error: `return [], None`
- General error: `return [], None`

**Step 4: Graph.py caller update**

In `src/pipeline/graph.py`, update the `extract_evidence_ledger` call site (~line 750):

```python
# OLD:
ledger_entries = await extract_evidence_ledger(final_sb)

# NEW:
ledger_result = await extract_evidence_ledger(final_sb)
ledger_entries, extractor_usage = ledger_result if isinstance(ledger_result, tuple) else (ledger_result, None)

# Propagate extractor cost to session
if extractor_usage:
    from src.services.session_accounting import update_session_from_raw
    current_state = current_state.model_copy(
        update={"session": update_session_from_raw(
            current_state.session,
            input_tokens=extractor_usage["input_tokens"],
            output_tokens=extractor_usage["output_tokens"],
            cost_usd=extractor_usage["cost_usd"],
        )},
    )
```

**Step 5: Verify**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -c "from src.agents.source_book.writer import run; print('OK')"`
Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -c "from src.pipeline.graph import source_book_node; print('OK')"`

**Step 6: Commit**

```
git add src/agents/source_book/writer.py src/agents/source_book/reviewer.py src/agents/source_book/evidence_extractor.py src/pipeline/graph.py
git commit -m "feat: propagate real cost/tokens through SB writer, reviewer, evidence extractor"
```

---

## Task 3: Early SB-path agent cost lines

**Files:**
- Modify: `src/agents/context/agent.py` (~line 42)
- Modify: `src/agents/retrieval/planner.py` (~line 39)
- Modify: `src/agents/retrieval/ranker.py` (~line 37)
- Modify: `src/agents/proposal_strategy/agent.py` (~line 150)
- Modify: `src/agents/external_research/agent.py` (_update_session function)

**Step 1: Add cost_usd line to 4 inline-mutation agents**

Each of context, planner, ranker, and proposal_strategy has this pattern:
```python
state.session.total_input_tokens += result.input_tokens
state.session.total_output_tokens += result.output_tokens
state.session.total_llm_calls += 1
```

Add ONE line after each block:
```python
state.session.total_cost_usd += result.cost_usd
```

**Step 2: External research agent**

In `src/agents/external_research/agent.py`, replace `_update_session()` (lines 803-809) with:
```python
def _update_session(state: DeckForgeState, llm_result) -> object:
    """Update session metadata with token usage and cost."""
    from src.services.session_accounting import update_session_from_llm
    return update_session_from_llm(state.session, llm_result)
```

**Step 3: Verify**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -c "from src.agents.context.agent import run; print('OK')"`
Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -c "from src.agents.proposal_strategy.agent import run; print('OK')"`

**Step 4: Commit**

```
git add src/agents/context/agent.py src/agents/retrieval/planner.py src/agents/retrieval/ranker.py src/agents/proposal_strategy/agent.py src/agents/external_research/agent.py
git commit -m "feat: add cost_usd propagation to all SB-path agents"
```

---

## Task 4: Backend SSE enrichment + optimistic broadcast

**Files:**
- Modify: `backend/models/api_models.py` (SSEEvent class, ~line 658)
- Modify: `backend/services/pipeline_runtime.py` (advance_source_book_session + _sync_source_book_session + _derive_source_book_agent_runs)

**Step 1: Enrich SSEEvent model**

In `backend/models/api_models.py`, add two optional fields to `SSEEvent` (after the existing fields):
```python
agent_runs: list[dict] | None = None
session_metadata: dict | None = None
```

**Step 2: Add proposal_strategist to _derive_source_book_agent_runs**

In `backend/services/pipeline_runtime.py`, in `_derive_source_book_agent_runs()`, add to the agent list (between routing_agent and sb_writer):
```python
("proposal_strategist", "Proposal Strategist", "Claude Opus 4.6", "Win themes", "evidence_curation", 3),
```

Add status derivation:
```python
if state.proposal_strategy:
    runs["proposal_strategist"].status = AgentRunStatus.COMPLETE
    win_themes = getattr(state.proposal_strategy, "win_themes", [])
    runs["proposal_strategist"].metric_value = f"{len(win_themes)} themes"
```

Add to `stage_to_agents` map:
```python
PipelineStage.EVIDENCE_CURATION.value: ["evidence_curator", "routing_agent", "proposal_strategist"],
```

**Step 3: Pre-invoke optimistic broadcast**

In `advance_source_book_session()`, BEFORE `graph.ainvoke()` (before line 199), add:

```python
# Pre-invoke optimistic broadcast for immediate UI feedback
if resume_payload is not None and resume_payload.get("approved"):
    last_gate_num = session.completed_gates[-1].gate_number if session.completed_gates else 0
    if last_gate_num == 2:
        # Gate 2 approved → evidence curation about to start
        optimistic_stage = "evidence_curation"
        optimistic_label = "Evidence Curation"
        optimistic_runs = _derive_source_book_agent_runs(
            session.graph_state or _build_initial_state(session, session_manager)
        )
        # Force evidence_curator to RUNNING for optimistic display
        for r in optimistic_runs:
            if r.agent_key == "evidence_curator" and r.status == AgentRunStatus.WAITING:
                r.status = AgentRunStatus.RUNNING
                r.metric_value = "running"
                break
        session_manager.update_stage(
            session.session_id, optimistic_stage,
            stage_label=optimistic_label, step_number=4,
        )
        await broadcaster.broadcast(
            session.session_id,
            _build_event(
                "stage_change",
                session_id=session.session_id,
                stage=optimistic_stage,
                stage_key=optimistic_stage,
                stage_label=optimistic_label,
                step_number=4,
                agent_runs=[r.model_dump() for r in optimistic_runs],
                message=optimistic_label,
            ),
        )
```

Note: broadcasts include BOTH `stage` and `stage_key` so both ActivityTimeline (`event.stage`) and the store (`event.stage_key`) work correctly.

**Step 4: Post-invoke broadcast in _sync_source_book_session**

In `_sync_source_book_session()`, after the agent_runs and stage update (after line 295), before error/gate handling:

```python
# Post-invoke broadcast with real agent state + session metadata
status_response = session_manager.get(session.session_id)
metadata_dict = None
if status_response:
    sr = status_response.to_status_response()
    metadata_dict = sr.session_metadata.model_dump() if sr.session_metadata else None

await broadcaster.broadcast(
    session.session_id,
    _build_event(
        "stage_change",
        session_id=session.session_id,
        stage=stage_key,
        stage_key=stage_key,
        stage_label=stage_label,
        step_number=step_number,
        agent_runs=[r.model_dump() for r in agent_runs],
        session_metadata=metadata_dict,
        message=stage_label,
    ),
)
```

**Step 5: Verify**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -c "from backend.services.pipeline_runtime import advance_source_book_session; print('OK')"`
Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -c "from backend.models.api_models import SSEEvent; e = SSEEvent(type='test'); print('agent_runs' in e.model_fields); print('OK')"`

**Step 6: Commit**

```
git add backend/models/api_models.py backend/services/pipeline_runtime.py
git commit -m "feat: SSE stage_change with agent_runs payload + pre-invoke optimistic broadcast"
```

---

## Task 5: Frontend SSE event type + store hydration

**Files:**
- Modify: `frontend/src/lib/types/pipeline.ts` (SSEEvent interface)
- Modify: `frontend/src/stores/pipeline-store.ts:236-239` (handleSSEEvent stage_change case)
- Test: `frontend/src/stores/pipeline-store.test.ts`

**Step 1: Add fields to SSEEvent type**

In `frontend/src/lib/types/pipeline.ts`, find the `SSEEvent` interface and add:
```ts
agent_runs?: AgentRunInfo[];
session_metadata?: SessionMetadata;
```

**Step 2: Update handleSSEEvent**

In `frontend/src/stores/pipeline-store.ts`, replace the `stage_change` case (lines 237-239):

```typescript
// OLD:
case "stage_change":
  if (event.stage) store.setStage(event.stage);
  break;

// NEW:
case "stage_change":
  if (event.stage) store.setStage(event.stage);
  if (event.agent_runs) {
    set({ agentRuns: event.agent_runs });
  }
  if (event.session_metadata) {
    set({ sessionMetadata: event.session_metadata });
  }
  break;
```

**Step 3: Write tests**

In `frontend/src/stores/pipeline-store.test.ts`, add:

```typescript
it("stage_change with agent_runs updates store agentRuns", () => {
  const { result } = renderHook(() => usePipelineStore());
  act(() => {
    result.current.handleSSEEvent({
      type: "stage_change",
      timestamp: new Date().toISOString(),
      stage: "evidence_curation",
      agent_runs: [
        { agent_key: "evidence_curator", agent_label: "Evidence Curator", model: "Claude", status: "running", metric_label: "Evidence", metric_value: "running", step_key: "evidence_curation", step_number: 3 },
      ],
    } as SSEEvent);
  });
  expect(result.current.agentRuns).toHaveLength(1);
  expect(result.current.agentRuns[0].agent_key).toBe("evidence_curator");
});

it("stage_change without agent_runs preserves existing agentRuns", () => {
  const { result } = renderHook(() => usePipelineStore());
  const existing = [{ agent_key: "context_agent", agent_label: "Context", model: "GPT", status: "complete" as const, metric_label: "m", metric_value: "v", step_key: "s", step_number: 1 }];
  act(() => { result.current.setAgentRuns(existing); });
  act(() => {
    result.current.handleSSEEvent({
      type: "stage_change",
      timestamp: new Date().toISOString(),
      stage: "source_research",
    } as SSEEvent);
  });
  expect(result.current.agentRuns).toEqual(existing);
});
```

**Step 4: Verify**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson\frontend" && npx tsc --noEmit --pretty 2>&1 | head -10`
Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson\frontend" && npx vitest run src/stores/pipeline-store.test.ts --reporter=verbose 2>&1 | tail -15`

**Step 5: Commit**

```
git add frontend/src/lib/types/pipeline.ts frontend/src/stores/pipeline-store.ts frontend/src/stores/pipeline-store.test.ts
git commit -m "feat: hydrate agentRuns and sessionMetadata from stage_change SSE events"
```

---

## Task 6: AgentStatusGrid SB agent ordering

**Files:**
- Modify: `frontend/src/components/pipeline/AgentStatusGrid.tsx:12-24`
- Test: update/add tests in `AgentStatusGrid.test.tsx` (if exists) or create

**Step 1: Add SB agent order and proposalMode branching**

In `AgentStatusGrid.tsx`, add after the existing `AGENT_ORDER` (line 24):

```typescript
const SB_AGENT_ORDER = [
  "context_agent",
  "retrieval_planner",
  "retrieval_ranker",
  "evidence_curator",
  "routing_agent",
  "proposal_strategist",
  "sb_writer",
  "sb_reviewer",
  "sb_evidence_extractor",
];
```

Import `usePipelineStore` and read `proposalMode`:
```typescript
const proposalMode = usePipelineStore((s) => s.proposalMode);
const agentOrder = proposalMode === "source_book_only" ? SB_AGENT_ORDER : AGENT_ORDER;
```

Replace usages of `AGENT_ORDER` in the component with `agentOrder`.

**Step 2: Write tests**

Test that SB agent order is used when `proposalMode === "source_book_only"` and deck order is used for `"standard"`. Mock the store to provide `proposalMode` and appropriate `agentRuns` data.

**Step 3: Verify**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson\frontend" && npx vitest run src/components/pipeline/AgentStatusGrid.test.tsx --reporter=verbose 2>&1 | tail -15`

**Step 4: Commit**

```
git add frontend/src/components/pipeline/AgentStatusGrid.tsx frontend/src/components/pipeline/AgentStatusGrid.test.tsx
git commit -m "feat: SB agent ordering in AgentStatusGrid for source_book_only mode"
```

---

## Task 7: PipelineProgressBar + ActivityTimeline stage mappings

**Files:**
- Modify: `frontend/src/components/pipeline/PipelineProgressBar.tsx:25-56` (STAGES stageKeys)
- Modify: `frontend/src/components/pipeline/ActivityTimeline.tsx:186-211` (formatStageLabel)
- Modify: `frontend/src/components/pipeline/ActivityTimeline.tsx:214-243` (formatBackendAgentName)
- Modify: `frontend/src/components/pipeline/ActivityTimeline.tsx:102-111` (stage_change long hint)

**Step 1: PipelineProgressBar stage keys**

In `PipelineProgressBar.tsx`, the `sourceBook` stage definition (line 38-43) already has `source_book_generation` in `stageKeys`. Add `evidence_curation`, `proposal_strategy`, and `source_book_review`:

```typescript
{
  id: "sourceBook",
  gateNumber: 3,
  labelKey: "stages.sourceBook",
  stageKeys: [
    "report_generation", "report", "source_book_generation", "source_book",
    "evidence_curation", "proposal_strategy", "source_book_review",
  ],
},
```

These all collapse into the "Source Book" step in the 3-step bar.

**Step 2: ActivityTimeline formatStageLabel**

In `ActivityTimeline.tsx`, add cases to `formatStageLabel()` (after line 208):

```typescript
case "evidence_curation":
  return t("stages.evidenceCuration");
case "proposal_strategy":
  return t("stages.proposalStrategy");
case "source_book_generation":
  return t("stages.sourceBookGeneration");
case "source_book_review":
  return t("stages.sourceBookReview");
```

**Step 3: ActivityTimeline formatBackendAgentName**

Add SB agent cases (after line 240, before the default):

```typescript
case "evidence_curator":
  return t("agents.evidenceCurator");
case "routing_agent":
  return t("agents.routingAgent");
case "proposal_strategist":
  return t("agents.proposalStrategist");
case "sb_writer":
  return t("agents.sbWriter");
case "sb_reviewer":
  return t("agents.sbReviewer");
case "sb_evidence_extractor":
  return t("agents.sbEvidenceExtractor");
```

**Step 4: Long-stage hint**

In `ActivityTimeline.tsx`, in the `stage_change` case of `mapEventToItem()` (lines 103-111), add a hint for long SB stages:

```typescript
case "stage_change": {
  const stageLabel = formatStageLabel(event.stage, t);
  const isLongStage = event.stage === "evidence_curation" || event.stage === "source_book_generation";
  return {
    id: `stage-${index}`,
    label: isLongStage
      ? `${t("timelineStageChanged", { stage: stageLabel })} ${t("longStageHint")}`
      : t("timelineStageChanged", { stage: stageLabel }),
    timestamp: event.timestamp,
    tone: "info",
  };
}
```

**Step 5: Commit**

```
git add frontend/src/components/pipeline/PipelineProgressBar.tsx frontend/src/components/pipeline/ActivityTimeline.tsx
git commit -m "feat: map SB stages and agents in progress bar and activity timeline"
```

---

## Task 8: i18n keys

**Files:**
- Modify: `frontend/src/i18n/messages/en.json`
- Modify: `frontend/src/i18n/messages/ar.json`

**Step 1: Add stage labels under "pipeline" → "stages"**

English (in `"stages"` object, after existing entries):
```json
"evidenceCuration": "Evidence Curation",
"proposalStrategy": "Proposal Strategy",
"sourceBookGeneration": "Source Book Generation",
"sourceBookReview": "Source Book Review"
```

**Step 2: Add agent labels under "pipeline" → "agents"**

If there is no `"agents"` sub-object yet, create it as a sibling to `"stages"`. If `"agents"` already exists with deck agent keys, add the SB keys:

```json
"agents": {
  "context": "Context Agent",
  "retrievalPlanner": "Retrieval Planner",
  "ranker": "Ranker Agent",
  "analysis": "Analysis Agent",
  "research": "Research Agent",
  "draft": "Draft Agent",
  "review": "Review Agent",
  "refine": "Refine Agent",
  "finalReview": "Final Review Agent",
  "presentation": "Presentation Agent",
  "qa": "QA Agent",
  "evidenceCurator": "Evidence Curator",
  "routingAgent": "Routing Agent",
  "proposalStrategist": "Proposal Strategist",
  "sbWriter": "Source Book Writer",
  "sbReviewer": "Source Book Reviewer",
  "sbEvidenceExtractor": "Evidence Extractor"
}
```

**Step 3: Add long stage hint**

Under `"pipeline"`:
```json
"longStageHint": "(this may take several minutes)"
```

**Step 4: Arabic equivalents**

Same structure with Arabic translations. Stage labels:
- Evidence Curation → تنظيم الأدلة
- Proposal Strategy → استراتيجية العرض
- Source Book Generation → إنشاء كتاب المصدر
- Source Book Review → مراجعة كتاب المصدر

Agent labels:
- Evidence Curator → منظم الأدلة
- Routing Agent → وكيل التوجيه
- Proposal Strategist → استراتيجي العرض
- Source Book Writer → كاتب كتاب المصدر
- Source Book Reviewer → مراجع كتاب المصدر
- Evidence Extractor → مستخرج الأدلة

Long stage hint → (قد يستغرق هذا عدة دقائق)

**Step 5: Commit**

```
git add frontend/src/i18n/messages/en.json frontend/src/i18n/messages/ar.json
git commit -m "feat(i18n): add SB stage labels, agent labels, and long-stage hint"
```

---

## Task 9: Full verification

**Step 1: TypeScript check**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson\frontend" && npx tsc --noEmit --pretty`
Expected: 0 errors

**Step 2: Full frontend test suite**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson\frontend" && npx vitest run --reporter=verbose`
Expected: all tests pass (37+ existing + new store/grid tests)

**Step 3: Backend imports**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -c "from backend.services.pipeline_runtime import advance_source_book_session; from src.services.session_accounting import update_session_from_llm; from src.services.llm import LLMResponse; print('ALL OK')"`

**Step 4: Backend unit tests**

Run: `cd "C:\Projects\Deckbuilder\.claude\worktrees\agitated-williamson" && python -m pytest src/services/test_session_accounting.py -v`

---

## Summary

| Task | Scope | Files |
|------|-------|-------|
| 1 | LLMResponse.cost_usd + helpers | llm.py, session_accounting.py, test |
| 2 | SB agent cost (writer/reviewer/extractor) | writer.py, reviewer.py, evidence_extractor.py, graph.py |
| 3 | Early agent cost (1-line adds) | context, planner, ranker, strategy, external_research |
| 4 | Backend SSE enrichment + optimistic broadcast | api_models.py, pipeline_runtime.py |
| 5 | Frontend store hydration from SSE | pipeline.ts types, pipeline-store.ts, test |
| 6 | AgentStatusGrid SB ordering | AgentStatusGrid.tsx, test |
| 7 | ProgressBar + Timeline stage/agent mappings | PipelineProgressBar.tsx, ActivityTimeline.tsx |
| 8 | i18n keys | en.json, ar.json |
| 9 | Full verification | all |

Total: ~15 files changed, 2 created, ~9 commits.
