/**
 * Gate5QA — Quality Assurance review panel.
 *
 * Displays QA results as a sortable table with pass/fail badges per slide.
 * Gate data contains { results: QAResult[] } with slide_index, check, status, details.
 */

"use client";

import { type ReactNode } from "react";
import { FileCheck2, Presentation, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable, type DataTableColumn } from "../shared/DataTable";
import type { GateInfo } from "@/lib/types/pipeline";
import { usePipelineStore } from "@/stores/pipeline-store";

export interface Gate5QAProps {
  gate: GateInfo;
}

interface QAResult {
  slide_index: number;
  check: string;
  status: "pass" | "fail" | "warning";
  details: string;
  [key: string]: unknown;
}

export function Gate5QA({ gate }: Gate5QAProps) {
  const t = useTranslations("gate");
  const tExport = useTranslations("export");
  const results = extractResults(gate.gate_data);
  const outputs = usePipelineStore((state) => state.outputs);
  const passCount = results.filter((r) => r.status === "pass").length;
  const failCount = results.filter((r) => r.status === "fail").length;
  const warnCount = results.filter((r) => r.status === "warning").length;
  const lintStatus = deriveStatus(results, ["lint", "overflow", "layout"]);
  const densityStatus = deriveStatus(results, ["density", "fit", "text"]);
  const isReadyForExport = failCount === 0;

  const columns: DataTableColumn<QAResult>[] = [
    {
      key: "slide_index",
      label: t("qaSlide"),
      sortable: true,
      width: "w-20",
      render: (row) => (
        <span className="font-mono text-xs text-sg-slate/70">
          #{row.slide_index}
        </span>
      ),
    },
    {
      key: "check",
      label: t("qaCheck"),
      sortable: true,
      render: (row) => (
        <span className="text-sm text-sg-navy">{row.check}</span>
      ),
    },
    {
      key: "status",
      label: t("qaStatus"),
      sortable: true,
      width: "w-24",
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: "details",
      label: t("qaDetails"),
      render: (row) => (
        <span className="text-xs text-sg-slate/70">{row.details}</span>
      ),
    },
  ];

  return (
    <div data-testid="gate-5-qa">
      <p className="mb-4 text-sm text-sg-slate/70 dark:text-slate-300">{gate.summary}</p>

      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <SummaryCard
          icon={<ShieldCheck className="h-4 w-4" aria-hidden="true" />}
          label={t("qaReadiness")}
          value={isReadyForExport ? t("qaReady") : t("qaNeedsFixes")}
          tone={isReadyForExport ? "success" : "warning"}
        />
        <SummaryCard
          icon={<FileCheck2 className="h-4 w-4" aria-hidden="true" />}
          label={t("qaLintStatus")}
          value={lintStatus === "Pass" ? t("qaReady") : t("qaReview")}
          tone={lintStatus === "Pass" ? "success" : "warning"}
        />
        <SummaryCard
          icon={<Presentation className="h-4 w-4" aria-hidden="true" />}
          label={t("qaDensityStatus")}
          value={densityStatus === "Pass" ? t("qaReady") : t("qaReview")}
          tone={densityStatus === "Pass" ? "success" : "warning"}
        />
      </div>

      {results.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Badge variant="success">
            {t("qaPassed", { count: passCount })}
          </Badge>
          {failCount > 0 && (
            <Badge variant="error">
              {t("qaFailed", { count: failCount })}
            </Badge>
          )}
          {warnCount > 0 && (
            <Badge variant="warning">
              {t("qaWarnings", { count: warnCount })}
            </Badge>
          )}
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <Button
          variant="primary"
          size="sm"
          disabled={!outputs?.pptx_ready}
          className="bg-sg-teal hover:bg-sg-navy"
        >
          {tExport("exportPptxShort")}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={!outputs?.docx_ready}
        >
          {tExport("exportDocxShort")}
        </Button>
      </div>

      <DataTable<QAResult>
        columns={columns}
        data={results}
        getRowKey={(row, i) => `${row.slide_index}-${row.check}-${i}`}
        emptyMessage={t("noData")}
      />
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

function extractResults(data: unknown): QAResult[] {
  if (!data || typeof data !== "object") return [];
  const obj = data as Record<string, unknown>;
  const results = obj.results;
  if (!Array.isArray(results)) return [];

  return results.map((r: Record<string, unknown>, i: number) => ({
    slide_index: typeof r.slide_index === "number" ? r.slide_index : i,
    check: String(r.check ?? "Unknown check"),
    status: validateStatus(r.status),
    details: String(r.details ?? ""),
  }));
}

function validateStatus(status: unknown): "pass" | "fail" | "warning" {
  if (status === "pass" || status === "fail" || status === "warning") {
    return status;
  }
  return "warning";
}

function StatusBadge({ status }: { status: "pass" | "fail" | "warning" }) {
  const variantMap = {
    pass: "success" as const,
    fail: "error" as const,
    warning: "warning" as const,
  };
  const labelMap = {
    pass: "qaPass",
    fail: "qaFail",
    warning: "qaWarning",
  };

  const t = useTranslations("gate");
  return <Badge variant={variantMap[status]}>{t(labelMap[status])}</Badge>;
}

function deriveStatus(results: QAResult[], keywords: string[]): "Pass" | "Review" {
  const matching = results.filter((result) =>
    keywords.some((keyword) => result.check.toLowerCase().includes(keyword)),
  );

  if (matching.length === 0) return "Review";
  return matching.every((result) => result.status === "pass") ? "Pass" : "Review";
}

function SummaryCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone: "success" | "warning";
}) {
  return (
    <div className="rounded-xl border border-sg-border bg-sg-mist/60 p-4 dark:border-slate-800 dark:bg-slate-950/70">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-sg-slate/55 dark:text-slate-400">
        <span className={tone === "success" ? "text-emerald-600" : "text-sg-orange"}>
          {icon}
        </span>
        {label}
      </div>
      <p className="mt-2 text-sm font-semibold text-sg-navy dark:text-slate-100">{value}</p>
    </div>
  );
}
