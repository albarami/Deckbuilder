# DeckForge — Foundation Design Document

> **Scope: M1 (Enums) + M2 (Pydantic Models) + M3 (Master State) + design prep for M4 (Config/LLM)**
> M4 implementation is explicitly deferred until M1–M3 are reviewed.

**Date:** 2026-03-06
**Source of truth:** `docs/DeckForge-State-Schema-v1.1.md`
**Cross-reference:** `docs/DeckForge-Prompt-Library-v1.4.md` Appendix A (enums), Appendix C (ID patterns)

---

## M1: Enums — `src/models/enums.py`

### What

One file. 19 `StrEnum` classes. Copied verbatim from State Schema v1.1, Section 1. These are the canonical enum values from Prompt Library Appendix A.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Base class | `StrEnum` (stdlib `enum`) | Python 3.12+ native. Serializes as strings. No extra dependency. |
| Naming | Class names `PascalCase`, values match Appendix A exactly | Values are API contract — must be exact strings. |
| Number of classes | 19 | LayoutType, SensitivityTag, GapSeverity, QAIssueType, QASlideStatus, ActionScope, ActionType, Language, DocumentType, ClaimCategory, SearchStrategy, QueryPriority, PipelineStage, PresentationType, UserRole, ApprovalLevel, ConfidentialityLevel, ExtractionQuality, RenderStatus |

### Files

| File | Action | Lines (est.) |
|------|--------|-------------|
| `src/models/enums.py` | Create | ~213 |
| `tests/agents/test_enums.py` | Create | ~80 |

### Acceptance Criteria

1. All 19 classes present with exact member names and values from State Schema Section 1
2. Every value in Prompt Library Appendix A is represented
3. `ruff check src/models/enums.py` and `mypy src/models/enums.py` pass with zero errors
4. All tests pass: enum membership, string serialization, iteration

### Risks

- None. This is a direct transcription. The only risk is a typo.

---

## M2: Pydantic Models — `src/models/*.py`

### What

9 model files. Copied verbatim from State Schema v1.1, Sections 2–10. These define every data structure in the DeckForge pipeline (except master state).

### Dependency Order (Build Sequence)

Models must be created in this order because of import dependencies:

```
1. common.py        — no internal imports (only pydantic, datetime)
2. rfp.py           — imports common, enums
3. claims.py        — imports common, enums
4. report.py        — imports common, enums
5. slides.py        — imports common, enums
6. actions.py       — imports common, enums
7. waiver.py        — imports common, enums
8. qa.py            — imports common, enums
9. indexing.py       — imports common, enums
```

Key: files 2–9 depend only on `common.py` and `enums.py`. They do NOT depend on each other. `state.py`, `ids.py`, and `__init__.py` (M3) depend on ALL of them, which is why they are in a separate milestone.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Base class | `DeckForgeBaseModel` (in common.py) with `extra="forbid"`, `validate_assignment=True`, `use_enum_values=True` | Catches schema drift. Validates on assignment. Serializes enums as strings. Per State Schema v1.1. |
| `ChartSpec.x_axis` / `y_axis` | `dict | None` | State Schema spec uses loose dict. Accept as-is. |
| `SlideMove.from_` field | `Field(alias="from")` with `populate_by_name=True` | Python keyword conflict. State Schema v1.1 specifies this exact pattern. |
| `IndexedDateRange.from_date` | `Field(alias="from")` with `populate_by_name=True` | Same keyword conflict pattern. |
| `actions.py` discriminated union | `Annotated[Union[...], Field(discriminator="type")]` | Pydantic v2 native discriminated unions. State Schema v1.1 specifies this. |

### Files

| File | Section in State Schema | Classes | Lines (est.) |
|------|------------------------|---------|-------------|
| `src/models/common.py` | Section 2 | `DeckForgeBaseModel`, `BilingualText`, `DateRange`, `ChangeLogEntry` | ~30 |
| `src/models/rfp.py` | Section 3 | `EvaluationSubItem`, `EvaluationSubCriterion`, `EvaluationCategory`, `EvaluationCriteria`, `ScopeItem`, `Deliverable`, `ComplianceRequirement`, `KeyDates`, `SubmissionFormat`, `RFPGap`, `Completeness`, `RFPContext` | ~100 |
| `src/models/claims.py` | Section 4 | `ClaimObject`, `GapObject`, `Contradiction`, `CaseStudy`, `TeamProfile`, `ComplianceEvidence`, `FrameworkReference`, `SourceManifestEntry`, `ReferenceIndex` | ~115 |
| `src/models/report.py` | Section 5 | `ReportSection`, `ReportGap`, `ReportSourceEntry`, `ResearchReport` | ~45 |
| `src/models/slides.py` | Section 6 | `ChartSpec`, `BodyContent`, `SlideObject`, `SlideOutline`, `WrittenSlides` | ~70 |
| `src/models/actions.py` | Section 7 | 11 action classes + `ConversationAction` union + `ConversationResponse` | ~110 |
| `src/models/waiver.py` | Section 8 | `WaiverObject` | ~30 |
| `src/models/qa.py` | Section 9 | `QAIssue`, `SlideValidation`, `DeckValidationSummary`, `QAResult` | ~45 |
| `src/models/indexing.py` | Section 10 | `QualityBreakdown`, `IndexedDateRange`, `IndexingInput`, `IndexingOutput` | ~55 |
| `tests/agents/test_models.py` | — | Tests for all model files | ~200 |

### Acceptance Criteria

1. Every model class matches State Schema doc verbatim — same field names, same types, same defaults
2. All internal imports resolve: `from .common import ...`, `from .enums import ...`
3. Every model can be instantiated with valid data
4. Every model rejects invalid data (`extra="forbid"` catches unexpected fields)
5. `SlideMove` and `IndexedDateRange` work with both `from_` (Python) and `"from"` (JSON)
6. All 11 action types deserialize correctly via the discriminated union
7. `ruff check src/models/` and `mypy src/models/` pass clean
8. All tests pass

### Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `extra="forbid"` on `DeckForgeBaseModel` conflicts with `SlideMove`'s `populate_by_name` | Medium | `SlideMove` has its own `model_config` override. Test with raw JSON `{"from": "S-001", "to": "S-002"}`. |
| `Literal[ActionType.REWRITE_SLIDE]` may not work with `use_enum_values=True` | Low | Pydantic v2 handles this. Explicit test case. |
| `ChangeLogEntry.timestamp` default uses `lambda: datetime.now(UTC)` — may cause issues in tests | Low | Use `freezegun` or accept approximate timestamp matching in tests. |

---

## M3: Master State + IDs + Re-export — `src/models/state.py` + `src/utils/ids.py` + `src/models/__init__.py`

### What

Three files. `state.py` contains the `DeckForgeState` class plus 6 supporting classes (`UploadedDocument`, `ConversationTurn`, `GateDecision`, `RetrievedSource`, `SessionMetadata`, `ErrorInfo`). `ids.py` provides thread-safe sequential ID generators for all entity types. `__init__.py` provides the central re-export for convenient imports. Together these tie the entire model layer into a usable package.

### Why Separate Milestone

`state.py` imports from **every other model file**: `rfp.py`, `claims.py`, `report.py`, `slides.py`, `qa.py`, `waiver.py`, `actions.py`. If any of those files have an error, `state.py` won't import. `__init__.py` re-exports from all files including state. M3 is the integration test for M1 + M2.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| `DeckForgeState` base | `DeckForgeBaseModel` (inherits `extra="forbid"`) | Consistent with all other models. Catches unexpected state fields. |
| Gate fields | `gate_1: GateDecision | None = None` through `gate_5` | Optional because gates are populated as pipeline progresses. |
| Serialization | JSON via Pydantic `.model_dump_json()` / `.model_validate_json()` | Local dev persists to `./state/session.json`. Must round-trip cleanly. |
| ID generators | Thread-safe with `threading.Lock`, `reset_counters()` for test isolation | State Schema v1.1, Section 12 specifies this exact implementation. |
| `__init__.py` re-export | Wildcard enum import + explicit named imports for all models | State Schema v1.1, Section 13 specifies this exact pattern. |

### Files

| File | Section in State Schema | Classes | Lines (est.) |
|------|------------------------|---------|-------------|
| `src/models/state.py` | Section 11 | `UploadedDocument`, `ConversationTurn`, `GateDecision`, `RetrievedSource`, `SessionMetadata`, `ErrorInfo`, `DeckForgeState` | ~140 |
| `src/utils/ids.py` | Section 12 | 9 ID generator functions + `reset_counters()` | ~65 |
| `src/models/__init__.py` | Section 13 | Central re-export of all models, enums, and state classes | ~20 |
| `tests/agents/test_state.py` | — | Tests for state creation, serialization, nested model population | ~120 |
| `tests/agents/test_ids.py` | — | Tests for ID generators | ~60 |

### Acceptance Criteria

1. `DeckForgeState` matches State Schema Section 11 verbatim
2. All imports from other model files resolve without errors
3. Empty state can be created: `DeckForgeState()` succeeds with all defaults
4. State with populated nested models (rfp_context, reference_index, slides, etc.) serializes to JSON and deserializes back identically
5. ID generators produce sequential, zero-padded IDs; `reset_counters()` resets state
6. `src/models/__init__.py` re-exports all public classes (enums, models, state)
7. `ruff check src/models/ src/utils/` and `mypy src/models/ src/utils/` pass clean
8. All tests pass (state + ids + re-export smoke test)

### Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Circular import if state.py imports actions.py which imports enums differently | Low | actions.py only imports from common.py and enums.py — no circular path to state.py |
| JSON serialization of `datetime` fields with timezone | Medium | Pydantic v2 handles `datetime` with `UTC` natively. Test with explicit round-trip. |

---

## M4: Config + LLM Wrapper — Design Only (No Implementation)

> **This section documents the design for M4. Implementation waits until M1–M3 are reviewed.**

### What Will Be Built

| File | Purpose |
|------|---------|
| `src/config/settings.py` | Pydantic `BaseSettings` loading from `.env`. Environment, backend selection, paths. |
| `src/config/models.py` | `MODEL_MAP` dict mapping agent names to model strings. Per .cursorrules. |
| `src/services/llm.py` | Unified async wrapper for OpenAI + Anthropic. Handles retries, token counting, structured output. |

### Design Decisions (Pre-Approved by Architecture Doc)

| Decision | Choice | Source |
|----------|--------|--------|
| Settings pattern | `pydantic-settings` `BaseSettings` with `.env` file | Scaffold doc Section 4 |
| Model mapping | `MODEL_MAP: dict[str, str]` in `src/config/models.py` | .cursorrules, exact dict specified |
| LLM abstraction | Single `async def call_llm()` function with `model`, `system_prompt`, `user_message`, `response_model` params | .cursorrules LLM Wrapper Pattern |
| Retry strategy | 3 attempts, exponential backoff (2s, 4s, 8s) | Architecture doc Section 9, .cursorrules Error Handling |
| Provider routing | If model string starts with `gpt` → OpenAI; if `claude` → Anthropic | Architecture doc Section 5 agent table |
| Structured output | OpenAI: native structured outputs mode. Anthropic: tool-use-based structured output | Provider API capabilities |
| Local vs production | `Settings.environment` field; backends swap via config, not code | Scaffold doc Section 4 |

### Why M4 Waits

1. `call_llm()` accepts `response_model: type[BaseModel]` — the models must exist first
2. No agent can be tested until the LLM wrapper exists, but the wrapper design depends on the model layer shape
3. Clean separation: M1–M3 = data layer, M4 = service layer. Different review concerns.

### Interface Contract (For Reference During M1–M3)

```python
async def call_llm(
    model: str,
    system_prompt: str,
    user_message: str,
    response_model: type[DeckForgeBaseModel],
    temperature: float = 0.0,
    max_tokens: int = 4000,
) -> DeckForgeBaseModel:
    """Unified LLM call with retries, token counting, and structured output."""
    ...
```

This interface is documented here so M1–M3 tests can be written with knowledge of how models will be used downstream, without requiring the wrapper to exist yet.

---

*End of Foundation Design | DeckForge | 2026-03-06*
