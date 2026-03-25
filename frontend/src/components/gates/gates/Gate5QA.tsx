/**
 * Gate5QA — Quality Assurance review panel.
 *
 * Renders Gate5QaReviewData from the backend, using real
 * submission_readiness, fail_close, lint/density/coverage status,
 * waivers, and deliverables from governance services.
 */

"use client";

import { type ReactNode } from "react";
import { FileCheck2, Presentation, ShieldAlert, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable, type DataTableColumn } from "../shared/DataTable";
import type { GateInfo, Gate5QaReviewData, ReadinessStatus } from "@/lib/types/pipeline";

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
  const data = gate.gate_data as Gate5QaReviewData | null | undefined;

  // Use backend-provided readiness values instead of deriving locally
  const submissionReadiness = data?.submission_readiness ?? "review";
  const failClose = data?.fail_close ?? false;
  const lintStatus = data?.lint_status ?? "review";
  const densityStatus = data?.density_status ?? "review";
  const templateCompliance = data?.template_compliance ?? "review";
  // languageStatus reserved for future use (language QA panel)
  const coverageStatus = data?.coverage_status ?? "review";
  const criticalGaps = data?.critical_gaps ?? [];
  const waivers = data?.waivers ?? [];
  const deliverables = data?.deliverables ?? [];
  const results = extractResults(data);

  const passCount = results.filter((r) => r.status === "pass").length;
  const failCount = results.filter((r) => r.status === "fail").length;
  const warnCount = results.filter((r) => r.status === "warning").length;

  const isReadyForExport = submissionReadiness === "ready";
  const pptxDeliverable = deliverables.find((d) => d.key === "pptx");
  const docxDeliverable = deliverables.find((d) => d.key === "docx");

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

      {/* Fail-close warning */}
      {failClose && (
        <div className="mb-4 rounded-lg border border-red-300 bg-red-50 p-3 dark:border-red-800/50 dark:bg-red-900/20">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-red-600 dark:text-red-400" aria-hidden="true" />
            <span className="text-sm font-semibold text-red-700 dark:text-red-400">
              {t("qaFailClose")}
            </span>
          </div>
          {criticalGaps.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-sm text-red-600 dark:text-red-300">
              {criticalGaps.map((gap) => (
                <li key={gap.gap_id}>{gap.label}: {gap.description}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="mb-4 grid gap-3 md:grid-cols-3 lg:grid-cols-5">
        <SummaryCard
          icon={<ShieldCheck className="h-4 w-4" aria-hidden="true" />}
          label={t("qaReadiness")}
          value={readinessLabel(submissionReadiness, t)}
          tone={readinessTone(submissionReadiness)}
        />
        <SummaryCard
          icon={<FileCheck2 className="h-4 w-4" aria-hidden="true" />}
          label={t("qaLintStatus")}
          value={readinessLabel(lintStatus, t)}
          tone={readinessTone(lintStatus)}
        />
        <SummaryCard
          icon={<Presentation className="h-4 w-4" aria-hidden="true" />}
          label={t("qaDensityStatus")}
          value={readinessLabel(densityStatus, t)}
          tone={readinessTone(densityStatus)}
        />
        <SummaryCard
          icon={<FileCheck2 className="h-4 w-4" aria-hidden="true" />}
          label={t("qaTemplateCompliance")}
          value={readinessLabel(templateCompliance, t)}
          tone={readinessTone(templateCompliance)}
        />
        <SummaryCard
          icon={<FileCheck2 className="h-4 w-4" aria-hidden="true" />}
          label={t("qaCoverage")}
          value={readinessLabel(coverageStatus, t)}
          tone={readinessTone(coverageStatus)}
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

      {/* Waivers */}
      {waivers.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800/50 dark:bg-amber-900/20">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-400">
            {t("qaWaivers")}
          </p>
          <div className="mt-1 flex flex-wrap gap-1">
            {waivers.map((w) => (
              <Badge key={w.waiver_id} variant="warning">{w.label}</Badge>
            ))}
          </div>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <Button
          variant="primary"
          size="sm"
          disabled={!isReadyForExport || !pptxDeliverable?.ready}
          className="bg-sg-teal hover:bg-sg-navy"
        >
          {tExport("exportPptxShort")}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={!docxDeliverable?.ready}
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

function extractResults(data: Gate5QaReviewData | null | undefined): QAResult[] {
  if (!data?.results || !Array.isArray(data.results)) return [];

  return data.results.map((r, i) => ({
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

function readinessLabel(
  status: ReadinessStatus | string,
  t: (key: string) => string,
): string {
  switch (status) {
    case "ready": return t("qaReady");
    case "review": return t("qaReview");
    case "needs_fixes": return t("qaNeedsFixes");
    case "blocked": return t("qaBlocked");
    default: return t("qaReview");
  }
}

function readinessTone(status: ReadinessStatus | string): "success" | "warning" | "error" {
  switch (status) {
    case "ready": return "success";
    case "review": return "warning";
    case "needs_fixes": return "warning";
    case "blocked": return "error";
    default: return "warning";
  }
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
  tone: "success" | "warning" | "error";
}) {
  const toneColors = {
    success: "text-emerald-600",
    warning: "text-sg-orange",
    error: "text-red-600",
  };

  return (
    <div className="rounded-xl border border-sg-border bg-sg-mist/60 p-4 dark:border-slate-800 dark:bg-slate-950/70">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-sg-slate/55 dark:text-slate-400">
        <span className={toneColors[tone]}>
          {icon}
        </span>
        {label}
      </div>
      <p className="mt-2 text-sm font-semibold text-sg-navy dark:text-slate-100">{value}</p>
    </div>
  );
}
