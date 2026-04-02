# Artifact Viewer Components — Design

Date: 2026-04-01
Scope: Frontend artifact viewer components for Source Book pipeline completion surface.

---

## Architecture: Shell + Typed Renderers (Approach C)

Shared `ArtifactViewerShell` handles chrome (title, download button, loading/error/empty states).
Each artifact gets a dedicated typed renderer. No generic JSON viewer.

## File Layout

All files colocated under `frontend/src/components/artifacts/`:

```
artifacts/
  types.ts                          # Viewer-normalized typed contracts
  ArtifactViewerShell.tsx           # Presentation-only shell
  ArtifactViewerShell.test.tsx
  ArtifactViewerTabs.tsx            # Tab container for export page
  ArtifactViewerTabs.test.tsx
  EvidenceLedgerViewer.tsx          # Table: claims, confidence, status
  EvidenceLedgerViewer.test.tsx
  BlueprintViewer.tsx               # Sectioned cards: contract entries
  BlueprintViewer.test.tsx
  EvidencePackViewer.tsx            # Card list: sources, tiers, findings
  EvidencePackViewer.test.tsx
  RoutingReportViewer.tsx           # Summary: classification, packs, warnings
  RoutingReportViewer.test.tsx
  SourceBookArtifactSummary.tsx     # Compact summary for PipelineComplete
  SourceBookArtifactSummary.test.tsx
```

Integration test:
```
tests/integration/export-artifact-viewers.integration.test.tsx
```

## Typed Contracts (types.ts)

Viewer-normalized types, not raw backend dumps.

### EvidenceLedgerData

```ts
export interface LedgerEntry {
  claim_id: string;
  claim_text: string;
  source_type: "internal" | "external";
  source_reference: string;
  confidence: number;           // 0.0-1.0
  verifiability_status: "verified" | "partially_verified" | "unverified" | "gap";
  verification_note: string;
}

export interface EvidenceLedgerData {
  entries: LedgerEntry[];
}
```

### BlueprintData

Targets the TRANSFORMED blueprint export shape from `blueprint_transform.py`,
NOT legacy raw `SlideBlueprintEntry` lists from older runs.

```ts
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

export interface BlueprintData {
  contract_entries: BlueprintContractEntry[];
  validation_violations: string[];
  legacy_count: number;
  contract_count: number;
}
```

### EvidencePackData

```ts
export interface EvidenceSource {
  source_id: string;
  provider: string;
  title: string;
  authors: string[];
  source_type: string;
  year: number;
  url: string;
  relevance_score: number;      // 0.0-1.0
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
```

### RoutingReportData

Classification-based shape matching the routing service output.

```ts
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
```

## Component Specifications

### ArtifactViewerShell

Presentation-only. No fetching, no tab state.

Props:
- `title: string`
- `subtitle?: string`
- `onDownload?: () => void`
- `downloadLabel?: string`
- `isDownloading?: boolean`
- `isLoading?: boolean`
- `error?: string | null`
- `isEmpty?: boolean`
- `emptyMessage?: string`
- `children: React.ReactNode`

Renders: title bar with subtitle, download button (right-aligned), then loading spinner OR error message OR empty state OR children.

### EvidenceLedgerViewer

Props: `data: EvidenceLedgerData`

Table columns: Claim ID, Claim Text (truncated, expandable), Source Reference, Confidence (progress bar + percentage), Status (Badge: verified=success, gap=error, partially_verified=warning, unverified=default). Sorted by confidence descending. Entry count in subtitle via Shell.

### BlueprintViewer

Props: `data: BlueprintData`

Grouped by section_id. Each section: section name header, ownership Badge (house=info, dynamic=success, hybrid=warning). Each entry: slide_title, key_message, bullet_points list, evidence_ids as small badges. Validation violations shown as amber warning banner at top if any.

### EvidencePackViewer

Props: `data: EvidencePackData`

Card list. Each source card: title + year, provider badge, tier badge (primary=success, secondary=info, analogical=default), relevance bar, mapped_rfp_theme tag, key_findings as collapsible bullet list. Coverage assessment as header summary. Sorted by relevance_score descending.

### RoutingReportViewer

Props: `data: RoutingReportData`

Single summary card. Classification fields as definition list (jurisdiction, sector, domain, client_type, regulatory_frame). Confidence as progress bar. Selected packs as Badge chips. Fallback packs as secondary Badge chips. Warnings as amber alert list.

### SourceBookArtifactSummary

Reads from existing `SourceBookSummary` contract in pipeline store (already populated at completion). Fields used directly:
- `word_count`
- `reviewer_score`
- `pass_number`
- `evidence_ledger_entries`
- `slide_blueprint_entries`
- `external_sources`

Also reads readiness flags from `outputs` (source_book_ready, evidence_ledger_ready, etc.).

Renders: metric cards (word count, reviewer score, pass number), secondary counts (ledger, blueprints, sources), readiness badges per artifact, single CTA "View Evidence Details" navigating to `/pipeline/[id]/export`.

No inline artifact data. Counts and status only.

### ArtifactViewerTabs

Lives on the export page, BELOW the existing ExportPanel.

Handles:
- Tab state (which artifact is active)
- Lazy data fetching per tab via `getArtifact()` from `lib/api/artifacts.ts`
- Passes fetched data + loading/error state to Shell + Viewer

Four tabs: Evidence Ledger, Slide Blueprints, External Evidence, Routing Report.
Query logs and execution log remain download-only buttons (in ExportPanel, not in tabs).

## Consumer Wiring

### PipelineComplete.tsx

In the Source Book branch (`SourceBookCompletePanel`): add `SourceBookArtifactSummary` component. Reads from store's `sourceBookSummary` and `outputs`.

### /pipeline/[id]/export/page.tsx

Page layout when `proposalMode === "source_book_only"`:
1. Session/export header (existing)
2. ExportPanel (existing, has SB download buttons)
3. ArtifactViewerTabs (new, below ExportPanel)

## Test Plan

### Component tests (colocated):

- `ArtifactViewerShell.test.tsx` — loading/error/empty/content states, download button callback
- `EvidenceLedgerViewer.test.tsx` — renders entries, confidence bars, status badges, empty state
- `BlueprintViewer.test.tsx` — renders grouped sections, ownership badges, violation banner
- `EvidencePackViewer.test.tsx` — renders source cards, tier badges, relevance bars, coverage summary
- `RoutingReportViewer.test.tsx` — renders classification fields, packs, confidence, warnings
- `SourceBookArtifactSummary.test.tsx` — renders counts from store, CTA navigation
- `ArtifactViewerTabs.test.tsx` — tab switching, lazy fetch on activation

### Integration test:

- `tests/integration/export-artifact-viewers.integration.test.tsx` — mounts export page with SB session, verifies tab switching triggers artifact fetch, verifies data renders in each viewer

## Scope Guard

- Full viewers for 4 primary artifacts: evidence ledger, blueprints, evidence pack, routing report
- Query logs and execution log: download-only (no dedicated viewer)
- No generic JSON viewer
- No over-abstraction in artifact content rendering
