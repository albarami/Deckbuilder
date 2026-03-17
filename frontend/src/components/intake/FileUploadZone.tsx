/**
 * FileUploadZone — Drag-and-drop file upload for RFP documents.
 *
 * Accepts PDF, DOCX, TXT files. Shows uploaded file chips with remove.
 * Calls the upload API to get upload IDs for pipeline start.
 */

"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { uploadDocuments } from "@/lib/api/upload";
import type { UploadedFileInfo } from "@/lib/types/pipeline";
import { APIError } from "@/lib/types/api";

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
];

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"];

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

export interface FileUploadZoneProps {
  /** Called when uploads succeed — provides list of uploaded file info */
  onFilesUploaded: (files: UploadedFileInfo[]) => void;
  /** Currently uploaded files (controlled from parent) */
  uploadedFiles: UploadedFileInfo[];
  /** Remove a file by upload_id */
  onFileRemoved: (uploadId: string) => void;
  /** Disable during pipeline start */
  disabled?: boolean;
}

export function FileUploadZone({
  onFilesUploaded,
  uploadedFiles,
  onFileRemoved,
  disabled = false,
}: FileUploadZoneProps) {
  const t = useTranslations("intake");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const validateFiles = useCallback(
    (files: File[]): { valid: File[]; errors: string[] } => {
      const valid: File[] = [];
      const errors: string[] = [];

      for (const file of files) {
        const ext = "." + file.name.split(".").pop()?.toLowerCase();
        if (
          !ACCEPTED_TYPES.includes(file.type) &&
          !ACCEPTED_EXTENSIONS.includes(ext)
        ) {
          errors.push(t("unsupportedFileType", { filename: file.name }));
          continue;
        }
        if (file.size > MAX_FILE_SIZE) {
          errors.push(t("exceedsMaxSize", { filename: file.name }));
          continue;
        }
        valid.push(file);
      }

      return { valid, errors };
    },
    [t],
  );

  const handleUpload = useCallback(
    async (rawFiles: FileList | File[]) => {
      const files = Array.from(rawFiles);
      if (files.length === 0) return;

      const { valid, errors } = validateFiles(files);
      if (errors.length > 0) {
        setUploadError(errors.join("; "));
      }
      if (valid.length === 0) return;

      setIsUploading(true);
      setUploadError(null);

      try {
        const response = await uploadDocuments(valid);
        onFilesUploaded(response.uploads);
      } catch (err) {
        if (err instanceof APIError) {
          setUploadError(err.message);
        } else {
          setUploadError(t("uploadFailed"));
        }
      } finally {
        setIsUploading(false);
        // Reset file input
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    },
    [validateFiles, onFilesUploaded, t],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) setIsDragOver(true);
    },
    [disabled],
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (!disabled && e.dataTransfer.files.length > 0) {
        handleUpload(e.dataTransfer.files);
      }
    },
    [disabled, handleUpload],
  );

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        handleUpload(e.target.files);
      }
    },
    [handleUpload],
  );

  const handleZoneClick = useCallback(() => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, [disabled]);

  return (
    <div className="space-y-3">
      <label className="block text-sm font-semibold text-sg-navy dark:text-slate-100">
        {t("uploadFiles")}
      </label>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={t("dragDrop")}
        className={[
          "relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition-colors",
          isDragOver && !disabled
            ? "border-sg-blue bg-sg-blue/5 dark:border-sky-300 dark:bg-sky-400/10"
            : "border-sg-border bg-sg-mist/50 dark:border-slate-800 dark:bg-slate-950/60",
          disabled
            ? "cursor-not-allowed opacity-50"
            : "cursor-pointer hover:border-sg-blue/50 hover:bg-sg-mist dark:hover:border-sky-300/50 dark:hover:bg-slate-900/80",
        ].join(" ")}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleZoneClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleZoneClick();
          }
        }}
      >
        {/* Upload icon */}
        <UploadIcon />

        <p className="mt-3 text-sm font-medium text-sg-slate dark:text-slate-200">
          {isUploading ? t("uploading") : t("dragDrop")}
        </p>
        <p className="mt-1 text-xs text-sg-slate/60 dark:text-slate-400">{t("supportedFormats")}</p>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
          className="sr-only"
          onChange={handleFileInputChange}
          disabled={disabled}
          aria-label={t("uploadFiles")}
        />

        {/* Loading overlay */}
        {isUploading && (
          <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-white/80 dark:bg-slate-950/80">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-sg-blue border-t-transparent" />
          </div>
        )}
      </div>

      {/* Error message */}
      {uploadError && (
        <p className="text-sm text-red-600" role="alert">
          {uploadError}
        </p>
      )}

      {/* Uploaded file chips */}
      {uploadedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid="uploaded-files">
          {uploadedFiles.map((file) => (
            <FileChip
              key={file.upload_id}
              file={file}
              onRemove={() => onFileRemoved(file.upload_id)}
              disabled={disabled}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── FileChip ───────────────────────────────────────────────────────────

function FileChip({
  file,
  onRemove,
  disabled,
}: {
  file: UploadedFileInfo;
  onRemove: () => void;
  disabled: boolean;
}) {
  const ext = file.filename.split(".").pop()?.toUpperCase() ?? "FILE";
  const sizeKb = Math.round(file.size_bytes / 1024);
  const sizeLabel = sizeKb >= 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-sg-border bg-sg-white px-3 py-1.5 text-sm dark:border-slate-800 dark:bg-slate-950">
      <FileTypeIcon ext={ext} />
      <span className="max-w-[160px] truncate font-medium text-sg-navy dark:text-slate-100">
        {file.filename}
      </span>
      <span className="text-xs text-sg-slate/60 dark:text-slate-400">{sizeLabel}</span>
      {!disabled && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="ml-0.5 rounded-full p-0.5 text-sg-slate/40 transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-500/10"
          aria-label={`Remove ${file.filename}`}
        >
          <svg viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
            <path d="M5.28 4.22a.75.75 0 00-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 101.06 1.06L8 9.06l2.72 2.72a.75.75 0 101.06-1.06L9.06 8l2.72-2.72a.75.75 0 00-1.06-1.06L8 6.94 5.28 4.22z" />
          </svg>
        </button>
      )}
    </span>
  );
}

// ── Icons ──────────────────────────────────────────────────────────────

function UploadIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className="h-10 w-10 text-sg-blue/60"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
      />
    </svg>
  );
}

function FileTypeIcon({ ext }: { ext: string }) {
  const colorMap: Record<string, string> = {
    PDF: "text-red-500",
    DOCX: "text-sg-blue",
    TXT: "text-sg-slate",
  };

  return (
    <span
      className={`text-[10px] font-bold ${colorMap[ext] ?? "text-sg-slate"}`}
    >
      {ext}
    </span>
  );
}
