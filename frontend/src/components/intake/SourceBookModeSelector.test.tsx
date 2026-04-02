/**
 * SourceBookModeSelector component tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SourceBookModeSelector } from "./SourceBookModeSelector";
import type { ProposalMode } from "@/lib/types/pipeline";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const messages: Record<string, string> = {
      "modeSelector.title": "What would you like to generate?",
      "modeSelector.deckTitle": "Full Proposal Deck",
      "modeSelector.deckDescription": "Complete proposal with research report, branded slides, and QA review.",
      "modeSelector.sourceBookTitle": "Source Book Only",
      "modeSelector.sourceBookDescription": "Proposal intelligence document with evidence, blueprints, and routing analysis.",
    };
    return messages[key] ?? key;
  },
}));

describe("SourceBookModeSelector", () => {
  let onChange: ReturnType<typeof vi.fn<(mode: ProposalMode) => void>>;

  beforeEach(() => {
    onChange = vi.fn<(mode: ProposalMode) => void>();
  });

  it("renders both mode cards", () => {
    render(
      <SourceBookModeSelector value="standard" onChange={onChange} />,
    );
    expect(screen.getByText("What would you like to generate?")).toBeInTheDocument();
    expect(screen.getByText("Full Proposal Deck")).toBeInTheDocument();
    expect(screen.getByText("Source Book Only")).toBeInTheDocument();
  });

  it("marks the selected card with aria-pressed", () => {
    render(
      <SourceBookModeSelector value="standard" onChange={onChange} />,
    );
    const deckCard = screen.getByTestId("mode-card-standard");
    const sbCard = screen.getByTestId("mode-card-source_book_only");

    expect(deckCard).toHaveAttribute("aria-pressed", "true");
    expect(sbCard).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onChange with source_book_only when SB card is clicked", () => {
    render(
      <SourceBookModeSelector value="standard" onChange={onChange} />,
    );
    fireEvent.click(screen.getByTestId("mode-card-source_book_only"));
    expect(onChange).toHaveBeenCalledWith("source_book_only");
  });

  it("calls onChange with standard when deck card is clicked", () => {
    render(
      <SourceBookModeSelector value="source_book_only" onChange={onChange} />,
    );
    fireEvent.click(screen.getByTestId("mode-card-standard"));
    expect(onChange).toHaveBeenCalledWith("standard");
  });

  it("marks SB card as selected when value is source_book_only", () => {
    render(
      <SourceBookModeSelector value="source_book_only" onChange={onChange} />,
    );
    const sbCard = screen.getByTestId("mode-card-source_book_only");
    const deckCard = screen.getByTestId("mode-card-standard");

    expect(sbCard).toHaveAttribute("aria-pressed", "true");
    expect(deckCard).toHaveAttribute("aria-pressed", "false");
  });

  it("disables both cards when disabled", () => {
    render(
      <SourceBookModeSelector value="standard" onChange={onChange} disabled />,
    );
    expect(screen.getByTestId("mode-card-standard")).toBeDisabled();
    expect(screen.getByTestId("mode-card-source_book_only")).toBeDisabled();
  });

  it("treats lite mode as deck-selected (deck card highlighted)", () => {
    render(
      <SourceBookModeSelector value="lite" onChange={onChange} />,
    );
    const deckCard = screen.getByTestId("mode-card-standard");
    const sbCard = screen.getByTestId("mode-card-source_book_only");

    expect(deckCard).toHaveAttribute("aria-pressed", "true");
    expect(sbCard).toHaveAttribute("aria-pressed", "false");
  });

  it("treats full mode as deck-selected (deck card highlighted)", () => {
    render(
      <SourceBookModeSelector value="full" onChange={onChange} />,
    );
    const deckCard = screen.getByTestId("mode-card-standard");
    const sbCard = screen.getByTestId("mode-card-source_book_only");

    expect(deckCard).toHaveAttribute("aria-pressed", "true");
    expect(sbCard).toHaveAttribute("aria-pressed", "false");
  });
});
