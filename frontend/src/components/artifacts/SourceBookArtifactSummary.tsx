/**
 * SourceBookArtifactSummary — Lightweight summary panel for the pipeline completion view.
 *
 * Reads source book metrics and artifact readiness from the pipeline store.
 * No data fetching — purely derived from existing store state.
 */

"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Link } from "@/i18n/routing";
import { usePipelineStore } from "@/stores/pipeline-store";

export function SourceBookArtifactSummary() {
  const summary = usePipelineStore((s) => s.sourceBookSummary);
  const outputs = usePipelineStore((s) => s.outputs);
  const sessionId = usePipelineStore((s) => s.sessionId);
  const t = useTranslations("artifacts");

  if (!summary) return null;

  const readinessBadges: { label: string; ready: boolean }[] = [
    { label: t("summary.sourceBook"), ready: outputs?.source_book_ready ?? false },
    { label: t("summary.evidenceLedger"), ready: outputs?.evidence_ledger_ready ?? false },
    { label: t("summary.blueprints"), ready: outputs?.slide_blueprint_ready ?? false },
    { label: t("summary.evidencePack"), ready: outputs?.external_evidence_ready ?? false },
    { label: t("summary.routingReport"), ready: outputs?.routing_report_ready ?? false },
  ];

  return (
    <Card
      variant="flat"
      className="space-y-4 border border-sg-border dark:border-slate-700 dark:bg-slate-900"
    >
      {/* Primary metrics — 3 column grid */}
      <div className="grid grid-cols-3 gap-4">
        <div className="text-center">
          <p className="text-2xl font-bold text-sg-navy dark:text-slate-100">
            {summary.word_count.toLocaleString()}
          </p>
          <p className="text-xs text-sg-slate/70 dark:text-slate-400">
            {t("summary.wordCount")}
          </p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-sg-navy dark:text-slate-100">
            {summary.reviewer_score} / 5
          </p>
          <p className="text-xs text-sg-slate/70 dark:text-slate-400">
            {t("summary.reviewerScore")}
          </p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-sg-navy dark:text-slate-100">
            {summary.pass_number}
          </p>
          <p className="text-xs text-sg-slate/70 dark:text-slate-400">
            {t("summary.passNumber")}
          </p>
        </div>
      </div>

      {/* Secondary metrics — 3 column grid, smaller */}
      <div className="grid grid-cols-3 gap-4">
        <div className="text-center">
          <p className="text-lg font-semibold text-sg-navy dark:text-slate-200">
            {summary.evidence_ledger_entries}
          </p>
          <p className="text-xs text-sg-slate/70 dark:text-slate-400">
            {t("summary.evidenceLedger")}
          </p>
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold text-sg-navy dark:text-slate-200">
            {summary.slide_blueprint_entries}
          </p>
          <p className="text-xs text-sg-slate/70 dark:text-slate-400">
            {t("summary.blueprints")}
          </p>
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold text-sg-navy dark:text-slate-200">
            {summary.external_sources}
          </p>
          <p className="text-xs text-sg-slate/70 dark:text-slate-400">
            {t("summary.externalSources")}
          </p>
        </div>
      </div>

      {/* Readiness badges */}
      <div className="flex flex-wrap gap-2">
        {readinessBadges.map(({ label, ready }) => (
          <span
            key={label}
            className={
              ready
                ? "inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300"
                : "inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400"
            }
          >
            {label}: {ready ? t("summary.ready") : t("summary.notReady")}
          </span>
        ))}
      </div>

      {/* CTA */}
      {sessionId && (
        <div>
          <Link href={`/pipeline/${sessionId}/export`}>
            <Button variant="secondary" size="sm">
              {t("summary.viewDetails")}
            </Button>
          </Link>
        </div>
      )}
    </Card>
  );
}
