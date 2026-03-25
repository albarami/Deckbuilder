import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StartPipelineButton } from "@/components/intake/StartPipelineButton";

const mockStart = vi.fn();
const mockPush = vi.fn();

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      startPipeline: "Start Pipeline",
      starting: "Starting...",
      needInput: "Need input",
      startError: "Start failed",
    };
    return map[key] ?? key;
  },
}));

vi.mock("@/hooks/use-pipeline", () => ({
  usePipeline: () => ({
    start: (...args: unknown[]) => mockStart(...args),
    isStarting: false,
  }),
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: (...args: unknown[]) => mockPush(...args) }),
}));

describe("integration: intake upload and start flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStart.mockResolvedValue("session-100");
  });

  it("submits upload + optional paste in start payload and routes to session", async () => {
    render(
      <StartPipelineButton
        uploadedFiles={[
          { upload_id: "up-1", filename: "RFP.pdf", size_bytes: 1500 },
          { upload_id: "up-2", filename: "Annex.docx", size_bytes: 2800 },
        ]}
        pastedText={"  supplemental context from intake form  "}
        config={{
          language: "en",
          proposalMode: "standard",
          sector: "Public Sector",
          geography: "KSA",
        }}
      />,
    );

    fireEvent.click(screen.getByTestId("start-pipeline-btn"));

    await waitFor(() => expect(mockStart).toHaveBeenCalledTimes(1));
    expect(mockStart).toHaveBeenCalledWith({
      documents: [
        { upload_id: "up-1", filename: "RFP.pdf" },
        { upload_id: "up-2", filename: "Annex.docx" },
      ],
      text_input: "supplemental context from intake form",
      language: "en",
      proposal_mode: "standard",
      sector: "Public Sector",
      geography: "KSA",
      renderer_mode: "template_v2",
    });
    expect(mockPush).toHaveBeenCalledWith("/pipeline/session-100");
  });
});
