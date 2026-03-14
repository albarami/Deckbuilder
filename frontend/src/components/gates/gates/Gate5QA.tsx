/**
 * Gate5QA — Quality Assurance review panel.
 *
 * Displays QA results as a sortable table with pass/fail badges per slide.
 * Gate data contains { results: QAResult[] } with slide_index, check, status, details.
 */

"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "../shared/DataTable";
import type { GateInfo } from "@/lib/types/pipeline";

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
  const results = extractResults(gate.gate_data);
  const passCount = results.filter((r) => r.status === "pass").length;
  const failCount = results.filter((r) => r.status === "fail").length;
  const warnCount = results.filter((r) => r.status === "warning").length;

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
      <p className="mb-4 text-sm text-sg-slate/70">{gate.summary}</p>

      {results.length > 0 && (
        <div className="mb-4 flex items-center gap-3">
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
    pass: "Pass",
    fail: "Fail",
    warning: "Warning",
  };

  return <Badge variant={variantMap[status]}>{labelMap[status]}</Badge>;
}
