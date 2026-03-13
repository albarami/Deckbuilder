/**
 * FileUploadZone component tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FileUploadZone, type FileUploadZoneProps } from "./FileUploadZone";
import type { UploadedFileInfo } from "@/lib/types/pipeline";

// ── Mocks ──────────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const messages: Record<string, string> = {
      uploadFiles: "Upload RFP Documents",
      dragDrop: "Drag and drop files here, or click to browse",
      supportedFormats: "PDF, DOCX, TXT — max 50MB per file",
      uploading: "Uploading...",
    };
    return messages[key] ?? key;
  },
}));

const mockUploadDocuments = vi.fn();
vi.mock("@/lib/api/upload", () => ({
  uploadDocuments: (...args: unknown[]) => mockUploadDocuments(...args),
}));

vi.mock("@/lib/types/api", () => ({
  APIError: class APIError extends Error {
    code: string;
    status: number;
    constructor(message: string, code: string, status: number) {
      super(message);
      this.code = code;
      this.status = status;
    }
  },
}));

// ── Helpers ────────────────────────────────────────────────────────────

const mockFile: UploadedFileInfo = {
  upload_id: "uuid-1",
  filename: "test.pdf",
  size_bytes: 1024,
  content_type: "application/pdf",
  extracted_text_length: 500,
  detected_language: "en",
};

function renderUploadZone(overrides: Partial<FileUploadZoneProps> = {}) {
  const defaultProps: FileUploadZoneProps = {
    onFilesUploaded: vi.fn(),
    uploadedFiles: [],
    onFileRemoved: vi.fn(),
    disabled: false,
    ...overrides,
  };
  return render(<FileUploadZone {...defaultProps} />);
}

// ── Tests ──────────────────────────────────────────────────────────────

describe("FileUploadZone", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders upload zone with label and instructions", () => {
    renderUploadZone();
    expect(screen.getByText("Upload RFP Documents")).toBeInTheDocument();
    expect(
      screen.getByText("Drag and drop files here, or click to browse"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("PDF, DOCX, TXT — max 50MB per file"),
    ).toBeInTheDocument();
  });

  it("renders file chips for uploaded files", () => {
    renderUploadZone({ uploadedFiles: [mockFile] });
    expect(screen.getByText("test.pdf")).toBeInTheDocument();
    expect(screen.getByText("1 KB")).toBeInTheDocument();
  });

  it("calls onFileRemoved when remove button clicked", () => {
    const onFileRemoved = vi.fn();
    renderUploadZone({ uploadedFiles: [mockFile], onFileRemoved });
    const removeBtn = screen.getByLabelText("Remove test.pdf");
    fireEvent.click(removeBtn);
    expect(onFileRemoved).toHaveBeenCalledWith("uuid-1");
  });

  it("does not show remove button when disabled", () => {
    renderUploadZone({ uploadedFiles: [mockFile], disabled: true });
    expect(screen.queryByLabelText("Remove test.pdf")).not.toBeInTheDocument();
  });

  it("uploads files on file input change", async () => {
    const onFilesUploaded = vi.fn();
    mockUploadDocuments.mockResolvedValueOnce({
      uploads: [mockFile],
    });

    renderUploadZone({ onFilesUploaded });

    const fileInput = screen.getByLabelText(
      "Upload RFP Documents",
      { selector: "input" },
    );

    const file = new File(["content"], "test.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(mockUploadDocuments).toHaveBeenCalledWith([file]);
      expect(onFilesUploaded).toHaveBeenCalledWith([mockFile]);
    });
  });

  it("shows error for unsupported file type", async () => {
    renderUploadZone();

    const fileInput = screen.getByLabelText(
      "Upload RFP Documents",
      { selector: "input" },
    );

    const file = new File(["content"], "test.exe", {
      type: "application/x-msdownload",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "test.exe: unsupported file type",
      );
    });
  });

  it("has accessible drop zone", () => {
    renderUploadZone();
    const dropZone = screen.getByRole("button", {
      name: "Drag and drop files here, or click to browse",
    });
    expect(dropZone).toBeInTheDocument();
  });
});
