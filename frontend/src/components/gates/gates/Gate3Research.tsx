/**
 * Gate3Research — Research Report review panel.
 *
 * Legacy fallback for Gate 3 payloads that are not Source Book review data.
 *
 * Renders the research report output as markdown via MarkdownViewer.
 * Gate data contains { report: string } with the full markdown report.
 */

"use client";

import { useTranslations } from "next-intl";
import { MarkdownViewer } from "../shared/MarkdownViewer";
import type { GateInfo } from "@/lib/types/pipeline";

export interface Gate3ResearchProps {
  gate: GateInfo;
}

export function Gate3Research({ gate }: Gate3ResearchProps) {
  const t = useTranslations("gate");
  const report = extractReport(gate.gate_data);

  return (
    <div data-testid="gate-3-research">
      <p className="mb-4 text-sm text-sg-slate/70">{gate.summary}</p>

      {report ? (
        <div className="rounded-lg border border-sg-border bg-white p-4">
          <MarkdownViewer content={report} />
        </div>
      ) : (
        <p className="text-sm text-sg-slate/50 italic">{t("noData")}</p>
      )}
    </div>
  );
}

function extractReport(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const obj = data as Record<string, unknown>;
  // Backend sends report_markdown (Gate3ReportReviewData contract)
  if (typeof obj.report_markdown === "string" && obj.report_markdown.length > 0) {
    return obj.report_markdown;
  }
  // Legacy fallback
  if (typeof obj.report === "string" && obj.report.length > 0) {
    return obj.report;
  }
  return null;
}
