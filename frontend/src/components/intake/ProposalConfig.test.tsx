/**
 * ProposalConfig component tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProposalConfig, isConfigValid, type ProposalConfigValues } from "./ProposalConfig";

// ── Mocks ──────────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const messages: Record<string, string> = {
      configuration: "Proposal Configuration",
      language: "Language",
      proposalMode: "Proposal Mode",
      sector: "Sector",
      geography: "Geography",
      selectSector: "Select sector...",
      selectGeography: "Select geography...",
      "config.languageEn": "English",
      "config.languageAr": "Arabic",
      "config.modeLite": "Lite",
      "config.modeStandard": "Standard",
      "config.modeFull": "Full",
    };
    return messages[key] ?? key;
  },
}));

// ── Helpers ────────────────────────────────────────────────────────────

const defaultConfig: ProposalConfigValues = {
  language: "en",
  proposalMode: "standard",
  sector: "",
  geography: "",
};

// ── Tests ──────────────────────────────────────────────────────────────

describe("ProposalConfig", () => {
  let onChange: (values: ProposalConfigValues) => void;

  beforeEach(() => {
    onChange = vi.fn();
  });

  it("renders all config fields", () => {
    render(
      <ProposalConfig values={defaultConfig} onChange={onChange} />,
    );
    expect(screen.getByText("Proposal Configuration")).toBeInTheDocument();
    expect(screen.getByLabelText("Language")).toBeInTheDocument();
    expect(screen.getByLabelText("Proposal Mode")).toBeInTheDocument();
    expect(screen.getByLabelText("Sector")).toBeInTheDocument();
    expect(screen.getByLabelText("Geography")).toBeInTheDocument();
  });

  it("calls onChange when language changes", () => {
    render(
      <ProposalConfig values={defaultConfig} onChange={onChange} />,
    );
    fireEvent.change(screen.getByLabelText("Language"), {
      target: { value: "ar" },
    });
    expect(onChange).toHaveBeenCalledWith({
      ...defaultConfig,
      language: "ar",
    });
  });

  it("calls onChange when sector changes", () => {
    render(
      <ProposalConfig values={defaultConfig} onChange={onChange} />,
    );
    fireEvent.change(screen.getByLabelText("Sector"), {
      target: { value: "Technology" },
    });
    expect(onChange).toHaveBeenCalledWith({
      ...defaultConfig,
      sector: "Technology",
    });
  });

  it("calls onChange when geography changes", () => {
    render(
      <ProposalConfig values={defaultConfig} onChange={onChange} />,
    );
    fireEvent.change(screen.getByLabelText("Geography"), {
      target: { value: "Saudi Arabia" },
    });
    expect(onChange).toHaveBeenCalledWith({
      ...defaultConfig,
      geography: "Saudi Arabia",
    });
  });

  it("disables all fields when disabled", () => {
    render(
      <ProposalConfig values={defaultConfig} onChange={onChange} disabled />,
    );
    expect(screen.getByLabelText("Language")).toBeDisabled();
    expect(screen.getByLabelText("Proposal Mode")).toBeDisabled();
    expect(screen.getByLabelText("Sector")).toBeDisabled();
    expect(screen.getByLabelText("Geography")).toBeDisabled();
  });

  it("renders mode options", () => {
    render(
      <ProposalConfig values={defaultConfig} onChange={onChange} />,
    );
    const modeSelect = screen.getByLabelText("Proposal Mode");
    expect(modeSelect).toHaveValue("standard");
  });
});

describe("isConfigValid", () => {
  it("returns false when sector is empty", () => {
    expect(
      isConfigValid({
        language: "en",
        proposalMode: "standard",
        sector: "",
        geography: "Saudi Arabia",
      }),
    ).toBe(false);
  });

  it("returns false when geography is empty", () => {
    expect(
      isConfigValid({
        language: "en",
        proposalMode: "standard",
        sector: "Technology",
        geography: "",
      }),
    ).toBe(false);
  });

  it("returns true when all fields are filled", () => {
    expect(
      isConfigValid({
        language: "en",
        proposalMode: "standard",
        sector: "Technology",
        geography: "Saudi Arabia",
      }),
    ).toBe(true);
  });
});
