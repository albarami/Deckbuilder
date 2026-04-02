/**
 * RoutingReportViewer -- Summary card for the routing report artifact.
 *
 * Displays classification details, routing confidence, selected/fallback packs,
 * and any routing warnings.
 */

"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { RoutingReportData } from "./types";

export function RoutingReportViewer({ data }: { data: RoutingReportData }) {
  const t = useTranslations("artifacts");
  const pct = Math.round(data.routing_confidence * 100);
  const { classification } = data;

  return (
    <div className="space-y-4">
      {/* Classification section */}
      <div className="rounded-lg border border-sg-border bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-sg-slate/70 dark:text-slate-400">
          {t("routing.classificationTitle")}
        </h3>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="font-medium text-sg-slate/70 dark:text-slate-400">
            {t("routing.jurisdiction")}
          </dt>
          <dd className="text-sg-slate dark:text-slate-200">
            {classification.jurisdiction}
          </dd>

          <dt className="font-medium text-sg-slate/70 dark:text-slate-400">
            {t("routing.sector")}
          </dt>
          <dd className="text-sg-slate dark:text-slate-200">
            {classification.sector}
          </dd>

          <dt className="font-medium text-sg-slate/70 dark:text-slate-400">
            {t("routing.domain")}
          </dt>
          <dd className="text-sg-slate dark:text-slate-200">
            {classification.domain}
          </dd>

          <dt className="font-medium text-sg-slate/70 dark:text-slate-400">
            {t("routing.clientType")}
          </dt>
          <dd className="text-sg-slate dark:text-slate-200">
            {classification.client_type}
          </dd>

          {classification.regulatory_frame && (
            <>
              <dt className="font-medium text-sg-slate/70 dark:text-slate-400">
                {t("routing.regulatoryFrame")}
              </dt>
              <dd className="text-sg-slate dark:text-slate-200">
                {classification.regulatory_frame}
              </dd>
            </>
          )}
        </dl>
      </div>

      {/* Confidence bar */}
      <div className="rounded-lg border border-sg-border bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-sg-slate/70 dark:text-slate-400">
            {t("routing.confidence")}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-sg-mist/30 dark:bg-slate-950/40">
            <div
              className="h-full rounded-full bg-sg-teal"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="w-9 text-right text-xs font-medium text-sg-slate dark:text-slate-200">
            {pct}%
          </span>
        </div>
      </div>

      {/* Selected packs */}
      <div className="rounded-lg border border-sg-border bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-sg-slate/70 dark:text-slate-400">
          {t("routing.selectedPacks")}
        </h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {data.selected_packs.map((p) => (
            <Badge key={p} variant="info">
              {p}
            </Badge>
          ))}
        </div>
      </div>

      {/* Fallback packs (conditional) */}
      {data.fallback_packs_used.length > 0 && (
        <div className="rounded-lg border border-sg-border bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-sg-slate/70 dark:text-slate-400">
            {t("routing.fallbackPacks")}
          </h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {data.fallback_packs_used.map((p) => (
              <Badge key={p} variant="warning">
                {p}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Warnings (conditional) */}
      {data.warnings.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-700 dark:bg-amber-950/30">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
              {t("routing.warnings")}
            </h3>
          </div>
          <ul className="mt-2 list-inside list-disc space-y-0.5 text-sm text-amber-800 dark:text-amber-200">
            {data.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
