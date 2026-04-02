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
import { useIsPptEnabled } from "@/hooks/use-is-ppt-enabled";
import { DownloadButton } from "./DownloadButton";
import { ExportSummary } from "./ExportSummary";
import {
  downloadPptx,
  downloadDocx,
  downloadSourceIndex,
  downloadGapReport,
  downloadSourceBook,
  downloadResearchQueryLog,
  downloadQueryExecutionLog,
} from "@/lib/api/export";
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
  /** True when Gate 3 is pending and Source Book is ready for review */
  sourceBookGatePending?: boolean;
  /** True when Source Book is approved and DOCX is ready */
  sourceBookReadyCheckpoint?: boolean;
  /** True when proposal_mode is source_book_only */
  isSourceBookMode?: boolean;
}

export function ExportPanel({
  sessionId,
  outputs,
  metadata,
  completedGates,
  startedAt,
  elapsedMs,
  className = "",
  sourceBookGatePending = false,
  sourceBookReadyCheckpoint = false,
  isSourceBookMode = false,
}: ExportPanelProps) {
  const t = useTranslations("export");
  const tSourceBook = useTranslations("sourceBook");
  const isPptEnabled = useIsPptEnabled();

  const handlePptxDownload = useCallback(
    () => downloadPptx(sessionId),
    [sessionId],
  );

  const handleDocxDownload = useCallback(
    () => downloadDocx(sessionId),
    [sessionId],
  );

  const handleSourceIndexDownload = useCallback(
    () => downloadSourceIndex(sessionId),
    [sessionId],
  );

  const handleGapReportDownload = useCallback(
    () => downloadGapReport(sessionId),
    [sessionId],
  );

  const handleSourceBookDownload = useCallback(
    () => downloadSourceBook(sessionId),
    [sessionId],
  );

  const handleQueryLogDownload = useCallback(
    () => downloadResearchQueryLog(sessionId),
    [sessionId],
  );

  const handleExecLogDownload = useCallback(
    () => downloadQueryExecutionLog(sessionId),
    [sessionId],
  );

  const isReady = outputs !== null;
  const slideCount = outputs?.slide_count ?? 0;
  const sourceBookReady = outputs?.source_book_ready ?? false;
  const sourceBookEligible = isSourceBookMode
    ? (sourceBookGatePending || sourceBookReadyCheckpoint || sourceBookReady)
    : (sourceBookGatePending || sourceBookReadyCheckpoint || (outputs?.docx_ready ?? false));
  const showFullPipelineMessage = !sourceBookEligible && !isReady;

  return (
    <div className={`space-y-6 ${className}`} data-testid="export-panel">
      {/* Header card with download buttons */}
      <Card variant="elevated" className="space-y-5 rounded-2xl dark:border-slate-800 dark:bg-slate-900">
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
            <h2 className="text-lg font-bold text-sg-navy dark:text-slate-100">{t("title")}</h2>
            {isSourceBookMode ? (
              <p className="text-sm text-sg-slate/70 dark:text-slate-300">
                {sourceBookEligible ? tSourceBook("readyTitle") : t("notReady")}
              </p>
            ) : isReady ? (
              <p className="text-sm text-sg-slate/70 dark:text-slate-300">
                {t("slideCount", { count: slideCount })}
              </p>
            ) : (
              <p className="text-sm text-amber-600 dark:text-amber-400">
                {showFullPipelineMessage ? t("notReady") : tSourceBook("readyTitle")}
              </p>
            )}
          </div>
        </div>

        {/* Download buttons — Source Book mode vs Deck mode */}
        {isSourceBookMode ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="download-section">
            <DownloadButton
              label={tSourceBook("downloadDocxNow")}
              onDownload={handleSourceBookDownload}
              variant="primary"
              available={sourceBookEligible}
              unavailableLabel={tSourceBook("downloadDocxNow")}
              errorMessage={t("downloadError")}
            />
            <DownloadButton
              label={t("downloadQueryLog")}
              onDownload={handleQueryLogDownload}
              variant="secondary"
              available={isReady && (outputs?.research_query_log_ready ?? false)}
              unavailableLabel={t("downloadQueryLog")}
              errorMessage={t("downloadError")}
            />
            <DownloadButton
              label={t("downloadExecLog")}
              onDownload={handleExecLogDownload}
              variant="secondary"
              available={isReady && (outputs?.query_execution_log_ready ?? false)}
              unavailableLabel={t("downloadExecLog")}
              errorMessage={t("downloadError")}
            />
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="download-section">
            <DownloadButton
              label={t("downloadPptx")}
              onDownload={handlePptxDownload}
              variant="primary"
              available={isPptEnabled && isReady && (outputs?.pptx_ready ?? false)}
              unavailableLabel={t("downloadPptx")}
              errorMessage={t("downloadError")}
            />
            <DownloadButton
              label={tSourceBook("downloadDocxNow")}
              onDownload={handleDocxDownload}
              variant="primary"
              available={sourceBookEligible}
              unavailableLabel={tSourceBook("downloadDocxNow")}
              errorMessage={t("downloadError")}
            />
            <DownloadButton
              label={t("downloadSourceIndex")}
              onDownload={handleSourceIndexDownload}
              variant="secondary"
              available={isReady && (outputs?.source_index_ready ?? false)}
              unavailableLabel={t("downloadSourceIndex")}
              errorMessage={t("downloadError")}
            />
            <DownloadButton
              label={t("downloadGapReport")}
              onDownload={handleGapReportDownload}
              variant="secondary"
              available={isReady && (outputs?.gap_report_ready ?? false)}
              unavailableLabel={t("downloadGapReport")}
              errorMessage={t("downloadError")}
            />
          </div>
        )}

        {/* File format hints */}
        {isReady && !isSourceBookMode && (
          <div className="flex flex-wrap gap-2" data-testid="format-hints">
            {isPptEnabled && outputs?.pptx_ready && (
              <Badge variant="info">{t("formatPptx")}</Badge>
            )}
            {sourceBookEligible && (
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
