/**
 * GatePanel component tests.
 *
 * Tests the master gate container dispatching by gate number (1-5).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { GatePanel } from "./GatePanel";
import type { GateInfo } from "@/lib/types/pipeline";

// ── Mocks ──────────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const t = (key: string, values?: Record<string, unknown>) => {
      const messages: Record<string, string> = {
        title: `Gate ${values?.number ?? ""} Review`,
        reviewRequired: "Review Required",
        approveLabel: "Approve & Continue",
        rejectLabel: "Reject & Revise",
        submitRejection: "Submit Rejection",
        cancelRejection: "Cancel",
        feedbackLabel: "Feedback",
        feedbackPlaceholder: "Provide feedback...",
        feedbackMinLength: `Minimum ${values?.count ?? 10} characters`,
        noData: "No data available",
        gate1Name: "Context Analysis",
        gate2Name: "Source Research",
        gate3Name: "Report Generation",
        gate4Name: "Slide Rendering",
        gate5Name: "Quality Assurance",
        includeSource: "Include source",
        sourcesSelected: `${values?.count ?? 0} of ${values?.total ?? 0} selected`,
        slideCount: `${values?.count ?? 0} slides`,
        qaSlide: "Slide",
        qaCheck: "Check",
        qaStatus: "Status",
        qaDetails: "Details",
        qaPassed: `${values?.count ?? 0} passed`,
        qaFailed: `${values?.count ?? 0} failed`,
        qaWarnings: `${values?.count ?? 0} warnings`,
      };
      return messages[key] ?? key;
    };
    return t;
  },
}));

vi.mock("@/hooks/use-gate", () => ({
  useGate: () => ({
    approve: vi.fn().mockResolvedValue(undefined),
    reject: vi.fn().mockResolvedValue(undefined),
    isDecidingGate: false,
    currentGate: null,
    completedGates: [],
  }),
}));

vi.mock("@/stores/locale-store", () => ({
  useLocaleStore: () => ({
    locale: "en",
    direction: "ltr",
    isRtl: false,
  }),
}));

// ── Helpers ────────────────────────────────────────────────────────────

function makeGate(gateNumber: number, data?: unknown): GateInfo {
  return {
    gate_number: gateNumber,
    summary: `Gate ${gateNumber} summary`,
    prompt: `Please review gate ${gateNumber} output`,
    gate_data: data,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────

describe("GatePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders gate panel with header and actions", () => {
    render(<GatePanel gate={makeGate(1)} />);
    expect(screen.getByTestId("gate-panel")).toBeInTheDocument();
    expect(screen.getByTestId("gate-header")).toBeInTheDocument();
    expect(screen.getByTestId("gate-actions")).toBeInTheDocument();
  });

  it("renders Gate 1 — Context Analysis", () => {
    render(
      <GatePanel
        gate={makeGate(1, {
          client_name: "Acme Corp",
          sector: "Technology",
        })}
      />,
    );
    expect(screen.getByTestId("gate-1-context")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Technology")).toBeInTheDocument();
  });

  it("renders Gate 2 — Source Research with checkboxes", () => {
    render(
      <GatePanel
        gate={makeGate(2, {
          sources: [
            { id: "s1", title: "Source A", relevance_score: 0.9 },
            { id: "s2", title: "Source B", relevance_score: 0.6 },
          ],
        })}
      />,
    );
    expect(screen.getByTestId("gate-2-sources")).toBeInTheDocument();
    expect(screen.getByText("Source A")).toBeInTheDocument();
    expect(screen.getByText("Source B")).toBeInTheDocument();
    // Checkboxes present
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(2);
    expect(checkboxes[0]).toBeChecked();
    expect(checkboxes[1]).toBeChecked();
  });

  it("renders Gate 3 — Research Report with markdown", () => {
    render(
      <GatePanel
        gate={makeGate(3, {
          report: "# Research Report\n\n## Key Findings\n\n- Finding one\n- Finding two",
        })}
      />,
    );
    expect(screen.getByTestId("gate-3-research")).toBeInTheDocument();
    expect(screen.getByTestId("markdown-viewer")).toBeInTheDocument();
    expect(screen.getByText("Research Report")).toBeInTheDocument();
    expect(screen.getByText("Key Findings")).toBeInTheDocument();
  });

  it("renders Gate 4 — Slide Rendering with outline", () => {
    render(
      <GatePanel
        gate={makeGate(4, {
          slides: [
            { index: 0, title: "Cover", section: "Introduction", slide_type: "cover" },
            { index: 1, title: "Understanding", section: "Section 01", slide_type: "content" },
          ],
        })}
      />,
    );
    expect(screen.getByTestId("gate-4-slides")).toBeInTheDocument();
    expect(screen.getByText("Cover")).toBeInTheDocument();
    expect(screen.getByText("Understanding")).toBeInTheDocument();
    expect(screen.getByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText("Section 01")).toBeInTheDocument();
  });

  it("renders Gate 5 — QA Results with pass/fail badges", () => {
    render(
      <GatePanel
        gate={makeGate(5, {
          results: [
            { slide_index: 1, check: "Font check", status: "pass", details: "OK" },
            { slide_index: 2, check: "Layout check", status: "fail", details: "Overflow" },
          ],
        })}
      />,
    );
    expect(screen.getByTestId("gate-5-qa")).toBeInTheDocument();
    expect(screen.getByText("Font check")).toBeInTheDocument();
    expect(screen.getByText("Layout check")).toBeInTheDocument();
    expect(screen.getByText("Pass")).toBeInTheDocument();
    expect(screen.getByText("Fail")).toBeInTheDocument();
  });

  it("shows approve and reject buttons", () => {
    render(<GatePanel gate={makeGate(1)} />);
    expect(screen.getByTestId("gate-approve-btn")).toBeInTheDocument();
    expect(screen.getByTestId("gate-reject-btn")).toBeInTheDocument();
  });

  it("renders gate number in header", () => {
    render(<GatePanel gate={makeGate(3)} />);
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Gate 3 Review")).toBeInTheDocument();
  });

  it("shows review prompt from gate info", () => {
    render(<GatePanel gate={makeGate(1)} />);
    expect(
      screen.getByText("Please review gate 1 output"),
    ).toBeInTheDocument();
  });

  it("handles unknown gate number gracefully", () => {
    render(<GatePanel gate={makeGate(99)} />);
    expect(screen.getByText("Unknown gate: 99")).toBeInTheDocument();
  });

  it("handles empty gate data gracefully", () => {
    render(<GatePanel gate={makeGate(1, null)} />);
    expect(screen.getByText("No data available")).toBeInTheDocument();
  });
});
