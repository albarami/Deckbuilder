import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { PipelineProgressBar } from "./PipelineProgressBar";

const mockUseIsPptEnabled = vi.fn(() => false);

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, values?: Record<string, unknown>) => {
    const map: Record<string, string> = {
      stageTracker: "Stage Tracker",
      "stages.context": "Context",
      "stages.sources": "Sources",
      "stages.sourceBook": "Source Book",
      "stages.slides": "Slides",
      "stages.qa": "QA",
      complete: "Complete",
      gatePending: "Gate Pending",
      running: "Running",
      "sourceBook.pptComingSoon": "Slides & QA coming soon",
    };
    if (key === "stageGate") return `Gate ${String(values?.number ?? "")}`;
    return map[key] ?? key;
  },
}));

vi.mock("@/hooks/use-is-ppt-enabled", () => ({
  useIsPptEnabled: () => mockUseIsPptEnabled(),
}));

describe("PipelineProgressBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseIsPptEnabled.mockReturnValue(false);
  });

  it("shows 3 primary stages and coming soon note when PPT is disabled", () => {
    render(
      <PipelineProgressBar
        currentStage="source_book_generation"
        status="running"
        completedGates={[]}
        currentGate={null}
      />,
    );

    expect(screen.getByTestId("pipeline-stage-context")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-stage-sources")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-stage-sourceBook")).toBeInTheDocument();
    expect(screen.queryByTestId("pipeline-stage-slides")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pipeline-stage-qa")).not.toBeInTheDocument();
    expect(screen.getByText("Slides & QA coming soon")).toBeInTheDocument();
  });

  it("shows all 5 stages when PPT is enabled", () => {
    mockUseIsPptEnabled.mockReturnValue(true);

    render(
      <PipelineProgressBar
        currentStage="slides"
        status="running"
        completedGates={[]}
        currentGate={null}
      />,
    );

    expect(screen.getByTestId("pipeline-stage-context")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-stage-sources")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-stage-sourceBook")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-stage-slides")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-stage-qa")).toBeInTheDocument();
    expect(screen.queryByText("Slides & QA coming soon")).not.toBeInTheDocument();
  });
});
