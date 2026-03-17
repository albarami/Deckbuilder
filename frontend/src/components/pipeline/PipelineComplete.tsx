/**
 * PipelineComplete — Success state with export download buttons.
 *
 * Shows when pipeline status is "complete" with outputs ready.
 * Provides download buttons for PPTX and DOCX.
 */

"use client";

import { useCallback, useState } from "react";
import { CheckCircle2, Download, FileStack, Presentation } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Link } from "@/i18n/routing";
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
    <Card variant="elevated" className="space-y-4 rounded-2xl dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100">
          <CheckCircle2 className="h-6 w-6 text-emerald-600" aria-hidden="true" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-sg-navy dark:text-slate-100">{t("title")}</h3>
          <p className="text-sm text-sg-slate/70 dark:text-slate-300">
            {t("slideCount", { count: outputs.slide_count })}
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        {outputs.pptx_ready && (
          <Button
            variant="primary"
            size="md"
            loading={downloading === "pptx"}
            disabled={downloading !== null}
            onClick={() => handleDownload("pptx")}
            className="flex-1 bg-sg-teal hover:bg-sg-navy"
          >
            <Presentation className="h-4 w-4" aria-hidden="true" />
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
            <FileStack className="h-4 w-4" aria-hidden="true" />
            {t("downloadDocx")}
          </Button>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2 border-t border-sg-border pt-4">
        <Link href={`/pipeline/${sessionId}/slides`}>
          <Button variant="ghost" size="sm">
            <Presentation className="h-4 w-4" aria-hidden="true" />
            {t("viewSlides")}
          </Button>
        </Link>
        <Link href={`/pipeline/${sessionId}/export`}>
          <Button variant="ghost" size="sm">
            <Download className="h-4 w-4" aria-hidden="true" />
            {t("viewExport")}
          </Button>
        </Link>
      </div>
    </Card>
  );
}
