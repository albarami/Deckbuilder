/**
 * PipelinePreview component tests.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { PipelinePreview } from "./PipelinePreview";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const messages: Record<string, string> = {
      // Deck mode
      journeyTitle: "What happens after you click Generate Proposal",
      journeySubtitle: "DeckForge follows a report-first workflow.",
      journeySummary: "9 AI agents across 5 review stages.",
      journeyStepsTitle: "Workflow highlights",
      journeyStepsContext: "Parse the RFP brief.",
      journeyStepsSources: "Review the source set.",
      journeyStepsReport: "Approve the research report.",
      journeyStepsSlides: "Review the slide structure.",
      journeyStepsQa: "Validate readiness.",
      journeyGovernanceTitle: "Governance built in",
      journeyGovernanceBody: "No Free Facts.",
      journeyOutputsTitle: "Expected outputs",
      journeyOutputDeck: "Branded presentation deck",
      journeyOutputReport: "Approved research report",
      journeyOutputSources: "Source index",
      journeyOutputGap: "Gap report",
      // Source Book mode
      sbJourneyTitle: "What happens after you click Generate Source Book",
      sbJourneySubtitle: "Proposal-grade Source Book with evidence curation.",
      sbJourneySummary: "3 review stages with expert AI agents.",
      sbJourneyStepsContext: "Parse the RFP brief and confirm context.",
      sbJourneyStepsSources: "Review and approve evidence sources.",
      sbJourneyStepsSourceBook: "Review Source Book, download DOCX.",
      sbJourneyOutputSourceBook: "Source Book (DOCX)",
      sbJourneyOutputEvidenceLedger: "Evidence Ledger",
      sbJourneyOutputBlueprints: "Slide Blueprints",
      sbJourneyOutputRoutingReport: "Routing Report",
    };
    return messages[key] ?? key;
  },
}));

describe("PipelinePreview", () => {
  it("renders deck journey by default", () => {
    render(<PipelinePreview />);
    expect(screen.getByText("What happens after you click Generate Proposal")).toBeInTheDocument();
    expect(screen.getByText("Branded presentation deck")).toBeInTheDocument();
    expect(screen.getByText("Review the slide structure.")).toBeInTheDocument();
  });

  it("renders deck journey for standard mode", () => {
    render(<PipelinePreview proposalMode="standard" />);
    expect(screen.getByText("9 AI agents across 5 review stages.")).toBeInTheDocument();
    expect(screen.getByText("Approved research report")).toBeInTheDocument();
  });

  it("renders Source Book journey for source_book_only mode", () => {
    render(<PipelinePreview proposalMode="source_book_only" />);
    expect(screen.getByText("What happens after you click Generate Source Book")).toBeInTheDocument();
    expect(screen.getByText("3 review stages with expert AI agents.")).toBeInTheDocument();
    expect(screen.getByText("Review Source Book, download DOCX.")).toBeInTheDocument();
  });

  it("shows Source Book outputs in source_book_only mode", () => {
    render(<PipelinePreview proposalMode="source_book_only" />);
    expect(screen.getByText("Source Book (DOCX)")).toBeInTheDocument();
    expect(screen.getByText("Evidence Ledger")).toBeInTheDocument();
    expect(screen.getByText("Slide Blueprints")).toBeInTheDocument();
    expect(screen.getByText("Routing Report")).toBeInTheDocument();
  });

  it("does not show deck outputs in source_book_only mode", () => {
    render(<PipelinePreview proposalMode="source_book_only" />);
    expect(screen.queryByText("Branded presentation deck")).not.toBeInTheDocument();
    expect(screen.queryByText("Gap report")).not.toBeInTheDocument();
  });

  it("does not show SB steps in standard mode", () => {
    render(<PipelinePreview proposalMode="standard" />);
    expect(screen.queryByText("Review Source Book, download DOCX.")).not.toBeInTheDocument();
  });
});
