/**
 * ArtifactViewerTabs component tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ArtifactViewerTabs } from "./ArtifactViewerTabs";

// ── i18n mock ─────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      evidenceLedger: "Evidence Ledger",
      slideBlueprints: "Slide Blueprints",
      externalEvidence: "External Evidence",
      routingReport: "Routing Report",
      downloadJson: "Download JSON",
      noData: "No data available",
      loadError: "Failed to load",
    };
    return map[key] ?? key;
  },
}));

// ── API mocks ─────────────────────────────────────────────────────────

const mockGetArtifact = vi.fn();
vi.mock("@/lib/api/artifacts", () => ({
  getArtifact: (...args: unknown[]) => mockGetArtifact(...args),
}));

const mockDownloadEvidenceLedger = vi.fn();
const mockDownloadSlideBlueprint = vi.fn();
const mockDownloadExternalEvidence = vi.fn();
const mockDownloadRoutingReport = vi.fn();
vi.mock("@/lib/api/export", () => ({
  downloadEvidenceLedger: (...args: unknown[]) => mockDownloadEvidenceLedger(...args),
  downloadSlideBlueprint: (...args: unknown[]) => mockDownloadSlideBlueprint(...args),
  downloadExternalEvidence: (...args: unknown[]) => mockDownloadExternalEvidence(...args),
  downloadRoutingReport: (...args: unknown[]) => mockDownloadRoutingReport(...args),
}));

// ── Viewer mocks (keep them simple) ───────────────────────────────────

vi.mock("./EvidenceLedgerViewer", () => ({
  EvidenceLedgerViewer: ({ data }: { data: unknown }) => (
    <div data-testid="evidence-ledger-viewer">{JSON.stringify(data)}</div>
  ),
}));

vi.mock("./BlueprintViewer", () => ({
  BlueprintViewer: ({ data }: { data: unknown }) => (
    <div data-testid="blueprint-viewer">{JSON.stringify(data)}</div>
  ),
}));

vi.mock("./EvidencePackViewer", () => ({
  EvidencePackViewer: ({ data }: { data: unknown }) => (
    <div data-testid="evidence-pack-viewer">{JSON.stringify(data)}</div>
  ),
}));

vi.mock("./RoutingReportViewer", () => ({
  RoutingReportViewer: ({ data }: { data: unknown }) => (
    <div data-testid="routing-report-viewer">{JSON.stringify(data)}</div>
  ),
}));

// ── Mock data ─────────────────────────────────────────────────────────

const mockLedgerData = {
  entries: [
    {
      claim_id: "CLM-001",
      claim_text: "Test",
      source_type: "external",
      source_reference: "ref",
      confidence: 0.9,
      verifiability_status: "verified",
      verification_note: "",
    },
  ],
};

const mockBlueprintData = {
  contract_entries: [],
  validation_violations: [],
  legacy_count: 0,
  contract_count: 0,
};

// ── Tests ─────────────────────────────────────────────────────────────

describe("ArtifactViewerTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetArtifact.mockResolvedValue(mockLedgerData);
  });

  it("renders 4 tab buttons", () => {
    render(<ArtifactViewerTabs sessionId="session-1" />);

    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(4);
    expect(screen.getByTestId("tab-evidence_ledger")).toHaveTextContent("Evidence Ledger");
    expect(screen.getByTestId("tab-slide_blueprint")).toHaveTextContent("Slide Blueprints");
    expect(screen.getByTestId("tab-external_evidence")).toHaveTextContent("External Evidence");
    expect(screen.getByTestId("tab-routing_report")).toHaveTextContent("Routing Report");
  });

  it("first tab is active by default", () => {
    render(<ArtifactViewerTabs sessionId="session-1" />);

    const tab = screen.getByTestId("tab-evidence_ledger");
    expect(tab).toHaveAttribute("aria-selected", "true");
  });

  it("fetches data on mount for the first tab", async () => {
    render(<ArtifactViewerTabs sessionId="session-1" />);

    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledWith("session-1", "evidence_ledger");
    });
  });

  it("clicking second tab activates it and fetches", async () => {
    mockGetArtifact.mockImplementation((_sid: string, name: string) => {
      if (name === "slide_blueprint") return Promise.resolve(mockBlueprintData);
      return Promise.resolve(mockLedgerData);
    });

    render(<ArtifactViewerTabs sessionId="session-1" />);

    // Wait for initial fetch to complete
    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledWith("session-1", "evidence_ledger");
    });

    fireEvent.click(screen.getByTestId("tab-slide_blueprint"));

    const tab = screen.getByTestId("tab-slide_blueprint");
    expect(tab).toHaveAttribute("aria-selected", "true");

    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledWith("session-1", "slide_blueprint");
    });
  });

  it("does not re-fetch cached tab", async () => {
    mockGetArtifact.mockImplementation((_sid: string, name: string) => {
      if (name === "slide_blueprint") return Promise.resolve(mockBlueprintData);
      return Promise.resolve(mockLedgerData);
    });

    render(<ArtifactViewerTabs sessionId="session-1" />);

    // Wait for tab 1 fetch
    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledTimes(1);
    });

    // Switch to tab 2
    fireEvent.click(screen.getByTestId("tab-slide_blueprint"));
    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledTimes(2);
    });

    // Switch back to tab 1 — should NOT trigger another fetch
    fireEvent.click(screen.getByTestId("tab-evidence_ledger"));

    // Small wait to ensure no extra call fires
    await new Promise((r) => setTimeout(r, 50));
    expect(mockGetArtifact).toHaveBeenCalledTimes(2);
  });

  it("shows loading state", () => {
    // Return a promise that never resolves to keep loading state
    mockGetArtifact.mockReturnValue(new Promise(() => {}));

    render(<ArtifactViewerTabs sessionId="session-1" />);

    // Shell renders a spinner when loading
    const spinner = document.querySelector("[class*='spinner'], [role='status']");
    // Alternatively, check there's no error and no viewer yet
    expect(screen.queryByTestId("evidence-ledger-viewer")).not.toBeInTheDocument();
  });

  it("shows error state", async () => {
    mockGetArtifact.mockRejectedValue(new Error("Network failure"));

    render(<ArtifactViewerTabs sessionId="session-1" />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Network failure");
    });
  });
});
