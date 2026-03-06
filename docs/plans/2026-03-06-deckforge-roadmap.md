# DeckForge — Full System Roadmap

> **Current milestone: Foundation (Phase 0) only.**
> No agent code, no pipeline, no rendering until foundation is reviewed and approved.

**Date:** 2026-03-06
**Status:** Planning — awaiting Salim review before any implementation begins

---

## Milestone Sequence

| # | Milestone | Scope | Gate | Status |
|---|-----------|-------|------|--------|
| M0 | Project Scaffold + README | Folders, config, .gitignore, requirements, venv, README.md | Salim approved | **IN PROGRESS** — README.md pending |
| M1 | Foundation: Enums | `src/models/enums.py` — all 19 StrEnum classes | Salim review | **NEXT** (after README) |
| M2 | Foundation: Pydantic Models | 9 model files (`common.py` through `indexing.py`) | Salim review | Blocked on M1 |
| M3 | Foundation: Master State | `src/models/state.py` + `src/utils/ids.py` + `src/models/__init__.py` re-export | Salim review | Blocked on M2 |
| M4 | Foundation: Config + LLM Wrapper | `src/config/` + `src/services/llm.py` | Salim review | Blocked on M3 |
| M5 | Agents Phase 1 | Context → Retrieval → Analysis → Research (pipeline order) | Per-agent review | Blocked on M4 |
| M6 | Agents Phase 2 | Structure → Content → QA → Conversation Manager | Per-agent review | Blocked on M5 |
| M7 | Pipeline Wiring | LangGraph StateGraph, gates, CLI runner | Integration review | Blocked on M6 |
| M8 | PPTX Rendering | Design Agent (deterministic), template map | Render review | Blocked on M7 |
| M9 | Knowledge Layer | SharePoint indexing, Azure AI Search, extractors | Production review | Deferred |
| M10 | Integration & QA | BD Station API, observability, security, load testing | System review | Deferred |

---

## What Gets Built NOW vs Later

### NOW — Foundation (M1–M3)

These milestones produce the type system that every agent, service, and pipeline component depends on. Nothing can import `DeckForgeState`, `ClaimObject`, or `LayoutType` until these files exist and pass tests.

| Milestone | Creates | Why It Must Be First |
|-----------|---------|---------------------|
| M1: Enums | `src/models/enums.py` (19 StrEnum classes, ~210 lines) | Every model file imports enums. Nothing compiles without them. |
| M2: Models | `src/models/common.py`, `rfp.py`, `claims.py`, `report.py`, `slides.py`, `actions.py`, `waiver.py`, `qa.py`, `indexing.py` | Every agent's I/O contract is defined by these models. State depends on all of them. |
| M3: State | `src/models/state.py` + `src/utils/ids.py` + `src/models/__init__.py` | The master LangGraph state object, ID generators, and central re-export. Imports from every model file. Every agent reads/writes this. |

### NEXT — Config + LLM Wrapper (M4, after foundation review)

| Milestone | Creates | Why It Waits |
|-----------|---------|-------------|
| M4: Config + LLM | `src/config/settings.py`, `src/config/models.py`, `src/services/llm.py` | Requires models to exist for `response_model` parameter typing. Not part of the model layer — it's the service layer. Separate review cycle. |

### LATER — Agents and Beyond (M5+)

Each agent is built one at a time, in pipeline order, with its own test suite. No batching. Each agent gets its own review gate before the next begins.

---

## Dependency Graph

```
M0: Scaffold + README (in progress — README pending)
  └── M1: Enums
        └── M2: Pydantic Models (common → rfp → claims → report → slides → actions → waiver → qa → indexing)
              └── M3: Master State + ids.py + __init__.py re-export (imports ALL model files)
                    └── M4: Config + LLM Wrapper (imports models for response_model typing)
                          └── M5: Agents Phase 1 (Context → Retrieval → Analysis → Research)
                                └── M6: Agents Phase 2 (Structure → Content → QA → Conversation)
                                      └── M7: Pipeline Wiring (LangGraph StateGraph)
                                            └── M8: PPTX Rendering
                                                  └── M9: Knowledge Layer (deferred)
                                                        └── M10: Integration & QA (deferred)
```

Each arrow is a hard dependency — the child cannot begin until the parent is reviewed and approved.

---

## Review Gates

Every milestone has an explicit review gate before the next milestone begins.

| Gate | What Salim Reviews | Approval Criteria |
|------|-------------------|-------------------|
| G-M0 | README.md | Project purpose, architecture summary, milestone status, local setup, test commands, repo workflow. |
| G-M1 | `enums.py` + test file | All 19 StrEnum classes match Prompt Library Appendix A exactly. Tests pass. `ruff` + `mypy` clean. |
| G-M2 | 9 model files + test files | Every model matches State Schema doc verbatim. All cross-imports resolve. Tests pass. `ruff` + `mypy` clean. |
| G-M3 | `state.py` + `ids.py` + `__init__.py` + test files | `DeckForgeState` matches Section 11. `ids.py` matches Section 12. `__init__.py` matches Section 13. Imports all models. Serializes to/from JSON. Tests pass. `ruff` + `mypy` clean. |
| G-M4 | `settings.py` + `models.py` + `llm.py` + tests | MODEL_MAP matches architecture doc. Settings loads from `.env`. LLM wrapper handles both OpenAI and Anthropic. Retry logic works. |
| G-M5..M6 | Per-agent: `agent.py` + `prompts.py` + test file | Output matches Prompt Library schemas. System prompt is verbatim from doc. At least 3 test cases per agent. |
| G-M7 | `graph.py` + `gates.py` + `workflow.py` | Agents wired in correct pipeline order. Gates interrupt for human input. State persists between agents. |
| G-M8 | `renderer.py` + template map | Renders valid PPTX from SlideObjects. Template compliance passes. |

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| State Schema doc has a typo/inconsistency with Prompt Library | Model code breaks at integration | Cross-reference during M2: every field in state-schema.md is checked against prompt-library.md I/O schemas |
| `ChartSpec.x_axis`/`y_axis` use `dict` instead of typed model | Loose typing propagates to agents | Accept as-is per State Schema v1.1 spec; flag for Salim if problematic |
| `SlideMove.from_` alias pattern is tricky with `extra="forbid"` | Pydantic validation may reject `from` key | Test explicitly with raw JSON containing `"from"` key |
| `actions.py` discriminated union requires exact `Literal` typing | Any enum value drift breaks deserialization | Test all 11 action types with fixture data |
| LLM wrapper must handle both OpenAI and Anthropic with different APIs | Abstraction leak if not clean | Design in M4, implement with strategy pattern, test with mocks |

---

## Constraints

- **Cursor builds, Codex reviews** — all code written by Cursor, reviewed by Salim
- **No commits without approval** — Salim must explicitly say "commit"
- **No batching foundation milestones** — M1, M2, M3 are separate review cycles
- **Docs are source of truth** — if code contradicts docs, fix the code
- **No agent code in foundation** — foundation is pure data models, utilities, and config
- **Remote:** `origin` is `https://github.com/albarami/Deckbuilder.git` — all approved commits/pushes target that remote
- **README.md required** — M0 is not complete until README exists; README must precede M1

---

*End of Roadmap | DeckForge | 2026-03-06*
