/**
 * SlideExportBar — Download PPTX/DOCX bar for the slide browser page.
 *
 * Compact bar with download buttons for completed pipeline outputs.
 * Reuses the export API module.
 */

"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { downloadPptx, downloadDocx } from "@/lib/api/export";

export interface SlideExportBarProps {
  /** Pipeline session ID */
  sessionId: string;
  /** Whether PPTX is ready */
  pptxReady: boolean;
  /** Whether DOCX is ready */
  docxReady: boolean;
  /** Total slide count */
  slideCount: number;
  /** Optional CSS class */
  className?: string;
}

export function SlideExportBar({
  sessionId,
  pptxReady,
  docxReady,
  slideCount,
  className = "",
}: SlideExportBarProps) {
  const t = useTranslations("export");
  const [downloading, setDownloading] = useState<"pptx" | "docx" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = useCallback(
    async (format: "pptx" | "docx") => {
      setDownloading(format);
      setError(null);
      try {
        if (format === "pptx") {
          await downloadPptx(sessionId);
        } else {
          await downloadDocx(sessionId);
        }
      } catch {
        setError(t("downloadError"));
      } finally {
        setDownloading(null);
      }
    },
    [sessionId, t],
  );

  return (
    <div
      className={`flex flex-wrap items-center gap-3 rounded-lg border border-sg-border bg-white p-3 ${className}`}
      data-testid="slide-export-bar"
    >
      {/* Slide count */}
      <p className="flex-1 text-sm text-sg-slate/70">
        {t("slideCount", { count: slideCount })}
      </p>

      {/* Download buttons */}
      <div className="flex gap-2">
        {pptxReady && (
          <Button
            variant="primary"
            size="sm"
            loading={downloading === "pptx"}
            disabled={downloading !== null}
            onClick={() => handleDownload("pptx")}
          >
            <DownloadIcon />
            {t("downloadPptx")}
          </Button>
        )}
        {docxReady && (
          <Button
            variant="secondary"
            size="sm"
            loading={downloading === "docx"}
            disabled={downloading !== null}
            onClick={() => handleDownload("docx")}
          >
            <DownloadIcon />
            {t("downloadDocx")}
          </Button>
        )}
      </div>

      {/* Error */}
      {error && (
        <p className="w-full text-xs text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
      <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
      <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
    </svg>
  );
}
