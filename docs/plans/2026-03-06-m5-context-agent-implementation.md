# DeckForge — M5 Context Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Context Agent — the first LLM-powered agent in the DeckForge pipeline. Parses RFP input into a structured `RFPContext` object.

**Architecture:** Single async function `run(state) -> state` calling `call_llm()` with `MODEL_MAP["context_agent"]`. System prompt verbatim from Prompt Library Agent 1. Output parsed via `LLMResponse.parsed` into `RFPContext`.

**Tech Stack:** Python 3.12, Pydantic v2, pytest-asyncio, unittest.mock

**Remote:** `origin` is `https://github.com/albarami/Deckbuilder.git`

**Constraints:**
- No commits until Salim approves.
- Mocked LLM calls in tests — no live API calls.
- Strict incremental TDD: RED→GREEN per file.
- Do not build any other agent yet.
- System prompt must be verbatim from Prompt Library — no edits.

---

## Scope: 3 Files Only

| File | Purpose |
|------|---------|
| `src/agents/context/prompts.py` | `SYSTEM_PROMPT` constant (verbatim from Prompt Library) |
| `src/agents/context/agent.py` | `async def run(state: DeckForgeState) -> DeckForgeState` |
| `tests/agents/test_context_agent.py` | Mock-based tests for the Context Agent |

---

## Mandatory Implementation Rules

1. **Use `MODEL_MAP["context_agent"]`** — never hardcode `"gpt-5.4"`
2. **Call `call_llm(model=..., system_prompt=SYSTEM_PROMPT, user_message=..., response_model=RFPContext)`**
3. **Consume `result.parsed`** — `result` is `LLMResponse[RFPContext]`, not a raw `RFPContext`
4. **Read from `DeckForgeState`** — inputs are `state.ai_assist_summary`, `state.uploaded_documents`, `state.user_notes`
5. **Write to `DeckForgeState`** — set `state.rfp_context`, update `state.current_stage`
6. **Keep prompt text verbatim** — copy from Prompt Library Agent 1 Section, do not edit
7. **On `LLMError`** — populate `state.errors` with `ErrorInfo`, set `state.current_stage = PipelineStage.ERROR`, return state (do not crash)
8. **Update token counts** — add `result.input_tokens` and `result.output_tokens` to `state.session`

---

## Mock Target

Because `agent.py` imports `call_llm` via `from src.services.llm import LLMError, call_llm`, the correct patch target in tests is:

```python
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
```

This patches the name as it exists in the agent module's namespace, not at the source.

---

## Task 1: Write `src/agents/context/prompts.py`

This file contains only the system prompt as a constant string. No logic.

The entire system prompt from Prompt Library lines 34–59 must be copied exactly. No modifications.

---

## Task 2: Write failing tests

**Files:**
- Create: `tests/agents/test_context_agent.py`

The complete test file:

```python
"""Tests for the Context Agent — mock-based, no live API calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.common import BilingualText
from src.models.rfp import RFPContext
from src.models.state import DeckForgeState
from src.services.llm import LLMError, LLMResponse


def _make_sample_rfp_context() -> RFPContext:
    """Minimal valid RFPContext for test fixtures."""
    return RFPContext(
        rfp_name=BilingualText(en="Renewal of Support for SAP Systems"),
        issuing_entity=BilingualText(en="Saudi Industrial Development Fund"),
        mandate=BilingualText(en="Renew and supply SAP licenses for 24 months."),
    )


def _make_success_response() -> LLMResponse:
    """LLMResponse wrapping a valid RFPContext."""
    return LLMResponse(
        parsed=_make_sample_rfp_context(),
        input_tokens=150,
        output_tokens=80,
        model="gpt-5.4",
        latency_ms=500.0,
    )


def _make_input_state() -> DeckForgeState:
    """DeckForgeState with ai_assist_summary populated for Context Agent input."""
    return DeckForgeState(
        ai_assist_summary="RFP Name: Renewal of Support for SAP Systems. Entity: SIDF.",
        user_notes="Focus on SAP HANA experience.",
    )


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_happy_path(mock_call_llm: AsyncMock) -> None:
    """Valid AI Assist summary produces an RFPContext in state."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run

    result = await run(state)

    assert result.rfp_context is not None
    assert result.rfp_context.rfp_name.en == "Renewal of Support for SAP Systems"
    assert result.current_stage == "context_review"


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_uses_model_map(mock_call_llm: AsyncMock) -> None:
    """Agent calls call_llm with MODEL_MAP['context_agent'], not a hardcoded string."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run
    from src.config.models import MODEL_MAP

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["model"] == MODEL_MAP["context_agent"]


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_uses_system_prompt(mock_call_llm: AsyncMock) -> None:
    """Agent passes SYSTEM_PROMPT from prompts.py to call_llm."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    assert call_kwargs.kwargs["system_prompt"].startswith("You are the Context Agent")


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_handles_llm_error(mock_call_llm: AsyncMock) -> None:
    """LLMError is caught, state.errors populated, stage set to ERROR."""
    mock_call_llm.side_effect = LLMError(
        model="gpt-5.4", attempts=4, last_error=TimeoutError("timed out"),
    )
    state = _make_input_state()

    from src.agents.context.agent import run

    result = await run(state)

    assert result.current_stage == "error"
    assert len(result.errors) == 1
    assert result.errors[0].agent == "context_agent"
    assert result.rfp_context is None


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_updates_token_counts(mock_call_llm: AsyncMock) -> None:
    """Successful call updates state.session token counters."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run

    result = await run(state)

    assert result.session.total_input_tokens == 150
    assert result.session.total_output_tokens == 80
    assert result.session.total_llm_calls == 1


@pytest.mark.asyncio
@patch("src.agents.context.agent.call_llm", new_callable=AsyncMock)
async def test_context_agent_builds_user_message(mock_call_llm: AsyncMock) -> None:
    """User message sent to LLM includes ai_assist_summary, uploaded_documents, and user_notes."""
    mock_call_llm.return_value = _make_success_response()
    state = _make_input_state()

    from src.agents.context.agent import run

    await run(state)

    call_kwargs = mock_call_llm.call_args
    user_msg = json.loads(call_kwargs.kwargs["user_message"])
    assert "ai_assist_summary" in user_msg
    assert "uploaded_documents" in user_msg
    assert "user_notes" in user_msg
    assert user_msg["ai_assist_summary"] == state.ai_assist_summary
```

### Step 2.1: Run tests — RED

```
.venv\Scripts\python.exe -m pytest tests/agents/test_context_agent.py -v
```

Expected: FAIL — `ImportError` because `src.agents.context.agent` has no `run` function yet

---

## Task 3: Implement `src/agents/context/agent.py`

```python
"""Context Agent — parses RFP input into structured RFPContext."""

import json

from src.config.models import MODEL_MAP
from src.models.enums import PipelineStage
from src.models.rfp import RFPContext
from src.models.state import DeckForgeState, ErrorInfo
from src.services.llm import LLMError, call_llm

from .prompts import SYSTEM_PROMPT


async def run(state: DeckForgeState) -> DeckForgeState:
    """Context Agent — parse RFP summary into structured RFPContext."""
    user_message = json.dumps({
        "ai_assist_summary": state.ai_assist_summary,
        "uploaded_documents": [
            {"filename": d.filename, "content_text": d.content_text, "language": d.language}
            for d in state.uploaded_documents
        ],
        "user_notes": state.user_notes or None,
    })

    try:
        result = await call_llm(
            model=MODEL_MAP["context_agent"],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            response_model=RFPContext,
        )
        state.rfp_context = result.parsed
        state.current_stage = PipelineStage.CONTEXT_REVIEW
        state.session.total_input_tokens += result.input_tokens
        state.session.total_output_tokens += result.output_tokens
        state.session.total_llm_calls += 1
    except LLMError as e:
        state.current_stage = PipelineStage.ERROR
        state.errors.append(ErrorInfo(
            agent="context_agent",
            error_type=type(e.last_error).__name__,
            message=str(e),
            retries_attempted=e.attempts,
        ))
        state.last_error = state.errors[-1]

    return state
```

### Step 3.1: Run tests — GREEN

```
.venv\Scripts\python.exe -m pytest tests/agents/test_context_agent.py -v
```

Expected: ALL 6 tests PASS

---

## Task 4: Final Verification

```
.venv\Scripts\python.exe -m pytest tests/agents/ -v
.venv\Scripts\python.exe -m ruff check src/agents/context/ tests/agents/test_context_agent.py
.venv\Scripts\python.exe -m mypy src/agents/context/
```

Expected: ALL pass. Ruff clean. Mypy clean.

### --- STOP POINT: CONTEXT AGENT REVIEW ---

**Report to Salim:**
- Files created: `src/agents/context/prompts.py`, `src/agents/context/agent.py`, `tests/agents/test_context_agent.py`
- RED evidence for test file
- Final pytest, ruff, mypy output
- Confirmation: uses `MODEL_MAP["context_agent"]`, not hardcoded
- Confirmation: uses `result.parsed`, not raw return
- Confirmation: system prompt is verbatim from Prompt Library
- Confirmation: LLMError handled, errors populated, stage set to ERROR
- Confirmation: no other agents created

**Wait for Salim's approval before building Retrieval Planner.**

---

## What This Plan Does NOT Include

| Excluded | Why |
|----------|-----|
| Retrieval Planner/Ranker | Separate implementation plan after Context Agent is approved |
| Analysis Agent | Separate implementation plan |
| Research Agent | Separate implementation plan |
| Search service (`src/services/search.py`) | Deferred to Retrieval agent planning |
| Pipeline wiring | M7 |
| Gate logic | M7 |
| Live API calls | Mocks only |

---

*End of M5 Context Agent Implementation Plan (revised) | DeckForge | 2026-03-06*
