/**
 * PipelineComplete — Success state with export download buttons.
 *
 * Shows when pipeline status is "complete" with outputs ready.
 * Provides download buttons for PPTX and DOCX.
 */

"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { downloadPptx, downloadDocx } from "@/lib/api/export";
import type { PipelineOutputs } from "@/lib/types/pipeline";

export interface PipelineCompleteProps {
  sessionId: string;
  outputs: PipelineOutputs;
}

export function PipelineComplete({
  sessionId,
  outputs,
}: PipelineCompleteProps) {
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
    <Card variant="elevated" className="space-y-4">
      {/* Success header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100">
          <svg
            viewBox="0 0 20 20"
            fill="currentColor"
            className="h-6 w-6 text-emerald-600"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
              clipRule="evenodd"
            />
          </svg>
        </div>
        <div>
          <h3 className="text-lg font-semibold text-sg-navy">{t("title")}</h3>
          <p className="text-sm text-sg-slate/70">
            {t("slideCount", { count: outputs.slide_count })}
          </p>
        </div>
      </div>

      {/* Download buttons */}
      <div className="flex flex-col gap-2 sm:flex-row">
        {outputs.pptx_ready && (
          <Button
            variant="primary"
            size="md"
            loading={downloading === "pptx"}
            disabled={downloading !== null}
            onClick={() => handleDownload("pptx")}
            className="flex-1"
          >
            <DownloadIcon />
            {t("downloadPptx")}
          </Button>
        )}
        {outputs.docx_ready && (
          <Button
            variant="secondary"
            size="md"
            loading={downloading === "docx"}
            disabled={downloading !== null}
            onClick={() => handleDownload("docx")}
            className="flex-1"
          >
            <DownloadIcon />
            {t("downloadDocx")}
          </Button>
        )}
      </div>

      {/* Error */}
      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </Card>
  );
}

function DownloadIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
      <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
    </svg>
  );
}
