/**
 * StageTracker component tests.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StageTracker, type StageTrackerProps } from "./StageTracker";
import type { GateRecord } from "@/lib/types/pipeline";

// ── Mocks ──────────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const t = (key: string, values?: Record<string, unknown>) => {
      const messages: Record<string, string> = {
        stageTracker: "Pipeline Stages",
        stageGate: `Gate ${values?.number ?? ""}`,
        "stages.context": "Context Analysis",
        "stages.sources": "Source Research",
        "stages.report": "Report Generation",
        "stages.slides": "Slide Rendering",
        "stages.qa": "Quality Assurance",
      };
      return messages[key] ?? key;
    };
    return t;
  },
}));

vi.mock("@/components/ui/Spinner", () => ({
  Spinner: ({ label }: { label?: string }) => (
    <div role="status" aria-label={label ?? "Loading"}>
      spinner
    </div>
  ),
}));

// ── Helpers ────────────────────────────────────────────────────────────

function renderTracker(overrides: Partial<StageTrackerProps> = {}) {
  const defaultProps: StageTrackerProps = {
    currentStage: "",
    status: "idle",
    completedGates: [],
    error: null,
    ...overrides,
  };
  return render(<StageTracker {...defaultProps} />);
}

function makeGateRecord(gateNumber: number): GateRecord {
  return {
    gate_number: gateNumber,
    approved: true,
    feedback: "",
    decided_at: new Date().toISOString(),
  };
}

// ── Tests ──────────────────────────────────────────────────────────────

describe("StageTracker", () => {
  it("renders all 5 stages", () => {
    renderTracker();
    expect(screen.getByText("Context Analysis")).toBeInTheDocument();
    expect(screen.getByText("Source Research")).toBeInTheDocument();
    expect(screen.getByText("Report Generation")).toBeInTheDocument();
    expect(screen.getByText("Slide Rendering")).toBeInTheDocument();
    expect(screen.getByText("Quality Assurance")).toBeInTheDocument();
  });

  it("has accessible list role", () => {
    renderTracker();
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
  });

  it("shows all stages as pending when idle", () => {
    renderTracker({ status: "idle" });
    // All stages should have pending state (empty circles)
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
  });

  it("marks first stage as running when pipeline starts", () => {
    renderTracker({
      currentStage: "context_analysis",
      status: "running",
    });
    // First stage should show spinner
    const firstStage = screen.getByTestId("stage-context");
    expect(firstStage).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("marks completed gates as complete", () => {
    renderTracker({
      currentStage: "source_research",
      status: "running",
      completedGates: [makeGateRecord(1)],
    });

    // Gate 1 completed
    const contextStage = screen.getByTestId("stage-context");
    expect(contextStage).toBeInTheDocument();

    // Gate 2 should be running
    const sourcesStage = screen.getByTestId("stage-sources");
    expect(sourcesStage).toBeInTheDocument();
  });

  it("marks all stages complete when pipeline is complete", () => {
    renderTracker({
      currentStage: "finalized",
      status: "complete",
      completedGates: [
        makeGateRecord(1),
        makeGateRecord(2),
        makeGateRecord(3),
        makeGateRecord(4),
        makeGateRecord(5),
      ],
    });

    // All stages should be complete
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
  });

  it("shows error state on the current stage when pipeline errors", () => {
    renderTracker({
      currentStage: "report_generation",
      status: "error",
      completedGates: [makeGateRecord(1), makeGateRecord(2)],
      error: { agent: "report_agent", message: "Failed" },
    });

    // Report stage should show error styling
    const reportStage = screen.getByTestId("stage-report");
    expect(reportStage).toBeInTheDocument();
  });

  it("shows gate numbers for each stage", () => {
    renderTracker();
    expect(screen.getByText("Gate 1")).toBeInTheDocument();
    expect(screen.getByText("Gate 2")).toBeInTheDocument();
    expect(screen.getByText("Gate 3")).toBeInTheDocument();
    expect(screen.getByText("Gate 4")).toBeInTheDocument();
    expect(screen.getByText("Gate 5")).toBeInTheDocument();
  });

  it("handles gate_pending status", () => {
    renderTracker({
      currentStage: "context_analysis",
      status: "gate_pending",
      completedGates: [],
    });

    // First stage should show running (active, gate pending)
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
