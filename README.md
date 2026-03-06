# DeckForge

**Agentic Presentation Intelligence System**
**Report-First | No Free Facts | Bilingual Output**

DeckForge is an RFP-to-Deck engine built for Strategic Gears Consulting. It transforms institutional knowledge — stored across SharePoint presentations, proposals, reports, and frameworks — into consulting-grade proposal decks through a conversational, multi-agent workflow.

The system receives structured RFP summaries, searches and synthesizes relevant knowledge from a pre-indexed SharePoint corpus, generates a fully-cited research report for human approval, and converts that approved report into a branded slide deck in Arabic, English, or bilingual format.

---

## Architecture Summary

### Pipeline: 10 Steps, 5 Human Gates

1. **RFP Intake** — BD Station pushes structured AI Assist summary (10-field contract)
2. **Context Understanding** — Context Agent parses RFP into structured object → **Gate 1**
3. **SharePoint Retrieval** — Retrieval Agent executes 5-strategy search → **Gate 2**
4. **Deep Analysis** — Analysis Agent extracts atomic Claim Objects into Reference Index
5. **Research Report** — Research Agent writes fully-cited report → **Gate 3** (most important)
6. **Slide Outline** — Structure Agent converts report to slide structure → **Gate 4**
7. **Slide Content** — Content Agent distills report into slide copy
8. **Quality Assurance** — QA Agent enforces No Free Facts, validates every claim
9. **PPTX Rendering** — Design Agent renders branded PPTX via python-pptx → **Gate 5**
10. **Export** — Final PPTX, research report (.docx), source index, gap report

### 9 Agents, 3 Models

| Agent | Model | Role |
|-------|-------|------|
| Workflow Controller | LangGraph (deterministic) | State machine routing, gate enforcement |
| Conversation Manager | Claude Sonnet 4.6 | Natural language → structured actions |
| Context Agent | GPT-5.4 | RFP parsing into structured JSON |
| Retrieval Agent | GPT-5.4 + Azure AI Search | Query generation + source ranking |
| Analysis Agent | Claude Opus 4.6 | Deep extraction into atomic Claim Objects |
| Research Agent | Claude Opus 4.6 | Fully-cited research report generation |
| Structure Agent | GPT-5.4 | Report → slide outline conversion |
| Content Agent | GPT-5.4 | Slide copy writing from approved report |
| QA Agent | GPT-5.4 | No Free Facts enforcement, validation |
| Design Agent | python-pptx (deterministic) | Branded PPTX rendering |

### Core Principles

- **No Free Facts** — every factual claim must trace to a cited source. Unsupported claims fail closed.
- **Report-First** — a research report is approved by humans before any slides are created.
- **Gaps over guesses** — missing evidence is flagged explicitly, never fabricated.

---

## Current Milestone Status

| Milestone | Scope | Status |
|-----------|-------|--------|
| M0: Scaffold + README | Project structure, config, dependencies, README | **In progress** |
| M1: Enums | `src/models/enums.py` — 19 StrEnum classes | Planned |
| M2: Pydantic Models | 9 model files (`common.py` through `indexing.py`) | Planned |
| M3: Master State | `state.py` + `ids.py` + `__init__.py` re-export | Planned |
| M4: Config + LLM Wrapper | `settings.py` + `models.py` + `llm.py` | Planned |
| M5–M10: Agents, Pipeline, Rendering, Knowledge Layer | Full system | Deferred |

---

## Local Setup

### Prerequisites

- Python 3.12+
- Git

### Installation

```bash
git clone https://github.com/albarami/Deckbuilder.git
cd Deckbuilder

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. Azure keys are needed for production only.

---

## Test Commands

```bash
# Run all tests
.venv\Scripts\python.exe -m pytest tests/ -v

# Run tests for a specific module
.venv\Scripts\python.exe -m pytest tests/agents/test_enums.py -v

# Lint check
.venv\Scripts\python.exe -m ruff check src/

# Type check
.venv\Scripts\python.exe -m mypy src/

# All three (run before every review)
.venv\Scripts\python.exe -m pytest tests/ -v && .venv\Scripts\python.exe -m ruff check src/ && .venv\Scripts\python.exe -m mypy src/
```

---

## Repo Workflow

### Roles

- **Cursor** builds code
- **Salim** reviews, approves or rejects, and authorizes commits

### Protocol

1. **Read docs first** — architecture, prompt library, state schema, existing code
2. **Implement one thing** — exactly what Salim asked, nothing more
3. **Validate and test** — pytest, ruff, mypy must all pass
4. **Report results** — state what was built, what was tested, what passed
5. **Wait for approval** — no commits until Salim says "commit"

### Commit Convention

```
feat(scope): description    — new feature or agent
fix(scope): description     — bug fix
test(scope): description    — adding or updating tests
refactor(scope): description — code restructure (no behavior change)
docs(scope): description    — documentation changes
chore(scope): description   — config, dependencies, tooling
```

### Rules

- Never commit without Salim's explicit approval
- Never push broken code
- Never force push
- Docs are the source of truth — if code contradicts docs, fix the code
- All Pydantic models in `src/models/`, never inline in agent files
- All LLM calls through `src/services/llm.py`, never direct API imports in agents

### Remote

```
origin  https://github.com/albarami/Deckbuilder.git
```
