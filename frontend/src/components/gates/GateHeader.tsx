/**
 * GateHeader — Gate title bar with gate number and review prompt.
 *
 * Displays the gate number, translated title, and the AI-provided
 * review prompt that guides the consultant's decision.
 */

"use client";

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
    <div data-testid="gate-header">
      <div className="flex items-center gap-3">
        {/* Gate number circle */}
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100">
          <span className="text-lg font-bold text-amber-700">
            {gate.gate_number}
          </span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-sg-navy">
              {(t as (key: string, values?: Record<string, unknown>) => string)(
                "title",
                { number: gate.gate_number },
              )}
            </h2>
            <Badge variant="warning">{t("reviewRequired")}</Badge>
          </div>
          <p className="text-sm text-sg-slate/70">{t(nameKey)}</p>
        </div>
      </div>

      {/* Review prompt from the AI */}
      {gate.prompt && (
        <div className="mt-3 rounded-lg bg-sg-mist/50 p-3">
          <p className="text-sm text-sg-slate">{gate.prompt}</p>
        </div>
      )}
    </div>
  );
}
