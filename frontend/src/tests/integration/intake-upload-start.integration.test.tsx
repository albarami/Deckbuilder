import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import NewProposalPage from "@/app/[locale]/new/page";

const mockUploadDocuments = vi.fn();
const mockStart = vi.fn();
const mockPush = vi.fn();

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const map: Record<string, string> = {
      title: "New Proposal",
      subtitle: "Start from RFP inputs",
      uploadFiles: "Upload files",
      dragDrop: "Drag and drop files here",
      supportedFormats: "PDF, DOCX, TXT",
      uploading: "Uploading...",
      or: "or",
      orPasteText: "Or paste text",
      pasteHere: "Paste text here",
      charCount: "count",
      configuration: "Configuration",
      language: "Language",
      proposalMode: "Proposal mode",
      sector: "Sector",
      geography: "Geography",
      selectSector: "Select sector",
      selectGeography: "Select geography",
      "config.languageEn": "English",
      "config.languageAr": "Arabic",
      "config.modeLite": "Lite",
      "config.modeStandard": "Standard",
      "config.modeFull": "Full",
      startPipeline: "Start Pipeline",
      startSourceBook: "Generate Source Book",
      starting: "Starting...",
      needInput: "Need input",
      startError: "Start failed",
      "modeSelector.title": "What would you like to generate?",
      "modeSelector.deckTitle": "Full Proposal Deck",
      "modeSelector.deckDescription": "Complete proposal.",
      "modeSelector.sourceBookTitle": "Source Book Only",
      "modeSelector.sourceBookDescription": "Proposal intelligence document.",
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
vi.mock("@/lib/api/upload", () => ({
  uploadDocuments: (...args: unknown[]) => mockUploadDocuments(...args),
}));
vi.mock("@/stores/pipeline-store", () => ({
  usePipelineStore: (selector: (s: { isStarting: boolean }) => unknown) =>
    selector({ isStarting: false }),
}));
vi.mock("@/components/intake/PipelinePreview", () => ({
  PipelinePreview: () => null,
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: (...args: unknown[]) => mockPush(...args) }),
}));

describe("integration: intake upload and start flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUploadDocuments.mockResolvedValue({
      uploads: [
        {
          upload_id: "up-1",
          filename: "RFP.pdf",
          size_bytes: 1500,
          content_type: "application/pdf",
          extracted_text_length: 2500,
          detected_language: "en",
        },
      ],
    });
    mockStart.mockResolvedValue("session-100");
  });

  it("uses real intake surface: upload + optional paste + start composition", async () => {
    const { container } = render(<NewProposalPage />);
    const fileInput = container.querySelector("input[type='file']") as HTMLInputElement;
    expect(fileInput).toBeTruthy();
    const file = new File(["rfp content"], "RFP.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(mockUploadDocuments).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("uploaded-files")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Or paste text"), {
      target: { value: "  supplemental context from intake form  " },
    });
    fireEvent.change(container.querySelector("#config-sector") as HTMLSelectElement, {
      target: { value: "Government" },
    });
    fireEvent.change(container.querySelector("#config-geography") as HTMLSelectElement, {
      target: { value: "Saudi Arabia" },
    });
    fireEvent.click(screen.getByTestId("start-pipeline-btn"));

    await waitFor(() => expect(mockStart).toHaveBeenCalledTimes(1));
    expect(mockStart).toHaveBeenCalledWith({
      documents: [
        { upload_id: "up-1", filename: "RFP.pdf" },
      ],
      text_input: "supplemental context from intake form",
      language: "en",
      proposal_mode: "standard",
      sector: "Government",
      geography: "Saudi Arabia",
      renderer_mode: "template_v2",
    });
    expect(mockPush).toHaveBeenCalledWith("/pipeline/session-100");
  });

  it("selects Source Book mode and sends proposal_mode: source_book_only", async () => {
    const { container } = render(<NewProposalPage />);

    // Upload file
    const fileInput = container.querySelector("input[type='file']") as HTMLInputElement;
    const file = new File(["rfp content"], "RFP.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => expect(mockUploadDocuments).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("uploaded-files")).toBeInTheDocument());

    // Select Source Book mode
    fireEvent.click(screen.getByTestId("mode-card-source_book_only"));

    // Fill config — mode dropdown should be hidden, so only sector/geography
    fireEvent.change(container.querySelector("#config-sector") as HTMLSelectElement, {
      target: { value: "Government" },
    });
    fireEvent.change(container.querySelector("#config-geography") as HTMLSelectElement, {
      target: { value: "Saudi Arabia" },
    });

    // Button should say "Generate Source Book"
    expect(screen.getByTestId("start-pipeline-btn")).toHaveTextContent("Generate Source Book");

    // Start
    fireEvent.click(screen.getByTestId("start-pipeline-btn"));

    await waitFor(() => expect(mockStart).toHaveBeenCalledTimes(1));
    expect(mockStart).toHaveBeenCalledWith({
      documents: [
        { upload_id: "up-1", filename: "RFP.pdf" },
      ],
      text_input: undefined,
      language: "en",
      proposal_mode: "source_book_only",
      sector: "Government",
      geography: "Saudi Arabia",
      renderer_mode: "template_v2",
    });
    expect(mockPush).toHaveBeenCalledWith("/pipeline/session-100");
  });
});
