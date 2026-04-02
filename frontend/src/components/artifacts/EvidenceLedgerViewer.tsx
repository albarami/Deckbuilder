/**
 * EvidenceLedgerViewer — Table-like card layout for the evidence ledger artifact.
 *
 * Displays claim entries sorted by confidence descending, with:
 * - Claim ID (mono), claim text (expandable for long text), source reference
 * - Confidence progress bar + percentage
 * - Status badge (verified/partial/unverified/gap)
 */

"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import type { BadgeVariant } from "@/components/ui/Badge";
import type { EvidenceLedgerData, LedgerEntry } from "./types";

const STATUS_VARIANT: Record<LedgerEntry["verifiability_status"], BadgeVariant> = {
  verified: "success",
  partially_verified: "warning",
  unverified: "default",
  gap: "error",
};

const MAX_CLAIM_LENGTH = 120;

export function EvidenceLedgerViewer({ data }: { data: EvidenceLedgerData }) {
  const t = useTranslations("artifacts");
  const sorted = [...data.entries].sort((a, b) => b.confidence - a.confidence);

  if (sorted.length === 0) {
    return <div />;
  }

  return (
    <div className="space-y-2">
      {/* Header row — desktop only */}
      <div className="hidden sm:grid sm:grid-cols-[90px_1fr_1fr_130px_100px] gap-3 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-sg-slate/70 dark:text-slate-400">
        <span>{t("ledger.colClaimId")}</span>
        <span>{t("ledger.colClaim")}</span>
        <span>{t("ledger.colSource")}</span>
        <span>{t("ledger.colConfidence")}</span>
        <span>{t("ledger.colStatus")}</span>
      </div>

      {sorted.map((entry) => (
        <LedgerRow key={entry.claim_id} entry={entry} t={t} />
      ))}
    </div>
  );
}

// ── Row component with expand/collapse ──────────────────────────────────

function LedgerRow({
  entry,
  t,
}: {
  entry: LedgerEntry;
  t: ReturnType<typeof useTranslations>;
}) {
  const isLong = entry.claim_text.length > MAX_CLAIM_LENGTH;
  const [expanded, setExpanded] = useState(false);
  const pct = Math.round(entry.confidence * 100);

  const displayText =
    isLong && !expanded
      ? entry.claim_text.slice(0, MAX_CLAIM_LENGTH) + "\u2026"
      : entry.claim_text;

  const statusKey = `ledger.status.${entry.verifiability_status}` as const;

  return (
    <div
      className="rounded-lg border border-sg-border bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60 sm:grid sm:grid-cols-[90px_1fr_1fr_130px_100px] sm:items-center sm:gap-3"
    >
      {/* Claim ID */}
      <span className="font-mono text-xs text-sg-slate/70 dark:text-slate-400">
        {entry.claim_id}
      </span>

      {/* Claim text — expandable */}
      <div className="mt-1 min-w-0 sm:mt-0">
        <p className="text-sm text-sg-slate dark:text-slate-200">
          {displayText}
        </p>
        {isLong && (
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="mt-0.5 text-xs font-medium text-sg-blue hover:text-sg-teal dark:text-sky-300 dark:hover:text-sky-200"
            data-testid={`expand-${entry.claim_id}`}
          >
            {expanded ? t("ledger.collapse") : t("ledger.expand")}
          </button>
        )}
      </div>

      {/* Source reference */}
      <p className="mt-1 text-xs text-sg-slate/60 dark:text-slate-400 sm:mt-0 sm:text-sm">
        {entry.source_reference}
      </p>

      {/* Confidence bar + percentage */}
      <div className="mt-2 flex items-center gap-2 sm:mt-0">
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

      {/* Status badge */}
      <div className="mt-2 sm:mt-0">
        <Badge variant={STATUS_VARIANT[entry.verifiability_status]}>
          {t(statusKey)}
        </Badge>
      </div>
    </div>
  );
}
