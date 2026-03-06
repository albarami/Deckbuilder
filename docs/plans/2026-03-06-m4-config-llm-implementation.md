# DeckForge — M4 Config + LLM Wrapper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create the config layer (`settings.py`, `models.py`) and unified LLM wrapper (`llm.py`) that every agent depends on.

**Architecture:** Settings from pydantic-settings loading `.env`. MODEL_MAP resolving from settings. Async LLM wrapper with provider routing, retries, structured output, and token counting. All tests use mocks — no live API calls.

**Tech Stack:** Python 3.12, pydantic-settings, openai 2.26.0, anthropic 0.84.0, pytest, pytest-asyncio, unittest.mock

**Remote:** `origin` is `https://github.com/albarami/Deckbuilder.git`

**Constraints:**
- No commits until Salim approves.
- No live API calls in tests.
- Strict incremental TDD: RED→GREEN per file.
- Do not create any agent code.

---

## Task 1: Settings — `src/config/settings.py`

### Step 1.1: Write failing test

**Files:**
- Create: `tests/agents/test_config.py`

```python
"""Tests for src/config/settings.py and src/config/models.py."""

import importlib
import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_config():
    """Clear settings cache and reload models before each test."""
    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    if "src.config.models" in importlib.import_module("sys").modules:
        import src.config.models

        importlib.reload(src.config.models)


# ── Settings tests ──


def test_settings_defaults():
    """Settings has correct defaults when no env vars are set."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-openai-key",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
    }, clear=True):
        from src.config.settings import Settings

        s = Settings()
        assert s.environment == "local"
        assert s.log_level == "DEBUG"
        assert s.local_docs_path == "./test_docs"
        assert s.template_path == "./templates/Presentation6.pptx"
        assert s.output_path == "./output"
        assert s.state_path == "./state"
        assert s.storage_backend == "local"
        assert s.search_backend == "local"
        assert s.state_backend == "local"


def test_settings_loads_api_keys():
    """Settings reads API keys as SecretStr from env vars."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test-123",
        "ANTHROPIC_API_KEY": "sk-ant-test-456",
    }, clear=True):
        from src.config.settings import Settings

        s = Settings()
        assert s.openai_api_key.get_secret_value() == "sk-test-123"
        assert s.anthropic_api_key.get_secret_value() == "sk-ant-test-456"


def test_settings_model_name_defaults():
    """Default model names match .env.example."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import Settings

        s = Settings()
        assert s.openai_model_gpt54 == "gpt-5.4"
        assert s.anthropic_model_opus == "claude-opus-4-6"
        assert s.anthropic_model_sonnet == "claude-sonnet-4-6"


def test_settings_env_override():
    """Settings fields are overridable via env vars."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
        "ENVIRONMENT": "production",
        "LOG_LEVEL": "INFO",
    }, clear=True):
        from src.config.settings import Settings

        s = Settings()
        assert s.environment == "production"
        assert s.log_level == "INFO"


def test_get_settings_returns_cached_instance():
    """get_settings() returns the same instance on repeated calls."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
```

### Step 1.2: Run test — RED

```
.venv\Scripts\python.exe -m pytest tests/agents/test_config.py::test_settings_defaults -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.config.settings'`

### Step 1.3: Implement `src/config/settings.py`

Create with `BaseSettings`, `SecretStr` for keys, `get_settings()` with `@lru_cache`. Fields exactly as in design doc Section 2.

### Step 1.4: Run test — GREEN

```
.venv\Scripts\python.exe -m pytest tests/agents/test_config.py -v -k "settings"
```

Expected: ALL 5 settings tests PASS

---

## Task 2: Model Map — `src/config/models.py`

### Step 2.1: Add failing tests to `tests/agents/test_config.py`

Append to the test file:

```python
# ── MODEL_MAP tests ──


def test_model_map_has_10_entries():
    """MODEL_MAP has exactly 10 agent entries."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        import src.config.models

        importlib.reload(src.config.models)
        assert len(src.config.models.MODEL_MAP) == 10


def test_model_map_keys_match_agents():
    """MODEL_MAP keys match the exact agent names from .cursorrules."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        import src.config.models

        importlib.reload(src.config.models)
        expected_keys = {
            "context_agent", "retrieval_planner", "retrieval_ranker",
            "analysis_agent", "research_agent", "structure_agent",
            "content_agent", "qa_agent", "conversation_manager",
            "indexing_classifier",
        }
        assert set(src.config.models.MODEL_MAP.keys()) == expected_keys


def test_model_map_openai_agents_use_gpt():
    """GPT-5.4 agents are mapped to gpt model string."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        import src.config.models

        importlib.reload(src.config.models)
        gpt_agents = [
            "context_agent", "retrieval_planner", "retrieval_ranker",
            "structure_agent", "content_agent", "qa_agent", "indexing_classifier",
        ]
        for agent in gpt_agents:
            assert "gpt" in src.config.models.MODEL_MAP[agent].lower(), f"{agent} should use GPT"


def test_model_map_anthropic_agents_use_claude():
    """Claude agents are mapped to correct claude model strings."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        import src.config.models

        importlib.reload(src.config.models)
        m = src.config.models.MODEL_MAP
        assert "opus" in m["analysis_agent"].lower()
        assert "opus" in m["research_agent"].lower()
        assert "sonnet" in m["conversation_manager"].lower()
```

### Step 2.2: Run test — RED

```
.venv\Scripts\python.exe -m pytest tests/agents/test_config.py -v -k "model_map"
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.config.models'` or empty module

### Step 2.3: Implement `src/config/models.py`

Build `MODEL_MAP` from `get_settings()` via `_build_model_map()`. Exactly 10 entries.

### Step 2.4: Run test — GREEN

```
.venv\Scripts\python.exe -m pytest tests/agents/test_config.py -v
```

Expected: ALL 9 config tests PASS (5 settings + 4 model map)

---

## Task 3: LLM Wrapper — `src/services/llm.py`

### Step 3.1: Write failing test file with concrete mocks

**Files:**
- Create: `tests/agents/test_llm.py`

```python
"""Tests for src/services/llm.py — unified LLM wrapper. All tests use mocks, no live API calls."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.common import DeckForgeBaseModel


class SampleOutput(DeckForgeBaseModel):
    """Test model for structured output."""
    name: str
    value: int


def _make_openai_response(content_json: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    """Build a mock OpenAI ChatCompletion response."""
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    message = MagicMock()
    message.content = content_json

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_anthropic_response(tool_input: dict, input_tokens: int = 100, output_tokens: int = 50):
    """Build a mock Anthropic Message response with a tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_input

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    response = MagicMock()
    response.content = [tool_block]
    response.usage = usage
    return response


@pytest.fixture(autouse=True)
def _reset_llm_clients():
    """Reset lazy client singletons between tests."""
    import src.services.llm as llm_mod

    llm_mod._openai_client = None
    llm_mod._anthropic_client = None
    yield
    llm_mod._openai_client = None
    llm_mod._anthropic_client = None


@pytest.fixture(autouse=True)
def _set_api_keys():
    """Ensure API keys are set for client initialization."""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-key",
        "ANTHROPIC_API_KEY": "test-key",
    }):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


# ── Provider routing tests ──


@pytest.mark.asyncio
async def test_routes_to_openai_for_gpt_model():
    """Model starting with 'gpt' calls openai.AsyncOpenAI.chat.completions.create."""
    mock_response = _make_openai_response('{"name": "test", "value": 42}')
    with patch(
        "openai.resources.chat.completions.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_create:
        from src.services.llm import call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="You are a test.",
            user_message="Return test data.",
            response_model=SampleOutput,
        )
        mock_create.assert_called_once()
        assert result.parsed.name == "test"
        assert result.parsed.value == 42


@pytest.mark.asyncio
async def test_routes_to_anthropic_for_claude_model():
    """Model starting with 'claude' calls anthropic.AsyncAnthropic.messages.create."""
    mock_response = _make_anthropic_response({"name": "test", "value": 42})
    with patch(
        "anthropic.resources.messages.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_create:
        from src.services.llm import call_llm

        result = await call_llm(
            model="claude-opus-4-6",
            system_prompt="You are a test.",
            user_message="Return test data.",
            response_model=SampleOutput,
        )
        mock_create.assert_called_once()
        assert result.parsed.name == "test"
        assert result.parsed.value == 42


@pytest.mark.asyncio
async def test_unknown_provider_raises_value_error():
    """Model not matching gpt/claude raises ValueError immediately."""
    from src.services.llm import call_llm

    with pytest.raises(ValueError, match="Unsupported model"):
        await call_llm(
            model="unknown-model-v1",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )


# ── Response structure tests ──


@pytest.mark.asyncio
async def test_returns_llm_response_with_parsed_model():
    """call_llm returns LLMResponse with .parsed as the Pydantic model."""
    mock_response = _make_openai_response('{"name": "hello", "value": 7}')
    with patch(
        "openai.resources.chat.completions.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from src.services.llm import LLMResponse, call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert isinstance(result, LLMResponse)
        assert isinstance(result.parsed, SampleOutput)
        assert result.parsed.name == "hello"
        assert result.parsed.value == 7


@pytest.mark.asyncio
async def test_response_includes_token_counts_openai():
    """LLMResponse.input_tokens and output_tokens populated from OpenAI usage."""
    mock_response = _make_openai_response('{"name": "t", "value": 1}', prompt_tokens=150, completion_tokens=75)
    with patch(
        "openai.resources.chat.completions.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.input_tokens == 150
        assert result.output_tokens == 75
        assert result.model == "gpt-5.4"
        assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_response_includes_token_counts_anthropic():
    """LLMResponse.input_tokens and output_tokens populated from Anthropic usage."""
    mock_response = _make_anthropic_response({"name": "t", "value": 1}, input_tokens=200, output_tokens=100)
    with patch(
        "anthropic.resources.messages.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="claude-opus-4-6",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.input_tokens == 200
        assert result.output_tokens == 100
        assert result.model == "claude-opus-4-6"


# ── Retry tests ──


@pytest.mark.asyncio
async def test_retries_on_timeout_then_succeeds():
    """Retries up to 3 times on APITimeoutError, succeeds on 4th attempt (initial + 3 retries)."""
    import openai

    mock_response = _make_openai_response('{"name": "ok", "value": 1}')
    mock_create = AsyncMock(
        side_effect=[
            openai.APITimeoutError(request=MagicMock()),
            openai.APITimeoutError(request=MagicMock()),
            openai.APITimeoutError(request=MagicMock()),
            mock_response,
        ]
    )
    with (
        patch("openai.resources.chat.completions.completions.AsyncCompletions.create", mock_create),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.parsed.name == "ok"
        assert mock_create.call_count == 4
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)
        mock_sleep.assert_any_call(8)


@pytest.mark.asyncio
async def test_raises_llm_error_after_4_failures():
    """Raises LLMError after 4 consecutive failures (initial + 3 retries)."""
    import openai

    mock_create = AsyncMock(
        side_effect=openai.APITimeoutError(request=MagicMock()),
    )
    with (
        patch("openai.resources.chat.completions.completions.AsyncCompletions.create", mock_create),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        from src.services.llm import LLMError, call_llm

        with pytest.raises(LLMError) as exc_info:
            await call_llm(
                model="gpt-5.4",
                system_prompt="test",
                user_message="test",
                response_model=SampleOutput,
            )
        assert exc_info.value.attempts == 4
        assert exc_info.value.model == "gpt-5.4"
        assert mock_create.call_count == 4


@pytest.mark.asyncio
async def test_retries_on_rate_limit():
    """RateLimitError triggers retry."""
    import openai

    mock_response = _make_openai_response('{"name": "ok", "value": 1}')
    mock_create = AsyncMock(
        side_effect=[
            openai.RateLimitError(
                message="rate limited", response=MagicMock(status_code=429), body=None,
            ),
            mock_response,
        ]
    )
    with (
        patch("openai.resources.chat.completions.completions.AsyncCompletions.create", mock_create),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="gpt-5.4",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.parsed.name == "ok"
        assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_no_retry_on_auth_error():
    """AuthenticationError fails immediately without retry."""
    import openai

    mock_create = AsyncMock(
        side_effect=openai.AuthenticationError(
            message="bad key", response=MagicMock(status_code=401), body=None,
        ),
    )
    with patch("openai.resources.chat.completions.completions.AsyncCompletions.create", mock_create):
        from src.services.llm import LLMError, call_llm

        with pytest.raises(LLMError) as exc_info:
            await call_llm(
                model="gpt-5.4",
                system_prompt="test",
                user_message="test",
                response_model=SampleOutput,
            )
        assert exc_info.value.attempts == 1
        assert mock_create.call_count == 1


@pytest.mark.asyncio
async def test_anthropic_retry_on_timeout():
    """Anthropic APITimeoutError also triggers retry."""
    import anthropic

    mock_response = _make_anthropic_response({"name": "ok", "value": 1})
    mock_create = AsyncMock(
        side_effect=[
            anthropic.APITimeoutError(request=MagicMock()),
            mock_response,
        ]
    )
    with (
        patch("anthropic.resources.messages.messages.AsyncMessages.create", mock_create),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        from src.services.llm import call_llm

        result = await call_llm(
            model="claude-opus-4-6",
            system_prompt="test",
            user_message="test",
            response_model=SampleOutput,
        )
        assert result.parsed.name == "ok"
        assert mock_create.call_count == 2
```

### Step 3.2: Run test — RED

```
.venv\Scripts\python.exe -m pytest tests/agents/test_llm.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.llm'`

### Step 3.3: Implement `src/services/llm.py`

Create:
- `LLMError` exception class with `model`, `attempts`, `last_error`
- `LLMResponse` frozen generic dataclass with `parsed`, `input_tokens`, `output_tokens`, `model`, `latency_ms`
- `_get_openai_client()` and `_get_anthropic_client()` lazy singletons
- `_call_openai()` — builds messages, sets `response_format` with JSON schema, parses `choices[0].message.content`
- `_call_anthropic()` — builds messages, sets `tools` + `tool_choice`, extracts `ToolUseBlock.input`
- `call_llm()` — routes by prefix, retry loop with backoff [2, 4, 8], catches retryable errors, raises `LLMError` on exhaustion or auth error

### Step 3.4: Run test — GREEN

```
.venv\Scripts\python.exe -m pytest tests/agents/test_llm.py -v
```

Expected: ALL 12 LLM tests PASS

---

## Task 4: Final Verification

### Step 4.1: Full regression

```
.venv\Scripts\python.exe -m pytest tests/agents/ -v
```

Expected: ALL tests pass (M1 enums + M2 models + M3 state/ids + M4 config/llm)

### Step 4.2: Ruff

```
.venv\Scripts\python.exe -m ruff check src/config/ src/services/llm.py tests/agents/test_config.py tests/agents/test_llm.py
```

Expected: All checks passed

### Step 4.3: Mypy

```
.venv\Scripts\python.exe -m mypy src/config/ src/services/llm.py
```

Expected: Success

### --- STOP POINT: M4 REVIEW ---

**Report to Salim:**
- Files created: `src/config/settings.py`, `src/config/models.py`, `src/services/llm.py`
- Test files: `tests/agents/test_config.py`, `tests/agents/test_llm.py`
- RED evidence for each file (settings, models, llm)
- Final pytest, ruff, mypy output
- Confirmation: no live API calls, all mocked
- Confirmation: no agent code created

**Wait for Salim's approval before M5.**

---

## Summary: What This Plan Does NOT Include

| Excluded | Why |
|----------|-----|
| Live API call tests | Mocks only per instruction |
| Any agent code | M5+ |
| Pipeline wiring | M7 |
| Azure/SharePoint clients | M9 |
| PPTX renderer | M8 |

---

*End of M4 Implementation Plan (revised) | DeckForge | 2026-03-06*
