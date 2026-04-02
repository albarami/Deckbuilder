/**
 * EvidencePackViewer -- Card layout for the external evidence pack artifact.
 *
 * Displays evidence sources sorted by relevance_score descending, with:
 * - Title + year (linked if url present), provider & tier badges
 * - Relevance progress bar + percentage
 * - RFP theme badge, collapsible key findings, optional proposal usage
 */

"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import type { BadgeVariant } from "@/components/ui/Badge";
import type { EvidencePackData, EvidenceSource } from "./types";

const TIER_VARIANT: Record<EvidenceSource["evidence_tier"], BadgeVariant> = {
  primary: "success",
  secondary: "info",
  analogical: "default",
};

const INITIAL_FINDINGS = 3;

export function EvidencePackViewer({ data }: { data: EvidencePackData }) {
  const t = useTranslations("artifacts");

  if (data.sources.length === 0) {
    return null;
  }

  const sorted = [...data.sources].sort(
    (a, b) => b.relevance_score - a.relevance_score,
  );

  return (
    <div className="space-y-4">
      {data.coverage_assessment && (
        <div className="rounded-lg border border-sg-border bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-sg-slate/70 dark:text-slate-400">
            {t("pack.coverageTitle")}
          </h3>
          <p className="mt-1 text-sm italic text-sg-slate dark:text-slate-300">
            {data.coverage_assessment}
          </p>
        </div>
      )}

      {sorted.map((source) => (
        <SourceCard key={source.source_id} source={source} t={t} />
      ))}
    </div>
  );
}

// -- Sub-component with per-card expand/collapse state ----------------------

function SourceCard({
  source,
  t,
}: {
  source: EvidenceSource;
  t: ReturnType<typeof useTranslations>;
}) {
  const [expanded, setExpanded] = useState(false);
  const pct = Math.round(source.relevance_score * 100);
  const hasMore = source.key_findings.length > INITIAL_FINDINGS;
  const visibleFindings =
    expanded || !hasMore
      ? source.key_findings
      : source.key_findings.slice(0, INITIAL_FINDINGS);

  return (
    <div className="rounded-lg border border-sg-border bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
      {/* Title + year */}
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-bold text-sg-slate dark:text-slate-100">
          {source.url ? (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-sg-blue dark:hover:text-sky-300"
            >
              {source.title}
            </a>
          ) : (
            source.title
          )}{" "}
          ({source.year})
        </p>
        <Badge variant="info">{source.provider}</Badge>
        <Badge variant={TIER_VARIANT[source.evidence_tier]}>
          {t(`pack.tier.${source.evidence_tier}` as Parameters<typeof t>[0])}
        </Badge>
      </div>

      {/* Relevance bar */}
      <div className="mt-2 flex items-center gap-2">
        <span className="text-xs font-medium text-sg-slate/70 dark:text-slate-400">
          {t("pack.relevance")}
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

      {/* Theme tag */}
      <div className="mt-2 flex items-center gap-2">
        <span className="text-xs font-medium text-sg-slate/70 dark:text-slate-400">
          {t("pack.theme")}
        </span>
        <Badge variant="navy">{source.mapped_rfp_theme}</Badge>
      </div>

      {/* Key findings */}
      {source.key_findings.length > 0 && (
        <div className="mt-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-sg-slate/70 dark:text-slate-400">
            {t("pack.keyFindings")}
          </h4>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm text-sg-slate dark:text-slate-300">
            {visibleFindings.map((finding, idx) => (
              <li key={idx}>{finding}</li>
            ))}
          </ul>
          {hasMore && (
            <button
              type="button"
              onClick={() => setExpanded((prev) => !prev)}
              className="mt-1 text-xs font-medium text-sg-blue hover:text-sg-teal dark:text-sky-300 dark:hover:text-sky-200"
            >
              {expanded
                ? t("pack.showLessFindings")
                : t("pack.showMoreFindings", {
                    count: source.key_findings.length,
                  })}
            </button>
          )}
        </div>
      )}

      {/* How to use in proposal */}
      {source.how_to_use_in_proposal && (
        <div className="mt-2">
          <span className="text-xs font-medium text-sg-slate/70 dark:text-slate-400">
            {t("pack.howToUse")}
          </span>
          <p className="mt-0.5 text-sm italic text-sg-slate/60 dark:text-slate-400">
            {source.how_to_use_in_proposal}
          </p>
        </div>
      )}
    </div>
  );
}
