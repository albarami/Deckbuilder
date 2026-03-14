/**
 * ExportSummary — Pipeline session metadata summary card.
 *
 * Displays session stats: duration, LLM calls, tokens, cost, gates passed.
 * Used on the export page to give context about the completed pipeline run.
 */

"use client";

import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { SessionMetadata, GateRecord } from "@/lib/types/pipeline";

export interface ExportSummaryProps {
  /** Pipeline session ID */
  sessionId: string;
  /** Pipeline start time (ISO string) */
  startedAt: string;
  /** Total elapsed time in ms */
  elapsedMs: number;
  /** Session metadata (LLM calls, tokens, cost) */
  metadata: SessionMetadata;
  /** Completed gates */
  completedGates: GateRecord[];
  /** Total slide count */
  slideCount: number;
  /** Optional CSS class */
  className?: string;
}

export function ExportSummary({
  sessionId,
  startedAt,
  elapsedMs,
  metadata,
  completedGates,
  slideCount,
  className = "",
}: ExportSummaryProps) {
  const t = useTranslations("export");

  return (
    <Card variant="flat" className={`space-y-4 ${className}`} data-testid="export-summary">
      {/* Title */}
      <h3 className="text-sm font-semibold text-sg-navy">{t("summaryTitle")}</h3>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {/* Session ID */}
        <StatItem
          label={t("summarySession")}
          value={sessionId.slice(0, 8)}
          testId="summary-session"
        />

        {/* Duration */}
        <StatItem
          label={t("summaryDuration")}
          value={formatDuration(elapsedMs)}
          testId="summary-duration"
        />

        {/* Slides */}
        <StatItem
          label={t("summarySlides")}
          value={String(slideCount)}
          testId="summary-slides"
        />

        {/* Gates */}
        <StatItem
          label={t("summaryGates")}
          value={`${completedGates.length}/5`}
          testId="summary-gates"
        />

        {/* LLM Calls */}
        <StatItem
          label={t("summaryLlmCalls")}
          value={String(metadata.total_llm_calls)}
          testId="summary-llm-calls"
        />

        {/* Input Tokens */}
        <StatItem
          label={t("summaryInputTokens")}
          value={formatNumber(metadata.total_input_tokens)}
          testId="summary-input-tokens"
        />

        {/* Output Tokens */}
        <StatItem
          label={t("summaryOutputTokens")}
          value={formatNumber(metadata.total_output_tokens)}
          testId="summary-output-tokens"
        />

        {/* Cost */}
        <StatItem
          label={t("summaryCost")}
          value={`$${metadata.total_cost_usd.toFixed(2)}`}
          testId="summary-cost"
        />
      </div>

      {/* Gate timeline */}
      {completedGates.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-sg-slate/70">{t("summaryGateTimeline")}</h4>
          <div className="flex flex-wrap gap-2">
            {completedGates.map((gate) => (
              <Badge
                key={gate.gate_number}
                variant={gate.approved ? "success" : "warning"}
                data-testid={`gate-badge-${gate.gate_number}`}
              >
                {t("summaryGateNumber", { number: gate.gate_number })}
                {gate.approved ? " \u2713" : " \u21BB"}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Started at */}
      <p className="text-xs text-sg-slate/50" data-testid="summary-started-at">
        {t("summaryStarted")}: {formatTimestamp(startedAt)}
      </p>
    </Card>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────

interface StatItemProps {
  label: string;
  value: string;
  testId: string;
}

function StatItem({ label, value, testId }: StatItemProps) {
  return (
    <div className="space-y-1" data-testid={testId}>
      <p className="text-xs text-sg-slate/60">{label}</p>
      <p className="text-sm font-semibold text-sg-navy">{value}</p>
    </div>
  );
}

/** Format milliseconds into human-readable duration */
function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

/** Format large numbers with K/M suffixes */
function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/** Format ISO timestamp for display */
function formatTimestamp(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleString();
  } catch {
    return iso;
  }
}
