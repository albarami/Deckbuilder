/**
 * SourceBookArtifactSummary component tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { SourceBookArtifactSummary } from "./SourceBookArtifactSummary";

// ── i18n mock ─────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      "summary.wordCount": "Word Count",
      "summary.reviewerScore": "Reviewer Score",
      "summary.passNumber": "Pass",
      "summary.evidenceLedger": "Evidence Ledger",
      "summary.blueprints": "Blueprints",
      "summary.externalSources": "External Sources",
      "summary.ready": "Ready",
      "summary.notReady": "Pending",
      "summary.sourceBook": "Source Book",
      "summary.evidencePack": "Evidence Pack",
      "summary.routingReport": "Routing Report",
      "summary.viewDetails": "View Evidence Details",
    };
    return map[key] ?? key;
  },
}));

// ── Link mock ─────────────────────────────────────────────────────────

vi.mock("@/i18n/routing", () => ({
  Link: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

// ── Pipeline store mock ──────────────────────────────────────────────

let mockStoreState: Record<string, unknown> = {};

vi.mock("@/stores/pipeline-store", () => ({
  usePipelineStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector(mockStoreState),
}));

// ── Mock data ────────────────────────────────────────────────────────

const baseSummary = {
  word_count: 15000,
  reviewer_score: 4,
  threshold_met: true,
  competitive_viability: "strong",
  evidence_ledger_entries: 42,
  slide_blueprint_entries: 18,
  external_sources: 7,
  capability_mappings: 12,
  consultant_count: 3,
  real_consultant_names: ["Alice", "Bob", "Carol"],
  project_count: 5,
  pass_number: 2,
};

const baseOutputs = {
  source_book_ready: true,
  evidence_ledger_ready: true,
  slide_blueprint_ready: false,
  external_evidence_ready: true,
  routing_report_ready: false,
  research_query_log_ready: true,
  query_execution_log_ready: true,
};

// ── Tests ────────────────────────────────────────────────────────────

describe("SourceBookArtifactSummary", () => {
  beforeEach(() => {
    mockStoreState = {
      sourceBookSummary: null,
      outputs: null,
      sessionId: null,
    };
  });

  it("returns null when no summary", () => {
    const { container } = render(<SourceBookArtifactSummary />);
    expect(container.innerHTML).toBe("");
  });

  it("renders primary metrics", () => {
    mockStoreState = {
      sourceBookSummary: baseSummary,
      outputs: baseOutputs,
      sessionId: "sess-123",
    };

    render(<SourceBookArtifactSummary />);

    expect(screen.getByText("15,000")).toBeInTheDocument();
    expect(screen.getByText("4 / 5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Word Count")).toBeInTheDocument();
    expect(screen.getByText("Reviewer Score")).toBeInTheDocument();
    expect(screen.getByText("Pass")).toBeInTheDocument();
  });

  it("renders secondary metrics", () => {
    mockStoreState = {
      sourceBookSummary: baseSummary,
      outputs: baseOutputs,
      sessionId: "sess-123",
    };

    render(<SourceBookArtifactSummary />);

    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("shows readiness badges with correct status", () => {
    mockStoreState = {
      sourceBookSummary: baseSummary,
      outputs: baseOutputs,
      sessionId: "sess-123",
    };

    render(<SourceBookArtifactSummary />);

    expect(screen.getByText("Source Book: Ready")).toBeInTheDocument();
    expect(screen.getByText("Evidence Ledger: Ready")).toBeInTheDocument();
    expect(screen.getByText("Blueprints: Pending")).toBeInTheDocument();
    expect(screen.getByText("Evidence Pack: Ready")).toBeInTheDocument();
    expect(screen.getByText("Routing Report: Pending")).toBeInTheDocument();
  });

  it("renders CTA link with correct href", () => {
    mockStoreState = {
      sourceBookSummary: baseSummary,
      outputs: baseOutputs,
      sessionId: "sess-123",
    };

    render(<SourceBookArtifactSummary />);

    const button = screen.getByRole("button", { name: /view evidence details/i });
    expect(button).toBeInTheDocument();

    const link = button.closest("a");
    expect(link).toHaveAttribute("href", "/pipeline/sess-123/export");
  });

  it("handles null outputs gracefully — badges show Pending", () => {
    mockStoreState = {
      sourceBookSummary: baseSummary,
      outputs: null,
      sessionId: "sess-123",
    };

    render(<SourceBookArtifactSummary />);

    expect(screen.getByText("Source Book: Pending")).toBeInTheDocument();
    expect(screen.getByText("Evidence Ledger: Pending")).toBeInTheDocument();
    expect(screen.getByText("Blueprints: Pending")).toBeInTheDocument();
    expect(screen.getByText("Evidence Pack: Pending")).toBeInTheDocument();
    expect(screen.getByText("Routing Report: Pending")).toBeInTheDocument();
  });
});
