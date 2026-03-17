/**
 * GateHeader — Gate title bar with gate number and review prompt.
 *
 * Displays the gate number, translated title, and the AI-provided
 * review prompt that guides the consultant's decision.
 */

"use client";

import { ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import type { GateInfo } from "@/lib/types/pipeline";

export interface GateHeaderProps {
  /** Gate information from the pipeline */
  gate: GateInfo;
}

/** Gate number → descriptive name mapping key */
const GATE_NAME_KEYS: Record<number, string> = {
  1: "gate1Name",
  2: "gate2Name",
  3: "gate3Name",
  4: "gate4Name",
  5: "gate5Name",
};

export function GateHeader({ gate }: GateHeaderProps) {
  const t = useTranslations("gate");
  const nameKey = GATE_NAME_KEYS[gate.gate_number] ?? "gate1Name";

  return (
    <div
      className="sg-brand-surface rounded-t-2xl border-b border-sg-border px-6 py-5 dark:border-slate-800"
      data-testid="gate-header"
    >
      <div className="flex items-start gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sg-teal text-white shadow-sg-card">
          <ShieldCheck className="h-5 w-5" aria-hidden="true" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold tracking-tight text-sg-navy dark:text-slate-100">
              {(t as (key: string, values?: Record<string, unknown>) => string)(
                "title",
                { number: gate.gate_number },
              )}
            </h2>
            <Badge variant="warning">{t("reviewRequired")}</Badge>
          </div>
          <p className="mt-1 text-sm text-sg-slate/70 dark:text-slate-300">{t(nameKey)}</p>
        </div>
      </div>

      {gate.prompt && (
        <div className="mt-4 rounded-xl border border-sg-border/70 bg-white/75 p-4 dark:border-slate-800 dark:bg-slate-950/65">
          <p className="text-sm text-sg-slate dark:text-slate-200">{gate.prompt}</p>
        </div>
      )}
    </div>
  );
}
