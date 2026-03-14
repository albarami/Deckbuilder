/**
 * Gate3Research — Research Report review panel.
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
  if (typeof obj.report === "string" && obj.report.length > 0) {
    return obj.report;
  }
  return null;
}
