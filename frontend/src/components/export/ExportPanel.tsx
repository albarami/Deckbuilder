/**
 * ExportPanel — Main export container with download buttons and summary.
 *
 * Composes DownloadButton and ExportSummary into a cohesive export view.
 * Handles pipeline-not-ready state (409) with a friendly message.
 */

"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DownloadButton } from "./DownloadButton";
import { ExportSummary } from "./ExportSummary";
import { downloadPptx, downloadDocx } from "@/lib/api/export";
import type {
  PipelineOutputs,
  SessionMetadata,
  GateRecord,
} from "@/lib/types/pipeline";

export interface ExportPanelProps {
  /** Pipeline session ID */
  sessionId: string;
  /** Pipeline outputs (null if not complete) */
  outputs: PipelineOutputs | null;
  /** Session metadata */
  metadata: SessionMetadata;
  /** Completed gates */
  completedGates: GateRecord[];
  /** Pipeline start time */
  startedAt: string;
  /** Total elapsed time in ms */
  elapsedMs: number;
  /** Optional CSS class */
  className?: string;
}

export function ExportPanel({
  sessionId,
  outputs,
  metadata,
  completedGates,
  startedAt,
  elapsedMs,
  className = "",
}: ExportPanelProps) {
  const t = useTranslations("export");

  const handlePptxDownload = useCallback(
    () => downloadPptx(sessionId),
    [sessionId],
  );

  const handleDocxDownload = useCallback(
    () => downloadDocx(sessionId),
    [sessionId],
  );

  const isReady = outputs !== null;
  const slideCount = outputs?.slide_count ?? 0;

  return (
    <div className={`space-y-6 ${className}`} data-testid="export-panel">
      {/* Header card with download buttons */}
      <Card variant="elevated" className="space-y-5">
        {/* Success indicator and title */}
        <div className="flex items-center gap-3">
          {isReady ? (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100">
              <CheckCircleIcon />
            </div>
          ) : (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
              <ClockIcon />
            </div>
          )}
          <div>
            <h2 className="text-lg font-bold text-sg-navy">{t("title")}</h2>
            {isReady ? (
              <p className="text-sm text-sg-slate/70">
                {t("slideCount", { count: slideCount })}
              </p>
            ) : (
              <p className="text-sm text-amber-600">{t("notReady")}</p>
            )}
          </div>
        </div>

        {/* Download buttons */}
        <div className="grid gap-3 sm:grid-cols-2" data-testid="download-section">
          <DownloadButton
            label={t("downloadPptx")}
            onDownload={handlePptxDownload}
            variant="primary"
            available={isReady && (outputs?.pptx_ready ?? false)}
            unavailableLabel={t("downloadPptx")}
            errorMessage={t("downloadError")}
          />
          <DownloadButton
            label={t("downloadDocx")}
            onDownload={handleDocxDownload}
            variant="secondary"
            available={isReady && (outputs?.docx_ready ?? false)}
            unavailableLabel={t("downloadDocx")}
            errorMessage={t("downloadError")}
          />
        </div>

        {/* File format hints */}
        {isReady && (
          <div className="flex flex-wrap gap-2" data-testid="format-hints">
            {outputs?.pptx_ready && (
              <Badge variant="info">{t("formatPptx")}</Badge>
            )}
            {outputs?.docx_ready && (
              <Badge variant="info">{t("formatDocx")}</Badge>
            )}
          </div>
        )}
      </Card>

      {/* Session summary */}
      <ExportSummary
        sessionId={sessionId}
        startedAt={startedAt}
        elapsedMs={elapsedMs}
        metadata={metadata}
        completedGates={completedGates}
        slideCount={slideCount}
      />
    </div>
  );
}

// ── Icons ────────────────────────────────────────────────────────────────

function CheckCircleIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-7 w-7 text-emerald-600"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-7 w-7 text-amber-600"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-13a.75.75 0 00-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 000-1.5h-3.25V5z"
        clipRule="evenodd"
      />
    </svg>
  );
}
