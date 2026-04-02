/**
 * BlueprintViewer component tests.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { BlueprintViewer } from "./BlueprintViewer";
import type { BlueprintData } from "./types";

// ── i18n mock ─────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const map: Record<string, string> = {
      "blueprint.violationsTitle": "Validation Warnings",
      "blueprint.ownership.house": "House",
      "blueprint.ownership.dynamic": "Dynamic",
      "blueprint.ownership.hybrid": "Hybrid",
      "blueprint.slideTitle": "Slide Title",
      "blueprint.keyMessage": "Key Message",
      "blueprint.bulletPoints": "Content Points",
      "blueprint.evidenceRefs": "Evidence References",
      "blueprint.visualGuidance": "Visual Guidance",
    };

    const fn = (key: string, params?: Record<string, unknown>) => {
      if (key === "blueprint.stats") {
        return `${params?.contract} contract entries from ${params?.legacy} legacy blueprints`;
      }
      return map[key] ?? key;
    };
    return fn;
  },
}));

// ── lucide-react mock ────────────────────────────────────────────────

vi.mock("lucide-react", () => ({
  AlertTriangle: (props: Record<string, unknown>) => <svg data-testid="alert-triangle-icon" {...props} />,
}));

// ── Mock data ────────────────────────────────────────────────────────

const mockData: BlueprintData = {
  contract_entries: [
    {
      section_id: "executive_summary",
      section_name: "Executive Summary",
      ownership: "house",
      slide_title: "Mission & Vision",
      key_message: "Transforming government services through digital innovation",
      bullet_points: ["Digital-first strategy", "Citizen experience focus"],
      evidence_ids: ["EXT-001", "EXT-003"],
      visual_guidance: "Use ministry branding colors",
    },
    {
      section_id: "executive_summary",
      section_name: "Executive Summary",
      ownership: "dynamic",
      slide_title: "Project Scope",
      key_message: null,
      bullet_points: ["Phase 1: Assessment", "Phase 2: Design"],
      evidence_ids: [],
      visual_guidance: null,
    },
    {
      section_id: "methodology",
      section_name: "Methodology",
      ownership: "hybrid",
      slide_title: "Delivery Framework",
      key_message: "Agile governance with waterfall milestones",
      bullet_points: ["Sprint cycles", "Gate reviews"],
      evidence_ids: ["EXT-007"],
      visual_guidance: "Timeline diagram preferred",
    },
  ],
  validation_violations: ["Missing evidence for slide 3", "Duplicate section_id detected"],
  legacy_count: 12,
  contract_count: 3,
};

// ── Tests ────────────────────────────────────────────────────────────

describe("BlueprintViewer", () => {
  it("renders section groups with headers", () => {
    render(<BlueprintViewer data={mockData} />);
    expect(screen.getByText("Executive Summary")).toBeInTheDocument();
    expect(screen.getByText("Methodology")).toBeInTheDocument();
  });

  it("shows ownership badges", () => {
    render(<BlueprintViewer data={mockData} />);
    expect(screen.getByText("House")).toBeInTheDocument();
    expect(screen.getByText("Dynamic")).toBeInTheDocument();
    expect(screen.getByText("Hybrid")).toBeInTheDocument();
  });

  it("renders entry content — slide_title, key_message, bullet_points, evidence_ids", () => {
    render(<BlueprintViewer data={mockData} />);

    // slide titles
    expect(screen.getByText("Mission & Vision")).toBeInTheDocument();
    expect(screen.getByText("Project Scope")).toBeInTheDocument();
    expect(screen.getByText("Delivery Framework")).toBeInTheDocument();

    // key messages
    expect(screen.getByText("Transforming government services through digital innovation")).toBeInTheDocument();
    expect(screen.getByText("Agile governance with waterfall milestones")).toBeInTheDocument();

    // bullet points
    expect(screen.getByText("Digital-first strategy")).toBeInTheDocument();
    expect(screen.getByText("Phase 1: Assessment")).toBeInTheDocument();
    expect(screen.getByText("Sprint cycles")).toBeInTheDocument();

    // evidence ids
    expect(screen.getByText("EXT-001")).toBeInTheDocument();
    expect(screen.getByText("EXT-003")).toBeInTheDocument();
    expect(screen.getByText("EXT-007")).toBeInTheDocument();
  });

  it("shows validation violations banner", () => {
    render(<BlueprintViewer data={mockData} />);
    expect(screen.getByText("Validation Warnings")).toBeInTheDocument();
    expect(screen.getByText("Missing evidence for slide 3")).toBeInTheDocument();
    expect(screen.getByText("Duplicate section_id detected")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("does not show banner when violations are empty", () => {
    const noViolations: BlueprintData = {
      ...mockData,
      validation_violations: [],
    };
    render(<BlueprintViewer data={noViolations} />);
    expect(screen.queryByText("Validation Warnings")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("groups entries by section_id", () => {
    const { container } = render(<BlueprintViewer data={mockData} />);
    const sections = container.querySelectorAll("section");
    expect(sections).toHaveLength(2);

    // First section should contain 2 entry cards
    const firstSectionCards = sections[0].querySelectorAll(".rounded-lg.border");
    expect(firstSectionCards).toHaveLength(2);

    // Second section should contain 1 entry card
    const secondSectionCards = sections[1].querySelectorAll(".rounded-lg.border");
    expect(secondSectionCards).toHaveLength(1);
  });

  it("renders stats line with contract_count and legacy_count", () => {
    render(<BlueprintViewer data={mockData} />);
    expect(screen.getByText("3 contract entries from 12 legacy blueprints")).toBeInTheDocument();
  });
});
