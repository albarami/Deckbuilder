# DECKFORGE — Project Scaffold & Cursor Rules

**Project Setup, Folder Structure, .cursorrules, and Development Protocol**

Version 1.0 — March 2026 — CONFIDENTIAL
Companion to: DeckForge v3.1 Architecture + Prompt Library v1.4

---

## 1. Project Scaffold

### 1.1 Repository Setup

```bash
# Create repository
mkdir deckforge && cd deckforge
git init
git remote add origin git@github.com:YOUR_ORG/deckforge.git

# Create folder structure
mkdir -p src/{agents,models,services,pipeline,utils,config}
mkdir -p src/agents/{context,retrieval,analysis,research,structure,content,qa,conversation,indexing}
mkdir -p tests/{agents,integration,fixtures}
mkdir -p docs scripts templates output state test_docs .cursor/rules

# Create initial files
touch src/__init__.py
touch src/agents/__init__.py
touch src/models/__init__.py
touch src/services/__init__.py
touch src/pipeline/__init__.py
touch src/utils/__init__.py
touch src/config/__init__.py
touch .env.example .gitignore requirements.txt pyproject.toml README.md .cursorrules
touch .cursor/rules/deckforge.mdc
```

### 1.2 Folder Structure

```
deckforge/
├── .cursor/
│   └── rules/                    # Cursor rules (auto-loaded)
│       └── deckforge.mdc         # Main rules file
├── .cursorrules                  # Root rules file (legacy support)
├── docs/
│   ├── architecture.md           # DeckForge v3.1 Final Architecture
│   ├── prompt-library.md         # Prompt Library with all agent specs
│   ├── template-map.md           # PPTX template specification (TBD)
│   └── state-schema.md           # Pydantic state models (TBD)
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py               # Base agent class + LLM wrapper
│   │   ├── context/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Context Agent implementation
│   │   │   └── prompts.py        # System prompt + schemas
│   │   ├── retrieval/
│   │   │   ├── __init__.py
│   │   │   ├── planner.py        # Query Planner (Pass 1)
│   │   │   ├── ranker.py         # Source Ranker (Pass 2)
│   │   │   └── prompts.py
│   │   ├── analysis/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Analysis Agent
│   │   │   └── prompts.py
│   │   ├── research/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Research Agent (core)
│   │   │   └── prompts.py
│   │   ├── structure/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Structure Agent
│   │   │   └── prompts.py
│   │   ├── content/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Content Agent
│   │   │   └── prompts.py
│   │   ├── qa/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # QA Agent
│   │   │   └── prompts.py
│   │   ├── conversation/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Conversation Manager
│   │   │   └── prompts.py
│   │   └── indexing/
│   │       ├── __init__.py
│   │       ├── classifier.py     # SharePoint document classifier
│   │       └── prompts.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── common.py             # DeckForgeBaseModel, BilingualText, DateRange
│   │   ├── state.py              # DeckForgeState — master LangGraph state
│   │   ├── rfp.py                # RFPContext, EvaluationCriteria, etc.
│   │   ├── claims.py             # ClaimObject, ReferenceIndex, GapObject
│   │   ├── slides.py             # SlideObject, ChartSpec, SlideOutline
│   │   ├── report.py             # ResearchReport, ReportSection
│   │   ├── actions.py            # ConversationAction (discriminated union)
│   │   ├── waiver.py             # WaiverObject
│   │   ├── qa.py                 # QAResult, SlideValidation, DeckValidationSummary
│   │   ├── indexing.py           # IndexingInput, IndexingOutput
│   │   └── enums.py              # All canonical enums
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py                # Unified LLM wrapper (OpenAI + Anthropic)
│   │   ├── search.py             # Azure AI Search client
│   │   ├── sharepoint.py         # Microsoft Graph API client
│   │   ├── renderer.py           # python-pptx PPTX renderer (Design Agent)
│   │   └── storage.py            # File storage (local for dev, Azure Blob for prod)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── graph.py              # LangGraph StateGraph definition
│   │   ├── gates.py              # Human approval gate logic
│   │   └── workflow.py           # Pipeline orchestration
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py           # Pydantic Settings (env vars)
│   │   ├── models.py             # Model name → API config mapping
│   │   └── template.py           # Template visual config
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── extractors.py         # PPTX/PDF/DOCX text extraction
│   │   ├── chunking.py           # Hierarchical chunking logic
│   │   └── ids.py                # ID generators (CLM-NNNN, GAP-NNN, etc.)
│   └── main.py                   # FastAPI app entry point
├── templates/
│   └── Presentation6.pptx        # Strategic Gears master template
├── tests/
│   ├── agents/
│   │   ├── test_context_agent.py
│   │   ├── test_retrieval_planner.py
│   │   ├── test_retrieval_ranker.py
│   │   ├── test_analysis_agent.py
│   │   ├── test_research_agent.py
│   │   ├── test_structure_agent.py
│   │   ├── test_content_agent.py
│   │   ├── test_qa_agent.py
│   │   └── test_conversation_agent.py
│   ├── integration/
│   │   └── test_full_pipeline.py
│   └── fixtures/
│       ├── sidf_sap_rfp.json     # SIDF SAP RFP test fixture
│       ├── sample_sources/       # Sample SharePoint docs for testing
│       └── expected_outputs/     # Golden output files
├── scripts/
│   ├── index_sharepoint.py       # One-time SharePoint indexing script
│   └── run_pipeline.py           # CLI pipeline runner for local testing
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── output/                       # Generated PPTX/DOCX output (gitignored)
├── state/                        # Local session state persistence (gitignored)
├── test_docs/                    # Local sample documents (replaces SharePoint for dev)
└── README.md
```

### 1.3 Key Files Content

#### `.env.example`

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL_GPT54=gpt-5.4

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL_OPUS=claude-opus-4-6
ANTHROPIC_MODEL_SONNET=claude-sonnet-4-6

# Azure
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=...
AZURE_SEARCH_INDEX=deckforge-knowledge
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com
AZURE_OPENAI_KEY=...
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# SharePoint (for production — not needed for local dev)
SHAREPOINT_TENANT_ID=...
SHAREPOINT_CLIENT_ID=...
SHAREPOINT_CLIENT_SECRET=...
SHAREPOINT_SITE_URL=https://strategicgears.sharepoint.com/sites/proposals

# Local dev
LOCAL_DOCS_PATH=./test_docs
TEMPLATE_PATH=./templates/Presentation6.pptx
OUTPUT_PATH=./output
STATE_PATH=./state
LOG_LEVEL=DEBUG
```

#### `.gitignore`

```
# Python
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/
dist/
build/

# Environment
.env
.env.local

# IDE
.vscode/
.idea/

# Generated output (not tracked)
output/
state/
*.log
logs/

# OS
.DS_Store
Thumbs.db
```

#### `requirements.txt`

```
# Core
fastapi>=0.115.0
uvicorn>=0.32.0
pydantic>=2.10.0
pydantic-settings>=2.6.0
python-dotenv>=1.0.0

# LLM
openai>=1.60.0
anthropic>=0.42.0

# LangGraph
langgraph>=0.2.0
langchain-core>=0.3.0

# Azure
azure-search-documents>=11.6.0
azure-identity>=1.19.0

# Document processing
python-pptx>=1.0.0
python-docx>=1.1.0
PyPDF2>=3.0.0
openpyxl>=3.1.0

# Local vector search
numpy>=2.1.0

# Utilities
aiohttp>=3.11.0
redis>=5.2.0
rich>=13.9.0  # CLI formatting

# Testing
pytest>=8.3.0
pytest-asyncio>=0.24.0

# Code quality
ruff>=0.9.0
mypy>=1.14.0
```

#### `pyproject.toml`

```toml
[project]
name = "deckforge"
version = "0.1.0"
requires-python = ">=3.12"

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP"]

[tool.mypy]
python_version = "3.12"
strict = false
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 2. The .cursorrules File

This is the main rules file. Place it at the project root as `.cursorrules` AND copy to `.cursor/rules/deckforge.mdc` for Cursor's new rules system.

```markdown
# DECKFORGE — Cursor Development Rules

## IDENTITY
You are building DeckForge, an RFP-to-Deck agentic system for Strategic Gears Consulting.
The system uses LangGraph, GPT-5.4, Claude Opus 4.6, Claude Sonnet 4.6, python-pptx, and Azure AI Search.
You are the Engineer. Salim is the Coordinator. Salim gives instructions, you execute. Salim reviews and approves or rejects.

## CRITICAL PROTOCOL — FOLLOW THIS ON EVERY TASK

### Step 1: READ BEFORE YOU CODE
Before writing ANY code, you MUST:
1. Read ALL relevant documents in the `docs/` folder
2. Read the specific agent's section in `docs/prompt-library.md`
3. Read the relevant model schemas in `src/models/`
4. Read any existing code in the target directory
5. Use Superpower where relevant — choose the appropriate skill for the task and read the skill docs first
6. State what you read and what you understood before proceeding

You MUST NOT skip this step. You MUST NOT assume you know the schema — read it.
Superpower is installed intentionally. Use the relevant Superpower skill when it materially helps the task. Do not use skills blindly — choose the appropriate one and read its docs first.

### Step 2: IMPLEMENT ONE THING
- Do exactly what Salim asked. Nothing more, nothing less.
- Do NOT refactor code Salim did not ask you to change.
- Do NOT add features Salim did not request.
- Do NOT change function signatures of existing working code.
- Do NOT install packages without asking first.
- If the instruction is ambiguous, ASK before coding.

### Step 3: VALIDATE AND TEST
Before declaring done:
1. Run the code / function to confirm it works
2. Run any relevant tests: `pytest tests/agents/test_<agent>.py -v`
3. Check for type errors and import issues
4. Confirm output matches the schema defined in `docs/prompt-library.md`
5. State what you tested and what the result was

### Step 4: GIT COMMIT AND PUSH
After Salim approves (not before):
1. `git add` only the files you changed
2. `git commit -m "<type>: <description>"` using conventional commits
3. `git push` to the current branch

Commit types:
- `feat:` new feature or agent
- `fix:` bug fix
- `refactor:` code restructure (no behavior change)
- `test:` adding or updating tests
- `docs:` documentation changes
- `chore:` config, dependencies, tooling

NEVER commit without Salim's explicit approval.
NEVER push broken code.
NEVER force push.

## PROJECT CONVENTIONS

### Python Style
- Python 3.12+
- Type hints on ALL functions (params and return types)
- Pydantic v2 models for ALL data structures
- Async functions for all LLM calls and I/O operations
- f-strings for string formatting (no .format() or %)
- 4-space indentation
- Max line length: 120 characters
- Docstrings on all public functions (Google style)

### File Organization
- Each agent lives in its own directory: `src/agents/<name>/`
- Each agent directory has: `agent.py` (logic), `prompts.py` (system prompt + schemas)
- All Pydantic models live in `src/models/` — agents import from there, never define models inline
- All LLM calls go through `src/services/llm.py` — never call OpenAI/Anthropic directly from agents
- All config via `src/config/settings.py` using pydantic-settings — no hardcoded values

### Naming
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Pydantic models: `PascalCase` ending in descriptive name (e.g., `ClaimObject`, `SlideObject`, `RFPContext`)
- Agent functions: `async def run(state: DeckForgeState) -> DeckForgeState`

### LLM Wrapper Pattern
Every LLM call MUST go through the unified wrapper using the MODEL_MAP — never hardcode model strings in agents:

```python
from src.services.llm import call_llm
from src.config.models import MODEL_MAP

# The wrapper handles: model selection, retries, token counting, logging
result = await call_llm(
    model=MODEL_MAP["context_agent"],  # Resolved from config, NEVER hardcoded
    system_prompt=SYSTEM_PROMPT,
    user_message=user_input,
    response_model=OutputSchema, # Pydantic model for structured output
    temperature=0.0,
    max_tokens=4000,
)
```

Never import `openai` or `anthropic` directly in agent code.
Never pass a model string like `"gpt-5.4"` directly — always use `MODEL_MAP["agent_name"]`.

### Agent Pattern
Every agent follows this pattern:

```python
# src/agents/<name>/agent.py
from src.models.state import DeckForgeState
from src.services.llm import call_llm
from .prompts import SYSTEM_PROMPT, OutputSchema

async def run(state: DeckForgeState) -> DeckForgeState:
    """<Agent Name> — <one line description>."""
    # 1. Extract inputs from state
    # 2. Build the user message from state data
    # 3. Call the LLM
    # 4. Validate output against schema
    # 5. Update state with results
    # 6. Return updated state
    return state
```

### State Management
- The master state is `DeckForgeState` in `src/models/state.py`
- Every agent reads from state and writes back to state
- State is a Pydantic model — type-safe, serializable
- LangGraph manages state transitions between agents
- State is persisted to disk (local dev) or Redis (production) after each agent

### Environment Variables
- All API keys, endpoints, and config via `.env` file
- Loaded by `src/config/settings.py` using pydantic-settings
- NEVER hardcode API keys, model names, or URLs in code
- Model names are mapped in `src/config/models.py`:
  ```python
  MODEL_MAP = {
      "context_agent": "gpt-5.4",
      "retrieval_planner": "gpt-5.4",
      "retrieval_ranker": "gpt-5.4",
      "analysis_agent": "claude-opus-4.6",
      "research_agent": "claude-opus-4.6",
      "structure_agent": "gpt-5.4",
      "content_agent": "gpt-5.4",
      "qa_agent": "gpt-5.4",
      "conversation_manager": "claude-sonnet-4.6",
      "indexing_classifier": "gpt-5.4",
  }
  ```

### Testing
- Every agent gets a test file: `tests/agents/test_<agent>.py`
- Test fixtures live in `tests/fixtures/`
- Test with real LLM calls for prompt quality and integration validation
- Use fixtures and deterministic tests for schema compliance, state transitions, and utility logic
- Use `pytest-asyncio` for async tests
- Minimum test coverage per agent:
  - Happy path (standard RFP input → correct structured output)
  - Missing/incomplete input (gaps detected correctly)
  - Arabic input (if applicable)
  - Schema compliance (output matches Pydantic model)

### Error Handling
- All LLM calls wrapped in try/except
- On LLM failure: retry 3x with exponential backoff (2s, 4s, 8s)
- On persistent failure: log error, update state with error info, do NOT crash
- Never swallow exceptions silently — always log with `rich` or structured logging

### Documentation
- `docs/` folder contains the architecture and prompt library — these are the SOURCE OF TRUTH
- If code contradicts docs, the DOCS are correct — fix the code
- Update docs only when Salim explicitly asks

## REFERENCE DOCUMENTS (read before every task)

These documents define the system. Read them before every implementation task:

1. `docs/architecture.md` — Full system architecture, pipeline, agents, security, cost model
2. `docs/prompt-library.md` — All agent prompts, I/O schemas, few-shot examples, enums, ID rules
3. `src/models/state.py` — Master state definition (once created)
4. `src/models/enums.py` — Canonical enum values (once created)

## WHAT YOU MUST NEVER DO

- Never modify the architecture or prompt library without Salim's explicit instruction
- Never add "helpful" features Salim didn't ask for
- Never refactor working code during a feature task
- Never use a different model than what the architecture specifies for an agent
- Never hardcode values that should be in config
- Never commit without approval
- Never skip reading the docs before coding
- Never define Pydantic models inside agent files — they go in src/models/
- Never call LLM APIs directly — always use the wrapper
- Never generate content without [Ref:] traceability in agents that require it
```

---

## 3. Development Workflow

### How Salim and Cursor Work Together

```
SALIM                           CURSOR (Engineer)
  │                                  │
  │  "Build the Context Agent"       │
  │ ───────────────────────────────> │
  │                                  │ 1. Read docs/prompt-library.md → Context Agent section
  │                                  │ 2. Read docs/architecture.md → Agent table
  │                                  │ 3. Read src/models/ → existing schemas
  │                                  │ 4. State what was read and understood
  │                                  │ 5. Implement agent.py + prompts.py
  │                                  │ 6. Run tests
  │                                  │ 7. Report: "Done. Here's what I built, here's the test result."
  │                                  │
  │  Reviews code                    │
  │  "Approved" or "Rejected: ..."   │
  │ ───────────────────────────────> │
  │                                  │
  │  If approved:                    │
  │  "Commit and push"              │
  │ ───────────────────────────────> │
  │                                  │ git add, commit, push
  │                                  │
  │  If rejected:                    │
  │  "Fix: the output schema..."    │
  │ ───────────────────────────────> │
  │                                  │ Fix exactly what was requested
  │                                  │ Re-test
  │                                  │ Report results
  │                                  │
```

### Build Order (Recommended)

```
Phase 0: Foundation
  Task 0.1: Create project scaffold (folders, files, .gitignore, requirements.txt)
  Task 0.2: Create src/models/enums.py (all canonical enums from Appendix A)
  Task 0.3: Create src/models/ (all Pydantic models: rfp.py, claims.py, slides.py, report.py, actions.py, waiver.py)
  Task 0.4: Create src/models/state.py (DeckForgeState master state)
  Task 0.5: Create src/services/llm.py (unified LLM wrapper for OpenAI + Anthropic)
  Task 0.6: Create src/config/settings.py + src/config/models.py

Phase 1: Agents (one at a time, in pipeline order)
  Task 1.1: Context Agent (src/agents/context/) + test
  Task 1.2: Retrieval Planner (src/agents/retrieval/planner.py) + test
  Task 1.3: Retrieval Ranker (src/agents/retrieval/ranker.py) + test
  Task 1.4: Analysis Agent (src/agents/analysis/) + test
  Task 1.5: Research Agent (src/agents/research/) + test
  Task 1.6: Structure Agent (src/agents/structure/) + test
  Task 1.7: Content Agent (src/agents/content/) + test
  Task 1.8: QA Agent (src/agents/qa/) + test
  Task 1.9: Conversation Manager (src/agents/conversation/) + test

Phase 2: Pipeline
  Task 2.1: Create src/pipeline/graph.py (LangGraph StateGraph wiring all agents)
  Task 2.2: Create src/pipeline/gates.py (human approval gate logic — CLI for local)
  Task 2.3: Create scripts/run_pipeline.py (CLI runner: input RFP → output PPTX)
  Task 2.4: Integration test with real SIDF SAP RFP

Phase 3: Rendering
  Task 3.1: Create src/services/renderer.py (python-pptx Design Agent)
  Task 3.2: Template map extraction from Presentation6.pptx
  Task 3.3: Test render with sample slide objects → verify PPTX output

Phase 4: Knowledge Layer (for production — skip for local prototype if using test docs)
  Task 4.1: Create src/services/sharepoint.py (Graph API client)
  Task 4.2: Create src/agents/indexing/classifier.py + prompts.py
  Task 4.3: Create src/utils/extractors.py (PPTX/PDF/DOCX extraction)
  Task 4.4: Create src/utils/chunking.py (hierarchical chunking)
  Task 4.5: Create scripts/index_sharepoint.py
  Task 4.6: Create src/services/search.py (Azure AI Search client)
```

### Commit Message Examples

```
feat: add Context Agent with GPT-5.4 structured output
feat: add Retrieval Planner with 5-strategy query generation
feat: add Analysis Agent with atomic claim extraction
feat: add Research Agent with No Free Facts enforcement
feat: add QA Agent with fail-close on critical gaps
feat: add LangGraph pipeline with 5 gates
fix: correct claim ID mapping in Research Agent output
test: add SIDF SAP RFP integration test
chore: update model config for GPT-5.4 pricing
docs: update prompt library with revised QA framing rule
```

---

## 4. Local Development vs Production

### For Salim's Local Build

Replace SharePoint + Azure AI Search with local equivalents:

| Production Component | Local Equivalent |
|---------------------|-----------------|
| SharePoint + Graph API | `./test_docs/` folder with sample PPTX/PDF/DOCX files |
| Azure AI Search | In-memory vector search using `numpy` + `text-embedding-3-large` via API |
| Azure Blob Storage | Local `./output/` folder |
| Redis (state persistence) | JSON file on disk (`./state/session.json`) |
| Azure AD auth | None (single user) |
| BD Station webhook | CLI input (`scripts/run_pipeline.py`) |

The code should use **abstraction layers** so swapping local → production is a config change, not a code rewrite:

```python
# src/config/settings.py
class Settings(BaseSettings):
    environment: str = "local"  # "local" or "production"
    storage_backend: str = "local"  # "local" or "azure"
    search_backend: str = "local"  # "local" or "azure"
    state_backend: str = "local"  # "local" or "redis"
    local_docs_path: str = "./test_docs"
    output_path: str = "./output"
    state_path: str = "./state"
    template_path: str = "./templates/Presentation6.pptx"
```

**Note:** SharePoint integration in production uses the Microsoft Graph REST API directly (`src/services/sharepoint.py`), not an SDK. The local equivalent is simply reading files from `./test_docs/`.

---

*End of Document | DeckForge Project Scaffold v1.0 | March 2026*
