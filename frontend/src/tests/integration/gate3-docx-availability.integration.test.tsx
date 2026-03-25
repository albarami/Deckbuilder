import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { GatePanel } from "@/components/gates/GatePanel";
import type { GateInfo } from "@/lib/types/pipeline";

const mockDownloadDocx = vi.fn().mockResolvedValue(undefined);
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
    selector({ sessionId: "session-g3" }),
}));

vi.mock("@/lib/api/export", () => ({
  downloadDocx: (...args: unknown[]) => mockDownloadDocx(...args),
}));

const gate3Pending: GateInfo = {
  gate_number: 3,
  agent_name: "reviewer",
  payload_type: "source_book_review",
  summary: "Source book pending review",
  gate_data: {
    source_book_title: "Source Book Draft",
    total_word_count: 3980,
    section_count: 7,
    sections: [
      { section_id: "1", title: "Executive Summary", preview_paragraph: "A" },
      { section_id: "2", title: "Client Context", preview_paragraph: "B" },
      { section_id: "3", title: "Problem Framing", preview_paragraph: "C" },
      { section_id: "4", title: "Solution Approach", preview_paragraph: "D" },
      { section_id: "5", title: "Evidence Package", preview_paragraph: "E" },
      { section_id: "6", title: "Delivery Blueprint", preview_paragraph: "F" },
      { section_id: "7", title: "Risks and Assumptions", preview_paragraph: "G" },
    ],
    quality_summary: { reviewer_score: 89, benchmark_passed: true },
    evidence_summary: { evidence_ledger_entries: 22, external_source_count: 14 },
    blueprint_summary: { total_entries: 10, covered_sections: ["Executive Summary"] },
  },
  available_actions: ["approve", "reject"],
};

describe("integration: gate 3 DOCX availability", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows DOCX button and invokes download while gate 3 is pending", async () => {
    render(<GatePanel gate={gate3Pending} />);

    const docxBtn = screen.getByTestId("gate-3-docx-download");
    expect(docxBtn).toBeInTheDocument();

    fireEvent.click(docxBtn);
    await waitFor(() => expect(mockDownloadDocx).toHaveBeenCalledWith("session-g3"));
  });
});
