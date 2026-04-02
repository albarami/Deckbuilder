/**
 * EvidenceLedgerViewer component tests.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EvidenceLedgerViewer } from "./EvidenceLedgerViewer";
import type { EvidenceLedgerData } from "./types";

// ── i18n mock ─────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      "ledger.colClaimId": "Claim ID",
      "ledger.colClaim": "Claim",
      "ledger.colSource": "Source",
      "ledger.colConfidence": "Confidence",
      "ledger.colStatus": "Status",
      "ledger.expand": "Show more",
      "ledger.collapse": "Show less",
      "ledger.status.verified": "Verified",
      "ledger.status.partially_verified": "Partial",
      "ledger.status.unverified": "Unverified",
      "ledger.status.gap": "Gap",
    };
    return map[key] ?? key;
  },
}));

// ── Mock data ─────────────────────────────────────────────────────────

const mockData: EvidenceLedgerData = {
  entries: [
    {
      claim_id: "CLM-001",
      claim_text: "The ministry achieved 95% digitization of core services by 2024.",
      source_type: "external",
      source_reference: "EXT-003: World Bank Digital Government Report 2024",
      confidence: 0.92,
      verifiability_status: "verified",
      verification_note: "Confirmed via World Bank dataset.",
    },
    {
      claim_id: "CLM-002",
      claim_text: "Strategic Gears has delivered 40+ transformation projects across GCC.",
      source_type: "internal",
      source_reference: "SG Portfolio Database",
      confidence: 0.45,
      verifiability_status: "gap",
      verification_note: "Engine 2 proof required.",
    },
    {
      claim_id: "CLM-003",
      claim_text:
        "Agile governance frameworks reduce delivery risk by 30-40% in public sector contexts according to multiple international benchmarks and peer-reviewed studies from leading institutions.",
      source_type: "external",
      source_reference: "EXT-007: McKinsey Public Sector Report",
      confidence: 0.78,
      verifiability_status: "partially_verified",
      verification_note: "Range confirmed, exact figure needs citation.",
    },
  ],
};

// ── Tests ─────────────────────────────────────────────────────────────

describe("EvidenceLedgerViewer", () => {
  it("renders entries with claim IDs", () => {
    render(<EvidenceLedgerViewer data={mockData} />);
    expect(screen.getByText("CLM-001")).toBeInTheDocument();
    expect(screen.getByText("CLM-002")).toBeInTheDocument();
    expect(screen.getByText("CLM-003")).toBeInTheDocument();
  });

  it("renders translated column headers", () => {
    render(<EvidenceLedgerViewer data={mockData} />);
    expect(screen.getByText("Claim ID")).toBeInTheDocument();
    expect(screen.getByText("Claim")).toBeInTheDocument();
    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.getByText("Confidence")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders source_reference as a visible column", () => {
    render(<EvidenceLedgerViewer data={mockData} />);
    expect(screen.getByText("EXT-003: World Bank Digital Government Report 2024")).toBeInTheDocument();
    expect(screen.getByText("SG Portfolio Database")).toBeInTheDocument();
    expect(screen.getByText("EXT-007: McKinsey Public Sector Report")).toBeInTheDocument();
  });

  it("truncates long claim text and shows expand/collapse toggle", () => {
    const longText = "A".repeat(200);
    const data: EvidenceLedgerData = {
      entries: [
        {
          claim_id: "CLM-LONG",
          claim_text: longText,
          source_type: "internal",
          source_reference: "ref",
          confidence: 0.5,
          verifiability_status: "unverified",
          verification_note: "",
        },
      ],
    };

    render(<EvidenceLedgerViewer data={data} />);

    // Shows truncated text
    const truncated = "A".repeat(120) + "\u2026";
    expect(screen.getByText(truncated)).toBeInTheDocument();

    // Has expand button
    const expandBtn = screen.getByText("Show more");
    expect(expandBtn).toBeInTheDocument();

    // Click to expand
    fireEvent.click(expandBtn);
    expect(screen.getByText(longText)).toBeInTheDocument();
    expect(screen.getByText("Show less")).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(screen.getByText("Show less"));
    expect(screen.getByText(truncated)).toBeInTheDocument();
  });

  it("does not show expand button for short claims", () => {
    const data: EvidenceLedgerData = {
      entries: [
        {
          claim_id: "CLM-SHORT",
          claim_text: "Short claim.",
          source_type: "internal",
          source_reference: "ref",
          confidence: 0.9,
          verifiability_status: "verified",
          verification_note: "",
        },
      ],
    };

    render(<EvidenceLedgerViewer data={data} />);
    expect(screen.queryByText("Show more")).not.toBeInTheDocument();
  });

  it("shows confidence percentage", () => {
    const data: EvidenceLedgerData = {
      entries: [
        {
          claim_id: "CLM-PCT",
          claim_text: "Test claim",
          source_type: "internal",
          source_reference: "ref",
          confidence: 0.85,
          verifiability_status: "verified",
          verification_note: "",
        },
      ],
    };

    render(<EvidenceLedgerViewer data={data} />);
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("shows translated status badges", () => {
    const data: EvidenceLedgerData = {
      entries: [
        { claim_id: "V", claim_text: "a", source_type: "internal", source_reference: "r", confidence: 0.9, verifiability_status: "verified", verification_note: "" },
        { claim_id: "P", claim_text: "b", source_type: "internal", source_reference: "r", confidence: 0.7, verifiability_status: "partially_verified", verification_note: "" },
        { claim_id: "U", claim_text: "c", source_type: "internal", source_reference: "r", confidence: 0.5, verifiability_status: "unverified", verification_note: "" },
        { claim_id: "G", claim_text: "d", source_type: "internal", source_reference: "r", confidence: 0.3, verifiability_status: "gap", verification_note: "" },
      ],
    };

    render(<EvidenceLedgerViewer data={data} />);
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("Partial")).toBeInTheDocument();
    expect(screen.getByText("Unverified")).toBeInTheDocument();
    expect(screen.getByText("Gap")).toBeInTheDocument();
  });

  it("sorts by confidence descending", () => {
    const data: EvidenceLedgerData = {
      entries: [
        { claim_id: "CLM-LOW", claim_text: "Low", source_type: "internal", source_reference: "r", confidence: 0.3, verifiability_status: "unverified", verification_note: "" },
        { claim_id: "CLM-HIGH", claim_text: "High", source_type: "internal", source_reference: "r", confidence: 0.9, verifiability_status: "verified", verification_note: "" },
        { claim_id: "CLM-MID", claim_text: "Mid", source_type: "internal", source_reference: "r", confidence: 0.6, verifiability_status: "partially_verified", verification_note: "" },
      ],
    };

    const { container } = render(<EvidenceLedgerViewer data={data} />);
    const claimIds = container.querySelectorAll(".font-mono");
    expect(claimIds[0]?.textContent).toBe("CLM-HIGH");
    expect(claimIds[1]?.textContent).toBe("CLM-MID");
    expect(claimIds[2]?.textContent).toBe("CLM-LOW");
  });

  it("handles empty entries", () => {
    const data: EvidenceLedgerData = { entries: [] };
    const { container } = render(<EvidenceLedgerViewer data={data} />);
    expect(container.firstChild).toBeTruthy();
  });
});
