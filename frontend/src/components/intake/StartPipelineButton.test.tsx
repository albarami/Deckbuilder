/**
 * StartPipelineButton component tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { StartPipelineButton } from "./StartPipelineButton";
import type { ProposalConfigValues } from "./ProposalConfig";

const mockStart = vi.fn();
const mockPush = vi.fn();

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const messages: Record<string, string> = {
      startPipeline: "Generate Proposal",
      startSourceBook: "Generate Source Book",
      starting: "Starting...",
      startError: "Failed to start pipeline.",
      needInput: "Upload files or paste text to get started.",
    };
    return messages[key] ?? key;
  },
}));

vi.mock("@/hooks/use-pipeline", () => ({
  usePipeline: () => ({
    start: mockStart,
    isStarting: false,
  }),
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const standardConfig: ProposalConfigValues = {
  language: "en",
  proposalMode: "standard",
  sector: "Technology",
  geography: "Saudi Arabia",
};

const sbConfig: ProposalConfigValues = {
  language: "en",
  proposalMode: "source_book_only",
  sector: "Technology",
  geography: "Saudi Arabia",
};

const files = [{
  upload_id: "u1",
  filename: "rfp.pdf",
  size_bytes: 1024,
  content_type: "application/pdf",
  extracted_text_length: 500,
  detected_language: "en" as const,
}];

describe("StartPipelineButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStart.mockResolvedValue("sess-123");
  });

  it("shows 'Generate Proposal' for standard mode", () => {
    render(
      <StartPipelineButton
        uploadedFiles={files}
        pastedText=""
        config={standardConfig}
      />,
    );
    expect(screen.getByTestId("start-pipeline-btn")).toHaveTextContent("Generate Proposal");
  });

  it("shows 'Generate Source Book' for source_book_only mode", () => {
    render(
      <StartPipelineButton
        uploadedFiles={files}
        pastedText=""
        config={sbConfig}
      />,
    );
    expect(screen.getByTestId("start-pipeline-btn")).toHaveTextContent("Generate Source Book");
  });

  it("sends proposal_mode: source_book_only in the start request", async () => {
    render(
      <StartPipelineButton
        uploadedFiles={files}
        pastedText=""
        config={sbConfig}
      />,
    );

    fireEvent.click(screen.getByTestId("start-pipeline-btn"));

    await waitFor(() => {
      expect(mockStart).toHaveBeenCalledWith(
        expect.objectContaining({
          proposal_mode: "source_book_only",
        }),
      );
    });
  });

  it("sends proposal_mode: standard for standard mode", async () => {
    render(
      <StartPipelineButton
        uploadedFiles={files}
        pastedText=""
        config={standardConfig}
      />,
    );

    fireEvent.click(screen.getByTestId("start-pipeline-btn"));

    await waitFor(() => {
      expect(mockStart).toHaveBeenCalledWith(
        expect.objectContaining({
          proposal_mode: "standard",
        }),
      );
    });
  });

  it("is disabled when no files or text provided", () => {
    render(
      <StartPipelineButton
        uploadedFiles={[]}
        pastedText=""
        config={standardConfig}
      />,
    );
    expect(screen.getByTestId("start-pipeline-btn")).toBeDisabled();
  });

  it("navigates to session page after successful start", async () => {
    render(
      <StartPipelineButton
        uploadedFiles={files}
        pastedText=""
        config={standardConfig}
      />,
    );

    fireEvent.click(screen.getByTestId("start-pipeline-btn"));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/pipeline/sess-123");
    });
  });
});
