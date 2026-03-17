/**
 * Gate1Context — RFP Context Analysis review panel.
 *
 * Displays extracted RFP context as key-value pairs:
 * client name, sector, geography, language, key requirements, etc.
 * Gate data is an object of string key-value pairs from context_agent.
 */

"use client";

import { useTranslations } from "next-intl";
import type { GateInfo } from "@/lib/types/pipeline";

export interface Gate1ContextProps {
  gate: GateInfo;
}

interface ContextEntry {
  key: string;
  value: string;
}

export function Gate1Context({ gate }: Gate1ContextProps) {
  const t = useTranslations("gate");
  const entries = extractEntries(gate.gate_data);

  return (
    <div data-testid="gate-1-context">
      <p className="mb-4 text-sm text-sg-slate/70 dark:text-slate-300">{gate.summary}</p>

      {entries.length === 0 ? (
        <p className="text-sm italic text-sg-slate/50 dark:text-slate-400">{t("noData")}</p>
      ) : (
        <div className="divide-y divide-sg-border rounded-lg border border-sg-border dark:divide-slate-800 dark:border-slate-800">
          {entries.map((entry) => (
            <div
              key={entry.key}
              className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-start sm:gap-4"
            >
              <dt className="min-w-[140px] text-xs font-semibold uppercase tracking-wider text-sg-slate/60 dark:text-slate-400">
                {formatKey(entry.key)}
              </dt>
              <dd className="flex-1 text-sm text-sg-navy dark:text-slate-100">{entry.value}</dd>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

function extractEntries(data: unknown): ContextEntry[] {
  if (!data || typeof data !== "object") return [];

  return Object.entries(data as Record<string, unknown>)
    .filter(([, v]) => v != null && String(v).length > 0)
    .map(([key, value]) => ({
      key,
      value: Array.isArray(value) ? value.join(", ") : String(value),
    }));
}

/** Convert snake_case keys to Title Case labels */
function formatKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
