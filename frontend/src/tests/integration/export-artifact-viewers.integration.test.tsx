/**
 * Integration test — Export page + ArtifactViewerTabs.
 *
 * Verifies that the export page renders ExportPanel with download buttons,
 * conditionally mounts ArtifactViewerTabs based on artifact flags,
 * lazy-fetches artifact data on tab activation, and caches fetched tabs.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PipelineStatusResponse } from "@/lib/types/pipeline";

// ── Mock functions ──────────────────────────────────────────────────────

const mockGetStatus = vi.fn();
const mockGetArtifact = vi.fn();

// ── Module mocks ────────────────────────────────────────────────────────

vi.mock("@/lib/api/pipeline", () => ({
  getStatus: (...args: unknown[]) => mockGetStatus(...args),
}));

vi.mock("@/lib/api/artifacts", () => ({
  getArtifact: (...args: unknown[]) => mockGetArtifact(...args),
}));

vi.mock("@/lib/api/export", () => ({
  downloadSourceBook: vi.fn().mockResolvedValue(undefined),
  downloadResearchQueryLog: vi.fn().mockResolvedValue(undefined),
  downloadQueryExecutionLog: vi.fn().mockResolvedValue(undefined),
  downloadPptx: vi.fn().mockResolvedValue(undefined),
  downloadDocx: vi.fn().mockResolvedValue(undefined),
  downloadSourceIndex: vi.fn().mockResolvedValue(undefined),
  downloadGapReport: vi.fn().mockResolvedValue(undefined),
  downloadEvidenceLedger: vi.fn().mockResolvedValue(undefined),
  downloadSlideBlueprint: vi.fn().mockResolvedValue(undefined),
  downloadExternalEvidence: vi.fn().mockResolvedValue(undefined),
  downloadRoutingReport: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      let result = key;
      for (const [k, v] of Object.entries(params)) {
        result = result.replace(`{${k}}`, String(v));
      }
      return result;
    }
    return key;
  },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "sess-sb-001" }),
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: vi.fn() }),
  Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/hooks/use-is-ppt-enabled", () => ({
  useIsPptEnabled: () => false,
}));

vi.mock("@/stores/pipeline-store", () => ({
  usePipelineStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ sourceBookSummary: null, outputs: null, sessionId: "sess-sb-001" }),
}));

// ── Import component under test (after mocks) ──────────────────────────

import ExportPage from "@/app/[locale]/pipeline/[id]/export/page";

// ── Mock data ───────────────────────────────────────────────────────────

const sbCompleteStatus: PipelineStatusResponse = {
  session_id: "sess-sb-001",
  status: "complete",
  proposal_mode: "source_book_only",
  current_stage: "finalized",
  current_stage_label: "Finalized",
  current_step_number: null,
  current_gate_number: null,
  current_gate: null,
  completed_gates: [
    { gate_number: 1, approved: true, feedback: "", decided_at: "2026-04-01T10:00:00Z" },
    { gate_number: 2, approved: true, feedback: "", decided_at: "2026-04-01T10:05:00Z" },
    { gate_number: 3, approved: true, feedback: "", decided_at: "2026-04-01T10:10:00Z" },
  ],
  outputs: {
    pptx_ready: false,
    docx_ready: false,
    source_index_ready: false,
    gap_report_ready: false,
    slide_count: 0,
    preview_ready: false,
    deliverables: [],
    source_book_ready: true,
    evidence_ledger_ready: true,
    slide_blueprint_ready: true,
    external_evidence_ready: true,
    routing_report_ready: true,
    research_query_log_ready: true,
    query_execution_log_ready: true,
  },
  started_at: "2026-04-01T09:55:00Z",
  elapsed_ms: 900000,
  session_metadata: {
    total_llm_calls: 12,
    total_input_tokens: 50000,
    total_output_tokens: 80000,
    total_cost_usd: 2.5,
  },
  agent_runs: [],
  error: null,
  source_book_summary: null,
  deliverables: [],
  rfp_name: "Test RFP",
  issuing_entity: "Test Entity",
};

const sbRunningStatus: PipelineStatusResponse = {
  ...sbCompleteStatus,
  status: "running" as const,
  current_stage: "source_book_generation",
  current_stage_label: "Source Book Generation",
  completed_gates: [
    { gate_number: 1, approved: true, feedback: "", decided_at: "2026-04-01T10:00:00Z" },
    { gate_number: 2, approved: true, feedback: "", decided_at: "2026-04-01T10:05:00Z" },
  ],
  outputs: {
    ...sbCompleteStatus.outputs!,
    source_book_ready: false,
    evidence_ledger_ready: false,
    slide_blueprint_ready: false,
    external_evidence_ready: false,
    routing_report_ready: false,
    research_query_log_ready: false,
    query_execution_log_ready: false,
  },
};

const mockLedgerData = {
  entries: [
    {
      claim_id: "CLM-001",
      claim_text: "Test claim",
      source_type: "external",
      source_reference: "EXT-001",
      confidence: 0.9,
      verifiability_status: "verified",
      verification_note: "",
    },
  ],
};

const mockBlueprintData = {
  contract_entries: [
    {
      section_id: "exec",
      section_name: "Executive Summary",
      ownership: "house",
      slide_title: "Overview",
      key_message: "Key msg",
      bullet_points: ["Point 1"],
      evidence_ids: ["E1"],
      visual_guidance: null,
    },
  ],
  validation_violations: [],
  legacy_count: 5,
  contract_count: 1,
};

const mockEvidencePackData = {
  sources: [
    {
      source_id: "EXT-001",
      provider: "semantic_scholar",
      title: "Paper A",
      authors: [],
      source_type: "academic",
      year: 2024,
      url: "",
      relevance_score: 0.85,
      mapped_rfp_theme: "methodology",
      key_findings: ["Finding 1"],
      evidence_tier: "primary",
      evidence_class: "international_benchmark",
    },
  ],
  search_queries_used: ["test query"],
  coverage_assessment: "Adequate coverage",
};

const mockRoutingData = {
  classification: {
    jurisdiction: "Saudi Arabia",
    sector: "Government",
    domain: "Digital",
    client_type: "Ministry",
    confidence: 0.91,
  },
  selected_packs: ["saudi_public_sector"],
  fallback_packs_used: [],
  warnings: [],
  routing_confidence: 0.82,
};

// ── Tests ───────────────────────────────────────────────────────────────

describe("integration: export page with artifact viewer tabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockGetArtifact.mockImplementation((_sessionId: string, name: string) => {
      const data: Record<string, unknown> = {
        evidence_ledger: mockLedgerData,
        slide_blueprint: mockBlueprintData,
        external_evidence: mockEvidencePackData,
        routing_report: mockRoutingData,
      };
      return Promise.resolve(data[name]);
    });
  });

  it("renders ExportPanel with SB download buttons when artifacts ready", async () => {
    mockGetStatus.mockResolvedValue(sbCompleteStatus);
    render(<ExportPage />);

    await waitFor(() => {
      expect(screen.getByTestId("export-panel")).toBeInTheDocument();
    });

    const downloadSection = screen.getByTestId("download-section");
    expect(downloadSection).toBeInTheDocument();
    // SB mode renders 3 buttons (Source Book DOCX, Research Query Log, Query Execution Log)
    const buttons = downloadSection.querySelectorAll("button");
    expect(buttons.length).toBe(3);
  });

  it("renders ArtifactViewerTabs when artifact flags are true", async () => {
    mockGetStatus.mockResolvedValue(sbCompleteStatus);
    render(<ExportPage />);

    await waitFor(() => {
      expect(screen.getByTestId("tab-evidence_ledger")).toBeInTheDocument();
    });

    expect(screen.getByTestId("tab-slide_blueprint")).toBeInTheDocument();
    expect(screen.getByTestId("tab-external_evidence")).toBeInTheDocument();
    expect(screen.getByTestId("tab-routing_report")).toBeInTheDocument();
  });

  it("does NOT render ArtifactViewerTabs when artifact flags are all false", async () => {
    mockGetStatus.mockResolvedValue(sbRunningStatus);
    render(<ExportPage />);

    await waitFor(() => {
      expect(screen.getByTestId("export-panel")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("tab-evidence_ledger")).not.toBeInTheDocument();
    expect(screen.queryByTestId("tab-slide_blueprint")).not.toBeInTheDocument();
    expect(screen.queryByTestId("tab-external_evidence")).not.toBeInTheDocument();
    expect(screen.queryByTestId("tab-routing_report")).not.toBeInTheDocument();
  });

  it("first tab fetches artifact data on mount", async () => {
    mockGetStatus.mockResolvedValue(sbCompleteStatus);
    render(<ExportPage />);

    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledWith("sess-sb-001", "evidence_ledger");
    });
  });

  it("switching tabs fetches new tab data", async () => {
    mockGetStatus.mockResolvedValue(sbCompleteStatus);
    render(<ExportPage />);

    await waitFor(() => {
      expect(screen.getByTestId("tab-slide_blueprint")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("tab-slide_blueprint"));

    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledTimes(2);
    });

    expect(mockGetArtifact).toHaveBeenCalledWith("sess-sb-001", "slide_blueprint");
  });

  it("switching back to cached tab does NOT re-fetch", async () => {
    mockGetStatus.mockResolvedValue(sbCompleteStatus);
    render(<ExportPage />);

    // Wait for first tab fetch (evidence_ledger)
    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledWith("sess-sb-001", "evidence_ledger");
    });

    // Switch to slide_blueprint
    fireEvent.click(screen.getByTestId("tab-slide_blueprint"));
    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledTimes(2);
    });

    // Switch back to evidence_ledger (cached — should NOT trigger fetch)
    fireEvent.click(screen.getByTestId("tab-evidence_ledger"));

    // Small wait to ensure no additional fetch fires
    await new Promise((r) => setTimeout(r, 100));

    expect(mockGetArtifact).toHaveBeenCalledTimes(2);
  });
});
