/**
 * Gate2Sources — Source Research review panel.
 *
 * Displays discovered sources with relevance scores and inclusion checkboxes.
 * Reviewer can toggle source inclusion before approving/rejecting.
 * Modifications are sent back via the gate decision payload.
 */

"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import type { GateInfo } from "@/lib/types/pipeline";

export interface Gate2SourcesProps {
  gate: GateInfo;
  /** Called when source modifications change */
  onModificationsChange?: (modifications: SourceModifications) => void;
}

export interface SourceModifications {
  included_sources: string[];
  excluded_sources: string[];
}

interface SourceItem {
  id: string;
  title: string;
  url?: string;
  relevance_score: number;
  snippet?: string;
}

export function Gate2Sources({ gate, onModificationsChange }: Gate2SourcesProps) {
  const t = useTranslations("gate");
  const sources = extractSources(gate.gate_data);
  const [included, setIncluded] = useState<Set<string>>(
    () => new Set(sources.map((s) => s.id)),
  );

  const handleToggle = useCallback(
    (sourceId: string) => {
      setIncluded((prev) => {
        const next = new Set(prev);
        if (next.has(sourceId)) {
          next.delete(sourceId);
        } else {
          next.add(sourceId);
        }

        // Notify parent of modifications
        const allIds = sources.map((s) => s.id);
        const modifications: SourceModifications = {
          included_sources: allIds.filter((id) => next.has(id)),
          excluded_sources: allIds.filter((id) => !next.has(id)),
        };
        onModificationsChange?.(modifications);

        return next;
      });
    },
    [sources, onModificationsChange],
  );

  return (
    <div data-testid="gate-2-sources">
      <p className="mb-4 text-sm text-sg-slate/70 dark:text-slate-300">{gate.summary}</p>

      {sources.length === 0 ? (
        <p className="text-sm italic text-sg-slate/50 dark:text-slate-400">{t("noData")}</p>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-sg-slate/60 dark:text-slate-400">
            {t("sourcesSelected", { count: included.size, total: sources.length })}
          </p>
          <ul className="divide-y divide-sg-border rounded-lg border border-sg-border dark:divide-slate-800 dark:border-slate-800">
            {sources.map((source) => (
              <li key={source.id} className="flex items-start gap-3 px-4 py-3">
                <input
                  type="checkbox"
                  checked={included.has(source.id)}
                  onChange={() => handleToggle(source.id)}
                  className="mt-1 h-4 w-4 rounded border-sg-border text-sg-blue focus:ring-sg-blue/20 dark:border-slate-700 dark:bg-slate-950"
                  aria-label={`${t("includeSource")}: ${source.title}`}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-sg-navy dark:text-slate-100">
                      {source.title}
                    </span>
                    <RelevanceBadge score={source.relevance_score} />
                  </div>
                  {source.url && (
                    <p className="mt-0.5 truncate text-xs text-sg-blue/70 dark:text-sky-300/80">
                      {source.url}
                    </p>
                  )}
                  {source.snippet && (
                    <p className="mt-1 line-clamp-2 text-xs text-sg-slate/60 dark:text-slate-400">
                      {source.snippet}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

function extractSources(data: unknown): SourceItem[] {
  if (!data || typeof data !== "object") return [];

  const obj = data as Record<string, unknown>;
  const sources = obj.sources;

  if (!Array.isArray(sources)) return [];

  return sources.map((s: Record<string, unknown>, i: number) => ({
    id: String(s.source_id ?? s.id ?? `source_${i}`),
    title: String(s.title ?? `Source ${i + 1}`),
    url: s.url ? String(s.url) : undefined,
    relevance_score: typeof s.relevance_score === "number" ? s.relevance_score : 0,
    snippet: s.snippet ? String(s.snippet) : undefined,
  }));
}

function RelevanceBadge({ score }: { score: number }) {
  const variant = score >= 0.8 ? "success" : score >= 0.5 ? "warning" : "default";
  return (
    <Badge variant={variant}>
      {Math.round(score * 100)}%
    </Badge>
  );
}
