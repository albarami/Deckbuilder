# DeckForge — Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create the complete Pydantic v2 type system (enums, models, state, ID generators) that every DeckForge agent depends on.

**Architecture:** Verbatim transcription from State Schema v1.1 into Python files, validated by TDD. No interpretation, no additions. Three sequential milestones (M1 → M2 → M3) with explicit stop-and-review between each. README.md must be delivered before M1 begins.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, ruff, mypy

**Remote:** `origin` is `https://github.com/albarami/Deckbuilder.git` — all future approved commits/pushes target that remote.

**Constraints:**
- No commits. No pushes. No extra refactoring.
- Each milestone is a separate Salim review.
- Do NOT proceed to M1 until README.md is delivered and M0 is approved.
- Do NOT proceed to M2 until Salim approves M1.
- Do NOT proceed to M3 until Salim approves M2.
- M4 (config/LLM) is NOT part of this plan.

---

## PRE-MILESTONE: README.md (completes M0)

### Task 0.1: Create README.md

**Files:**
- Create: `README.md`

The README must cover:
1. **Project purpose** — what DeckForge is, who it's for
2. **Architecture summary** — 9 agents, 10-step pipeline, 5 gates, multi-model strategy
3. **Current milestone status** — M0 in progress, M1–M3 planned, M4+ deferred
4. **Local setup** — Python 3.12, venv, pip install, .env.example
5. **Test commands** — pytest, ruff, mypy
6. **Repo workflow** — Cursor builds, Salim reviews, conventional commits, no force push

**Verification:**

```
.venv\Scripts\python.exe -m ruff check README.md 2>$null; echo "README.md exists: $(Test-Path README.md)"
```

### --- STOP POINT: M0 COMPLETE ---

**Report to Salim:**
- File created: `README.md`
- M0 is now fully complete (scaffold + README)

**Wait for Salim's acknowledgment before proceeding to M1.**

---

## MILESTONE 1: Enums — `src/models/enums.py`

### Task 1.1: Write the failing test for enums

**Files:**
- Create: `tests/agents/test_enums.py`

**Step 1: Write the test file**

```python
"""Tests for src/models/enums.py — validates all 19 StrEnum classes against Prompt Library Appendix A."""

from enum import StrEnum


def test_layout_type_values():
    from src.models.enums import LayoutType
    assert issubclass(LayoutType, StrEnum)
    expected = {"TITLE", "AGENDA", "SECTION", "CONTENT_1COL", "CONTENT_2COL", "DATA_CHART",
                "FRAMEWORK", "COMPARISON", "STAT_CALLOUT", "TEAM", "TIMELINE", "COMPLIANCE_MATRIX", "CLOSING"}
    assert {e.value for e in LayoutType} == expected


def test_sensitivity_tag_values():
    from src.models.enums import SensitivityTag
    expected = {"compliance", "financial", "client_specific", "capability", "general"}
    assert {e.value for e in SensitivityTag} == expected


def test_gap_severity_values():
    from src.models.enums import GapSeverity
    expected = {"critical", "medium", "low"}
    assert {e.value for e in GapSeverity} == expected


def test_qa_issue_type_values():
    from src.models.enums import QAIssueType
    expected = {"UNGROUNDED_CLAIM", "INCONSISTENCY", "EMBELLISHMENT", "TEMPLATE_VIOLATION",
                "TEXT_OVERFLOW", "UNCOVERED_CRITERION", "CRITICAL_GAP_UNRESOLVED"}
    assert {e.value for e in QAIssueType} == expected


def test_action_type_values():
    from src.models.enums import ActionType
    expected = {"rewrite_slide", "add_slide", "remove_slide", "reorder_slides",
                "additional_retrieval", "show_sources", "change_language", "export",
                "fill_gap", "waive_gap", "update_report"}
    assert {e.value for e in ActionType} == expected


def test_pipeline_stage_values():
    from src.models.enums import PipelineStage
    expected = {"intake", "context_review", "source_review", "analysis", "report_review",
                "outline_review", "content_generation", "qa", "deck_review", "finalized", "error"}
    assert {e.value for e in PipelineStage} == expected


def test_language_values():
    from src.models.enums import Language
    expected = {"en", "ar", "bilingual", "mixed"}
    assert {e.value for e in Language} == expected


def test_document_type_values():
    from src.models.enums import DocumentType
    expected = {"proposal", "case_study", "capability_statement", "technical_report",
                "client_presentation", "internal_framework", "rfp_response", "financial_report",
                "team_profile", "methodology_document", "certificate", "other"}
    assert {e.value for e in DocumentType} == expected


def test_claim_category_values():
    from src.models.enums import ClaimCategory
    expected = {"project_reference", "team_profile", "certification", "methodology",
                "financial_data", "compliance_evidence", "company_metric"}
    assert {e.value for e in ClaimCategory} == expected


def test_all_enums_are_str_serializable():
    from src.models.enums import LayoutType, SensitivityTag, Language
    assert str(LayoutType.TITLE) == "TITLE"
    assert str(SensitivityTag.COMPLIANCE) == "compliance"
    assert str(Language.AR) == "ar"


def test_enum_count():
    """Verify we have exactly 19 StrEnum classes."""
    import src.models.enums as enums_module
    enum_classes = [v for v in vars(enums_module).values()
                    if isinstance(v, type) and issubclass(v, StrEnum) and v is not StrEnum]
    assert len(enum_classes) == 19, f"Expected 19 enums, found {len(enum_classes)}: {[c.__name__ for c in enum_classes]}"
```

**Step 2: Run test to verify it fails**

```
.venv\Scripts\python.exe -m pytest tests/agents/test_enums.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.enums'` (file is empty)

### Task 1.2: Implement enums

**Files:**
- Create: `src/models/enums.py`

**Step 3: Copy code verbatim from State Schema v1.1, Section 1**

The entire content of `src/models/enums.py` is defined in the State Schema doc, Section 1. Copy the code block exactly. Do not add, remove, or rename anything.

**Step 4: Run test to verify it passes**

```
.venv\Scripts\python.exe -m pytest tests/agents/test_enums.py -v
```

Expected: ALL PASS (11 tests)

**Step 5: Lint and type check**

```
.venv\Scripts\python.exe -m ruff check src/models/enums.py
.venv\Scripts\python.exe -m mypy src/models/enums.py
```

Expected: Both clean (0 errors)

### --- STOP POINT: M1 REVIEW ---

**Report to Salim:**
- Files created: `src/models/enums.py`, `tests/agents/test_enums.py`
- Test results: X/11 passed
- Lint results: ruff clean / not clean
- Type check results: mypy clean / not clean
- Enum count: 19 classes confirmed

**Wait for Salim's approval before proceeding to M2.**

---

## MILESTONE 2: Pydantic Models

> **Do NOT start until M1 is approved.**

### Task 2.1: Write failing test for common.py

**Files:**
- Create: `tests/agents/test_models.py`

**Step 1: Write the initial test block for common.py**

```python
"""Tests for src/models/ — validates all Pydantic models against State Schema v1.1."""

import json
from datetime import UTC, datetime


def test_deckforge_base_model_rejects_extra_fields():
    from src.models.common import DeckForgeBaseModel
    import pytest
    class Sample(DeckForgeBaseModel):
        name: str
    with pytest.raises(Exception):
        Sample(name="test", unexpected="field")


def test_bilingual_text():
    from src.models.common import BilingualText
    bt = BilingualText(en="Hello", ar="مرحبا")
    assert bt.en == "Hello"
    assert bt.ar == "مرحبا"
    bt_en_only = BilingualText(en="Hello")
    assert bt_en_only.ar is None


def test_date_range():
    from src.models.common import DateRange
    dr = DateRange(start="2023-02", end="2023-11")
    assert dr.start == "2023-02"
    dr_empty = DateRange()
    assert dr_empty.start is None


def test_changelog_entry_has_timestamp():
    from src.models.common import ChangeLogEntry
    entry = ChangeLogEntry(agent="test", description="test change")
    assert entry.timestamp is not None
    assert entry.timestamp.tzinfo is not None
```

**Step 2: Run — expected FAIL** (common.py is empty)

```
.venv\Scripts\python.exe -m pytest tests/agents/test_models.py -v
```

### Task 2.2: Implement common.py

**Step 3: Copy from State Schema Section 2 verbatim**

**Step 4: Run tests — expected PASS for common.py tests**

### Task 2.3: Implement remaining model files (one at a time)

For each file, follow the same RED-GREEN cycle:

| Order | File | State Schema Section | Add tests to `tests/agents/test_models.py` for... |
|-------|------|---------------------|---------------------------------------------|
| 1 | `src/models/rfp.py` | Section 3 | `RFPContext` creation with valid data, `BilingualText` fields, `RFPGap` severity enum, nested `EvaluationCriteria` |
| 2 | `src/models/claims.py` | Section 4 | `ClaimObject` with confidence bounds (0.6–1.0), `ReferenceIndex` with empty lists, `CaseStudy` with optional fields |
| 3 | `src/models/report.py` | Section 5 | `ResearchReport` creation, `ReportSection` with sensitivity tags |
| 4 | `src/models/slides.py` | Section 6 | `SlideObject` with layout enum, `ChartSpec` with literal type, `SlideOutline` with slide list |
| 5 | `src/models/actions.py` | Section 7 | All 11 action types individually, discriminated union deserialization from raw JSON, `SlideMove` with `"from"` alias |
| 6 | `src/models/waiver.py` | Section 8 | `WaiverObject` creation, severity enum, timestamp default |
| 7 | `src/models/qa.py` | Section 9 | `QAResult` with validations, `DeckValidationSummary` defaults, issue types |
| 8 | `src/models/indexing.py` | Section 10 | `IndexingOutput` quality score bounds (0–5), `IndexedDateRange` with `"from"` alias, duplicate likelihood literal |

**For each file, the pattern is:**
1. Add tests to `tests/agents/test_models.py` for that file's models
2. Run `.venv\Scripts\python.exe -m pytest tests/agents/test_models.py -v` — new tests FAIL
3. Create the file by copying from State Schema doc
4. Run `.venv\Scripts\python.exe -m pytest tests/agents/test_models.py -v` — all tests PASS
5. Run `.venv\Scripts\python.exe -m ruff check src/models/<file>.py`

### Task 2.4: Full validation

```
.venv\Scripts\python.exe -m pytest tests/agents/test_enums.py tests/agents/test_models.py -v
.venv\Scripts\python.exe -m ruff check src/models/
.venv\Scripts\python.exe -m mypy src/models/
```

Expected: ALL tests pass. Ruff clean. Mypy clean.

### --- STOP POINT: M2 REVIEW ---

**Report to Salim:**
- Files created: `src/models/common.py`, `rfp.py`, `claims.py`, `report.py`, `slides.py`, `actions.py`, `waiver.py`, `qa.py`, `indexing.py`
- Test file: `tests/agents/test_models.py`
- Test results: X/Y passed
- Lint results: ruff clean / not clean
- Type check results: mypy clean / not clean
- Specific validation: discriminated union works, alias fields work, all enums serialize correctly

**Wait for Salim's approval before proceeding to M3.**

---

## MILESTONE 3: Master State + ID Generators + Re-export

> **Do NOT start until M2 is approved.**

### Task 3.1: Write failing test for ids.py

**Files:**
- Create: `tests/agents/test_ids.py`

**Test cases:**

```python
"""Tests for src/utils/ids.py — validates ID generation per Appendix C."""

from src.utils.ids import (
    next_claim_id, next_gap_id, next_doc_id, next_slide_id,
    next_scope_id, next_deliverable_id, next_compliance_id,
    next_waiver_id, next_section_id, reset_counters,
)


def test_claim_id_format():
    reset_counters()
    assert next_claim_id() == "CLM-0001"
    assert next_claim_id() == "CLM-0002"


def test_gap_id_format():
    reset_counters()
    assert next_gap_id() == "GAP-001"


def test_slide_id_format():
    reset_counters()
    assert next_slide_id() == "S-001"
    assert next_slide_id() == "S-002"


def test_section_id_format():
    reset_counters()
    assert next_section_id() == "SEC-01"


def test_reset_counters():
    reset_counters()
    next_claim_id()
    next_claim_id()
    reset_counters()
    assert next_claim_id() == "CLM-0001"


def test_ids_are_sequential():
    reset_counters()
    ids = [next_doc_id() for _ in range(5)]
    assert ids == ["DOC-001", "DOC-002", "DOC-003", "DOC-004", "DOC-005"]
```

**Step 1:** Write test file → **Step 2:** Run, expect FAIL

```
.venv\Scripts\python.exe -m pytest tests/agents/test_ids.py -v
```

### Task 3.2: Implement ids.py

**Step 3:** Copy `ids.py` from State Schema Section 12 verbatim.

**Step 4:** Run tests — expected PASS

```
.venv\Scripts\python.exe -m pytest tests/agents/test_ids.py -v
```

### Task 3.3: Write failing test for state.py

**Files:**
- Create: `tests/agents/test_state.py`

**Test cases:**

```python
"""Tests for src/models/state.py — validates DeckForgeState against State Schema Section 11."""

import json


def test_empty_state_creation():
    from src.models.state import DeckForgeState
    state = DeckForgeState()
    assert state.current_stage == "intake"
    assert state.output_language == "en"
    assert state.rfp_context is None
    assert state.errors == []


def test_state_serialization_roundtrip():
    from src.models.state import DeckForgeState
    state = DeckForgeState()
    json_str = state.model_dump_json()
    restored = DeckForgeState.model_validate_json(json_str)
    assert restored.current_stage == state.current_stage
    assert restored.output_language == state.output_language


def test_state_with_nested_rfp_context():
    from src.models.state import DeckForgeState
    from src.models.rfp import RFPContext
    from src.models.common import BilingualText
    rfp = RFPContext(
        rfp_name=BilingualText(en="Test RFP"),
        issuing_entity=BilingualText(en="Test Entity"),
        mandate=BilingualText(en="Test mandate"),
    )
    state = DeckForgeState(rfp_context=rfp)
    assert state.rfp_context is not None
    assert state.rfp_context.rfp_name.en == "Test RFP"


def test_state_with_gate_decision():
    from src.models.state import DeckForgeState, GateDecision
    gate = GateDecision(gate_number=1, approved=True, feedback="LGTM")
    state = DeckForgeState(gate_1=gate)
    assert state.gate_1.approved is True
    assert state.gate_1.gate_number == 1


def test_state_rejects_extra_fields():
    from src.models.state import DeckForgeState
    import pytest
    with pytest.raises(Exception):
        DeckForgeState(nonexistent_field="value")


def test_state_full_roundtrip_with_nested_models():
    from src.models.state import DeckForgeState, GateDecision, RetrievedSource, SessionMetadata
    from src.models.rfp import RFPContext
    from src.models.common import BilingualText
    state = DeckForgeState(
        rfp_context=RFPContext(
            rfp_name=BilingualText(en="SAP Renewal"),
            issuing_entity=BilingualText(en="SIDF"),
            mandate=BilingualText(en="Renew SAP licenses"),
        ),
        gate_1=GateDecision(gate_number=1, approved=True),
        retrieved_sources=[
            RetrievedSource(doc_id="DOC-001", title="Test Doc", relevance_score=85),
        ],
    )
    json_str = state.model_dump_json()
    restored = DeckForgeState.model_validate_json(json_str)
    assert restored.rfp_context.rfp_name.en == "SAP Renewal"
    assert restored.gate_1.approved is True
    assert len(restored.retrieved_sources) == 1
    assert restored.retrieved_sources[0].doc_id == "DOC-001"
```

**Step 5:** Write test file → **Step 6:** Run, expect FAIL

```
.venv\Scripts\python.exe -m pytest tests/agents/test_state.py -v
```

### Task 3.4: Implement state.py

**Step 7:** Copy from State Schema Section 11 verbatim.

**Step 8:** Run tests — expected PASS

```
.venv\Scripts\python.exe -m pytest tests/agents/test_state.py -v
```

### Task 3.5: Create models __init__.py re-export

**Files:**
- Modify: `src/models/__init__.py`

Copy verbatim from State Schema Section 13. This is the central re-export.

**Verification — add to `tests/agents/test_models.py`:**

```python
def test_models_reexport():
    from src.models import (
        DeckForgeBaseModel, BilingualText, RFPContext, ClaimObject,
        ResearchReport, SlideObject, ConversationAction, WaiverObject,
        QAResult, IndexingOutput, LayoutType, SensitivityTag,
        DeckForgeState, GateDecision, RetrievedSource, SessionMetadata,
        ErrorInfo, UploadedDocument, ConversationTurn,
    )
    assert DeckForgeBaseModel is not None
    assert DeckForgeState is not None
```

### Task 3.6: Full regression — all tests

```
.venv\Scripts\python.exe -m pytest tests/agents/test_enums.py tests/agents/test_models.py tests/agents/test_ids.py tests/agents/test_state.py -v
.venv\Scripts\python.exe -m ruff check src/models/ src/utils/
.venv\Scripts\python.exe -m mypy src/models/ src/utils/
```

Expected: ALL tests pass across all test files. Ruff clean. Mypy clean.

### --- STOP POINT: M3 REVIEW ---

**Report to Salim:**
- Files created: `src/models/state.py`, `src/utils/ids.py`, updated `src/models/__init__.py`
- Test files: `tests/agents/test_state.py`, `tests/agents/test_ids.py`, updated `tests/agents/test_models.py`
- Test results: X/Y passed (including ALL previous tests from M1 + M2)
- Lint results: ruff clean / not clean
- Type check results: mypy clean / not clean
- Specific validation: empty state creation, JSON round-trip, nested model population, extra field rejection, ID generation, re-export smoke test
- Full regression: all enums + models + ids + state tests pass

**Wait for Salim's approval before proceeding to M4 (Config + LLM Wrapper).**

---

## Summary: What This Plan Does NOT Include

| Excluded | Why |
|----------|-----|
| `src/config/settings.py` | M4 — separate milestone, after foundation review |
| `src/config/models.py` | M4 — separate milestone |
| `src/services/llm.py` | M4 — separate milestone |
| Any agent code | Phase 1 (M5+) — blocked on M4 |
| Any pipeline code | Phase 2 (M7) |
| Any rendering code | Phase 3 (M8) |
| Commits or pushes | Explicitly forbidden until Salim approves |
| Refactoring of scaffold files | Not requested |

---

*End of Foundation Implementation Plan | DeckForge | 2026-03-06*
