/**
 * RoutingReportViewer component tests.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoutingReportViewer } from "./RoutingReportViewer";
import type { RoutingReportData } from "./types";

// -- i18n mock ----------------------------------------------------------------

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const fn = (key: string) => {
      const map: Record<string, string> = {
        "routing.classificationTitle": "Classification",
        "routing.jurisdiction": "Jurisdiction",
        "routing.sector": "Sector",
        "routing.domain": "Domain",
        "routing.clientType": "Client Type",
        "routing.regulatoryFrame": "Regulatory Frame",
        "routing.confidence": "Routing Confidence",
        "routing.selectedPacks": "Selected Packs",
        "routing.fallbackPacks": "Fallback Packs",
        "routing.warnings": "Routing Warnings",
      };
      return map[key] ?? key;
    };
    return fn;
  },
}));

// -- Mock lucide-react --------------------------------------------------------

vi.mock("lucide-react", () => ({
  AlertTriangle: (props: Record<string, unknown>) => (
    <svg data-testid="alert-triangle-icon" {...props} />
  ),
}));

// -- Mock data ----------------------------------------------------------------

const mockData: RoutingReportData = {
  classification: {
    jurisdiction: "Saudi Arabia",
    sector: "Government",
    domain: "Digital Transformation",
    client_type: "Ministry",
    confidence: 0.91,
    regulatory_frame: "Vision 2030 NTP",
  },
  selected_packs: ["saudi_public_sector", "digital_transformation"],
  fallback_packs_used: ["generic_mena_public_sector"],
  warnings: ["Low keyword match for investment_promotion pack"],
  routing_confidence: 0.82,
};

// -- Tests --------------------------------------------------------------------

describe("RoutingReportViewer", () => {
  it("renders classification fields", () => {
    render(<RoutingReportViewer data={mockData} />);
    expect(screen.getByText("Saudi Arabia")).toBeInTheDocument();
    expect(screen.getByText("Government")).toBeInTheDocument();
    expect(screen.getByText("Digital Transformation")).toBeInTheDocument();
    expect(screen.getByText("Ministry")).toBeInTheDocument();
  });

  it("shows regulatory_frame when present", () => {
    render(<RoutingReportViewer data={mockData} />);
    expect(screen.getByText("Regulatory Frame")).toBeInTheDocument();
    expect(screen.getByText("Vision 2030 NTP")).toBeInTheDocument();
  });

  it("omits regulatory_frame when absent", () => {
    const dataWithout: RoutingReportData = {
      ...mockData,
      classification: {
        jurisdiction: "UAE",
        sector: "Finance",
        domain: "Banking",
        client_type: "Central Bank",
        confidence: 0.85,
      },
    };
    render(<RoutingReportViewer data={dataWithout} />);
    expect(screen.queryByText("Regulatory Frame")).not.toBeInTheDocument();
  });

  it("shows routing confidence percentage", () => {
    render(<RoutingReportViewer data={mockData} />);
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText("Routing Confidence")).toBeInTheDocument();
  });

  it("renders selected packs as badges", () => {
    render(<RoutingReportViewer data={mockData} />);
    expect(screen.getByText("saudi_public_sector")).toBeInTheDocument();
    expect(screen.getByText("digital_transformation")).toBeInTheDocument();
  });

  it("renders fallback packs when present", () => {
    render(<RoutingReportViewer data={mockData} />);
    expect(screen.getByText("Fallback Packs")).toBeInTheDocument();
    expect(
      screen.getByText("generic_mena_public_sector"),
    ).toBeInTheDocument();
  });

  it("does not render fallback section when empty", () => {
    const dataNoFallback: RoutingReportData = {
      ...mockData,
      fallback_packs_used: [],
    };
    render(<RoutingReportViewer data={dataNoFallback} />);
    expect(screen.queryByText("Fallback Packs")).not.toBeInTheDocument();
  });

  it("shows warnings when present", () => {
    render(<RoutingReportViewer data={mockData} />);
    expect(screen.getByText("Routing Warnings")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Low keyword match for investment_promotion pack",
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("alert-triangle-icon")).toBeInTheDocument();
  });

  it("does not render warnings section when empty", () => {
    const dataNoWarnings: RoutingReportData = {
      ...mockData,
      warnings: [],
    };
    const { container } = render(
      <RoutingReportViewer data={dataNoWarnings} />,
    );
    expect(screen.queryByText("Routing Warnings")).not.toBeInTheDocument();
    // No alert triangle icon (warnings section absent)
    expect(
      screen.queryByTestId("alert-triangle-icon"),
    ).not.toBeInTheDocument();
  });
});
