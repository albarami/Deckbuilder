import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Gate3SourceBookData, GateInfo } from "@/lib/types/pipeline";
import { Gate3SourceBook } from "./Gate3SourceBook";

const mockDownloadDocx = vi.fn().mockResolvedValue(undefined);
const mockUseLocale = vi.fn(() => "en");

vi.mock("next-intl", () => ({
  useLocale: () => mockUseLocale(),
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      noData: "No data available for review.",
    };
    return map[key] ?? key;
  },
}));

vi.mock("@/stores/pipeline-store", () => ({
  usePipelineStore: (selector: (state: { sessionId: string }) => unknown) =>
    selector({ sessionId: "sess-123" }),
}));

vi.mock("@/lib/api/export", () => ({
  downloadDocx: (...args: unknown[]) => mockDownloadDocx(...args),
}));

const gateData: Gate3SourceBookData = {
  reviewer_score: 4,
  threshold_met: true,
  competitive_viability: "strong",
  pass_number: 2,
  rewrite_required: false,
  section_critiques: [
    {
      section_id: "sec-1",
      score: 4,
      issues: ["Minor formatting"],
      rewrite_instructions: [],
    },
    {
      section_id: "sec-2",
      score: 3,
      issues: ["Needs more detail"],
      rewrite_instructions: ["Expand evidence base"],
    },
  ],
  coherence_issues: ["Cross-reference gap between sections 3 and 5"],
  word_count: 18500,
  evidence_count: 25,
  blueprint_count: 13,
  docx_preview_url: "/api/pipeline/sess-123/artifact/source_book_preview",
};

const gate: GateInfo = {
  gate_number: 3,
  summary: "Source Book ready for review",
  prompt: "Review and approve the Source Book",
  payload_type: "source_book_review",
  gate_data: gateData,
};

describe("Gate3SourceBook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseLocale.mockReturnValue("en");
  });

  it("renders review-centric payload with score, critiques, and metrics", () => {
    render(<Gate3SourceBook gate={gate} />);

    // Title defaults to "Source Book" when source_book_title not provided
    expect(screen.getByText("Source Book")).toBeInTheDocument();
    // Word count from new payload
    expect(screen.getByText("18,500 words")).toBeInTheDocument();
    // Threshold badge
    expect(screen.getAllByText("Passed").length).toBeGreaterThan(0);
    // Competitive viability
    expect(screen.getByText("strong")).toBeInTheDocument();
    // Quality & Benchmark section
    expect(screen.getByText("Quality & Benchmark")).toBeInTheDocument();
    // Section critiques rendered
    expect(screen.getByText("sec-1")).toBeInTheDocument();
    expect(screen.getByText("4/5")).toBeInTheDocument();
    expect(screen.getByText(/Minor formatting/)).toBeInTheDocument();
    expect(screen.getByText("sec-2")).toBeInTheDocument();
    expect(screen.getByText("3/5")).toBeInTheDocument();
    expect(screen.getByText(/Needs more detail/)).toBeInTheDocument();
  });

  it("shows DOCX button and triggers download with the current session id", async () => {
    render(<Gate3SourceBook gate={gate} />);

    const button = screen.getByTestId("gate-3-docx-download");
    fireEvent.click(button);

    await waitFor(() => expect(mockDownloadDocx).toHaveBeenCalledWith("sess-123"));
  });

  it("uses RTL container when locale is Arabic", () => {
    mockUseLocale.mockReturnValue("ar");
    render(<Gate3SourceBook gate={gate} />);

    expect(screen.getByTestId("gate-3-source-book")).toHaveAttribute("dir", "rtl");
  });
});
