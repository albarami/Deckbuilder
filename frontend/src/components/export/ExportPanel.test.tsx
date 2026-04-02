/**
 * ExportPanel component tests.
 *
 * Tests the export panel with download buttons, summary display,
 * ready/not-ready states, and download interactions.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ExportPanel } from "./ExportPanel";
import type {
  PipelineOutputs,
  SessionMetadata,
  GateRecord,
} from "@/lib/types/pipeline";

// ── Mocks ──────────────────────────────────────────────────────────────

const mockUseIsPptEnabled = vi.fn(() => true);
let mockLocale: "en" | "ar" = "en";

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const t = (key: string, values?: Record<string, unknown>) => {
      const messagesEn: Record<string, string> = {
        title: "Export Deliverables",
        downloadPptx: "Download Presentation (PPTX)",
        downloadDocx: "Download Research Report (DOCX)",
        notReady: "Export will be available after the pipeline completes.",
        slideCount: `${values?.count ?? 0} slides generated`,
        downloadError: "Download failed. Please try again.",
        formatPptx: "PowerPoint (.pptx)",
        formatDocx: "Word Document (.docx)",
        summaryTitle: "Session Summary",
        summarySession: "Session",
        summaryDuration: "Duration",
        summarySlides: "Slides",
        summaryGates: "Gates",
        summaryLlmCalls: "LLM Calls",
        summaryInputTokens: "Input Tokens",
        summaryOutputTokens: "Output Tokens",
        summaryCost: "Cost",
        summaryGateTimeline: "Gate Timeline",
        summaryGateNumber: `Gate ${values?.number ?? ""}`,
        summaryStarted: "Started",
      };
      const messagesAr: Record<string, string> = {
        title: "تصدير المخرجات",
        downloadPptx: "تنزيل العرض (PPTX)",
        downloadDocx: "تنزيل التقرير (DOCX)",
        notReady: "سيتوفر التصدير بعد اكتمال خط الأنابيب.",
        slideCount: `${values?.count ?? 0} شرائح`,
        downloadError: "فشل التنزيل",
        formatPptx: "باوربوينت (.pptx)",
        formatDocx: "مستند وورد (.docx)",
        summaryTitle: "ملخص الجلسة",
        summarySession: "الجلسة",
        summaryDuration: "المدة",
        summarySlides: "الشرائح",
        summaryGates: "البوابات",
        summaryLlmCalls: "نداءات LLM",
        summaryInputTokens: "رموز الإدخال",
        summaryOutputTokens: "رموز الإخراج",
        summaryCost: "التكلفة",
        summaryGateTimeline: "سجل البوابات",
        summaryGateNumber: `البوابة ${values?.number ?? ""}`,
        summaryStarted: "بدأ",
        readyTitle: "كتاب المصدر جاهز",
        downloadDocxNow: "نزّل ملف DOCX الآن",
      };
      const active = mockLocale === "ar" ? messagesAr : messagesEn;
      return active[key] ?? key;
    };
    return t;
  },
}));

vi.mock("@/stores/locale-store", () => ({
  useLocaleStore: () => ({
    locale: mockLocale,
    direction: mockLocale === "ar" ? "rtl" : "ltr",
    isRtl: mockLocale === "ar",
  }),
}));

vi.mock("@/hooks/use-is-ppt-enabled", () => ({
  useIsPptEnabled: () => mockUseIsPptEnabled(),
}));

const mockDownloadPptx = vi.fn().mockResolvedValue(undefined);
const mockDownloadDocx = vi.fn().mockResolvedValue(undefined);

vi.mock("@/lib/api/export", () => ({
  downloadPptx: (...args: unknown[]) => mockDownloadPptx(...args),
  downloadDocx: (...args: unknown[]) => mockDownloadDocx(...args),
}));

// ── Helpers ────────────────────────────────────────────────────────────

const mockOutputs: PipelineOutputs = {
  pptx_ready: true,
  docx_ready: true,
  source_index_ready: false,
  gap_report_ready: false,
  slide_count: 24,
  preview_ready: true,
  deliverables: [],
  source_book_ready: false,
  evidence_ledger_ready: false,
  slide_blueprint_ready: false,
  external_evidence_ready: false,
  routing_report_ready: false,
  research_query_log_ready: false,
  query_execution_log_ready: false,
};

const mockMetadata: SessionMetadata = {
  total_llm_calls: 42,
  total_input_tokens: 125000,
  total_output_tokens: 45000,
  total_cost_usd: 3.75,
};

const mockGates: GateRecord[] = [
  { gate_number: 1, approved: true, feedback: "", decided_at: "2024-01-01T10:05:00Z" },
  { gate_number: 2, approved: true, feedback: "", decided_at: "2024-01-01T10:10:00Z" },
  { gate_number: 3, approved: false, feedback: "Needs revision", decided_at: "2024-01-01T10:15:00Z" },
  { gate_number: 4, approved: true, feedback: "", decided_at: "2024-01-01T10:20:00Z" },
  { gate_number: 5, approved: true, feedback: "", decided_at: "2024-01-01T10:25:00Z" },
];

const defaultProps = {
  sessionId: "abc12345-def6-7890-abcd-ef1234567890",
  outputs: mockOutputs,
  metadata: mockMetadata,
  completedGates: mockGates,
  startedAt: "2024-01-01T10:00:00Z",
  elapsedMs: 300000,
};

// ── Tests ──────────────────────────────────────────────────────────────

describe("ExportPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseIsPptEnabled.mockReturnValue(true);
    mockLocale = "en";
  });

  it("renders the export panel with title", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("export-panel")).toBeInTheDocument();
    expect(screen.getByText("Export Deliverables")).toBeInTheDocument();
  });

  it("shows slide count when outputs are ready", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByText("24 slides generated")).toBeInTheDocument();
  });

  it("shows not-ready message when outputs are null", () => {
    render(<ExportPanel {...defaultProps} outputs={null} />);
    expect(
      screen.getByText("Export will be available after the pipeline completes."),
    ).toBeInTheDocument();
  });

  it("renders download buttons when ready", () => {
    render(<ExportPanel {...defaultProps} />);
    const downloadButtons = screen.getAllByTestId("download-button");
    expect(downloadButtons).toHaveLength(2);
  });

  it("renders unavailable download buttons when not ready", () => {
    render(<ExportPanel {...defaultProps} outputs={null} />);
    const unavailable = screen.getAllByTestId("download-unavailable");
    expect(unavailable).toHaveLength(4);
  });

  it("keeps DOCX available when gate 3 is pending (outputs null)", () => {
    render(
      <ExportPanel
        {...defaultProps}
        outputs={null}
        sourceBookGatePending
      />,
    );
    const downloadButtons = screen.getAllByTestId("download-button");
    expect(downloadButtons).toHaveLength(1);
  });

  it("hides PPTX download when PPT is disabled", () => {
    mockUseIsPptEnabled.mockReturnValue(false);
    render(<ExportPanel {...defaultProps} />);
    const downloadButtons = screen.getAllByTestId("download-button");
    expect(downloadButtons).toHaveLength(1);
    expect(screen.queryByText("PowerPoint (.pptx)")).not.toBeInTheDocument();
    expect(screen.getByText("Word Document (.docx)")).toBeInTheDocument();
  });

  it("renders source-book export copy in Arabic under RTL wrapper", () => {
    mockLocale = "ar";
    mockUseIsPptEnabled.mockReturnValue(false);
    render(
      <div dir="rtl">
        <ExportPanel
          {...defaultProps}
          outputs={null}
          sourceBookGatePending
        />
      </div>,
    );
    expect(screen.getByText("تصدير المخرجات")).toBeInTheDocument();
    expect(screen.getByText("كتاب المصدر جاهز")).toBeInTheDocument();
    expect(screen.getByText("نزّل ملف DOCX الآن")).toBeInTheDocument();
  });

  it("triggers PPTX download on click", async () => {
    render(<ExportPanel {...defaultProps} />);
    const buttons = screen.getAllByTestId("download-button");
    fireEvent.click(buttons[0]);
    await waitFor(() => {
      expect(mockDownloadPptx).toHaveBeenCalledWith("abc12345-def6-7890-abcd-ef1234567890");
    });
  });

  it("triggers DOCX download on click", async () => {
    render(<ExportPanel {...defaultProps} />);
    const buttons = screen.getAllByTestId("download-button");
    fireEvent.click(buttons[1]);
    await waitFor(() => {
      expect(mockDownloadDocx).toHaveBeenCalledWith("abc12345-def6-7890-abcd-ef1234567890");
    });
  });

  it("shows format badges when outputs are ready", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("format-hints")).toBeInTheDocument();
    expect(screen.getByText("PowerPoint (.pptx)")).toBeInTheDocument();
    expect(screen.getByText("Word Document (.docx)")).toBeInTheDocument();
  });

  it("hides format badges when not ready", () => {
    render(<ExportPanel {...defaultProps} outputs={null} />);
    expect(screen.queryByTestId("format-hints")).not.toBeInTheDocument();
  });

  // ── ExportSummary tests (integrated) ──────────────────────────────

  it("renders the session summary card", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("export-summary")).toBeInTheDocument();
    expect(screen.getByText("Session Summary")).toBeInTheDocument();
  });

  it("displays session ID (truncated)", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("summary-session")).toBeInTheDocument();
    expect(screen.getByText("abc12345")).toBeInTheDocument();
  });

  it("displays duration", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("summary-duration")).toBeInTheDocument();
    expect(screen.getByText("5m 0s")).toBeInTheDocument();
  });

  it("displays slide count in summary", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("summary-slides")).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
  });

  it("displays gates passed count", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("summary-gates")).toBeInTheDocument();
    expect(screen.getByText("5/5")).toBeInTheDocument();
  });

  it("displays LLM call count", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("summary-llm-calls")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("displays token counts with formatting", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("summary-input-tokens")).toBeInTheDocument();
    expect(screen.getByText("125.0K")).toBeInTheDocument();
    expect(screen.getByTestId("summary-output-tokens")).toBeInTheDocument();
    expect(screen.getByText("45.0K")).toBeInTheDocument();
  });

  it("displays cost", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("summary-cost")).toBeInTheDocument();
    expect(screen.getByText("$3.75")).toBeInTheDocument();
  });

  it("displays gate timeline badges", () => {
    render(<ExportPanel {...defaultProps} />);
    expect(screen.getByTestId("gate-badge-1")).toBeInTheDocument();
    expect(screen.getByTestId("gate-badge-3")).toBeInTheDocument();
    expect(screen.getByTestId("gate-badge-5")).toBeInTheDocument();
  });

  it("shows only PPTX when DOCX is not ready", () => {
    const partialOutputs: PipelineOutputs = {
      pptx_ready: true,
      docx_ready: false,
      source_index_ready: false,
      gap_report_ready: false,
      slide_count: 10,
      preview_ready: false,
      deliverables: [],
      source_book_ready: false,
      evidence_ledger_ready: false,
      slide_blueprint_ready: false,
      external_evidence_ready: false,
      routing_report_ready: false,
      research_query_log_ready: false,
      query_execution_log_ready: false,
    };
    render(<ExportPanel {...defaultProps} outputs={partialOutputs} />);
    const downloadButtons = screen.getAllByTestId("download-button");
    expect(downloadButtons).toHaveLength(1);
    const unavailable = screen.getAllByTestId("download-unavailable");
    expect(unavailable).toHaveLength(3);
  });

  it("handles zero elapsed time", () => {
    render(<ExportPanel {...defaultProps} elapsedMs={0} />);
    expect(screen.getByText("0s")).toBeInTheDocument();
  });

  it("handles empty gates list", () => {
    render(<ExportPanel {...defaultProps} completedGates={[]} />);
    expect(screen.getByText("0/5")).toBeInTheDocument();
    expect(screen.queryByTestId("gate-badge-1")).not.toBeInTheDocument();
  });
});
