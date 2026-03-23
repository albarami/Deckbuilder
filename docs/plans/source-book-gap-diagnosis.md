# Source Book Gap Diagnosis

> Code-evidence-based diagnosis of why the current Source Book fails to meet benchmark quality.

## A) Why Section 7 (Evidence Ledger) Is Empty

### Root Cause: Token truncation + permissive schema defaults

**Evidence:**
- `src/models/source_book.py` line 176: `EvidenceLedger.entries` uses `Field(default_factory=list)` — starts empty and Pydantic accepts it without error
- `src/agents/source_book/writer.py` lines 162-170: Writer calls `call_llm()` with `max_tokens=16000` for the ENTIRE SourceBook (all 7 sections in one JSON response)
- `src/agents/source_book/writer.py` lines 188-192: Empty ledger triggers a warning log but does NOT fail or retry
- The evidence ledger is Section 7 — the LAST section. When the LLM runs out of token budget generating Sections 1-6 (especially Section 6 slide blueprints with 8+ complex entries), Section 7 is truncated to `"entries": []`

**Fix required:**
1. Increase `max_tokens` from 16000 to at least 24000
2. Add a hard validation: if `evidence_ledger.entries` is empty after generation, fail and retry (or generate the ledger in a separate LLM call)
3. Alternatively: programmatically build the ledger post-generation by scanning Sections 1-6 for CLM-xxxx and EXT-xxx references

## B) Why Perplexity Returns Zero Results

### Root Cause: Deprecated model name causes silent HTTP error

**Evidence:**
- `src/config/settings.py` line 33: `perplexity_api_key` maps to env var `PERPLEXITY_API_KEY`
- `.env` line 10: `PERPLEXITY_API_KEY=pplx-***REDACTED***` — key IS present
- `src/services/perplexity.py` line 21: `DEFAULT_MODEL = "llama-3.1-sonar-large-128k-online"` — this model name is **deprecated** by Perplexity
- `src/services/perplexity.py` lines 106-112: On any `HTTPStatusError`, function logs a warning and returns `None` (graceful degradation)
- Callers (methodology filler line 219, understanding filler line 216, external_research agent line 142) check `if result and result.content:` and silently skip enrichment

**Failure path:** Key loaded OK → API call made with deprecated model name → HTTP 400/422 → warning logged → `None` returned → caller skips → zero results

**Fix required:**
1. Update `DEFAULT_MODEL` in `src/services/perplexity.py` line 21 to current Perplexity model: `"sonar"` or `"sonar-pro"`
2. Promote the warning log to ERROR level so failures are visible
3. Persist the query and error details to a research_query_log artifact

## C) Why Semantic Scholar Returns 403

### Root Cause: Wrong API endpoint path

**Evidence:**
- `src/services/semantic_scholar.py` line 19: `SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"` — correct base URL
- `src/services/semantic_scholar.py` lines 91-93: Auth header `x-api-key: {api_key}` — correct format
- `src/services/semantic_scholar.py` line 98: Request goes to `/paper/search` — **WRONG endpoint**
- Per the user-provided API documentation, the correct endpoint is `/paper/search/bulk` for bulk search, or the standard search uses `GET /paper/search?query=...` (which requires different auth or is deprecated for API key users)
- `src/services/semantic_scholar.py` lines 104-110: On `HTTPStatusError` (including 403), returns empty list silently
- `src/config/settings.py` line 32: `semantic_scholar_api_key` maps to `SEMANTIC_SCHOLAR_API_KEY`
- `.env` line 8: `SEMANTIC_SCHOLAR_API_KEY=***REDACTED***` — key present

**Failure path:** Key loaded OK → request to `/paper/search` → 403 Forbidden → warning logged → empty list returned → caller skips

**Fix required:**
1. Change endpoint from `/paper/search` to `/paper/search/bulk` in `src/services/semantic_scholar.py`
2. Update pagination: bulk endpoint uses token-based pagination, not `limit` parameter
3. Persist raw S2 results and query logs to artifacts

## D) Why Named Consultants / Prior Projects Are Placeholder-Level

### Root Cause: Output schema too thin to capture KG richness + no person-project cross-references

**Evidence:**

**D1. ConsultantProfile schema is too thin:**
- `src/models/source_book.py` lines 57-63: `ConsultantProfile` has only 4 fields: `name`, `role`, `relevance`, `evidence_ids`
- **Missing fields:** `certifications`, `years_experience`, `education`, `domain_expertise`, `prior_employers`, `nationality`
- The KG's `PersonProfile` (`src/models/knowledge.py` lines 16-35) has ALL of these fields
- The LLM receives rich KG data but has no output schema field to put certifications/experience — forced to cram into `relevance` free-text or drop

**D2. ProjectExperience schema is too thin:**
- `src/models/source_book.py` lines 66-77: `ProjectExperience` has only `project_name`, `client`, `outcomes`, `evidence_ids`
- **Missing fields:** `sector`, `duration_months`, `contract_value`, `methodologies`, `team_size`, `domain_tags`
- Rich project data in KG cannot be structured in the output

**D3. Certifications is a single string, not a structured list:**
- `src/models/source_book.py` line 86: `certifications_and_compliance: str` — single prose string
- Real examples show individual certification entries per person (PMP, TOGAF, CISSP, etc.)

**D4. No person-to-project cross-references in KG:**
- Both KG files (`state/index/knowledge_graph.json`, `state/index_positive/knowledge_graph.json`) have `"projects": []` for all PersonProfile entries
- Entity extractor (`src/agents/indexing/entity_extractor.py`) extracts `team_members` on ProjectRecord and `projects` on PersonProfile but does not cross-link them
- Without knowing which consultant worked on which project, the LLM cannot write credible associations

**D5. KG data IS rich — 28 internal team members (default), 5 (positive proof), 140 projects:**
- The writer at `src/agents/source_book/writer.py` lines 87-126 correctly serializes KG data including `name`, `current_role`, `certifications`, `years_experience`, `domain_expertise`, `projects`
- The prompt at `src/agents/source_book/prompts.py` lines 41-53 does instruct the LLM to use real names
- But the output schema constrains what the LLM can produce

**Fix required:**
1. Expand `ConsultantProfile` to add: `certifications: list[str]`, `years_experience: int | None`, `education: list[str]`, `domain_expertise: list[str]`
2. Expand `ProjectExperience` to add: `sector: str`, `duration: str`, `methodologies: list[str]`
3. Replace `certifications_and_compliance: str` with structured list
4. Populate person-to-project cross-references in entity extractor merge logic
5. Increase `max_tokens` to 24000+ to give the LLM space for richer output

## E) Why the TimelineFiller Crashes (KeyError)

### Root Cause: Investigated — NOT reproducible on current branch

**Evidence:**
- `src/agents/section_fillers/timeline.py` line 216: `.format()` call with `methodology_context` and `output_language`
- The SYSTEM_PROMPT (lines 67-99) does NOT contain literal `{"items": ...}` JSON — the phrase used is `an OBJECT with an "items" field` (no curly braces around JSON)
- Only two format placeholders exist: `{methodology_context}` and `{output_language}`, both supplied
- The crash may have been fixed in a prior commit or exists on a different branch

**Status:** Not a current blocker on this branch. Will verify during test run.

## F) Why the MethodologyFiller Title Validation Crashes

### Root Cause: Strict 5-word validator raises ValueError instead of truncating

**Evidence:**
- `src/agents/section_fillers/g2_schemas.py` lines 353-359: `PhaseContent.validate_phase_title_words` raises `ValueError` when `phase_title` exceeds 5 words
- Compare with `SlideOutput.validate_title_length` (lines 186-193) which gracefully truncates to 15 words
- The LLM generates Arabic phase titles that often exceed 5 words (Arabic words are shorter, titles need more words for equivalent meaning)
- This causes a Pydantic validation error during `call_llm` response parsing, crashing the filler

**Fix required:**
1. Change the validator from raising `ValueError` to gracefully truncating to 5 words (matching `SlideOutput` pattern)
2. Alternatively, increase the word limit to 8 for Arabic (Arabic titles naturally require more words)
