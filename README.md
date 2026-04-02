# DeckForge

Agentic proposal intelligence system for Strategic Gears Consulting. Transforms RFP documents into proposal-grade Source Books and presentation decks through a multi-agent pipeline with human approval gates.

---

## Quick Start (Windows)

### Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | 3.12+ | `python --version` |
| Node.js | 18.17+ | `node --version` |
| npm | 9+ | `npm --version` |
| Git | any | `git --version` |

**For live mode** (real LLM calls): you need API keys for OpenAI and Anthropic. See [Environment Setup](#environment-setup).

### 1. Clone and install backend

```powershell
git clone https://github.com/albarami/Deckbuilder.git
cd Deckbuilder

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Install frontend

```powershell
cd frontend
npm install
cd ..
```

### 3. Environment setup

**Backend** -- copy the example and fill in your API keys:

```powershell
copy .env.example .env
```

Edit `.env` and set:

| Variable | Required for | Notes |
|----------|-------------|-------|
| `OPENAI_API_KEY` | Live mode | GPT-5.4 calls |
| `ANTHROPIC_API_KEY` | Live mode | Claude Opus/Sonnet calls |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional | Richer academic evidence in Source Book mode |
| `PERPLEXITY_API_KEY` | Optional | Richer web evidence in Source Book mode |
| `AZURE_SEARCH_*` | Production only | Not needed for local dev |
| `SHAREPOINT_*` | Production only | Not needed for local dev |

**Frontend** -- create `frontend/.env.local`:

```powershell
copy frontend\.env.local.example frontend\.env.local
```

Default values work for local development. Only change if your backend runs on a different port.

### 4. Start the backend

```powershell
# Activate venv if not already active
.venv\Scripts\activate

# Live mode (real LLM calls, requires API keys)
$env:PIPELINE_MODE="live"
uvicorn backend.server:app --reload --port 8000
```

Verify: open `http://localhost:8000/api/health` -- should return `{"status": "ok", ...}`.

### 5. Start the frontend

In a **separate terminal**:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000` in your browser.

### 6. Smoke test

1. Navigate to **New Proposal** (`/en/new`)
2. Select **Source Book Only** mode
3. Upload any PDF (an RFP document works best)
4. Select a sector and geography
5. Click **Generate Source Book**
6. Approve Gate 1 (Context Review) and Gate 2 (Source Review)
7. Wait for Source Book generation (2-8 minutes in live mode)
8. Review Gate 3 -- download DOCX, approve or reject with feedback
9. View the completion panel with artifact summary

"Working" means: you see the agent grid updating, the timeline showing stage transitions, and Gate 3 appearing with a downloadable DOCX.

---

## Project Structure

```
Deckbuilder/
  backend/                  # FastAPI API layer
    models/api_models.py    # All API contracts (Pydantic)
    routers/                # HTTP endpoints (pipeline, gates, export, upload, slides)
    services/               # Session manager, SSE broadcaster, pipeline runtime
  src/                      # Core pipeline engine
    agents/                 # LLM agents (context, retrieval, source_book, etc.)
    models/                 # Domain models (state, source_book, rfp, etc.)
    pipeline/               # LangGraph graph definition
    services/               # LLM wrapper, routing, export, accounting
  frontend/                 # Next.js 14 + React 18 + TypeScript
    src/app/                # App router pages
    src/components/         # UI components (pipeline, gates, intake, artifacts, export)
    src/stores/             # Zustand state management
    src/hooks/              # Custom hooks (pipeline, SSE, gate)
    src/lib/                # API clients, types
    src/i18n/               # EN/AR translations
  templates/                # PPTX template (tracked in git)
  PROPOSAL_TEMPLATE/        # .potx proposal templates (NOT in git -- see note below)
  output/                   # Generated artifacts per session (gitignored)
  tests/                    # Backend pytest tests
  docs/plans/               # Implementation plans
```

---

## Pipeline Modes

The system has two proposal modes selectable from the intake UI:

| Mode | What it produces | Gates |
|------|-----------------|-------|
| **Source Book Only** | Proposal intelligence DOCX + evidence ledger + blueprints + routing report | 3 gates (Context, Sources, Source Book) |
| **Full Proposal Deck** | Everything above + branded PPTX slide deck | 5 gates (+ Slides, QA) |

---

## Important Caveats

### dry_run mode is currently broken

`PIPELINE_MODE=dry_run` does not work reliably. `src/pipeline/dry_run.py` patches `src.pipeline.graph.load_documents`, which no longer exists. For real validation, use `PIPELINE_MODE=live` with valid API keys.

### PROPOSAL_TEMPLATE directory

The `PROPOSAL_TEMPLATE/` directory contains `.potx` branded templates and is **not tracked in git** (too large / environment-specific). It is only needed for the **Full Proposal Deck** mode (PPTX rendering). **Source Book Only** mode works without it.

If you need deck rendering, obtain the template files separately and place them in `PROPOSAL_TEMPLATE/`:
- `Arabic_Proposal_Template.potx`
- `PROPOSAL_TEMPLATE EN.potx`

### API costs

Live mode makes real LLM calls. A full Source Book run costs approximately $2-5 USD across 15-16 LLM calls (GPT-5.4 + Claude Opus/Sonnet).

---

## Test Commands

### Backend

```powershell
.venv\Scripts\activate

# Run all backend tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/services/test_session_accounting.py -v
```

### Frontend

```powershell
cd frontend

# TypeScript check
npx tsc --noEmit

# Run all tests
npx vitest run --reporter=verbose

# Watch mode
npx vitest
```

---

## Troubleshooting

### Backend won't start

**"Module not found" errors:**
Make sure the venv is activated and you ran `pip install -r requirements.txt` from the repo root.

**"OPENAI_API_KEY not set" or similar:**
Copy `.env.example` to `.env` and fill in your API keys. The backend reads from `.env` via `python-dotenv`.

### Frontend can't reach backend

**CORS errors or "Failed to fetch":**
- Ensure the backend is running on port 8000: `http://localhost:8000/api/health`
- The frontend defaults to `http://localhost:8000` as the API URL
- If you changed the backend port, create `frontend/.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:YOUR_PORT`

### Frontend shows raw stage keys (e.g., "evidence_curation")

This means the i18n translation keys are missing. Pull the latest code -- the EN/AR translation files should have all stage and agent labels.

### Pipeline stuck or no SSE events

- Check the backend terminal for error logs
- Ensure `PIPELINE_MODE=live` is set (not `dry_run`)
- The Source Book generation phase takes 2-8 minutes -- the UI should show "Evidence Curation" with "(this may take several minutes)"

### npm install fails

- Ensure Node.js 18.17+ is installed
- Delete `frontend/node_modules` and `frontend/package-lock.json`, then run `npm install` again

---

## Architecture

### Backend: FastAPI + LangGraph

- `backend/server.py` -- FastAPI app with CORS, lifespan, router registration
- `backend/services/pipeline_runtime.py` -- Drives graph execution, SSE broadcasts, gate handling
- `backend/services/session_manager.py` -- In-memory session state
- `backend/services/sse_broadcaster.py` -- Per-session SSE event queues

### Frontend: Next.js 14 + Zustand

- App router with `[locale]` prefix (EN/AR)
- Zustand pipeline store with SSE event hydration
- Real-time agent grid, activity timeline, progress bar
- Artifact viewer components for Source Book mode

### Pipeline: LangGraph State Machine

- `src/pipeline/graph.py` -- Node definitions + edge routing
- `src/models/state.py` -- `DeckForgeState` master state object
- Agents are pure async functions: `run(state) -> dict[str, Any]`
- Gates are LangGraph interrupts -- backend catches them, frontend renders review UI
