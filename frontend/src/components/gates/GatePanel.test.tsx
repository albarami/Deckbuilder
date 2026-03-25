/**
 * GatePanel component tests.
 *
 * Tests the master gate container dispatching by gate number (1-5).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { GatePanel } from "./GatePanel";
import type { GateInfo } from "@/lib/types/pipeline";

const { mockApprove, mockReject, mockUseIsPptEnabled } = vi.hoisted(() => ({
  mockApprove: vi.fn().mockResolvedValue(undefined),
  mockReject: vi.fn().mockResolvedValue(undefined),
  mockUseIsPptEnabled: vi.fn(() => true),
}));

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
        qaReadiness: "Readiness",
        qaReady: "Ready",
        qaReview: "Review",
        qaNeedsFixes: "Needs Fixes",
        qaBlocked: "Blocked",
        qaFailClose: "Fail-close active",
        qaPass: "Pass",
        qaFail: "Fail",
        qaWarning: "Warning",
        qaWaivers: "Waivers",
        qaTemplateCompliance: "Template Compliance",
        qaCoverage: "Coverage",
        missingFields: "Missing Fields",
        evaluationHighlights: "Evaluation Highlights",
      };
      return messages[key] ?? key;
    };
    return t;
  },
  useLocale: () => "en",
}));

vi.mock("@/hooks/use-gate", () => ({
  useGate: () => ({
    approve: mockApprove,
    reject: mockReject,
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

vi.mock("@/hooks/use-is-ppt-enabled", () => ({
  useIsPptEnabled: () => mockUseIsPptEnabled(),
}));

// ── Helpers ────────────────────────────────────────────────────────────

function makeGate(gateNumber: number, data?: GateInfo["gate_data"]): GateInfo {
  return {
    gate_number: gateNumber,
    summary: `Gate ${gateNumber} summary`,
    prompt: `Please review gate ${gateNumber} output`,
    payload_type: "context_review",
    gate_data: data,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────

describe("GatePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseIsPptEnabled.mockReturnValue(true);
    mockApprove.mockResolvedValue(undefined);
    mockReject.mockResolvedValue(undefined);
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
          rfp_brief: {
            rfp_name: { en: "Acme Corp RFP", ar: "" },
            issuing_entity: "Acme Corp",
            procurement_platform: "",
            mandate_summary: "Technology services",
            scope_requirements: [],
            deliverables: [],
            technical_evaluation: [],
            financial_evaluation: [],
            mandatory_compliance: [],
            key_dates: {
              inquiry_deadline: "",
              submission_deadline: "",
              opening_date: "",
              expected_award_date: "",
              service_start_date: "",
            },
            submission_format: {
              format: "",
              delivery_method: "",
              file_requirements: [],
              additional_instructions: "",
            },
          },
          missing_fields: [],
          selected_output_language: "en",
          user_notes: "",
          evaluation_highlights: [],
        })}
      />,
    );
    expect(screen.getByTestId("gate-1-context")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp RFP")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
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
          report_markdown: "# Research Report\n\n## Key Findings\n\n- Finding one\n- Finding two",
          sections: [],
          gaps: [],
          sensitivity_summary: [],
          source_index: [],
        })}
      />,
    );
    expect(screen.getByTestId("gate-3-research")).toBeInTheDocument();
    expect(screen.getByTestId("markdown-viewer")).toBeInTheDocument();
    expect(screen.getByText("Research Report")).toBeInTheDocument();
    expect(screen.getByText("Key Findings")).toBeInTheDocument();
  });

  it("renders Gate 3 — Source Book panel when payload_type is source_book_review", () => {
    render(
      <GatePanel
        gate={{
          gate_number: 3,
          summary: "Source Book ready",
          prompt: "Please review",
          payload_type: "source_book_review",
          gate_data: {
            source_book_title: "Digital Transformation Source Book",
            total_word_count: 4200,
            section_count: 7,
            sections: [
              {
                section_id: "executive_summary",
                title: "Executive Summary",
                preview_paragraph: "This is the first section preview.",
              },
            ],
            quality_summary: {
              reviewer_score: 88,
              benchmark_passed: true,
              evidence_count: 25,
              blueprint_count: 13,
            },
            evidence_summary: {
              evidence_ledger_entries: 25,
              external_source_count: 9,
            },
            blueprint_summary: {
              total_entries: 13,
              covered_sections: ["executive_summary"],
            },
            docx_ready: true,
          },
        }}
      />,
    );
    expect(screen.getByTestId("gate-3-source-book")).toBeInTheDocument();
    expect(screen.getByTestId("gate-3-docx-download")).toBeInTheDocument();
    expect(screen.getByText("Digital Transformation Source Book")).toBeInTheDocument();
  });

  it("renders Gate 3 — Source Book panel via shape detection fallback", () => {
    render(
      <GatePanel
        gate={{
          gate_number: 3,
          summary: "Source Book shape",
          prompt: "Please review",
          payload_type: "report_review",
          gate_data: {
            total_word_count: 3100,
            section_count: 7,
            sections: [],
            docx_ready: true,
          },
        }}
      />,
    );
    expect(screen.getByTestId("gate-3-source-book")).toBeInTheDocument();
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
    // Titles appear in both the card grid and the section list
    expect(screen.getAllByText("Cover").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Understanding").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Introduction").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Section 01").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Gate 5 — QA Results with pass/fail badges", () => {
    render(
      <GatePanel
        gate={makeGate(5, {
          submission_readiness: "needs_fixes",
          fail_close: false,
          critical_gaps: [],
          lint_status: "ready",
          density_status: "ready",
          template_compliance: "ready",
          language_status: "ready",
          coverage_status: "ready",
          waivers: [],
          results: [
            { slide_index: 1, check: "Font check", status: "pass", details: "OK" },
            { slide_index: 2, check: "Layout check", status: "fail", details: "Overflow" },
          ],
          deliverables: [],
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
    // Gate number is rendered as part of the title string "Gate 3 Review"
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

  it("renders non-blocking coming soon treatment for gate 4 when PPT is disabled", () => {
    mockUseIsPptEnabled.mockReturnValue(false);
    render(<GatePanel gate={makeGate(4)} />);
    expect(screen.getByTestId("gate-ppt-coming-soon")).toBeInTheDocument();
    expect(screen.getByTestId("gate-ppt-continue-btn")).toBeInTheDocument();
  });

  it("auto-advances gate 4 when PPT is disabled", async () => {
    mockUseIsPptEnabled.mockReturnValue(false);
    render(<GatePanel gate={makeGate(4)} />);
    await screen.findByTestId("gate-ppt-coming-soon");
    expect(mockApprove).toHaveBeenCalled();
  });

  it("auto-advances gate 5 when PPT is disabled", async () => {
    mockUseIsPptEnabled.mockReturnValue(false);
    render(<GatePanel gate={makeGate(5)} />);
    await screen.findByTestId("gate-ppt-coming-soon");
    expect(mockApprove).toHaveBeenCalled();
  });

  it("handles empty gate data gracefully", () => {
    render(<GatePanel gate={makeGate(1, null)} />);
    expect(screen.getByText("No data available")).toBeInTheDocument();
  });
});
