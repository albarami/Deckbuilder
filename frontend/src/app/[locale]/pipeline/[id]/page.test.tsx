import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import PipelineSessionPage from "./page";

const mockUsePipeline = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "session-xyz" }),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, values?: Record<string, unknown>) => {
    if (key === "gatePendingTitle") return `Gate ${values?.number} Pending`;
    const map: Record<string, string> = {
      loading: "Loading",
      "sourceBook.readyTitle": "Your Source Book is ready",
      "stages.context": "Context",
      "stages.sources": "Sources",
      "stages.sourceBook": "Source Book",
      running: "Running",
      gatePending: "Gate Pending",
      metricLlmCalls: "LLM Calls",
      metricStatus: "Status",
      metricCost: "Cost",
      metricLive: "Live",
      metricReview: "In Review",
      readyTitle: "Your Source Book is ready",
      downloadDocxNow: "Download DOCX now",
      sectionPreview: "Sections",
      evidenceSummary: "Evidence",
      wordCount: "Words",
      downloadError: "Download failed",
    };
    return map[key] ?? key;
  },
}));

vi.mock("@/hooks/use-pipeline", () => ({
  usePipeline: () => mockUsePipeline(),
}));

vi.mock("@/hooks/use-sse", () => ({
  useSSE: vi.fn(),
}));

vi.mock("@/hooks/use-is-ppt-enabled", () => ({
  useIsPptEnabled: () => false,
}));

vi.mock("@/components/pipeline/PipelineHeader", () => ({
  PipelineHeader: () => <div data-testid="pipeline-header" />,
}));
vi.mock("@/components/pipeline/PipelineProgressBar", () => ({
  PipelineProgressBar: () => <div data-testid="pipeline-progress" />,
}));
vi.mock("@/components/pipeline/ActivityTimeline", () => ({
  ActivityTimeline: () => <div data-testid="activity-timeline" />,
}));
vi.mock("@/components/pipeline/AgentStatusGrid", () => ({
  AgentStatusGrid: () => <div data-testid="agent-grid" />,
}));
vi.mock("@/components/pipeline/JourneyLegend", () => ({
  JourneyLegend: () => <div data-testid="journey-legend" />,
}));
vi.mock("@/components/pipeline/PipelineErrorBanner", () => ({
  PipelineErrorBanner: () => <div data-testid="error-banner" />,
}));
vi.mock("@/components/pipeline/PipelineComplete", () => ({
  PipelineComplete: () => <div data-testid="pipeline-complete" />,
}));
vi.mock("@/components/gates/GatePanel", () => ({
  GatePanel: () => <div data-testid="gate-panel" />,
}));
vi.mock("@/lib/api/export", () => ({
  downloadDocx: vi.fn(),
}));
vi.mock("@/i18n/routing", () => ({
  Link: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

const basePipeline = {
  sessionId: "session-xyz",
  status: "running" as const,
  currentStage: "source_book_generation",
  currentGate: null,
  completedGates: [],
  outputs: null,
  error: null,
  startedAt: "2026-03-25T10:00:00Z",
  elapsedMs: 2000,
  events: [],
  isSourceBookGatePending: false,
  isSourceBookReadyCheckpoint: false,
  agentRuns: [],
  sessionMetadata: {
    total_llm_calls: 2,
    total_input_tokens: 100,
    total_output_tokens: 50,
    total_cost_usd: 0.2,
  },
  resume: vi.fn().mockResolvedValue(true),
};

describe("Pipeline session page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePipeline.mockReturnValue(basePipeline);
  });

  it("shows source book review panel and DOCX CTA when gate 3 is pending", async () => {
    mockUsePipeline.mockReturnValue({
      ...basePipeline,
      status: "gate_pending",
      isSourceBookGatePending: true,
      currentGate: {
        gate_number: 3,
        agent_name: "reviewer",
        payload_type: "source_book_review",
        gate_data: {
          section_count: 7,
          total_word_count: 4200,
          sections: [],
          quality_summary: { evidence_count: 25 },
          evidence_summary: { evidence_ledger_entries: 25 },
        },
        available_actions: ["approve", "reject"],
      },
    });

    render(<PipelineSessionPage />);
    expect(screen.getByText("Gate 3 Pending")).toBeInTheDocument();
    expect(screen.getByTestId("source-book-session-docx-btn")).toBeInTheDocument();
    expect(screen.getByTestId("gate-panel")).toBeInTheDocument();
  });

  it("shows source book ready checkpoint after gate 3 approval state", async () => {
    mockUsePipeline.mockReturnValue({
      ...basePipeline,
      status: "running",
      isSourceBookReadyCheckpoint: true,
      completedGates: [{ gate_number: 3, approved: true }],
    });

    render(<PipelineSessionPage />);
    expect(screen.getAllByText("Your Source Book is ready").length).toBeGreaterThan(0);
    expect(screen.getByTestId("source-book-session-docx-btn")).toBeInTheDocument();
  });
});
