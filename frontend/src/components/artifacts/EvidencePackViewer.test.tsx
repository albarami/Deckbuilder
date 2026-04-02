/**
 * EvidencePackViewer component tests.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EvidencePackViewer } from "./EvidencePackViewer";
import type { EvidencePackData } from "./types";

// -- i18n mock ----------------------------------------------------------------

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const fn = (key: string, params?: Record<string, unknown>) => {
      const map: Record<string, string> = {
        "pack.coverageTitle": "Coverage Assessment",
        "pack.tier.primary": "Primary",
        "pack.tier.secondary": "Secondary",
        "pack.tier.analogical": "Analogical",
        "pack.relevance": "Relevance",
        "pack.theme": "RFP Theme",
        "pack.keyFindings": "Key Findings",
        "pack.howToUse": "Proposal Usage",
        "pack.showLessFindings": "Show fewer",
      };
      if (key === "pack.showMoreFindings" && params?.count) {
        return `Show all ${params.count} findings`;
      }
      return map[key] ?? key;
    };
    return fn;
  },
}));

// -- Mock data ----------------------------------------------------------------

const mockSources: EvidencePackData["sources"] = [
  {
    source_id: "SRC-001",
    provider: "World Bank",
    title: "Digital Government Report",
    authors: ["Jane Doe"],
    source_type: "report",
    year: 2023,
    url: "https://example.com/report",
    relevance_score: 0.87,
    mapped_rfp_theme: "Digital Transformation",
    key_findings: [
      "Finding A",
      "Finding B",
      "Finding C",
      "Finding D",
      "Finding E",
    ],
    evidence_tier: "primary",
    evidence_class: "quantitative",
    how_to_use_in_proposal: "Cite as primary benchmark.",
  },
  {
    source_id: "SRC-002",
    provider: "McKinsey",
    title: "GCC Transformation",
    authors: ["John Smith"],
    source_type: "article",
    year: 2022,
    url: "",
    relevance_score: 0.65,
    mapped_rfp_theme: "Strategy",
    key_findings: ["Finding X", "Finding Y"],
    evidence_tier: "secondary",
    evidence_class: "qualitative",
  },
  {
    source_id: "SRC-003",
    provider: "Deloitte",
    title: "Innovation Index",
    authors: [],
    source_type: "index",
    year: 2024,
    url: "https://example.com/index",
    relevance_score: 0.92,
    mapped_rfp_theme: "Innovation",
    key_findings: ["Finding P"],
    evidence_tier: "analogical",
    evidence_class: "mixed",
  },
];

const fullData: EvidencePackData = {
  sources: mockSources,
  search_queries_used: ["digital government GCC"],
  coverage_assessment: "Good coverage of digital transformation themes.",
};

// -- Tests --------------------------------------------------------------------

describe("EvidencePackViewer", () => {
  it("renders coverage assessment", () => {
    render(<EvidencePackViewer data={fullData} />);
    expect(
      screen.getByText("Good coverage of digital transformation themes."),
    ).toBeInTheDocument();
  });

  it("renders source cards with title and year", () => {
    render(<EvidencePackViewer data={fullData} />);
    // Title is in a <p> with class font-bold; textContent includes " (year)"
    const titlePs = document.querySelectorAll("p.font-bold");
    const titles = Array.from(titlePs).map((p) => p.textContent);
    expect(titles).toContain("Digital Government Report (2023)");
    expect(titles).toContain("GCC Transformation (2022)");
  });

  it("shows provider and tier badges", () => {
    render(<EvidencePackViewer data={fullData} />);
    expect(screen.getByText("World Bank")).toBeInTheDocument();
    expect(screen.getByText("Primary")).toBeInTheDocument();
    expect(screen.getByText("McKinsey")).toBeInTheDocument();
    expect(screen.getByText("Secondary")).toBeInTheDocument();
    expect(screen.getByText("Deloitte")).toBeInTheDocument();
    expect(screen.getByText("Analogical")).toBeInTheDocument();
  });

  it("shows relevance percentage", () => {
    render(<EvidencePackViewer data={fullData} />);
    expect(screen.getByText("87%")).toBeInTheDocument();
  });

  it("shows theme tag", () => {
    render(<EvidencePackViewer data={fullData} />);
    expect(screen.getByText("Digital Transformation")).toBeInTheDocument();
    expect(screen.getByText("Strategy")).toBeInTheDocument();
    expect(screen.getByText("Innovation")).toBeInTheDocument();
  });

  it("collapses key findings and expands on click", () => {
    render(<EvidencePackViewer data={fullData} />);

    // First 3 visible for SRC-001 which has 5 findings
    expect(screen.getByText("Finding A")).toBeInTheDocument();
    expect(screen.getByText("Finding B")).toBeInTheDocument();
    expect(screen.getByText("Finding C")).toBeInTheDocument();
    // 4th and 5th hidden
    expect(screen.queryByText("Finding D")).not.toBeInTheDocument();
    expect(screen.queryByText("Finding E")).not.toBeInTheDocument();

    // Toggle button
    const showMore = screen.getByText("Show all 5 findings");
    expect(showMore).toBeInTheDocument();

    fireEvent.click(showMore);

    // Now all visible
    expect(screen.getByText("Finding D")).toBeInTheDocument();
    expect(screen.getByText("Finding E")).toBeInTheDocument();
    expect(screen.getByText("Show fewer")).toBeInTheDocument();

    // Collapse again
    fireEvent.click(screen.getByText("Show fewer"));
    expect(screen.queryByText("Finding D")).not.toBeInTheDocument();
  });

  it("sorts by relevance descending", () => {
    const { container } = render(<EvidencePackViewer data={fullData} />);
    // Cards are rendered as direct children of the space-y-4 wrapper,
    // skipping the first child (coverage assessment div).
    // Select all relevance percentage spans (one per source card)
    const pctSpans = container.querySelectorAll(".w-9");
    const percentages = Array.from(pctSpans).map((s) => s.textContent?.trim());
    // Expect order: SRC-003 (0.92), SRC-001 (0.87), SRC-002 (0.65)
    expect(percentages).toEqual(["92%", "87%", "65%"]);
  });

  it("handles empty sources", () => {
    const data: EvidencePackData = {
      sources: [],
      search_queries_used: [],
      coverage_assessment: "",
    };
    const { container } = render(<EvidencePackViewer data={data} />);
    expect(container.innerHTML).toBe("");
  });

  it("links title when url present", () => {
    render(<EvidencePackViewer data={fullData} />);
    // SRC-001 has a url — title is an <a> tag
    const link = screen.getByRole("link", {
      name: "Digital Government Report",
    });
    expect(link).toHaveAttribute("href", "https://example.com/report");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");

    // SRC-002 has no url — title should NOT be a link
    const titlePs = document.querySelectorAll("p.font-bold");
    const gccP = Array.from(titlePs).find((p) =>
      p.textContent?.includes("GCC Transformation"),
    );
    expect(gccP).toBeTruthy();
    expect(gccP!.querySelector("a")).toBeNull();
  });
});
