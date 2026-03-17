# DeckForge Technical Build Status



## Executive Summary

DeckForge is currently a **working technical prototype / bridge system** with these major capabilities already implemented:

- A **LangGraph-based proposal pipeline** with staged execution and human approval gates.
- A **FastAPI backend** that exposes pipeline start, status, SSE streaming, uploads, gate decisions, slide preview APIs, and export APIs.
- A **Next.js frontend** for dashboard, new proposal intake, live pipeline monitoring, gate review, slide browsing, and export views.
- A **deterministic rendering layer** for PPTX and DOCX generation.
- A **local retrieval and indexing foundation** for company knowledge search, including chunking, embeddings, classification, deduplication, and knowledge graph extraction.
- A **dry-run mode** for demos and local development without live LLM calls.

At the same time, the system is **not fully complete yet**. The biggest remaining gaps are:

- Real production-grade export delivery is not fully wired end-to-end.
- Session persistence is still in-memory.
- Frontend history/dashboard still rely on browser session storage instead of backend persistence.
- The company retrieval / RAG / indexing layer exists in foundation form, but the full enterprise knowledge integration is still planned rather than complete.
- There are a few backend/frontend integration mismatches that still need cleanup.

## End-to-End Journey

This section explains the current DeckForge journey from the moment a user starts a proposal until the system reaches review and export.

### Step 1. The user starts a proposal from the frontend

The journey begins in the Next.js frontend on the new proposal intake page.

From that screen, the user can currently:

- upload source files
- paste raw text
- provide a structured RFP brief
- choose language
- choose proposal mode
- choose sector and geography
- select renderer mode
- add user notes

The frontend then calls the pipeline start API through the typed API client layer.

### Step 2. The backend creates a pipeline session

When the start request reaches the FastAPI backend, `backend/routers/pipeline.py` validates the input and creates a new in-memory session through `backend/services/session_manager.py`.

At this point, the backend stores:

- a generated session ID
- session metadata such as language, proposal mode, sector, geography, and renderer mode
- any uploaded document references
- initial agent run cards
- initial deliverable placeholders

The backend then starts an asynchronous pipeline task rather than blocking the request.

### Step 3. The frontend switches into live session mode

After the start call succeeds, the frontend navigates to the pipeline session page.

That page restores state from the backend status endpoint and opens an SSE connection to the backend stream endpoint. The SSE layer is implemented through the frontend SSE client and the backend broadcaster.

This gives the frontend a live channel for:

- stage changes
- gate pending events
- completion events
- error events
- heartbeat events

This is the core reason the UI can behave like a live workflow instead of a simple polling page.

### Step 4. The runtime bridge builds the initial pipeline state

Inside `backend/services/pipeline_runtime.py`, the backend converts the API session into the LangGraph state model.

This step currently gathers:

- uploaded document text metadata
- raw text input or a structured brief summary
- user notes
- output language
- renderer selection input

The runtime then invokes the LangGraph graph in `src/pipeline/graph.py`.

### Step 5. Context understanding runs first

The first major pipeline stage is context extraction.

The context agent transforms the proposal intake into structured RFP context, including fields such as:

- RFP name
- issuing entity
- mandate
- scope
- deliverables
- compliance requirements
- key dates
- submission format

Once this context package is prepared, the graph pauses at Gate 1.

### Step 6. Gate 1 pauses for human review

Gate 1 is the first human checkpoint.

The backend packages the extracted context into a frontend-ready gate payload, and the frontend renders it in the gate review UI.

At this point the user can:

- approve the extracted context
- reject it with feedback

If approved, the pipeline resumes.

If rejected, the flow stops at that gate and records the decision.

### Step 7. Retrieval runs against the current knowledge layer

After Gate 1 approval, the graph enters retrieval.

The retrieval chain currently works as:

1. retrieval planner generates search queries
2. local search service executes semantic lookup
3. retrieval ranker selects and structures the best sources

Today, this is backed mainly by the local indexing and search foundation rather than a finished enterprise retrieval stack.

The system already has a real retrieval path, but the planned company-wide retrieval platform is still not fully complete.

### Step 8. Gate 2 presents sources for review

When retrieval completes, the backend prepares a source review payload and pauses at Gate 2.

The intended journey here is:

- the user sees the shortlisted sources
- the user chooses which sources to keep or exclude
- the selected sources become the approved evidence set for downstream analysis

This part is conceptually implemented, but it still has a wiring issue in the current build. The UI exists, but source selection modifications are not yet reliably submitted end-to-end.

### Step 9. Analysis converts approved sources into structured evidence

After Gate 2 approval, the analysis stage loads approved documents and extracts structured evidence.

This stage builds the reference layer that later stages depend on. In practical terms, it is where DeckForge begins converting documents into reusable internal knowledge objects rather than treating them as plain text.

The output includes evidence and claim structures that are later consumed by research and slide generation.

### Step 10. Research generates the report-first output

After analysis, the research stage produces the research report.

This is one of the most important architectural decisions in the system: slides are not supposed to be created first. The system generates a research report first and expects that report to become the approved factual base for the deck.

The research output includes:

- report markdown
- report sections
- gaps
- source index references
- sensitivity summaries

Then the graph pauses again at Gate 3.

### Step 11. Gate 3 is the main review checkpoint

Gate 3 is effectively the approval point for the report-first model.

At this stage, the frontend shows the report review payload and the user reviews:

- the research narrative
- gaps and missing evidence
- section-level summaries
- source references

If Gate 3 is approved, the system is allowed to move from evidence synthesis into deck creation.

### Step 12. Iterative slide building creates the presentation content

After Gate 3 approval, DeckForge runs the iterative slide build stage.

The current graph no longer treats this as a single simple slide-write call. Instead it uses a multi-turn build process that includes draft and review cycles before the final written slides are prepared.

This stage is responsible for converting the approved report into:

- slide titles
- key messages
- body content
- content guidance
- speaker notes
- source references on slides

This is the main bridge between research output and presentation output.

### Step 13. Gate 4 lets the user review slides before QA finishes the flow

Once the iterative slide build finishes, the backend prepares slide preview metadata and pauses at Gate 4.

The frontend can then show:

- slide cards
- preview text
- source claims
- source references
- slide-level metadata

The current preview experience is useful, but it is important to note that the thumbnail PNG endpoint still produces synthetic preview images rather than true rendered slide screenshots.

### Step 14. QA validates the deck

After Gate 4 approval, the graph moves into QA.

The QA stage validates whether the deck is ready to move to finalization. The gate payload generated from this stage includes readiness status, fail-close behavior, and slide-level validation details.

This is the quality barrier before final output is considered complete.

### Step 15. Gate 5 gives a final approval checkpoint

The last human review gate is Gate 5.

At this point the user reviews the QA result and can decide whether the output is ready for finalization.

This gives the system one last governance checkpoint before it marks the run complete.

### Step 16. Rendering generates deliverables

After Gate 5 approval, the pipeline enters rendering.

The rendering layer is deterministic and currently supports:

- PPTX deck generation
- DOCX report export
- legacy render path
- template-v2 render path

The render stage writes output artifact paths into the pipeline state, and the backend converts those into deliverable records for the frontend.

### Step 17. The frontend receives completion and exposes outputs

When the pipeline reaches finalization, the backend marks the session complete and emits a completion event over SSE.

The frontend then moves the session into the complete state and exposes:

- export page access
- slide browser access
- output readiness state
- session summary information

### Step 18. Export is available, but still partially placeholder

The user can open the export page and trigger downloads.

However, the current backend export endpoint still returns mock payload bytes for the files instead of streaming the actual generated artifacts from disk.

So the journey is complete from a product-flow perspective, but the final artifact delivery step is still only partially productionized.

### Step 19. History and session continuity are still limited

The frontend currently keeps some proposal history in browser `sessionStorage`, and the backend keeps live sessions in memory.

This means the current end-to-end journey works well for:

- local development
- demos
- single-session usage

But it is still limited for:

- durable history
- server restarts
- multi-user persistence
- production auditability

### Step 20. Where company retrieval, RAG, and indexing fit into the journey

The planned company retrieval and RAG system sits in the middle of this journey, mainly between Gate 1 and research generation.

The intended long-term journey is:

1. ingest company documents such as proposals, decks, reports, and frameworks
2. extract and normalize their content
3. chunk them into retrievable units
4. generate embeddings
5. classify and enrich them with metadata
6. extract entities and relationships into a knowledge graph
7. index them into a production search backend
8. retrieve the most relevant company evidence for each proposal
9. ground analysis, research, and slide generation on that retrieved evidence

Parts of this are already built locally today, especially the indexing and search foundation. What remains is turning that foundation into a full company-wide retrieval and RAG platform.

## What Is Actually Built Today

## 1. Core Pipeline Orchestration

The system already has a orchestrated pipeline in `src/pipeline/graph.py`.

### Implemented pipeline flow

The graph currently wires the following flow:

1. Context understanding
2. Gate 1
3. Retrieval
4. Gate 2
5. Analysis
6. Research report generation
7. Gate 3
8. Iterative slide build
9. Gate 4
10. QA
11. Gate 5
12. Render

### What is technically implemented here

- LangGraph `StateGraph` orchestration
- `MemorySaver` checkpointing
- Human-in-the-loop `interrupt()` gate handling
- Resume support using `Command(resume=...)`
- JSON state save/load helpers for crash recovery


## 2. Backend API Layer

The backend is implemented as a FastAPI application in `backend/server.py`.

### Implemented backend components

- FastAPI app bootstrap
- CORS configuration for local frontend development
- Shared singleton services attached to app state
- Health check endpoint
- Router registration for:
  - pipeline
  - gates
  - upload
  - slides
  - export

### Implemented API capabilities

The backend already supports these technical operations:

- Start a pipeline session
- Get pipeline session status
- Stream live events over SSE
- Submit gate decisions
- Upload source documents
- Fetch slide preview metadata
- Fetch slide thumbnail images
- Download deliverables
- List sessions for history/dashboard use


## 3. Session and Runtime State Management

The backend keeps pipeline sessions in an in-memory session manager implemented in `backend/services/session_manager.py`.

### Implemented session features

- Session creation and lookup
- Active session counting
- Pipeline stage tracking
- Gate pending state and gate history
- Agent run metadata storage
- Deliverable metadata storage
- Slide preview metadata storage
- Upload metadata storage
- Session expiration and cleanup loop
- Status response shaping for frontend use
- Session history response shaping

The backend session model already exposes a proper frontend-facing status and history contract.

### Current limitation

This storage is **in-memory only**.

- sessions do not survive server restart
- no database-backed persistence exists yet
- history is temporary unless the same backend process remains alive

## 4. Live Pipeline Runtime Bridge

`backend/services/pipeline_runtime.py` connects the FastAPI layer to the LangGraph pipeline.

### Implemented runtime behaviors

- Converts API/session input into `DeckForgeState`
- Invokes the graph asynchronously
- Supports resume after approval gates
- Syncs LangGraph state back into frontend-facing session objects
- Derives frontend stage labels and step numbers
- Builds gate payloads for all 5 review gates
- Builds slide preview payloads from generated slides
- Derives deliverables from pipeline state
- Broadcasts terminal and gate events to SSE clients
- Supports `dry_run` patching for local/demo mode


## 5. Human Review Gates

The system has a genuine 5-gate review workflow.

### Implemented gate types

- Gate 1: Context review
- Gate 2: Source review
- Gate 3: Research report review
- Gate 4: Slide review
- Gate 5: QA review

### What is already implemented

- Backend gate decision endpoint
- Gate validation rules
- Gate-specific payload generation
- Frontend gate container and gate-specific panels
- Approve/reject actions with feedback support

### Important conclusion

Human governance is a first-class part of the architecture, not something planned for later.

## 6. Frontend Application

The frontend is a Next.js 14 application with `next-intl`, Zustand stores, and a componentized UI.

### Implemented frontend pages

The codebase currently includes pages for:

- Dashboard
- New proposal intake
- Live pipeline session view
- Slide browser
- Export page
- History page

### Implemented frontend technical layers

- API client wrapper with typed error handling
- SSE client with reconnect behavior
- Zustand pipeline store
- Zustand slides store
- Locale-aware routing
- Gate review UI
- Export UI
- Slide preview UI
- Dashboard cards and history view

### Important conclusion

The frontend is already a usable application shell for the proposal workflow, not just a mock landing page.

## 7. Intake and Upload Flow

The intake flow is already implemented on both frontend and backend.

### Implemented intake capabilities

- Upload files through the frontend
- Paste raw text into the proposal intake page
- Configure language, proposal mode, sector, geography
- Start the pipeline from the frontend

### Implemented backend upload behavior

- Accepts PDF, DOCX, and TXT
- Enforces file-type and file-size limits
- Extracts text in live mode
- Stores upload metadata in backend session memory

### Current limitation

Uploads are stored in memory for M11-style bridge behavior, not in durable storage.

## 8. Rendering and Output Generation

The system already includes a deterministic rendering layer.

### Implemented rendering capabilities

In `src/services/renderer.py`:

- PPTX rendering with `python-pptx`
- DOCX export for research reports
- Layout mapping for multiple slide types
- Title, agenda, content, comparison, framework, team, timeline, compliance, and closing slide handling
- RTL support for Arabic slides
- Optional chart insertion
- Speaker notes writing

### Implemented rendering paths

- Legacy render path
- Template-v2 render path scaffold

### Important conclusion

The rendering layer is one of the strongest implemented parts of the system.

## 9. Search, Retrieval, and Indexing Foundation

The repository already contains a meaningful knowledge retrieval foundation in `src/services/search.py` and related services.

### What is already built

The current code already includes:

- Document extraction
- Chunking
- Embedding generation and caching
- Exact duplicate detection
- Near-duplicate detection
- Local vector search using numpy cosine similarity
- Document classification
- Entity extraction
- Knowledge graph merge/save flow
- Manifest generation for indexing output
- Semantic search helper functions
- Legacy `local_search()` and `load_documents()` compatibility helpers

The system already has a serious **retrieval and indexing base**.

However, this is still mainly a **local/dev knowledge layer**, not a finished enterprise company knowledge platform.

## 10. LLM and Model Integration

The project already has a unified LLM wrapper in `src/services/llm.py`.

### Implemented model capabilities

- OpenAI async client support
- Anthropic async client support
- Structured output parsing with Pydantic models
- Retry logic for timeout/rate-limit/server errors
- Unified response wrapper with token counts and latency
- Settings-based API key/model selection

### Important conclusion

Live model integration is present in code and not merely planned.

## 11. Dry-Run / Demo Mode

A full dry-run mode exists.

### Implemented dry-run features

- Typed mock responses for major agents
- Mock retrieval search results
- Mock document loading
- Backend support for `PIPELINE_MODE=dry_run`
- Tests designed around zero real LLM calls

The system can be demonstrated and developed locally without requiring a fully live AI stack.

## 12. Test Coverage Already Present

There is significant test scaffolding already in place.

### Current test areas in code

- Backend health, start, status, slides, upload, and export APIs
- Pipeline integration tests for graph flow and render output
- Frontend component tests with Vitest
- Playwright/e2e scaffolding in the frontend

### Important conclusion

The codebase already has a meaningful validation structure, even if it still needs more production-hardening tests.

## What Is Only Partially Built or Still Demo-Grade

## 1. Export API returns mock file payloads

The export endpoint currently validates session and deliverable readiness correctly, but it still returns `_mock_content(...)` instead of streaming the real generated files.

### Practical meaning

- The export contract exists
- The filenames and API flow exist
- The returned file payload is still placeholder content

This is one of the clearest remaining completion tasks.

## 2. Slide thumbnails are synthetic previews

The slide thumbnail endpoint currently generates PNG images using PIL with a synthetic preview card instead of rendering real slide images from actual PPTX output.

### Practical meaning

- Slide browser UX is implemented
- Thumbnail API exists
- The images are illustrative previews, not real rendered slide snapshots

## 3. Session persistence is not production-grade

Backend sessions are still stored in memory.

### Practical meaning

- good for local work and demo flows
- not good for durable production history, restarts, or multi-instance deployment

## 4. Frontend history/dashboard persistence is browser-local

The frontend dashboard, sidebar recent-session logic, and history page currently read from `sessionStorage` rather than from the backend session history API.

### Practical meaning

- works for a single browser/device demo flow
- does not give real shared history
- does not represent true persistent proposal history

## 5. Gate 2 source-selection review is not fully wired end-to-end

There are two important issues in the current implementation:

- The Gate 2 frontend source extractor expects `id`, while the backend payload exposes `source_id`.
- The gate panel collects modifications, but the `useGate()` hook does not currently send those modifications in the approve/reject API call.

### Practical meaning

The source review UI exists visually, but reviewer source selections are **not yet reliably preserved and submitted**.

## 6. Renderer selection is not fully honored in runtime

The session stores `renderer_mode`, but the backend runtime currently builds initial graph state with `RendererMode.TEMPLATE_V2` hardcoded.

### Practical meaning

The renderer selection contract exists at the API/session level, but runtime execution does not yet fully honor that choice.

## 7. Deliverable support is only partially surfaced in the frontend

The backend contract includes deliverables for:

- PPTX
- DOCX
- source index
- gap report

But the current frontend export flow only exposes download actions for PPTX and DOCX.

### Practical meaning

The broader deliverable model exists, but the UI and actual artifact generation are not fully finished.

## What Still Remains to Complete the Build

## 1. Finish production-grade export delivery

This is the most obvious completion item.

### Remaining work

- stream real PPTX files from actual render output
- stream real DOCX research reports from generated output
- generate and expose real source index artifacts
- generate and expose real gap report artifacts
- wire frontend export UI to all supported deliverables

## 2. Fix integration mismatches between frontend and backend

### Remaining work

- honor requested `renderer_mode`
- fix Gate 2 source-review payload shape mismatch
- send gate modifications from the frontend decision hook
- ensure frontend store uses backend deliverable metadata consistently

## 3. Add durable persistence

### Remaining work

- store sessions in a database or durable state backend
- persist uploaded document metadata and generated artifacts
- support backend session recovery after restart
- make history available across browsers and users

## 4. Complete company retrieval / RAG / indexing layer

This is the major strategic system still planned beyond the current prototype.

### What is already present as foundation

- local indexing pipeline
- chunking and embedding generation
- semantic search helpers
- classification and entity extraction
- knowledge graph merge/save flow
- retrieval planner and ranker stages in the LangGraph pipeline

### What still remains

- enterprise ingestion of company knowledge sources
- reliable indexing of company proposals, decks, reports, frameworks, and case studies
- production retrieval backend instead of local-only/dev-first behavior
- permission-aware document access and metadata handling
- stable corpus refresh/index update workflows
- stronger grounding between retrieval results and downstream generation

## 5. Implement the planned company knowledge retrieval architecture

### Planned direction

The intended company knowledge layer appears to be:

- ingest internal company documents
- extract and normalize text/content
- chunk and embed them
- classify and enrich them with metadata
- extract entities and relationships into a knowledge graph
- retrieve relevant company evidence during proposal generation
- use that retrieval as the factual grounding layer for report and slide generation

### In practical AI terms

This is the planned **company retrieval + RAG + indexing subsystem**.

It is **partly built at the service/foundation level**, but **not yet complete as a production company knowledge platform**.

## 6. Production search backend is still pending

The code includes an `AzureAISearchBackend` class, but it is still a stub that raises `NotImplementedError`.

### Remaining work

- choose and finish the production search backend
- likely Azure AI Search or equivalent enterprise retrieval service
- integrate it with the indexing pipeline and retrieval runtime
- validate quality, latency, permissions, and ranking behavior

## 7. Improve real-time execution visibility

SSE streaming is implemented and works for gate/terminal flow, but the real-time execution experience can still be improved.

### Remaining work

- richer per-agent event broadcasting
- stage transition broadcasts at finer granularity
- better progress telemetry for long-running live sessions
- clearer frontend visualization of agent execution details

## 8. Harden template-v2 rendering path

Template-v2 is present and materially wired, but it still needs completion and hardening.

### Remaining work

- ensure manifest generation is stable for all slide types
- verify template discovery and catalog-lock handling in all environments
- validate output fidelity against the official company template
- complete composition QA and template parity checks for production use

## 9. Add enterprise readiness features

### Remaining work

- authentication and authorization model
- secure artifact storage
- auditability of approvals and changes
- structured logging and observability
- deployment/runtime hardening
- operational workflows for indexing refresh and corpus maintenance

## Overall Status

**DeckForge is already a real technical system, not just a concept.**

It already has:

- a real multi-step AI pipeline
- human approval gates
- a working backend API
- a working frontend application
- slide/report generation code
- local retrieval/indexing foundations
- testing infrastructure

But it is still **between prototype and production system** because several critical completion items remain:

- durable persistence
- real artifact exports
- fully wired company retrieval/RAG/indexing
- production search backend
- a few frontend/backend wiring fixes

## Final Assessment

### Current state

DeckForge is best described today as a:

**working end-to-end technical prototype with strong architectural foundations and a partially implemented enterprise knowledge layer**.

### Not yet complete because

The system still needs:

- productionized exports
- persistent storage
- complete company retrieval and RAG integration
- finished indexing and search backend rollout
- integration cleanup between some frontend and backend components

### Most important takeaway

The hardest architectural parts are already present:

- pipeline orchestration
- human gate model
- backend/frontend bridge
- rendering layer
- indexing/retrieval foundation

What remains is mainly **product completion, production hardening, and enterprise knowledge integration**.
