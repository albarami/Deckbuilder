/**
 * GatePanel — Master gate container that dispatches by gate number.
 *
 * Composes:
 * - GateHeader (title, number, prompt)
 * - Gate-specific review panel (Gate1Context through Gate5QA)
 * - GateActions (approve/reject with feedback)
 *
 * Wired to the useGate hook for API integration.
 */

"use client";

import { useState, useCallback } from "react";
import { Card } from "@/components/ui/Card";
import { useTranslations } from "next-intl";
import { useGate } from "@/hooks/use-gate";
import { useIsPptEnabled } from "@/hooks/use-is-ppt-enabled";
import { GateHeader } from "./GateHeader";
import { GateActions } from "./GateActions";
import { Gate1Context } from "./gates/Gate1Context";
import { Gate2Sources, type SourceModifications } from "./gates/Gate2Sources";
import { Gate3Research } from "./gates/Gate3Research";
import { Gate3AssemblyPlan } from "./gates/Gate3AssemblyPlan";
import { Gate3SourceBook } from "./gates/Gate3SourceBook";
import { Gate4Slides } from "./gates/Gate4Slides";
import { Gate5QA } from "./gates/Gate5QA";
import type { GateDecisionRequest, GateInfo } from "@/lib/types/pipeline";

export interface GatePanelProps {
  /** Gate information from the pipeline store */
  gate: GateInfo;
}

export function GatePanel({ gate }: GatePanelProps) {
  const t = useTranslations("sourceBook");
  const tCommon = useTranslations("common");
  const isPptEnabled = useIsPptEnabled();
  const { approve, reject, isDecidingGate } = useGate();
  const [modifications, setModifications] = useState<SourceModifications | null>(null);
  const suppressPptGateReview = !isPptEnabled && (gate.gate_number === 4 || gate.gate_number === 5);

  const handleApprove = useCallback(async () => {
    await approve(modifications as GateDecisionRequest["modifications"]);
  }, [approve, modifications]);

  const handleReject = useCallback(
    async (feedback: string) => {
      await reject(feedback, modifications as GateDecisionRequest["modifications"]);
    },
    [reject, modifications],
  );

  const handleModificationsChange = useCallback(
    (mods: SourceModifications) => {
      setModifications(mods);
    },
    [],
  );

  return (
    <Card
      variant="elevated"
      noPadding
      className="overflow-hidden rounded-2xl shadow-sg-elevated dark:border-slate-800 dark:bg-slate-900"
      data-testid="gate-panel"
    >
      <GateHeader gate={gate} />

      <div className="px-6 py-5">
        <GateContent
          gate={gate}
          onModificationsChange={handleModificationsChange}
        />
      </div>

      {!suppressPptGateReview ? (
        <div className="border-t border-sg-border bg-sg-mist/60 px-6 py-4 dark:border-slate-800 dark:bg-slate-950/70">
          <GateActions
            onApprove={handleApprove}
            onReject={handleReject}
            modifications={modifications}
            isDeciding={isDecidingGate}
          />
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-sg-border bg-sg-mist/60 px-6 py-4 dark:border-slate-800 dark:bg-slate-950/70">
          <p className="text-sm text-sg-slate/70 dark:text-slate-300">{t("pptComingSoon")}</p>
          <button
            type="button"
            onClick={handleApprove}
            disabled={isDecidingGate}
            className="inline-flex items-center rounded-lg bg-sg-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-sg-navy disabled:cursor-not-allowed disabled:opacity-60"
            data-testid="gate-ppt-continue-btn"
          >
            {tCommon("next")}
          </button>
        </div>
      )}
    </Card>
  );
}

// ── Gate Content Dispatcher ─────────────────────────────────────────────

interface GateContentProps {
  gate: GateInfo;
  onModificationsChange: (mods: SourceModifications) => void;
}

function GateContent({ gate, onModificationsChange }: GateContentProps) {
  const t = useTranslations("sourceBook");
  const isPptEnabled = useIsPptEnabled();

  switch (gate.gate_number) {
    case 1:
      return <Gate1Context gate={gate} />;
    case 2:
      return (
        <Gate2Sources
          gate={gate}
          onModificationsChange={onModificationsChange}
        />
      );
    case 3:
      if (gate.payload_type === "source_book_review" || isSourceBookPayload(gate.gate_data)) {
        return <Gate3SourceBook gate={gate} />;
      }
      if (gate.payload_type === "assembly_plan_review") {
        return <Gate3AssemblyPlan gate={gate} />;
      }
      return <Gate3Research gate={gate} />;
    case 4:
      if (!isPptEnabled) return <PptComingSoonPanel message={t("pptComingSoon")} />;
      return <Gate4Slides gate={gate} />;
    case 5:
      if (!isPptEnabled) return <PptComingSoonPanel message={t("pptComingSoon")} />;
      return <Gate5QA gate={gate} />;
    default:
      return (
        <p className="text-sm text-sg-slate/50 italic">
          Unknown gate: {gate.gate_number}
        </p>
      );
  }
}

function PptComingSoonPanel({ message }: { message: string }) {
  return (
    <div
      data-testid="gate-ppt-coming-soon"
      className="rounded-xl border border-sg-border bg-sg-mist/35 px-4 py-4 text-sm text-sg-slate/75 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-300"
    >
      {message}
    </div>
  );
}

function isSourceBookPayload(data: unknown): boolean {
  if (!data || typeof data !== "object") return false;
  const obj = data as Record<string, unknown>;
  return (
    Array.isArray(obj.sections) &&
    typeof obj.total_word_count === "number" &&
    typeof obj.section_count === "number"
  );
}
