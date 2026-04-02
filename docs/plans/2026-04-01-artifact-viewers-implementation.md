# Artifact Viewer Components — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build 4 artifact viewer components with a shared shell, a completion summary, tabbed container, and wire them into the export page.

**Architecture:** Shared `ArtifactViewerShell` handles chrome (title, download button, loading/error/empty). Each artifact gets a typed renderer. `ArtifactViewerTabs` on the export page handles tab state and lazy fetching. `SourceBookArtifactSummary` on the completion panel shows lightweight counts.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, next-intl, Vitest + @testing-library/react

---

## Task 1: Typed Contracts

**Files:**
- Create: `frontend/src/components/artifacts/types.ts`

**Step 1: Write types.ts**

```ts
/**
 * Artifact viewer typed contracts.
 *
 * Viewer-normalized types consumed by each artifact renderer.
 * These are NOT raw backend dumps — they match the exported artifact JSON shapes.
 */

// ── Evidence Ledger (from evidence_ledger.json) ────────────────────────

export interface LedgerEntry {
  claim_id: string;
  claim_text: string;
  source_type: "internal" | "external";
  source_reference: string;
  confidence: number;
  verifiability_status: "verified" | "partially_verified" | "unverified" | "gap";
  verification_note: string;
}

export interface EvidenceLedgerData {
  entries: LedgerEntry[];
}

// ── Slide Blueprint (from slide_blueprint.json — TRANSFORMED contract) ─

export interface BlueprintContractEntry {
  section_id: string;
  section_name: string;
  ownership: "house" | "dynamic" | "hybrid";
  slide_title: string | null;
  key_message: string | null;
  bullet_points: string[];
  evidence_ids: string[];
  visual_guidance: string | null;
}

/** Targets the TRANSFORMED blueprint export from blueprint_transform.py,
 *  NOT legacy raw SlideBlueprintEntry lists. */
export interface BlueprintData {
  contract_entries: BlueprintContractEntry[];
  validation_violations: string[];
  legacy_count: number;
  contract_count: number;
}

// ── External Evidence Pack (from external_evidence.json) ───────────────

export interface EvidenceSource {
  source_id: string;
  provider: string;
  title: string;
  authors: string[];
  source_type: string;
  year: number;
  url: string;
  relevance_score: number;
  mapped_rfp_theme: string;
  key_findings: string[];
  evidence_tier: "primary" | "secondary" | "analogical";
  evidence_class: string;
  query_used?: string;
  how_to_use_in_proposal?: string;
  citation_count?: number;
}

export interface EvidencePackData {
  sources: EvidenceSource[];
  search_queries_used: string[];
  coverage_assessment: string;
}

// ── Routing Report (from routing_report.json) ──────────────────────────

export interface RoutingReportData {
  classification: {
    jurisdiction: string;
    sector: string;
    domain: string;
    client_type: string;
    confidence: number;
    regulatory_frame?: string;
  };
  selected_packs: string[];
  fallback_packs_used: string[];
  warnings: string[];
  routing_confidence: number;
}

// ── Artifact tab identifiers ───────────────────────────────────────────

export type ArtifactTab = "evidence_ledger" | "slide_blueprint" | "external_evidence" | "routing_report";
```

**Step 2: Verify types compile**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -5`
Expected: No errors

**Step 3: Commit**

```
git add frontend/src/components/artifacts/types.ts
git commit -m "feat(artifacts): add viewer-normalized typed contracts"
```

---

## Task 2: ArtifactViewerShell

**Files:**
- Create: `frontend/src/components/artifacts/ArtifactViewerShell.tsx`
- Create: `frontend/src/components/artifacts/ArtifactViewerShell.test.tsx`

**Step 1: Write the test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ArtifactViewerShell } from "./ArtifactViewerShell";

describe("ArtifactViewerShell", () => {
  it("renders title and children when not loading/error/empty", () => {
    render(
      <ArtifactViewerShell title="Evidence Ledger" subtitle="42 entries">
        <p>content here</p>
      </ArtifactViewerShell>,
    );
    expect(screen.getByText("Evidence Ledger")).toBeInTheDocument();
    expect(screen.getByText("42 entries")).toBeInTheDocument();
    expect(screen.getByText("content here")).toBeInTheDocument();
  });

  it("shows loading spinner when isLoading", () => {
    render(
      <ArtifactViewerShell title="Test" isLoading>
        <p>hidden</p>
      </ArtifactViewerShell>,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("hidden")).not.toBeInTheDocument();
  });

  it("shows error message when error is set", () => {
    render(
      <ArtifactViewerShell title="Test" error="Failed to load">
        <p>hidden</p>
      </ArtifactViewerShell>,
    );
    expect(screen.getByText("Failed to load")).toBeInTheDocument();
    expect(screen.queryByText("hidden")).not.toBeInTheDocument();
  });

  it("shows empty message when isEmpty", () => {
    render(
      <ArtifactViewerShell title="Test" isEmpty emptyMessage="No data available">
        <p>hidden</p>
      </ArtifactViewerShell>,
    );
    expect(screen.getByText("No data available")).toBeInTheDocument();
    expect(screen.queryByText("hidden")).not.toBeInTheDocument();
  });

  it("renders download button and calls onDownload", () => {
    const onDownload = vi.fn();
    render(
      <ArtifactViewerShell title="Test" onDownload={onDownload} downloadLabel="Download JSON">
        <p>content</p>
      </ArtifactViewerShell>,
    );
    const btn = screen.getByText("Download JSON");
    fireEvent.click(btn);
    expect(onDownload).toHaveBeenCalledTimes(1);
  });

  it("does not render download button when onDownload is not provided", () => {
    render(
      <ArtifactViewerShell title="Test">
        <p>content</p>
      </ArtifactViewerShell>,
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/artifacts/ArtifactViewerShell.test.tsx --reporter=verbose 2>&1 | tail -5`
Expected: FAIL (module not found)

**Step 3: Write implementation**

The shell is presentation-only. It renders:
- Title bar with optional subtitle (left) and download button (right)
- Priority: loading spinner > error message > empty state > children

Uses: `Card` from `@/components/ui/Card`, `Button` from `@/components/ui/Button`, `Spinner` from `@/components/ui/Spinner`, `Download` icon from `lucide-react`.

Props interface:
```ts
export interface ArtifactViewerShellProps {
  title: string;
  subtitle?: string;
  onDownload?: () => void;
  downloadLabel?: string;
  isDownloading?: boolean;
  isLoading?: boolean;
  error?: string | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  children: React.ReactNode;
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/artifacts/ArtifactViewerShell.test.tsx --reporter=verbose`
Expected: 6 tests PASS

**Step 5: Commit**

```
git add frontend/src/components/artifacts/ArtifactViewerShell.*
git commit -m "feat(artifacts): add ArtifactViewerShell with loading/error/empty states"
```

---

## Task 3: EvidenceLedgerViewer

**Files:**
- Create: `frontend/src/components/artifacts/EvidenceLedgerViewer.tsx`
- Create: `frontend/src/components/artifacts/EvidenceLedgerViewer.test.tsx`

**Step 1: Write the test**

Test should verify:
- Renders a row per entry with claim_id, truncated claim_text, source_reference
- Confidence rendered as progress bar + percentage text
- Status badge: verified=success, gap=error, partially_verified=warning, unverified=default
- Entries sorted by confidence descending
- Empty entries array renders gracefully

Use mock data: 3 entries with different statuses (verified, gap, unverified).

**Step 2: Run test — fails**

**Step 3: Write implementation**

Component signature: `function EvidenceLedgerViewer({ data }: { data: EvidenceLedgerData })`

Renders a table-like layout. Each row:
- `claim_id` as mono-font label
- `claim_text` truncated to ~100 chars with `title` attr for hover
- `source_reference` as small text
- Confidence: `<div>` progress bar (width = confidence * 100%) + `{Math.round(confidence * 100)}%`
- Status: `<Badge variant={statusVariantMap[entry.verifiability_status]}>{entry.verifiability_status}</Badge>`

Badge variant map:
```ts
const STATUS_VARIANT: Record<string, BadgeVariant> = {
  verified: "success",
  partially_verified: "warning",
  unverified: "default",
  gap: "error",
};
```

Sort entries: `[...data.entries].sort((a, b) => b.confidence - a.confidence)`

Uses: `Badge` from `@/components/ui/Badge`.

**Step 4: Run test — passes**

**Step 5: Commit**

```
git add frontend/src/components/artifacts/EvidenceLedgerViewer.*
git commit -m "feat(artifacts): add EvidenceLedgerViewer with confidence bars and status badges"
```

---

## Task 4: BlueprintViewer

**Files:**
- Create: `frontend/src/components/artifacts/BlueprintViewer.tsx`
- Create: `frontend/src/components/artifacts/BlueprintViewer.test.tsx`

**Step 1: Write the test**

Test should verify:
- Entries grouped by section_id, section_name as header
- Ownership badge per entry: house=info, dynamic=success, hybrid=warning
- slide_title, key_message, bullet_points list rendered
- evidence_ids as small Badge chips
- Validation violations show warning banner when present
- No banner when violations is empty

Mock data: 2 sections, 2 entries in first section, 1 in second, 1 violation string.

**Step 2: Run test — fails**

**Step 3: Write implementation**

Component signature: `function BlueprintViewer({ data }: { data: BlueprintData })`

Groups `data.contract_entries` by `section_id` using a `Map<string, BlueprintContractEntry[]>`.

Renders:
1. If `data.validation_violations.length > 0`: amber banner with warning icon and violation list
2. For each section group: section_name header + ownership badge, then entries as cards with slide_title, key_message, bullet_points `<ul>`, evidence_ids as `<Badge variant="info">` chips.

Ownership variant map:
```ts
const OWNERSHIP_VARIANT: Record<string, BadgeVariant> = {
  house: "info",
  dynamic: "success",
  hybrid: "warning",
};
```

**Step 4: Run test — passes**

**Step 5: Commit**

```
git add frontend/src/components/artifacts/BlueprintViewer.*
git commit -m "feat(artifacts): add BlueprintViewer with section grouping and ownership badges"
```

---

## Task 5: EvidencePackViewer

**Files:**
- Create: `frontend/src/components/artifacts/EvidencePackViewer.tsx`
- Create: `frontend/src/components/artifacts/EvidencePackViewer.test.tsx`

**Step 1: Write the test**

Test should verify:
- Coverage assessment rendered as header summary text
- Source cards: title + year, provider badge, tier badge (primary=success, secondary=info, analogical=default)
- Relevance bar rendered per source
- key_findings list rendered
- mapped_rfp_theme shown as tag
- Sources sorted by relevance_score descending
- Empty sources renders gracefully

Mock data: 3 sources with different tiers.

**Step 2: Run test — fails**

**Step 3: Write implementation**

Component signature: `function EvidencePackViewer({ data }: { data: EvidencePackData })`

Renders:
1. `data.coverage_assessment` as italic summary paragraph if present
2. Source cards sorted by `relevance_score` descending. Each card:
   - Title + `({year})`, provider badge (info), tier badge (success/info/default)
   - Relevance bar: `<div>` at `relevance_score * 100%` width
   - `mapped_rfp_theme` as `<Badge variant="navy">`
   - `key_findings` as `<ul>` bullet list (max 5 shown)

Tier variant map:
```ts
const TIER_VARIANT: Record<string, BadgeVariant> = {
  primary: "success",
  secondary: "info",
  analogical: "default",
};
```

**Step 4: Run test — passes**

**Step 5: Commit**

```
git add frontend/src/components/artifacts/EvidencePackViewer.*
git commit -m "feat(artifacts): add EvidencePackViewer with tier badges and relevance bars"
```

---

## Task 6: RoutingReportViewer

**Files:**
- Create: `frontend/src/components/artifacts/RoutingReportViewer.tsx`
- Create: `frontend/src/components/artifacts/RoutingReportViewer.test.tsx`

**Step 1: Write the test**

Test should verify:
- Classification fields rendered: jurisdiction, sector, domain, client_type
- regulatory_frame shown when present, omitted when undefined
- routing_confidence as progress bar + percentage
- selected_packs as Badge chips
- fallback_packs_used as secondary Badge chips (different variant)
- warnings as amber list items when present
- No warning section when warnings is empty

Mock data: classification with all fields, 2 packs, 1 fallback, 1 warning.

**Step 2: Run test — fails**

**Step 3: Write implementation**

Component signature: `function RoutingReportViewer({ data }: { data: RoutingReportData })`

Single card layout:
1. Definition list: `dl` with `dt`/`dd` pairs for classification fields
2. Confidence bar: same pattern as EvidenceLedger confidence
3. Packs section: `selected_packs.map(p => <Badge variant="info">{p}</Badge>)`
4. Fallback packs: `fallback_packs_used.map(p => <Badge variant="warning">{p}</Badge>)` with "Fallback" label
5. Warnings: if `data.warnings.length > 0`, amber background section with list

**Step 4: Run test — passes**

**Step 5: Commit**

```
git add frontend/src/components/artifacts/RoutingReportViewer.*
git commit -m "feat(artifacts): add RoutingReportViewer with classification fields and pack badges"
```

---

## Task 7: SourceBookArtifactSummary

**Files:**
- Create: `frontend/src/components/artifacts/SourceBookArtifactSummary.tsx`
- Create: `frontend/src/components/artifacts/SourceBookArtifactSummary.test.tsx`
- Modify: `frontend/src/components/pipeline/PipelineComplete.tsx` (wire into SourceBookCompletePanel)

**Step 1: Write the test**

Test should verify:
- Reads from store's `sourceBookSummary` and `outputs`
- Renders word_count, reviewer_score, pass_number as primary metrics
- Renders evidence_ledger_entries, slide_blueprint_entries, external_sources as secondary metrics
- Readiness badges from outputs (source_book_ready, evidence_ledger_ready, etc.)
- CTA button "View Evidence Details" present
- Handles null sourceBookSummary gracefully (renders nothing or minimal state)

Mock store with: `sourceBookSummary: { word_count: 15000, reviewer_score: 4, ... }`, `outputs: { source_book_ready: true, evidence_ledger_ready: true, ... }`

**Step 2: Run test — fails**

**Step 3: Write SourceBookArtifactSummary**

Component reads from pipeline store via `usePipelineStore`:
```ts
const summary = usePipelineStore((s) => s.sourceBookSummary);
const outputs = usePipelineStore((s) => s.outputs);
const sessionId = usePipelineStore((s) => s.sessionId);
```

If `!summary`, return null.

Renders:
- 3 primary metric cards in a grid: word count (formatted with toLocaleString), reviewer score (/5), pass number
- 3 secondary counts: evidence ledger entries, blueprint entries, external sources
- Readiness badges per artifact using `outputs?.evidence_ledger_ready` etc.
- CTA: `<Link href={/pipeline/${sessionId}/export}><Button>View Evidence Details</Button></Link>`

**Step 4: Wire into PipelineComplete.tsx**

In `SourceBookCompletePanel`, add `<SourceBookArtifactSummary />` between the download button and the footer links. Import from `@/components/artifacts/SourceBookArtifactSummary`.

**Step 5: Run tests — passes**

Run both: `npx vitest run src/components/artifacts/SourceBookArtifactSummary.test.tsx src/components/pipeline/PipelineComplete.test.tsx`

**Step 6: Commit**

```
git add frontend/src/components/artifacts/SourceBookArtifactSummary.*
git add frontend/src/components/pipeline/PipelineComplete.tsx
git commit -m "feat(artifacts): add SourceBookArtifactSummary and wire into PipelineComplete"
```

---

## Task 8: ArtifactViewerTabs

**Files:**
- Create: `frontend/src/components/artifacts/ArtifactViewerTabs.tsx`
- Create: `frontend/src/components/artifacts/ArtifactViewerTabs.test.tsx`

**Step 1: Write the test**

Test should verify:
- 4 tabs rendered: Evidence Ledger, Slide Blueprints, External Evidence, Routing Report
- First tab active by default
- Clicking a tab activates it (visual indicator)
- Lazy fetch: `getArtifact` called only when a tab is first activated
- Switching back to an already-fetched tab does not re-fetch
- Loading state passed to Shell while fetching
- Error state passed to Shell on fetch failure
- Download button per tab calls the correct download function

Mock `getArtifact` from `@/lib/api/artifacts` and download functions from `@/lib/api/export`.

**Step 2: Run test — fails**

**Step 3: Write implementation**

Props: `sessionId: string`

Internal state:
```ts
const [activeTab, setActiveTab] = useState<ArtifactTab>("evidence_ledger");
const [cache, setCache] = useState<Partial<Record<ArtifactTab, unknown>>>({});
const [loading, setLoading] = useState<Partial<Record<ArtifactTab, boolean>>>({});
const [errors, setErrors] = useState<Partial<Record<ArtifactTab, string>>>({});
```

On tab activation (via `useEffect` keyed on `activeTab`):
- If `cache[activeTab]` exists, skip
- Set `loading[activeTab] = true`, call `getArtifact(sessionId, activeTab)`, store result in `cache[activeTab]`, clear loading. On error, set `errors[activeTab]`.

Tab bar: 4 buttons styled as tabs (active = sg-teal border-bottom, others = ghost).

Tab content: `ArtifactViewerShell` wrapping the appropriate viewer:
- `evidence_ledger` → `<EvidenceLedgerViewer data={cache.evidence_ledger as EvidenceLedgerData} />`
- `slide_blueprint` → `<BlueprintViewer data={cache.slide_blueprint as BlueprintData} />`
- `external_evidence` → `<EvidencePackViewer data={cache.external_evidence as EvidencePackData} />`
- `routing_report` → `<RoutingReportViewer data={cache.routing_report as RoutingReportData} />`

Download button per tab uses the corresponding export function from `@/lib/api/export`.

Tab config:
```ts
const TAB_CONFIG: { key: ArtifactTab; label: string; downloadFn: (id: string) => Promise<void> }[] = [
  { key: "evidence_ledger", label: "Evidence Ledger", downloadFn: downloadEvidenceLedger },
  { key: "slide_blueprint", label: "Slide Blueprints", downloadFn: downloadSlideBlueprint },
  { key: "external_evidence", label: "External Evidence", downloadFn: downloadExternalEvidence },
  { key: "routing_report", label: "Routing Report", downloadFn: downloadRoutingReport },
];
```

**Step 4: Run test — passes**

**Step 5: Commit**

```
git add frontend/src/components/artifacts/ArtifactViewerTabs.*
git commit -m "feat(artifacts): add ArtifactViewerTabs with lazy fetch and tab switching"
```

---

## Task 9: Wire ArtifactViewerTabs into Export Page

**Files:**
- Modify: `frontend/src/app/[locale]/pipeline/[id]/export/page.tsx`

**Step 1: Write the wiring change**

In `export/page.tsx`, after the `<ExportPanel>` block, add:

```tsx
import { ArtifactViewerTabs } from "@/components/artifacts/ArtifactViewerTabs";
```

Then below `<ExportPanel ... />` in the JSX return:

```tsx
{statusData.proposal_mode === "source_book_only" && (
  <ArtifactViewerTabs sessionId={sessionId} />
)}
```

This places the tabbed viewers below ExportPanel only when in Source Book mode.

**Step 2: Verify types compile**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -5`
Expected: No errors

**Step 3: Commit**

```
git add frontend/src/app/[locale]/pipeline/[id]/export/page.tsx
git commit -m "feat(export): wire ArtifactViewerTabs below ExportPanel for source_book_only mode"
```

---

## Task 10: Integration Test

**Files:**
- Create: `frontend/src/tests/integration/export-artifact-viewers.integration.test.tsx`

**Step 1: Write the integration test**

Test should:
1. Mock `getStatus` to return a source_book_only session with status=complete
2. Mock `getArtifact` to return typed data for each artifact
3. Render the export page
4. Verify ExportPanel renders (existing behavior)
5. Verify ArtifactViewerTabs renders with 4 tab buttons
6. Verify first tab (Evidence Ledger) is active and fetches data
7. Click second tab (Slide Blueprints) — verify fetch is triggered and content renders
8. Click back to first tab — verify NO re-fetch (getArtifact call count stays at 2)
9. Verify download button present per tab

Mock: `@/lib/api/pipeline` (getStatus), `@/lib/api/artifacts` (getArtifact), `@/lib/api/export` (download functions).

**Step 2: Run test — passes**

Run: `cd frontend && npx vitest run src/tests/integration/export-artifact-viewers.integration.test.tsx --reporter=verbose`

**Step 3: Commit**

```
git add frontend/src/tests/integration/export-artifact-viewers.integration.test.tsx
git commit -m "test(integration): add export page artifact viewer tab switching and fetch coverage"
```

---

## Task 11: Full Test Suite + Type Check

**Step 1: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit --pretty`
Expected: 0 errors

**Step 2: Run full test suite**

Run: `cd frontend && npx vitest run --reporter=verbose`
Expected: All tests pass, including the new artifact viewer tests

**Step 3: Final commit if any fixes needed**

---

## Task 12: Add i18n Keys for Artifact Viewers

**Files:**
- Modify: `frontend/src/i18n/messages/en.json`
- Modify: `frontend/src/i18n/messages/ar.json`

**Step 1: Add keys under a new "artifacts" namespace**

English keys needed:
```json
{
  "artifacts": {
    "evidenceLedger": "Evidence Ledger",
    "slideBlueprints": "Slide Blueprints",
    "externalEvidence": "External Evidence",
    "routingReport": "Routing Report",
    "downloadJson": "Download JSON",
    "downloadDocx": "Download DOCX",
    "noData": "No data available for this artifact.",
    "loadError": "Failed to load artifact data.",
    "entries": "{count} entries",
    "sources": "{count} sources",
    "viewEvidenceDetails": "View Evidence Details",
    "validationWarnings": "Validation Warnings",
    "coverageAssessment": "Coverage Assessment",
    "classification": "Classification",
    "selectedPacks": "Selected Packs",
    "fallbackPacks": "Fallback Packs",
    "confidence": "Confidence"
  }
}
```

Add Arabic equivalents under the same structure.

**Step 2: Commit**

```
git add frontend/src/i18n/messages/en.json frontend/src/i18n/messages/ar.json
git commit -m "feat(i18n): add artifact viewer locale keys (en + ar)"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | types.ts | (types only) |
| 2 | ArtifactViewerShell | 6 tests |
| 3 | EvidenceLedgerViewer | ~5 tests |
| 4 | BlueprintViewer | ~5 tests |
| 5 | EvidencePackViewer | ~5 tests |
| 6 | RoutingReportViewer | ~5 tests |
| 7 | SourceBookArtifactSummary + PipelineComplete wiring | ~5 tests |
| 8 | ArtifactViewerTabs | ~6 tests |
| 9 | Export page wiring | (covered by integration) |
| 10 | Integration test | ~5 assertions |
| 11 | Full suite verification | all pass |
| 12 | i18n keys | (locale only) |

Total: ~12 tasks, ~42 tests, 10 new files, 3 modified files.
