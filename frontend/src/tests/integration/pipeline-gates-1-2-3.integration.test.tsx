import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { GatePanel } from "@/components/gates/GatePanel";
import type { GateInfo } from "@/lib/types/pipeline";

const mockApprove = vi.fn().mockResolvedValue(undefined);
const mockReject = vi.fn().mockResolvedValue(undefined);

vi.mock("next-intl", () => ({
  useLocale: () => "en",
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/hooks/use-gate", () => ({
  useGate: () => ({
    approve: (...args: unknown[]) => mockApprove(...args),
    reject: (...args: unknown[]) => mockReject(...args),
    isDecidingGate: false,
  }),
}));

vi.mock("@/hooks/use-is-ppt-enabled", () => ({
  useIsPptEnabled: () => false,
}));

vi.mock("@/stores/pipeline-store", () => ({
  usePipelineStore: (selector: (state: { sessionId: string }) => unknown) =>
    selector({ sessionId: "session-abc" }),
}));

vi.mock("@/lib/api/export", () => ({
  downloadDocx: vi.fn().mockResolvedValue(undefined),
}));

const gate1: GateInfo = {
  gate_number: 1,
  agent_name: "context_analyzer",
  payload_type: "context_review",
  summary: "Review extracted RFP context",
  gate_data: {
    rfp_brief: {
      rfp_name: { en: "National Transformation RFP" },
      issuing_entity: "Ministry of Digital Government",
    },
    missing_fields: [],
    evaluation_highlights: ["Scope parsed", "Deadlines captured"],
  },
  available_actions: ["approve", "reject"],
};

const gate2: GateInfo = {
  gate_number: 2,
  agent_name: "retrieval",
  payload_type: "source_review",
  summary: "Review retrieved evidence sources",
  gate_data: {
    sources: [
      { source_id: "s1", title: "Benchmark paper 1", relevance_score: 0.91 },
      { source_id: "s2", title: "Benchmark paper 2", relevance_score: 0.87 },
    ],
  },
  available_actions: ["approve", "reject"],
};

const gate3: GateInfo = {
  gate_number: 3,
  agent_name: "reviewer",
  payload_type: "source_book_review",
  summary: "Review source book draft",
  gate_data: {
    source_book_title: "Source Book",
    total_word_count: 4100,
    section_count: 7,
    sections: [
      { section_id: "1", title: "Executive Summary", preview_paragraph: "Preview 1" },
      { section_id: "2", title: "Client Context", preview_paragraph: "Preview 2" },
      { section_id: "3", title: "Problem Framing", preview_paragraph: "Preview 3" },
      { section_id: "4", title: "Solution Approach", preview_paragraph: "Preview 4" },
      { section_id: "5", title: "Evidence Package", preview_paragraph: "Preview 5" },
      { section_id: "6", title: "Delivery Blueprint", preview_paragraph: "Preview 6" },
      { section_id: "7", title: "Risks and Assumptions", preview_paragraph: "Preview 7" },
    ],
    quality_summary: { reviewer_score: 90, benchmark_passed: true },
    evidence_summary: { evidence_ledger_entries: 25, external_source_count: 16 },
    blueprint_summary: { total_entries: 12, covered_sections: ["Executive Summary"] },
  },
  available_actions: ["approve", "reject"],
};

describe("integration: gate 1 -> gate 2 -> gate 3 flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders each gate panel and supports approve interaction across progression", async () => {
    const { rerender } = render(<GatePanel gate={gate1} />);
    expect(screen.getByTestId("gate-1-context")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("gate-approve-btn"));
    await waitFor(() => expect(mockApprove).toHaveBeenCalledTimes(1));

    rerender(<GatePanel gate={gate2} />);
    expect(screen.getByTestId("gate-2-sources")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("includeSource: Benchmark paper 1"));
    fireEvent.click(screen.getByTestId("gate-approve-btn"));
    await waitFor(() => expect(mockApprove).toHaveBeenCalledTimes(2));

    rerender(<GatePanel gate={gate3} />);
    expect(screen.getByTestId("gate-3-source-book")).toBeInTheDocument();
    expect(screen.getByText("Section Preview")).toBeInTheDocument();
  });
});
