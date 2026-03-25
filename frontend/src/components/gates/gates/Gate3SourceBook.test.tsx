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
  source_book_title: "Government Transformation Source Book",
  total_word_count: 4820,
  section_count: 7,
  sections: [
    {
      section_id: "1",
      title: "Executive Summary",
      preview_paragraph:
        "This section captures the strategic intent, urgency, and delivery outcomes for the ministry.",
    },
    {
      section_id: "2",
      title: "Client Context",
      preview_paragraph:
        "This section outlines the operating model, mandate constraints, and stakeholder landscape.",
    },
    {
      section_id: "3",
      title: "Problem Framing",
      preview_paragraph:
        "This section defines the core delivery challenges and opportunity boundaries for transformation.",
    },
    {
      section_id: "4",
      title: "Solution Approach",
      preview_paragraph:
        "This section explains workstreams, execution phases, and coordination model across teams.",
    },
    {
      section_id: "5",
      title: "Evidence Package",
      preview_paragraph:
        "This section references evidence quality, external benchmarks, and source attribution policies.",
    },
    {
      section_id: "6",
      title: "Delivery Blueprint",
      preview_paragraph:
        "This section maps activities into milestones and artifacts aligned with proposal narrative flow.",
    },
    {
      section_id: "7",
      title: "Risks and Assumptions",
      preview_paragraph:
        "This section highlights delivery risks, mitigation plans, and assumptions requiring validation.",
    },
  ],
  quality_summary: {
    reviewer_score: 92,
    benchmark_passed: true,
    evidence_count: 25,
    blueprint_count: 13,
  },
  evidence_summary: {
    evidence_ledger_entries: 25,
    external_source_count: 16,
  },
  blueprint_summary: {
    total_entries: 13,
    covered_sections: [
      "Executive Summary",
      "Client Context",
      "Problem Framing",
      "Solution Approach",
      "Evidence Package",
      "Delivery Blueprint",
      "Risks and Assumptions",
    ],
  },
  docx_ready: true,
};

const gate: GateInfo = {
  gate_number: 3,
  agent_name: "reviewer",
  payload_type: "source_book_review",
  gate_data: gateData,
  available_actions: ["approve", "reject"],
};

describe("Gate3SourceBook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseLocale.mockReturnValue("en");
  });

  it("renders source-book summary, 7 section previews, and evidence/blueprint stats", () => {
    render(<Gate3SourceBook gate={gate} />);

    expect(screen.getByText("Government Transformation Source Book")).toBeInTheDocument();
    expect(screen.getByText("4,820 words")).toBeInTheDocument();
    expect(screen.getAllByText("Evidence Package").length).toBeGreaterThan(0);
    expect(screen.getByText("Slide Blueprint Summary")).toBeInTheDocument();
    expect(screen.getByText("Section Preview")).toBeInTheDocument();
    expect(screen.getAllByText("Executive Summary").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Risks and Assumptions").length).toBeGreaterThan(0);
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
