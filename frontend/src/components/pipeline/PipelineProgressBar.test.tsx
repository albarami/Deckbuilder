import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { PipelineProgressBar } from "./PipelineProgressBar";

const mockUseIsPptEnabled = vi.fn(() => false);
let mockLocale: "en" | "ar" = "en";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, values?: Record<string, unknown>) => {
    const enMap: Record<string, string> = {
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
    const arMap: Record<string, string> = {
      stageTracker: "متتبع المراحل",
      "stages.context": "السياق",
      "stages.sources": "المصادر",
      "stages.sourceBook": "كتاب المصدر",
      "stages.slides": "الشرائح",
      "stages.qa": "ضمان الجودة",
      complete: "مكتمل",
      gatePending: "بوابة معلقة",
      running: "قيد التنفيذ",
      "sourceBook.pptComingSoon": "الشرائح وضمان الجودة قريبًا",
    };
    const map = mockLocale === "ar" ? arMap : enMap;
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
    mockLocale = "en";
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

  it("renders Arabic labels correctly within RTL container", () => {
    mockLocale = "ar";
    render(
      <div dir="rtl">
        <PipelineProgressBar
          currentStage="source_book_generation"
          status="running"
          completedGates={[]}
          currentGate={null}
        />
      </div>,
    );

    expect(screen.getByText("السياق")).toBeInTheDocument();
    expect(screen.getByText("المصادر")).toBeInTheDocument();
    expect(screen.getByText("كتاب المصدر")).toBeInTheDocument();
    expect(screen.getByText("الشرائح وضمان الجودة قريبًا")).toBeInTheDocument();
  });
});
