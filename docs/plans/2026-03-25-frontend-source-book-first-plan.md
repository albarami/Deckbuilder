# Frontend Source Book-First Implementation Plan

Date: 2026-03-25  
Scope: Frontend-only implementation plan for a production-ready consultant experience through Gate 3 (Source Book stage).  
Constraint: Do not implement PPT-heavy flow in this phase; PPT remains secondary/coming soon.

---

## 1) File-by-File Change List

### A. Stage model, routing surfaces, and global state

1. `frontend/src/components/pipeline/PipelineProgressBar.tsx`  
   - **Change**: Replace fixed 5-stage primary progression with Source Book-first progression model.
     - New primary stages: `Context`, `Sources`, `Source Book`.
     - Add optional secondary indicator for PPT continuation (`Slides`, `QA`) controlled by feature flag.
   - **Why**: Current UI communicates a 5-stage report-to-slides pipeline as primary, which conflicts with Source Book-first product goal.

2. `frontend/src/components/pipeline/JourneyLegend.tsx`  
   - **Change**: Update legend copy and counts to emphasize Source Book-first flow and Gate 3 success checkpoint.
   - **Why**: Current legend frames full 5-gate progression as primary; needs product-aligned expectations.

3. `frontend/src/stores/pipeline-store.ts`  
   - **Change**:
     - Add computed/derived Source Book readiness helpers in store action logic:
       - `isSourceBookGatePending` (`status === "gate_pending" && currentGate?.gate_number === 3`)
       - `isSourceBookReadyCheckpoint` (Gate 3 approved and DOCX available OR backend indicates Source Book-ready state)
     - Keep existing full-pipeline fields intact for compatibility.
   - **Why**: Session page needs reliable state to expose DOCX and "Source Book Ready" messaging before full pipeline completion.

4. `frontend/src/hooks/use-pipeline.ts`  
   - **Change**: Expose new derived selectors from store and helper utilities for Source Book-first rendering decisions.
   - **Why**: Avoid duplicating condition logic across pages/components.

5. `frontend/src/hooks/use-gate.ts`  
   - **Change**: Preserve approve/reject behavior; add optional Gate-3-specific callback hook to refresh deliverable status post-decision.
   - **Why**: Keep Gate action flow consistent, but ensure DOCX/state reflects latest post-Gate-3 decisions.

---

### B. Gate 3 rendering and gate dispatch

6. `frontend/src/components/gates/GatePanel.tsx`  
   - **Change**:
     - Gate 3 dispatch to a new Source Book-specific component.
     - Keep legacy Gate 3 renderers behind fallback path only.
   - **Why**: Current Gate 3 panels (`Gate3Research`, `Gate3AssemblyPlan`) are legacy and not Source Book review UX.

7. `frontend/src/components/gates/gates/Gate3SourceBook.tsx` (**new**)  
   - **Change**: New Source Book review panel component (full model in section 2).
   - **Why**: Required dedicated review surface with summary, section previews, quality/evidence metrics, and immediate DOCX download.

8. `frontend/src/components/gates/gates/Gate3Research.tsx`  
   - **Change**: Convert to fallback renderer only (or deprecate with TODO note).
   - **Why**: Avoid deleting compatibility path while migrating Gate 3 primary UX.

9. `frontend/src/components/gates/gates/Gate3AssemblyPlan.tsx`  
   - **Change**: Remove as primary Gate 3 path; retain optional fallback if payload_type remains `assembly_plan_review`.
   - **Why**: Assembly-plan-centric UX is not the Source Book-first release objective.

---

### C. Session and export pages (Gate 3 DOCX-first availability)

10. `frontend/src/app/[locale]/pipeline/[id]/page.tsx`  
    - **Change**:
      - Add Gate-3-specific "Source Book Ready/Review" primary panel states.
      - In Gate 3 pending view, surface immediate DOCX action (prominent CTA).
      - After Gate 3 approval, render Source Book success checkpoint instead of forcing PPT-complete semantics.
    - **Why**: Today this page optimizes for full pipeline complete state; Source Book-first requires a meaningful endpoint at Gate 3.

11. `frontend/src/components/pipeline/PipelineComplete.tsx`  
    - **Change**:
      - Split into two modes:
        - `SourceBookCompletePanel` (primary for this release)
        - `FullPipelineCompletePanel` (kept for future/flag enabled)
      - Reorder CTA prominence: DOCX first, PPTX secondary/disabled/hidden per suppression strategy.
    - **Why**: Current completion surface is PPT-oriented and triggered only on full completion.

12. `frontend/src/app/[locale]/pipeline/[id]/export/page.tsx`  
    - **Change**:
      - Permit useful export surface when Gate 3 is pending/approved (not only `status === "complete"`).
      - Show Source Book readiness banner and DOCX primary action.
    - **Why**: Consultants must be able to retrieve DOCX as soon as Source Book is generated.

13. `frontend/src/components/export/ExportPanel.tsx`  
    - **Change**:
      - Make DOCX primary button and always visible when Gate 3 checkpoint is met.
      - PPTX shown as secondary and controlled by feature flag.
      - Add contextual labels for readiness source (Gate 3 vs full completion).
    - **Why**: Current layout equally/primarily supports PPT-driven export journey.

---

### D. PPT suppression/feature gating

14. `frontend/src/components/layout/Sidebar.tsx`  
    - **Change**: Hide or de-emphasize slides route links when PPT feature flag is off.
    - **Why**: Prevent PPT path from dominating Source Book-first experience.

15. `frontend/src/app/[locale]/pipeline/[id]/slides/page.tsx`  
    - **Change**:
      - If PPT flag off: show "Coming Soon" shell with redirect CTA back to pipeline/session export.
      - If PPT flag on: preserve existing behavior.
    - **Why**: Route should not appear as core outcome in this phase.

16. `frontend/src/lib/types/pipeline.ts`  
    - **Change**:
      - Add Gate 3 Source Book payload type:
        - `source_book_review` in `GatePayloadType`
        - `Gate3SourceBookData` interface (details below)
      - Add optional fields in `PipelineOutputs` if backend exposes Source Book readiness directly.
    - **Why**: Strong typed contract for new Gate 3 view model and state handling.

17. `frontend/src/lib/api/pipeline.ts` (optional minimal change)  
    - **Change**: No endpoint change required, but add helper parser/adapter function for Gate 3 Source Book data extraction.
    - **Why**: Keep component parsing clean and resilient to backend payload variants.

---

### E. Locale and copy updates

18. `frontend/src/i18n/messages/en.json`  
19. `frontend/src/i18n/messages/ar.json`  
    - **Change**:
      - Stage names, gate copy, CTA text, Source Book readiness messages.
      - New keys for:
        - `sourceBook.readyTitle`
        - `sourceBook.downloadDocxNow`
        - `sourceBook.sectionPreview`
        - `sourceBook.evidenceSummary`
        - `sourceBook.blueprintCoverage`
        - `sourceBook.pptComingSoon`
    - **Why**: Product wording currently emphasizes legacy report/slide pipeline.

---

### F. New tests and test updates

20. `frontend/src/components/gates/gates/Gate3SourceBook.test.tsx` (**new**)  
21. `frontend/src/components/pipeline/PipelineProgressBar.test.tsx` (update or create)  
22. `frontend/src/components/export/ExportPanel.test.tsx` (update)  
23. `frontend/src/app/[locale]/pipeline/[id]/page.test.tsx` (**new**)  
24. `frontend/src/hooks/use-pipeline.test.ts` (**new**)  
25. `frontend/src/hooks/use-gate.test.ts` (update as needed)  
26. `frontend/tests/e2e/source-book-first.spec.ts` (**new**)  
    - **Why**: Validate Source Book-first behavior and prevent regressions back to PPT-first assumptions.

---

## 2) New Gate 3 Source Book View Model

### Component to render Gate 3

- Primary renderer: `frontend/src/components/gates/gates/Gate3SourceBook.tsx`
- Dispatched from `GatePanel.tsx` when:
  - `gate.gate_number === 3`, and
  - `gate.payload_type` is `source_book_review` (preferred), or fallback shape detector finds Source Book keys.

### Proposed data contract (`Gate3SourceBookData`)

Add in `frontend/src/lib/types/pipeline.ts`:

```ts
export interface SourceBookSectionPreview {
  section_id: string;          // canonical ID (e.g., executive_summary)
  title: string;               // localized section title
  preview_paragraph: string;   // first paragraph preview
  word_count?: number;
}

export interface SourceBookQualitySummary {
  reviewer_score?: number;         // e.g., 0-100
  benchmark_passed?: boolean;
  evidence_count?: number;
  blueprint_count?: number;
}

export interface SourceBookEvidenceSummary {
  evidence_ledger_entries: number;
  external_source_count: number;
}

export interface SourceBookBlueprintSummary {
  total_entries: number;
  covered_sections: string[];      // section IDs covered by blueprint entries
}

export interface Gate3SourceBookData {
  source_book_title?: string;
  total_word_count: number;
  section_count: number;           // expected 7
  sections: SourceBookSectionPreview[];
  quality_summary?: SourceBookQualitySummary;
  evidence_summary?: SourceBookEvidenceSummary;
  blueprint_summary?: SourceBookBlueprintSummary;
  docx_ready: boolean;
}
```

### UI sections in `Gate3SourceBook.tsx`

1. **Source Book summary**
   - Word count, section count, title.
2. **Prominent DOCX download**
   - Primary CTA at top of panel.
   - Available while Gate 3 is pending.
3. **Section preview**
   - All 7 sections, each showing title + first paragraph preview.
4. **Quality/benchmark summary**
   - Reviewer/benchmark score and status if available.
5. **Evidence package visibility**
   - Ledger entry count + external source count.
6. **Slide blueprint summary**
   - Entry count + section coverage chips.
7. **Approve/Reject with feedback**
   - Reuse existing `GateActions` pattern from parent `GatePanel`.

### Data source in state

- Consume from `pipeline-store.currentGate.gate_data` through typed narrowing / adapter.
- DOCX button uses existing export API (`downloadDocx(sessionId)`).

---

## 3) Source-Book-First User Journey (Target UX)

1. **User opens dashboard**  
   - Page: `frontend/src/app/[locale]/page.tsx`  
   - Components: `QuickStats`, `RecentProposals`

2. **User clicks New Proposal**  
   - Route: `/[locale]/new`  
   - Page: `frontend/src/app/[locale]/new/page.tsx`

3. **User uploads RFP docs**  
   - Component: `FileUploadZone`  
   - API: `uploadDocuments` (`/api/upload`)

4. **User optionally pastes text**  
   - Component: `TextPasteArea`

5. **User clicks Start**  
   - Component: `StartPipelineButton`  
   - Hook/API: `usePipeline.start` -> `/api/pipeline/start`

6. **Pipeline runs: context analysis**  
   - Session page: `/[locale]/pipeline/[id]`  
   - Components: `PipelineHeader`, `PipelineProgressBar`, timeline/status cards

7. **Gate 1 appears and is interactive**  
   - `GatePanel` -> `Gate1Context` + `GateActions`

8. **Pipeline runs: source retrieval**  
   - Session page live state updates via SSE

9. **Gate 2 appears and is interactive**  
   - `GatePanel` -> `Gate2Sources` + `GateActions`

10. **Pipeline runs: evidence/strategy -> Source Book generation**  
    - Session page continues running state

11. **Gate 3 Source Book review appears**  
    - `GatePanel` -> `Gate3SourceBook`
    - User can:
      - view summary
      - view section previews
      - download DOCX immediately
      - approve/reject with feedback

12. **Success state: Source Book Ready**  
    - Session page primary panel shows:
      - "Your Source Book is ready"
      - persistent DOCX CTA
      - production summary (sections, word count, evidence)

13. **PPT stages are not primary**  
    - Gate 4/5 hidden or visibly "Coming Soon" per suppression strategy.

---

## 4) PPT / Gate 4 / Gate 5 Suppression Plan

### Selected option: **Feature-flagged**

Use `NEXT_PUBLIC_ENABLE_PPT=false` as default for Source Book-first release.

### Why this option

- Keeps one codebase for current and future rollout.
- Avoids deleting existing slide/export code while ensuring consultants see Source Book-first UX by default.
- Supports controlled activation without another refactor.

### Behavior under `NEXT_PUBLIC_ENABLE_PPT=false`

1. **Progress bar**
   - Primary model shows only 3 stages (`Context`, `Sources`, `Source Book`).
   - Optional collapsed note: "Slides & QA coming soon."

2. **Gate 4 / Gate 5**
   - Not rendered as active flow targets in primary journey.
   - If backend still emits gate 4/5, show non-blocking "Coming Soon" treatment rather than dominant review workflow.

3. **`/[locale]/pipeline/[id]/slides` route**
   - Route remains valid but page renders "Coming Soon" panel + CTA back to session/export.
   - Avoid hard 404 for bookmarked links.

4. **PPTX in `ExportPanel`**
   - Hidden or disabled with explicit "Coming Soon" label when flag is off.
   - DOCX is the main emphasized action.

5. **`PipelineComplete.tsx`**
   - Source Book completion mode shown by default.
   - Full PPT completion mode only active when flag is on and backend reaches full complete.

---

## 5) DOCX Availability at Gate 3

### Endpoint

- Keep existing endpoint: `GET /api/pipeline/{id}/export/docx`
- No new endpoint required for phase 1 unless backend gating forbids Gate 3 retrieval.

### Frontend enablement rule

Enable Gate 3 DOCX button when all are true:

1. `status === "gate_pending"`
2. `currentGate?.gate_number === 3`
3. Source Book gate data present (or fallback Gate 3 report payload present)

If endpoint returns 409/404, show inline "not ready yet" message and retry affordance.

### Session page persistence after Gate 3 approval

After Gate 3 approved:

- Show `Source Book Ready` panel on `pipeline/[id]/page.tsx`
- Keep DOCX button visible there and on `/pipeline/[id]/export`
- Do not require full pipeline `status === "complete"` to keep DOCX accessible

Implementation note: use `completedGates` + current outputs/status for robust persistence.

---

## 6) Frontend Test Plan

### Unit tests (Vitest)

1. `frontend/src/components/gates/gates/Gate3SourceBook.test.tsx`  
   - Renders summary stats, section previews (7), evidence/blueprint summaries.
   - DOCX button visible in Gate 3 state.

2. `frontend/src/components/export/ExportPanel.test.tsx`  
   - DOCX is primary/available at Source Book checkpoint.
   - PPTX hidden/disabled when `NEXT_PUBLIC_ENABLE_PPT=false`.

3. `frontend/src/components/pipeline/PipelineProgressBar.test.tsx`  
   - Shows 3-stage primary progression in Source Book-first mode.
   - Does not present Gate 4/5 as primary when PPT disabled.

4. `frontend/src/app/[locale]/pipeline/[id]/page.test.tsx`  
   - Gate 3 pending shows Source Book panel + download CTA.
   - Post-Gate-3 approved shows Source Book ready state.

5. `frontend/src/hooks/use-pipeline.test.ts` / `use-gate.test.ts`  
   - Derived state selectors for Source Book readiness.
   - Gate decision flow keeps state consistent around Gate 3 transition.

### Integration tests

1. Intake flow  
   - Upload + start pipeline request payload correctness.

2. Gate progression flow  
   - Gate 1 approve -> Gate 2 approve -> Gate 3 Source Book rendering.

3. Gate 3 DOCX behavior  
   - Download action available at Gate 3 pending (not only full complete).

### E2E tests (Playwright)

1. `frontend/tests/e2e/source-book-first.spec.ts` — happy path  
   - Dashboard -> New -> Upload -> Start -> Gate1 approve -> Gate2 approve -> Gate3 review -> DOCX download.

2. Gate rejection + retry path  
   - Reject at Gate 3 with feedback -> pipeline resumes -> Gate 3 returns -> approve.

3. PPT suppressed behavior  
   - With `NEXT_PUBLIC_ENABLE_PPT=false`, slides route shows Coming Soon and session/export stays Source Book-first.

---

## Delivery Notes

- This plan intentionally avoids component-level coding until approval.
- It treats Source Book as the first production endpoint, while preserving forward compatibility with PPT phases via feature flagging.
