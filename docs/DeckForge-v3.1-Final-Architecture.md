# DECKFORGE — Final Architecture Specification

**Agentic Presentation Intelligence System**
**Report-First | No Free Facts | Bilingual Output**

Strategic Gears Consulting
Technology & Digital Transformation Pillar
Version 3.1 — March 2026 — CONFIDENTIAL

---

## 1. Executive Summary

DeckForge is an RFP-to-Deck engine purpose-built for Strategic Gears Consulting. It transforms the firm's institutional knowledge — stored across SharePoint presentations, proposals, reports, and frameworks — into consulting-grade proposal decks through a conversational, multi-agent workflow.

The system integrates with BD Station to receive structured RFP summaries, searches and synthesizes relevant knowledge from a pre-indexed SharePoint corpus, generates a fully-cited research report for human approval, and then converts that approved report into a branded slide deck in Arabic, English, or bilingual format.

### Core Design Principles

- **No Free Facts**: Every factual claim must trace to a specific source document. If the system cannot cite it, the system cannot say it. Unsupported claims fail closed.
- **Report-First**: A comprehensive research report is generated and approved by humans before any slides are created. The deck is a faithful rendering of approved content.
- **Institutional memory first**: SharePoint content always takes priority over general knowledge. The system is an intelligent assembler of existing knowledge, not a creative writer.
- **Deterministic branding**: Template compliance is enforced by code, not AI. Colors, fonts, margins, and logo position are inherited from the master template file.
- **Approval gates, not auto-pilot**: The system proposes, the human decides. Five explicit gates ensure human control at every critical juncture.
- **Gaps over guesses**: A clearly flagged gap that the human fills with verified data produces a stronger proposal than an AI-generated claim that might be wrong.

---

## 2. The No Free Facts Framework

No Free Facts is a content governance framework that applies to every agent in the DeckForge pipeline. It is designed to make unsupported factual claims fail closed through source-bound generation and validation.

### 2.1 Core Rules

1. Every factual claim in any DeckForge output (report or slide) must include a source reference `[Ref: xxx]` pointing to a specific document, section, or slide in the knowledge base or uploaded files.
2. The LLM may synthesize, reorganize, summarize, and translate source content. It may not invent new facts, statistics, project names, client names, dates, certifications, or team qualifications.
3. General knowledge statements (e.g., "SAP HANA is an in-memory database") are permitted only for context framing, never for claims about Strategic Gears' capabilities, experience, or compliance. A whitelist of permitted framing phrases is maintained by the system administrator to help the QA Agent distinguish factual claims from general framing.
4. If the knowledge base does not contain sufficient evidence for a required proposal section, the system flags the gap explicitly (`GAP: [description]. Human input required.`) rather than filling it with generated content.
5. The QA Agent enforces this rule by checking every factual claim against the source reference index. Claims without valid references are rejected and flagged.
6. **Speaker notes are also governed by No Free Facts.** Presenter notes may contain delivery guidance and framing language but must not introduce factual claims absent from the slides and report.
7. **Human edits at Gate 3 are treated as authoritative.** When a human adds or modifies content in the research report, that content becomes a valid source. The human is the source — no additional reference is required for human-authored content.

### 2.2 Claim Object Schema

Every factual claim in the pipeline is represented as a structured object for machine-enforced traceability:

| Field | Type | Description |
|-------|------|-------------|
| `claim_id` | string | Unique identifier (e.g., "CLM-0047") |
| `claim_text` | string | The factual statement |
| `source_doc_id` | string | SharePoint document ID or uploaded file ID |
| `source_location` | string | Section, page, or slide number within the source |
| `evidence_span` | string | The specific text excerpt from the source that supports the claim |
| `sensitivity_tag` | enum | `compliance` · `financial` · `client_specific` · `capability` · `general` |
| `approved_by` | string \| null | Human approver identity (populated at Gate 3) |
| `approval_timestamp` | datetime \| null | When the claim was approved |
| `source_hash` | string | Hash of the source document at retrieval time |
| `source_version_id` | string | SharePoint version ID for auditability |

### 2.3 Mandatory Fail-Close Rule

**If an unresolved GAP exists in a mandatory compliance, certification, pricing, or client-specific section, DeckForge blocks finalization until the gap is resolved or explicitly waived by a human approver.** The system will not export a proposal deck with critical unresolved gaps. Non-critical gaps (e.g., missing background context, optional appendix items) are permitted in the final output but are clearly marked.

### 2.4 What This Means in Practice

| Scenario | Without No Free Facts | With No Free Facts |
|----------|----------------------|-------------------|
| RFP requires 5+ years SAP experience | LLM writes: "Strategic Gears has 8 years of SAP experience." (May be hallucinated.) | System searches knowledge base. Finds 3 SAP projects dated 2019–2025. Writes: "Strategic Gears has delivered SAP projects since 2019 [Ref: PROJ-041, PROJ-067, PROJ-089]." If no evidence found: `GAP: No SAP experience evidence in knowledge base.` |
| RFP asks for NCA cybersecurity compliance | LLM writes: "We are fully NCA compliant." (No evidence.) | System searches for NCA certification docs. If found: "NCA compliance demonstrated per [Ref: CERT-012]." If not: `GAP: NCA compliance evidence not found. Manual input required.` |
| Slide needs team Saudi percentage | LLM estimates: "70% Saudi nationals." (Potentially fabricated.) | System pulls HR data from past proposals. If found: "Saudi nationals: 68% [Ref: PROP-2025-Q3, Team Slide 4]." If not: `GAP: Saudization data required. Please provide current figures.` |

---

## 3. Report-First Architecture

### 3.1 Why Report-First

The v2.0 pipeline went directly from content synthesis to slide writing. This forced the system to think in slide format from the start, which has three problems: slides are hard for humans to review for factual accuracy; slide constraints force content compression before the human has approved the underlying facts; and the human approves a structure, not substance.

v2.1+ introduces a **Research Report** as a mandatory intermediate artifact. The system first produces a comprehensive, fully-cited document. The human reviews and approves the report. Only then does the system convert the approved report into slides.

### 3.2 Comparison

| Dimension | Slide-First | Report-First |
|-----------|-------------|--------------|
| Human reviews... | A slide outline (titles + bullet placeholders). Substance is hidden. | A full research report with cited evidence. Every claim is visible and challengeable. |
| Hallucination risk | High. LLM writes slide content directly. | Reduced. No Free Facts enforced in the report. Every claim has a [Ref]. QA Agent validates. |
| Content reusability | Low. Slides are the only output. | High. The report is independently valuable — briefing doc, oral presentation basis, future reference. |
| Deck accuracy | Depends on slide-level QA catching errors post-generation. | Deterministic. Slides are a faithful transformation of an approved document. |
| Iteration cost | Expensive. Changing content re-runs Content + Design agents. | Cheaper. Change the report, re-render slides. Content and design are decoupled. |

---

## 4. Pipeline: 10 Steps, 5 Gates

### Phase A: Understand

**Step 1: RFP Intake**

BD Station pushes the structured AI Assist summary (10-field contract) to DeckForge. The user may also upload original RFP PDFs and add strategic context notes. If BD Station is unavailable, a standalone intake form within DeckForge mirrors the same 10-field schema.

The 10 required fields from the AI Assist summary:

1. RFP Name (English and Arabic)
2. Issuing Entity and procurement platform (e.g., Etimad)
3. Overall mandate in 3–5 sentences
4. Scope of work as a structured list of requirements
5. Deliverables as a checklist
6. Technical evaluation criteria with exact weights and sub-weights
7. Financial evaluation criteria with weights
8. Mandatory compliance requirements (certifications, partnerships, legal)
9. Key dates: inquiry deadline, submission, opening, expected award, service start
10. Submission format requirements

**Step 2: Context Understanding**

The Context Agent parses the RFP summary, validates completeness against the 10-field schema, extracts the evaluation matrix with weights, and identifies gaps. If fields are missing or ambiguous, the agent prompts the user to fill them manually rather than guessing.

> **▶ GATE 1:** User confirms context understanding. Selects output language: Arabic, English, or Bilingual.

### Phase B: Retrieve & Research

**Step 3: SharePoint Knowledge Retrieval**

The Retrieval Agent executes a five-strategy search against the pre-indexed SharePoint knowledge layer:

| Strategy | What It Searches | Why It Matters |
|----------|-----------------|----------------|
| RFP-Aligned Search | Maps each evaluation criterion to specific knowledge areas | Ensures highest-weighted criteria get deepest evidence |
| Capability Match | Documents demonstrating specific capabilities required by the RFP | Builds compliance matrix and technical approach |
| Similar RFP Search | Past RFP responses for the same or similar entities/domains | Reuses proven proposal structures and win themes |
| Team & Resource Search | Team profiles, CVs, org charts, Saudization data | Addresses HR evaluation criteria |
| Framework Search | Methodology slides, approach diagrams, governance frameworks | Accelerates the technical approach section |

> **▶ GATE 2:** User reviews retrieved sources. Can add, remove, reprioritize, or request additional searches (e.g., "also search for our Aramco SAP work").

**Step 4: Deep Analysis & Knowledge Extraction**

The Analysis Agent reads all approved source documents in depth. Extracts project details, team profiles, certifications, methodologies, financial data, and compliance evidence. Every extracted fact is stored as a Claim Object (Section 2.2) with source reference, creating the **Reference Index** — the single source of truth for all downstream content.

#### Reference Index Schema

| Field | Type | Description |
|-------|------|-------------|
| `index_id` | string | Unique index identifier for this session |
| `rfp_context` | object | Parsed RFP object from Context Agent |
| `claims` | array[Claim Object] | All extracted factual claims with sources |
| `capabilities` | array | Strategic Gears capabilities matched to RFP requirements |
| `case_studies` | array | Structured project references (client, dates, scope, outcomes, team, value) |
| `team_profiles` | array | Named roles, qualifications, certifications, nationality |
| `compliance_evidence` | array | Certifications, partnerships, legal documents with [Ref] |
| `frameworks` | array | Reusable methodologies and approach models with [Ref] |
| `gaps` | array | Identified evidence gaps mapped to RFP criteria |
| `source_manifest` | array | All source documents with IDs, titles, SharePoint paths, version IDs, and retrieval timestamps |

**Step 5: Research Report Generation**

**This is the core step.** The Research Agent produces a comprehensive proposal research report structured around the RFP's evaluation criteria. The report is **not a slide outline** — it is a full document with:

- **Executive Summary**: Tailored to the RFP's mandate and Strategic Gears' positioning
- **Requirements Analysis**: Point-by-point mapping of RFP scope items to capabilities, each with `[Ref: xxx]`
- **Relevant Experience**: Detailed project case studies from the knowledge base — client, dates, scope, outcomes, team sizes — all cited
- **Technical Approach**: Methodology, tools, SLAs, governance model — drawn from past frameworks
- **Team Composition**: Named roles, qualifications, Saudi national ratio — sourced from past profiles
- **Compliance Matrix**: Every mandatory requirement mapped to evidence
- **Identified Gaps**: Sections where the knowledge base lacks sufficient evidence, clearly flagged with `GAP: [description]. Human input required.`
- **Source Index**: Complete list of all referenced documents with titles, dates, and SharePoint links

Each claim in the report carries a sensitivity tag (`compliance`, `financial`, `client_specific`, `capability`, `general`) to help the human reviewer prioritize their attention.

> **▶ GATE 3: THE MOST IMPORTANT GATE.** User reviews the full research report. Can verify facts, fill in GAP sections with real data, correct inaccuracies, add strategic positioning, adjust tone. **Human review is mandatory for compliance-sensitive, pricing-sensitive, and client-specific claims.** Once approved, this report becomes the canonical source for the deck.

### Phase C: Build Deck

**Step 6: Slide Structure & Outline**

The Structure Agent converts the approved research report into a slide-by-slide outline. It does not add new content — it restructures existing approved content into slide format. Each slide maps to a specific section of the approved report. Layout types are assigned based on content type. Criteria with higher weights receive proportionally greater emphasis in the deck.

> **▶ GATE 4:** User reviews slide outline. Can reorder, split, merge, or adjust layouts. Content changes go back to the report for consistency.

**Step 7: Slide Content Writing**

The Content Agent distills the approved report into consulting-grade slide copy. Key constraint: it may only use information present in the approved report. No new facts, no new claims. It compresses, formats, and sharpens — but does not create. Speaker notes reference the fuller report context and are also governed by No Free Facts.

**Step 8: Quality Assurance**

The QA Agent runs the following checks on every slide:

- **No Free Facts Check**: Every factual claim traces back to the approved report via Claim Objects. Untraceable claims are rejected.
- **Report Consistency Check**: No slide contradicts or embellishes the approved report.
- **Fail-Close Enforcement**: Any unresolved GAP in mandatory compliance, certification, pricing, or client-specific sections blocks finalization.
- **Template Compliance**: Colors, fonts, margins, logo position match the Strategic Gears master template.
- **Text Overflow**: Content fits within slide layout constraints without truncation.
- **RFP Coverage**: Every evaluation criterion is explicitly addressed in the deck.
- **Language Check**: If Arabic output, validates RTL alignment, Arabic text rendering, and bilingual consistency.
- **Framing Phrase Validation**: General statements are checked against the permitted framing phrase whitelist.

**Step 9: PPTX Rendering**

The Design Agent renders validated slides into a branded PPTX file using the Strategic Gears master template via python-pptx. The template (Presentation6.pptx) is loaded directly, inheriting all slide masters and layouts.

> **▶ GATE 5:** User reviews the rendered deck. Changes that affect content go back to the report. Changes that affect only layout or wording are applied directly.

**Step 10: Finalization & Export**

Final outputs:

- Branded .pptx file with speaker notes (Arabic, English, or Bilingual)
- Research report as .docx (the approved canonical document)
- Source index document listing all referenced materials with SharePoint links
- Gap report (if any non-critical gaps remain) for follow-up action

---

## 5. Agent Architecture (9 Agents)

### Model Selection Philosophy

DeckForge uses a multi-model strategy: the best model for each job, matched by capability, not provider loyalty. As of March 2026, GPT-5.4 (released March 5, 2026) leads in structured output, document understanding, token efficiency, and factual accuracy (33% fewer claim errors vs GPT-5.2). Claude Opus 4.6 leads in deep long-context synthesis, nuanced reasoning, and attributed narrative generation. Claude Sonnet 4.6 offers the best conversational instruction-following at mid-tier pricing.

| Agent | Role | Model | Why This Model |
|-------|------|-------|----------------|
| **Workflow Controller** | Conductor | LangGraph (deterministic) | State machine. No LLM. Routes pipeline, enforces gates, manages retries, persists state to Redis. |
| **Conversation Manager** | Interpreter | **Claude Sonnet 4.6** | Best at natural dialogue interpretation. Follows complex conversational instructions more precisely than GPT. Maps "fix slide 5" to `{action: rewrite, target: S-005}`. |
| **Context Agent** | Brief Analyst | **GPT-5.4** | Best at parsing messy input into clean structured JSON. Schema adherence is near-perfect with structured outputs mode. 1M token context handles large RFP documents. |
| **Retrieval Agent** | Knowledge Miner | **Azure AI Search + GPT-5.4** | GPT-5.4's Tool Search system generates diverse, precise search queries with 47% fewer tokens. Combined with Azure AI Search for semantic retrieval. |
| **Analysis Agent** | Deep Reader | **Claude Opus 4.6** | Reading 80K+ tokens of source documents and extracting structured Claim Objects with nuanced understanding. Opus holds coherence across massive inputs better than any other model. 200K context (1M beta). |
| **Research Agent** | Report Writer | **Claude Opus 4.6** | **Core agent.** Writing a comprehensive cited report that synthesizes dozens of sources into a coherent narrative with [Ref] tags throughout. This is Opus's strongest capability — deep synthesis with attribution. |
| **Structure Agent** | Narrative Architect | **GPT-5.4** | Converting an approved report into a structured slide outline is a document-understanding + structuring task. GPT-5.4 produces stronger presentation structures and is the most token-efficient reasoning model. |
| **Content Agent** | Slide Writer | **GPT-5.4** | Compressing report sections into consulting-grade slide copy. GPT-5.4 solves problems with significantly fewer tokens and excels at creating presentation deliverables. |
| **QA Agent** | No Free Facts Enforcer | **GPT-5.4** | Systematic rule checking: does every claim have a [Ref]? 33% fewer claim errors than GPT-5.2 makes this the most reliable model for validation. More methodical and less likely to "forgive" violations. |
| **Design Agent** | Template Engine | **python-pptx** (deterministic) | Renders validated slides into branded PPTX using SG master template. Supports Arabic RTL and bilingual layouts. No LLM involvement. |

### Agent I/O Contracts

| Agent | Input | Output |
|-------|-------|--------|
| Context | RFP AI Assist summary (JSON) + uploaded PDFs + user notes | Parsed RFP object: requirements list, evaluation matrix, compliance checklist, key dates, identified gaps, selected language |
| Retrieval | Parsed RFP object + evaluation criteria with weights | Ranked source list: doc ID, title, summary, relevance score, matched criteria, permission status |
| Analysis | Approved source list + full document content | Reference Index (schema in Section 4): Claim Objects, case studies, team profiles, compliance evidence, frameworks, gaps, source manifest |
| Research | Reference Index + parsed RFP object + selected language | Research Report (.docx): fully-cited proposal document structured by evaluation criteria, with sensitivity-tagged claims and explicit GAP flags |
| Structure | Approved Research Report + presentation type | Ordered array of Slide Objects with layout types, report section mappings, no new content |
| Content | Slide Objects (outline) + approved Research Report | Slide Objects (fully written): body_content, speaker_notes, chart_spec — all derived from report only |
| QA | Fully written Slide Objects + approved Research Report + Claim Object index | Validated Slide Objects: pass/fail per quality rule, flagged issues, fail-close blocks on critical GAPs |
| Design | Validated Slide Objects + master template file + language setting | Rendered .pptx file + slide-by-slide image previews |

### Slide Object Schema

| Field | Type | Description |
|-------|------|-------------|
| `slide_id` | string | Unique identifier (e.g., "S-001") |
| `title` | string | Insight-led headline (the "so what", not descriptive) |
| `key_message` | string | Single sentence: what the audience should take away |
| `body_content` | structured | Bullets, paragraphs, data points, or table data depending on layout |
| `layout_type` | enum | `TITLE` · `AGENDA` · `SECTION` · `CONTENT_1COL` · `CONTENT_2COL` · `DATA_CHART` · `FRAMEWORK` · `COMPARISON` · `STAT_CALLOUT` · `TEAM` · `TIMELINE` · `COMPLIANCE_MATRIX` · `CLOSING` |
| `chart_spec` | object \| null | Chart type (`bar`, `line`, `pie`, `doughnut`, `radar`, `scatter`), axis labels, data series array, color overrides, legend position |
| `source_refs` | array[string] | Claim IDs that inform this slide |
| `report_section_ref` | string | Which section of the approved report this slide derives from |
| `rfp_criterion_ref` | string \| null | Which RFP evaluation criterion this slide addresses |
| `speaker_notes` | string | Full-sentence notes for the presenter (No Free Facts applies) |
| `sensitivity_tags` | array[enum] | Inherited from claim sensitivity tags: `compliance`, `financial`, `client_specific`, `capability`, `general` |
| `change_history` | array[object] | Log of modifications: agent, timestamp, description |

---

## 6. SharePoint Knowledge Layer

### 6.1 Architecture: Content-First Indexing

The system does NOT rely on file names, folder paths, or SharePoint metadata to understand content. Instead: **every document is opened, read in full, and classified by its actual content.** A file named "Final_v2_FINAL_updated.pptx" in a folder called "Misc" is designed to be identified based on content rather than filename or folder metadata.

### 6.2 Indexing Pipeline (Runs Continuously in Background)

**Phase 1: Document Discovery & Extraction**

1. Microsoft Graph API crawler scans all configured SharePoint document libraries on a scheduled basis (every 4 hours, configurable). Webhook-based triggers for newly uploaded documents are supported for fast-moving BD teams.
2. Supported formats: PPTX, PDF, DOCX, XLSX. Unsupported formats flagged for manual review.
3. For PPTX files: custom extractor preserves slide-level structure (title, body text, speaker notes, layout type from slide master, chart data tables, table content). Each slide is extracted as a separate structured object.
4. For PDF/DOCX: Apache Tika extracts text; GPT-5.4 segments the text into logical sections (structured output mode ensures consistent section boundaries).
5. Change detection: only new or modified files (based on SharePoint `lastModifiedDateTime`) are re-processed. A hash is stored to avoid redundant work.

**Phase 2: Content Understanding & Classification**

GPT-5.4 reads extracted content and generates a structured metadata record for each document (GPT-5.4 chosen for this task due to superior structured JSON output and schema adherence):

- **Document type**: Proposal, Case Study, Capability Statement, Technical Report, Client Presentation, Internal Framework, RFP Response, Financial Report, Team Profile, Methodology Document
- **Domain tags**: AI/ML, Digital Transformation, SAP, ERP, Workforce, Cybersecurity, Data Analytics, Cloud, etc.
- **Client/Entity**: extracted from content (not folder name)
- **Geography**: KSA, Qatar, UAE, Egypt, Oman, etc.
- **Date range**: when the work was performed (from content, not file date)
- **Key frameworks used**: methodologies, models, approaches mentioned
- **Quality score**: LLM-assessed on explicit rubric (has client name: +1, has outcomes: +1, has methodology: +1, has data: +1, complete and current: +1. Scale 0–5.)

Additional indexing operations:

- **Topic clustering**: documents grouped into semantic clusters using embedding similarity
- **Duplicate/version detection**: near-duplicate documents identified using cosine similarity > 0.95; most recent/complete version retained

**Phase 3: Embedding & Vector Index**

Hierarchical chunking strategy:

- Level 1: Full document summary (1 embedding per document)
- Level 2: Section-level chunks (logical sections, not arbitrary token splits)
- Level 3: Slide-level chunks (for PPTX, each slide with its parent deck context)

Embeddings generated using Azure OpenAI `text-embedding-3-large` (3072 dimensions, supports Arabic natively). Stored in Azure AI Search with hybrid retrieval (vector + keyword + semantic reranking).

**Phase 4: Knowledge Graph (Phase 2 Build)**

Lightweight knowledge graph linking documents to clients, domains, team members, frameworks, and proposal outcomes (won/lost). Decision criteria for building: if the Phase 2 metadata alone cannot reliably answer cross-document queries like "Find all SAP HANA projects for government entities in KSA in the last 3 years with the teams that delivered them," the knowledge graph moves to priority.

### 6.3 Permission-Aware Retrieval

- At indexing time: each document's SharePoint permissions are recorded as index metadata
- At retrieval time: the requesting user's Azure AD identity is passed to Azure AI Search for security trimming
- Restricted documents are flagged: "A relevant SAP case study exists but you don't have access. Contact [owner] to request."
- No content from restricted documents is ever surfaced for unauthorized users

Note: Azure AI Search's SharePoint indexer with ACL ingestion is currently in preview. Fallback strategy: if the preview feature is deprecated, implement permission filtering at the application layer using Microsoft Graph API permission checks post-retrieval.

### 6.4 Retrieval Feedback Loop

When users modify the source list at Gate 2, the system captures: original retrieval results with scores, user modifications and reasons, final approved set. This signal feeds into periodic re-ranking model updates. Minimum data volume before update: 50 completed sessions. Updates require admin approval before deployment.

### 6.5 Indexing Cost Estimate

Initial indexing (one-time, best-case baseline for first-pass classification): estimated 5,000 documents at ~2K input tokens + ~500 output tokens per classification call via GPT-5.4. Input: ~10M tokens ($25 at $2.50/MTok). Output: ~2.5M tokens ($37.50 at $15/MTok). **Total estimated initial indexing cost: ~$63.** Incremental indexing: negligible (only new/modified documents). This estimate does not include re-processing churn, OCR failures, or richer metadata regeneration.

---

## 7. Technology Decisions (Final)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent Framework | **LangGraph** | Explicit state machines fit the gated workflow. Better observability, state checkpointing, conditional edges, and interrupt/resume at gates. |
| Orchestrator | **Deterministic State Machine + LLM Interpreter** | Workflow routing, gate enforcement, retries are deterministic code. Claude Sonnet 4.6 interprets NL commands only. The LLM does not control the workflow. |
| LLM Strategy | **Multi-model: GPT-5.4 + Claude Opus 4.6 + Claude Sonnet 4.6** | Best model per job. GPT-5.4 for structured output, document understanding, and validation (5 agents). Claude Opus 4.6 for deep synthesis and long-context reasoning (2 agents). Claude Sonnet 4.6 for conversational interpretation (1 agent). |
| GPT-5.4 | **$2.50/$15 per MTok** | OpenAI's most capable frontier model (released March 5, 2026). 1M token context, 33% fewer factual errors, 47% token efficiency improvement. Native structured output mode. |
| Claude Opus 4.6 | **$5/$25 per MTok** | Anthropic's deepest reasoning model. 200K context (1M beta). Strongest long-context synthesis and SWE-bench coding performance. |
| Claude Sonnet 4.6 | **$3/$15 per MTok** | Best instruction-following for conversational tasks. Cost-effective for the Conversation Manager role. |
| Embeddings | **Azure OpenAI text-embedding-3-large** | Best multilingual (Arabic + English) performance. 3072 dimensions. Runs within Azure tenant. |
| PPTX Rendering | **python-pptx (only)** | Runs natively in Python backend. Supports loading .pptx templates as masters. PptxGenJS dropped entirely. |
| Visual Enhancement | **Nano Banana Pro (Optional)** | Google DeepMind's Gemini-based AI image generation model for presentation visuals. Used only for visually rich infographic slides when specifically requested. Not part of core pipeline. Requires stable Gemini Image API — dependency risk acknowledged. |
| Cloud / Hosting | **Azure** | Aligned with SG tenant. Azure AD, SharePoint, Graph API, Azure AI Search, Azure OpenAI for embeddings — all within same tenant. |
| BD Station Integration | **REST API + Webhook** | BD Station pushes RFP summary via REST. DeckForge returns deck URL. Webhook notifies when ready. |

---

## 8. Security, Governance & Data Privacy

### 8.1 Access Control

- **Authentication**: Azure AD / Microsoft Entra ID SSO (same as Strategic Gears tenant)
- **Authorization**: RBAC — Admin (template management, system config), Consultant (full usage), Viewer (read-only)
- **SharePoint permission trimming**: retrieval results filtered by requesting user's SharePoint permissions
- **BD Station integration**: OAuth 2.0 client credentials with scoped permissions

### 8.2 Data Handling

- **Encryption at rest**: Azure Blob Storage with AES-256
- **Encryption in transit**: TLS 1.3 for all API calls including LLM
- **Data residency**: All data within Azure region configured for SG tenant. Azure KSA region if Saudi data sovereignty applies.
- **LLM data policy**: Anthropic's API does not train on customer data (confirm contractually). OpenAI's API data is not used for training by default when accessed via API (confirm via OpenAI Enterprise terms or Data Processing Agreement). For highest-sensitivity content, consider pseudonymization of client names during LLM processing — but weigh engineering cost against contractual protection.
- **Retention**: Generated presentations retained 90 days, then auto-archived. Session state retained 30 days, then deleted. Configurable per compliance requirements.

### 8.3 Audit Logging

- Every action logged: user identity, timestamp, action type, source documents accessed, LLM calls (model, token count, cost)
- **Content scope**: Audit logs capture metadata and claim references, not full LLM prompts/responses (to avoid creating a secondary sensitive data store). Full prompt logging available in debug mode for troubleshooting.
- Immutable append-only logs (Azure Table Storage), retained 1 year
- Accessible to Admin role for compliance review

---

## 9. Error Handling & Resilience

| Failure Scenario | System Behavior | User Experience |
|------------------|----------------|-----------------|
| SharePoint returns zero results | Retrieval Agent broadens queries progressively (3 attempts). If still zero, flags the gap. | "No relevant past work found for [domain]. You can proceed with web-researched context or upload materials manually." |
| LLM API timeout or rate limit | Exponential backoff retry (3 attempts, 2s/4s/8s). If all fail, queue task. For extended outages (30+ min): notify user with ETA, hold pipeline state. | "Processing is delayed. Your deck will be ready in approximately [X] minutes. We'll notify you." |
| Agent produces low-confidence output | QA Agent flags slides with untraceable claims. Pipeline continues but flags are surfaced. | Flagged slides highlighted: "This slide needs your review — content could not be fully verified against sources." |
| Corrupted source document | Extraction fails gracefully. Document skipped with warning. Indexing pipeline flags for manual review. | "1 document could not be read: [filename]. It has been excluded." |
| PPTX rendering fails | Design Agent retries with simplified layouts. If still failing, exports slide content as structured Word document. This is an exception recovery path, not normal operation. | "The PPTX could not be rendered. Here is the content in a Word document for manual template application." |
| User brief is ambiguous after clarification | Context Agent presents best interpretation with assumptions clearly stated. | "I've made the following assumptions: [list]. Please confirm or correct." |
| Mid-pipeline session interruption | LangGraph state persisted to Redis after every stage transition. Session resumable for 72 hours. | "Welcome back. Your deck for [RFP name] was paused at [stage]. Continue?" |
| Research Report Opus failure mid-generation | Partial report saved. User notified. Can retry from last checkpoint or switch to Sonnet for degraded-quality completion. | "Report generation was interrupted at [section]. Retry or continue with available content?" |
| Hallucinated content detected by QA | Claim without valid [Ref] is stripped from slide and replaced with GAP flag. | "Slide [N]: 2 claims could not be verified against sources and have been flagged for your input." |
| Critical GAP in mandatory section at export | **Finalization blocked.** User must resolve or explicitly waive. | "Cannot export: unresolved GAP in [Compliance/Certification]. Please fill this section or waive to proceed." |

---

## 10. Arabic & Bilingual Strategy

### 10.1 Language Selection

At Gate 1, the user selects output language. This choice propagates through the entire pipeline:

| Stage | English | Arabic | Bilingual |
|-------|---------|--------|-----------|
| Retrieval | English queries | Arabic + English queries (multilingual embeddings) | Both |
| Research Report | Written in English | Written in Arabic | English with Arabic terms preserved |
| Slide Content | English LTR | Arabic RTL | Primary language dominant, secondary in sub-text |
| Template Rendering | Standard SG template | RTL-mirrored SG template | Dual-direction layouts |

### 10.2 Technical Requirements

- **Embeddings**: Azure OpenAI `text-embedding-3-large` supports Arabic natively. Retrieval quality to be validated with a dedicated Arabic evaluation set (20+ queries with labeled relevant documents) before production.
- **Content generation**: Both Claude Opus 4.6 and GPT-5.4 support Arabic natively. The Research Agent (Opus) generates Arabic reports; the Content Agent (GPT-5.4) generates Arabic slide copy. Prompt templates include Arabic writing guidelines: formal Modern Standard Arabic for government proposals, with technical terms in both Arabic and English on first use.
- **PPTX rendering**: Arabic rendering will rely on template mirroring, right alignment, Arabic-capable fonts, and end-to-end rendering validation. RTL paragraph-direction handling in python-pptx requires XML-level manipulation (`p._pPr.set('rtl', '1')`) rather than high-level API calls. The Design Agent will include a custom RTL rendering layer handling paragraph-level direction, mixed LTR/RTL content, and Arabic numeral formatting. Any RTL behavior not natively guaranteed by the library will be verified through prototype testing before production release.
- **Font stack**: Aptos Arabic → Arial → Tahoma (fallback chain). Aptos Arabic availability must be verified in the target deployment environment (introduced 2023, may vary across Office versions).
- **QA validation**: Arabic-specific checks include RTL consistency, mixed LTR/RTL text handling, and numeral formatting (Eastern Arabic vs Western, per user preference).

---

## 11. Strategic Gears Template Specification

Extracted from the master template (Presentation6.pptx). These values are the only permitted visual parameters.

| Property | Value |
|----------|-------|
| Slide dimensions | 16:9 (10" × 5.625") |
| Primary navy | `#0E2841` — backgrounds, headers, footer bars |
| Accent teal | `#156082` — section headers, highlights |
| Accent blue | `#0F9ED5` — links, callouts, data viz accent |
| Dark teal | `#467886` — secondary text, captions |
| Background | White for content slides; Navy for title and section dividers |
| Heading font | Aptos Display (fallback: Arial, Segoe UI) |
| Body font | Aptos (fallback: Arial) |
| Arabic font | Aptos Arabic → Arial → Tahoma |
| Logo placement | Bottom-left on title slide; top-right or bottom-right on content slides |
| Cover style | Architectural photography (bridge/infrastructure), navy overlay, white text, date bottom-right |
| ToC style | Left-aligned section list with page numbers, photo strip on right edge |
| Slide layouts (13) | Title, ToC, Section Divider, Content 1-col, Content 2-col, Comparison, Chart/Data, Framework/Matrix, Team Grid, Timeline, Compliance Matrix, Key Stat, Closing |

The Design Agent loads the actual Presentation6.pptx as a python-pptx template, inheriting all slide masters and layouts directly. No visual properties are generated by AI.

---

## 12. Cost Model

Illustrative baseline estimates for a standard 20-slide proposal under typical corpus and iteration assumptions. Multi-model pricing as of March 6, 2026: GPT-5.4 at $2.50/$15 per MTok, Claude Opus 4.6 at $5/$25 per MTok, Claude Sonnet 4.6 at $3/$15 per MTok. **Verify current pricing at implementation start — model pricing changes frequently.**

| Agent | Model | Input Tokens | Output Tokens | Est. Cost |
|-------|-------|-------------|--------------|-----------|
| Context | GPT-5.4 | 15K | 3K | $0.08 |
| Retrieval | GPT-5.4 | 5K | 2K | $0.04 |
| Analysis | Claude Opus 4.6 | 80K | 15K | $0.78 |
| Research Report | Claude Opus 4.6 | 60K | 20K | $0.80 |
| Structure | GPT-5.4 | 25K | 8K | $0.18 |
| Content | GPT-5.4 | 40K | 20K | $0.40 |
| QA | GPT-5.4 | 30K | 5K | $0.15 |
| Iteration (avg 3 rounds) | Mixed | 30K | 10K | $0.30 |
| Embeddings | text-embedding-3-large | 10K | — | $0.01 |
| **TOTAL PER DECK** | | **~295K** | **~83K** | **~$2.74** |

The multi-model strategy delivers a dramatic cost reduction vs the v3.0 Claude-only approach (~$6.17): **$2.74 per deck, a 56% reduction** — while using higher-quality models for each task. This is driven by two factors: Claude Opus 4.6 at $5/$25 is 67% cheaper than the deprecated Opus 4.1 ($15/$75) used in earlier estimates, and GPT-5.4 at $2.50/$15 is cheaper than Claude Sonnet for the five agents where it is the better model.

At ~$3 per deck and 20 decks/month, monthly LLM cost is approximately $55–$70 plus Azure infrastructure ($200–$400/month).

Initial SharePoint indexing (one-time): ~$63 (see Section 6.5).

---

## 13. Non-Functional Requirements

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Deck generation time | Target: under 12 minutes for a 20-slide deck (excluding human gates), under defined operating conditions (indexed corpus prepared, limited concurrent load, no major extraction failures) | Measured from Gate 1 to Gate 5 preview |
| Per-agent latency budgets | Context (GPT-5.4) < 20s, Retrieval (GPT-5.4) < 30s, Analysis (Opus) < 3min, Research Report (Opus) < 4min, Structure (GPT-5.4) < 45s, Content (GPT-5.4) < 90s, QA (GPT-5.4) < 20s, Design < 60s | Per-agent timing in structured logs |
| Concurrent users | 10 simultaneous deck generations | Load test; queue overflow handled gracefully |
| Availability | 99.5% uptime during business hours (Sun–Thu, 8am–10pm AST) | Azure Monitor uptime tracking |
| Retrieval quality | Recall@10 > 80%, Precision@10 > 60% on evaluation test set | Test set: 50 English queries + 20 Arabic queries with manually labeled relevant documents |
| Template compliance | 100% of rendered slides pass automated template validation | Deterministic check against template config |
| Max file size | Input: 50MB per file, 200MB per session. Output: 100MB max PPTX | Enforced at API gateway |
| Session persistence | Sessions survive browser close for up to 72 hours | Redis state with TTL |

---

## 14. Monitoring & Observability

### 14.1 Logging

- Structured JSON logs for every agent invocation: agent name, input hash, output hash, model, token counts, latency, success/failure
- Conversation logs: every user message and system response with timestamps
- Retrieval logs: queries issued, results returned, user modifications at Gate 2
- All logs ship to Azure Monitor / Log Analytics
- **Distributed tracing**: OpenTelemetry-based end-to-end request tracing with correlation IDs linking all agent invocations, LLM calls, and retrieval queries for a single user request

### 14.2 Dashboards

- **Real-time**: Active sessions, pipeline stage distribution, average generation time, error rate
- **Cost**: Daily/weekly/monthly LLM spend by agent and model
- **Quality**: Average QA pass rate, No Free Facts violation rate, user iteration count per deck
- **Retrieval**: Query volume, result count, user modification rate at Gate 2

### 14.3 Alerting

- LLM API error rate > 5% in 15-minute window → alert on-call engineer
- Retrieval returning zero results for > 3 consecutive requests → alert system admin
- Average generation time exceeds 15 minutes → alert for capacity review
- Cost exceeds daily budget threshold → alert finance and admin
- No Free Facts violation rate > 10% in any session → alert for prompt quality review

---

## 15. Implementation Plan

### 15.1 Estimated Timeline: 20 Weeks

| Phase | Scope | Duration | Prerequisites |
|-------|-------|----------|---------------|
| Phase 0: Foundation | SharePoint audit, template digitization (extract exact layout specs from Presentation6.pptx), prompt engineering for each agent, Arabic evaluation query set creation, RTL template prototype testing | Weeks 1–3 | SharePoint access, brand guidelines, Azure subscription |
| Phase 1: Knowledge Layer | SharePoint indexing pipeline (Graph API crawler, extraction, classification, embedding, Azure AI Search), permission-aware retrieval, duplicate detection | Weeks 4–7 | Graph API permissions, Azure AI Search instance |
| Phase 2: Core Agents | Context + Retrieval + Analysis + Research Agents, Reference Index, Research Report generation, Gates 1–3, basic chat UI | Weeks 8–12 | LLM API access (OpenAI GPT-5.4 + Anthropic Claude Opus 4.6 + Sonnet 4.6), Phase 1 complete |
| Phase 3: Deck Pipeline | Structure + Content + QA + Design Agents, No Free Facts enforcement, python-pptx rendering with SG template, Arabic RTL rendering layer | Weeks 13–16 | Finalized template specs, Phase 2 complete |
| Phase 4: Integration & QA | BD Station API integration, Gates 4–5 UI, observability stack, security (Azure AD RBAC, audit logging), feedback loop, load testing | Weeks 17–19 | BD Station API ready, test users |
| Phase 5: Hardening & Launch | User acceptance testing with 5 real RFPs, retrieval quality evaluation (50 EN + 20 AR queries), prompt regression testing, production deployment, dry-run evaluation period | Week 20 | Real project briefs, senior consultant reviewers |

### 15.2 Team Requirements

| Role | Count | Skills |
|------|-------|--------|
| Backend / Agent Engineer | 2 | Python, FastAPI, LangGraph, OpenAI API, Anthropic Claude API, async programming |
| Azure / SharePoint Engineer | 1 | Microsoft Graph API, Azure AI Search, Azure AD, Azure Blob Storage |
| Frontend Engineer | 1 | React/Next.js, chat UI, file upload, slide preview rendering |
| Template / PPTX Engineer | 1 (can be part-time or shared) | python-pptx, XML manipulation for RTL, PowerPoint template design |
| **Total** | **4–5 engineers** | |

### 15.3 Testing Strategy

- **Unit tests**: Deterministic components (Workflow Controller state transitions, Design Agent template rendering, QA Agent rule checks)
- **Prompt regression tests**: For each LLM-powered agent, maintain a test suite of 10+ input/expected-output pairs. Run after every prompt change. Measure: output structure compliance, factual grounding rate, GAP detection accuracy.
- **Retrieval evaluation**: 50 English + 20 Arabic queries with manually labeled relevant documents. Measure Recall@10 and Precision@10. Must exceed targets before Phase 2 sign-off.
- **Integration tests**: End-to-end pipeline tests with 5 real past RFPs. Measure: report quality (human-rated), deck accuracy vs. manual baseline, No Free Facts violation rate.
- **Regression tests**: Template compliance suite run on every Design Agent change. Automated visual comparison of rendered slides against reference images.
- **Dry-run evaluation**: For the first 8 weeks of production, every DeckForge-generated deck is reviewed alongside a manually-created deck for the same RFP. Quality delta measured and reported.

---

## 16. Strategic Value

### Internal Impact (Track A)

- **Time savings**: Target 60–70% reduction in proposal creation time (to be validated during dry-run evaluation)
- **Knowledge leverage**: Institutional knowledge reused systematically, not lost in SharePoint folders
- **Consistency**: Every proposal deck meets the same quality bar regardless of who creates it
- **Onboarding**: New hires can produce senior-quality proposals by leveraging the firm's historical work
- **Dual output**: Both the research report and the deck are independently valuable deliverables

### Revenue Potential (Track B — Deferred)

White-label and "Presentation Intelligence as a Service" opportunities exist but are deferred until Track A is successfully delivered. Track B introduces multi-tenant isolation, client-specific branding, and commercial packaging that should not distort the first internal build.

### Competitive Differentiation

DeckForge is differentiated by SharePoint-grounded retrieval, the No Free Facts content governance framework, slide-level source traceability, report-first architecture with human approval of substantive content, deterministic brand rendering, and bilingual Arabic/English support — capabilities that no current commercial tool combines in a single system.

---

*End of Document | DeckForge v3.1 Final | Strategic Gears | March 2026*
