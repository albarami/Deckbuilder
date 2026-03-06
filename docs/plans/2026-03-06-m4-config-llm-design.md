# DeckForge — M4 Config + LLM Wrapper Design

> **Scope:** `src/config/settings.py` + `src/config/models.py` + `src/services/llm.py`
> **Depends on:** M1–M3 (enums, models, state) — all approved and pushed.
> **Blocks:** M5+ (every agent imports `call_llm` and `MODEL_MAP`).

**Date:** 2026-03-06 (revised)
**Source of truth:** `.cursorrules` (LLM Wrapper Pattern, Environment Variables), `docs/DeckForge-Project-Scaffold-v1.0.md` (Section 4), `docs/DeckForge-v3.1-Final-Architecture.md` (Sections 5, 7, 9)

---

## 1. What M4 Builds

| File | Purpose | Source of Truth |
|------|---------|-----------------|
| `src/config/settings.py` | Pydantic `BaseSettings` loading all env vars from `.env` | Scaffold doc Section 4, `.env.example` |
| `src/config/models.py` | `MODEL_MAP` dict mapping 10 agent names to model strings | `.cursorrules` lines 134–147 |
| `src/services/llm.py` | Unified `async def call_llm()` for both OpenAI and Anthropic | `.cursorrules` LLM Wrapper Pattern, Architecture doc Section 9 |

---

## 2. `src/config/settings.py` — Design

### Approach

Use `pydantic-settings` `BaseSettings` with `.env` file loading. Every field maps to an env var from `.env.example`. Local dev defaults are set so the system works without Azure/SharePoint keys.

### Fields

```python
# API Keys (SecretStr — prevents accidental logging)
openai_api_key: SecretStr
anthropic_api_key: SecretStr

# Model names (overridable per env)
openai_model_gpt54: str = "gpt-5.4"
anthropic_model_opus: str = "claude-opus-4-6"
anthropic_model_sonnet: str = "claude-sonnet-4-6"

# Azure (optional for local dev)
azure_search_endpoint: str = ""
azure_search_key: SecretStr = SecretStr("")
azure_search_index: str = "deckforge-knowledge"
azure_openai_endpoint: str = ""
azure_openai_key: SecretStr = SecretStr("")
azure_openai_embedding_model: str = "text-embedding-3-large"

# SharePoint (production only)
sharepoint_tenant_id: str = ""
sharepoint_client_id: str = ""
sharepoint_client_secret: SecretStr = SecretStr("")
sharepoint_site_url: str = ""

# Local dev paths + backend selection
environment: str = "local"
storage_backend: str = "local"
search_backend: str = "local"
state_backend: str = "local"
local_docs_path: str = "./test_docs"
template_path: str = "./templates/Presentation6.pptx"
output_path: str = "./output"
state_path: str = "./state"
log_level: str = "DEBUG"
```

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Base class | `pydantic_settings.BaseSettings` | Scaffold doc specifies this. Auto-loads from `.env`. |
| `model_config` | `SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")` | Allow `.env` to have extra keys. |
| Secret fields | `SecretStr` for all API keys and secrets | Prevents accidental logging. Call `.get_secret_value()` when passing to provider clients. |
| Singleton | Module-level `get_settings()` function with `@lru_cache` | Single instance per process. Test isolation via `get_settings.cache_clear()`. |

---

## 3. `src/config/models.py` — Design

### The Map (verbatim from .cursorrules, values from settings)

```python
def _build_model_map() -> dict[str, str]:
    settings = get_settings()
    return {
        "context_agent": settings.openai_model_gpt54,
        "retrieval_planner": settings.openai_model_gpt54,
        "retrieval_ranker": settings.openai_model_gpt54,
        "analysis_agent": settings.anthropic_model_opus,
        "research_agent": settings.anthropic_model_opus,
        "structure_agent": settings.openai_model_gpt54,
        "content_agent": settings.openai_model_gpt54,
        "qa_agent": settings.openai_model_gpt54,
        "conversation_manager": settings.anthropic_model_sonnet,
        "indexing_classifier": settings.openai_model_gpt54,
    }

MODEL_MAP: dict[str, str] = _build_model_map()
```

### Test Isolation

Because `MODEL_MAP` is built at import time from `get_settings()`, tests that patch env vars must:
1. Call `get_settings.cache_clear()` to reset the cached settings
2. Reload `src.config.models` via `importlib.reload()` to rebuild `MODEL_MAP`

This is documented in the test fixture below.

---

## 4. `src/services/llm.py` — Design

### Public Contract

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T", bound=DeckForgeBaseModel)

@dataclass(frozen=True)
class LLMResponse(Generic[T]):
    parsed: T
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: float

async def call_llm(
    model: str,
    system_prompt: str,
    user_message: str,
    response_model: type[T],
    temperature: float = 0.0,
    max_tokens: int = 4000,
) -> LLMResponse[T]:
    ...
```

Every call site receives `LLMResponse[T]` with `.parsed` (the Pydantic model), `.input_tokens`, `.output_tokens`, `.model`, `.latency_ms`. This is the single return type used everywhere — in tests, in agent code, in the design doc, and in the implementation plan.

### Provider Routing

| Model string prefix | Provider | SDK Client | Method |
|---------------------|----------|------------|--------|
| `gpt` | OpenAI | `openai.AsyncOpenAI` | `client.chat.completions.create(...)` |
| `claude` | Anthropic | `anthropic.AsyncAnthropic` | `client.messages.create(...)` |
| anything else | — | — | Raise `ValueError("Unsupported model: {model}")` |

### Exact SDK Surfaces (locked)

**OpenAI (openai 2.26.0):**
- Client: `openai.AsyncOpenAI(api_key=...)`
- Method: `client.chat.completions.create(...)`
- Returns: `openai.types.chat.ChatCompletion`
- Usage: `response.usage.prompt_tokens`, `response.usage.completion_tokens`
- Content: `response.choices[0].message.content` (JSON string to parse)
- Structured output: `response_format={"type": "json_schema", "json_schema": {"name": ..., "schema": response_model.model_json_schema()}}`
- Mock target: `openai.resources.chat.completions.completions.AsyncCompletions.create`

**Anthropic (anthropic 0.84.0):**
- Client: `anthropic.AsyncAnthropic(api_key=...)`
- Method: `client.messages.create(...)`
- Returns: `anthropic.types.Message`
- Usage: `response.usage.input_tokens`, `response.usage.output_tokens`
- Content: find `ToolUseBlock` in `response.content` where `block.type == "tool_use"`, extract `block.input` (dict)
- Structured output: `tools=[{"name": "structured_output", "description": "...", "input_schema": response_model.model_json_schema()}]`, `tool_choice={"type": "tool", "name": "structured_output"}`
- Mock target: `anthropic.resources.messages.messages.AsyncMessages.create`

**Error classes (both providers share identical names):**
- Retryable: `APITimeoutError`, `RateLimitError`, `InternalServerError`
- Non-retryable: `AuthenticationError` — fail immediately, no retry

### Retry Policy (aligned with .cursorrules)

- **1 initial attempt + 3 retries = 4 total attempts**
- **Backoff delays: 2s, 4s, 8s** (after 1st, 2nd, 3rd failure)
- Retryable errors: `APITimeoutError`, `RateLimitError`, `InternalServerError`
- Non-retryable errors: `AuthenticationError` — raise `LLMError` immediately
- On exhaustion (all 4 attempts fail): raise `LLMError` with `model`, `attempts=4`, `last_error`
- Backoff implemented via `asyncio.sleep()` — mocked in tests

### LLMError

```python
class LLMError(Exception):
    def __init__(self, model: str, attempts: int, last_error: Exception):
        self.model = model
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"LLM call failed after {attempts} attempts: {last_error}")
```

### Client Initialization

Lazy singletons:
- `_openai_client: AsyncOpenAI | None = None`
- `_anthropic_client: AsyncAnthropic | None = None`
- `_get_openai_client() -> AsyncOpenAI` — creates on first call, reuses after
- `_get_anthropic_client() -> AsyncAnthropic` — same pattern
- API keys read from `get_settings()` via `.get_secret_value()`

---

## 5. Test Strategy — Mocks Only, No Live API Calls

### Config Test Isolation (Fix 4)

```python
@pytest.fixture(autouse=True)
def _reset_config():
    """Clear settings cache and reload models before each test."""
    import importlib
    from src.config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    import src.config.models
    importlib.reload(src.config.models)
```

This fixture is `autouse=True` in `tests/agents/test_config.py`. It ensures:
- Each test gets a fresh `Settings` instance
- `MODEL_MAP` is rebuilt after env patches
- Test execution order does not affect results

### LLM Test Isolation

```python
@pytest.fixture(autouse=True)
def _reset_llm_clients():
    """Reset lazy client singletons between tests."""
    import src.services.llm as llm_mod
    llm_mod._openai_client = None
    llm_mod._anthropic_client = None
    yield
    llm_mod._openai_client = None
    llm_mod._anthropic_client = None
```

### Test Files

| File | Tests |
|------|-------|
| `tests/agents/test_config.py` | Settings defaults, API key loading, env override, MODEL_MAP 10 entries, MODEL_MAP key names, OpenAI/Anthropic agent mapping |
| `tests/agents/test_llm.py` | Provider routing (OpenAI/Anthropic/unknown), structured output parsing, retry on timeout, retry backoff timing, persistent failure raises LLMError, auth error no retry, token count extraction, latency measurement |

---

## 6. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| OpenAI `response_format` JSON schema may need `strict: true` | Medium | Test with exact schema shape. Add `strict: true` if needed. |
| Anthropic tool-use `block.input` may be string not dict | Low | SDK 0.84.0 returns parsed dict. Verify in mock shape. |
| `SecretStr` requires `.get_secret_value()` everywhere | Low | Centralized in `_get_openai_client()` and `_get_anthropic_client()`. |
| `lru_cache` on `get_settings()` + `importlib.reload()` on models may have import side effects | Medium | Autouse fixture in test_config.py handles this. Documented. |
| `asyncio.sleep` in retry makes tests slow if not mocked | Low | All retry tests mock `asyncio.sleep` via `patch("asyncio.sleep")`. |

---

## 7. What M4 Does NOT Include

| Excluded | Why |
|----------|-----|
| Any agent code | M5+ |
| Pipeline wiring | M7 |
| Azure AI Search client | M9 |
| SharePoint client | M9 |
| PPTX renderer | M8 |
| Live API call tests | Mocks only per instruction |

---

*End of M4 Design (revised) | DeckForge | 2026-03-06*
