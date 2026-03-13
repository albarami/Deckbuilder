/**
 * StageTracker — Vertical progress bar showing the 5 pipeline stages.
 *
 * Each stage shows: complete (checkmark), running (spinner), or pending (circle).
 * Stages are derived from the SSE event stream and pipeline status.
 *
 * The 5 stages map to the pipeline's gate structure:
 * 1. Context Analysis (Gate 1)
 * 2. Source Research (Gate 2)
 * 3. Report Generation (Gate 3)
 * 4. Slide Rendering (Gate 4)
 * 5. Quality Assurance (Gate 5)
 */

"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import type { GateRecord } from "@/lib/types/pipeline";

// ── Types ──────────────────────────────────────────────────────────────

export type StageState = "complete" | "running" | "pending" | "error";

export interface StageInfo {
  id: string;
  labelKey: string;
  gateNumber: number;
  state: StageState;
}

export interface StageTrackerProps {
  /** Current pipeline stage from store */
  currentStage: string;
  /** Pipeline status */
  status: string;
  /** Completed gates */
  completedGates: GateRecord[];
  /** Error info */
  error: { agent: string; message: string } | null;
}

// ── Stage Definitions ──────────────────────────────────────────────────

const STAGE_DEFS = [
  { id: "context", labelKey: "stages.context", gateNumber: 1, stageKeys: ["intake", "context_analysis", "context"] },
  { id: "sources", labelKey: "stages.sources", gateNumber: 2, stageKeys: ["source_research", "sources"] },
  { id: "report", labelKey: "stages.report", gateNumber: 3, stageKeys: ["report_generation", "report"] },
  { id: "slides", labelKey: "stages.slides", gateNumber: 4, stageKeys: ["slide_rendering", "slides", "rendering"] },
  { id: "qa", labelKey: "stages.qa", gateNumber: 5, stageKeys: ["quality_assurance", "qa", "finalized"] },
];

// ── Component ──────────────────────────────────────────────────────────

export function StageTracker({
  currentStage,
  status,
  completedGates,
  error,
}: StageTrackerProps) {
  const t = useTranslations("pipeline");

  const stages = useMemo((): StageInfo[] => {
    const completedGateNumbers = new Set(
      completedGates.map((g) => g.gate_number),
    );

    return STAGE_DEFS.map((def) => {
      let state: StageState = "pending";

      // Check if this stage's gate has been completed
      if (completedGateNumbers.has(def.gateNumber)) {
        state = "complete";
      }
      // Check if the current stage matches this definition
      else if (def.stageKeys.includes(currentStage)) {
        if (status === "error") {
          state = "error";
        } else if (status === "running" || status === "gate_pending") {
          state = "running";
        }
      }
      // If pipeline is complete and we haven't marked it yet
      else if (status === "complete" || status === "error") {
        // Check if this stage comes before the current/error stage
        const currentIdx = STAGE_DEFS.findIndex((d) =>
          d.stageKeys.includes(currentStage),
        );
        const thisIdx = STAGE_DEFS.indexOf(def);
        if (thisIdx < currentIdx) {
          state = "complete";
        }
        if (status === "complete" && currentStage === "finalized") {
          state = "complete";
        }
      }

      return {
        id: def.id,
        labelKey: def.labelKey,
        gateNumber: def.gateNumber,
        state,
      };
    });
  }, [currentStage, status, completedGates]);

  return (
    <div className="space-y-1" role="list" aria-label={t("stageTracker")}>
      {stages.map((stage, idx) => (
        <StageItem
          key={stage.id}
          stage={stage}
          isLast={idx === stages.length - 1}
          t={t}
        />
      ))}
    </div>
  );
}

// ── StageItem ──────────────────────────────────────────────────────────

function StageItem({
  stage,
  isLast,
  t,
}: {
  stage: StageInfo;
  isLast: boolean;
  t: (key: string) => string;
}) {
  return (
    <div className="flex gap-3" role="listitem" data-testid={`stage-${stage.id}`}>
      {/* Icon column with connecting line */}
      <div className="flex flex-col items-center">
        <StageIcon state={stage.state} />
        {!isLast && (
          <div
            className={[
              "w-0.5 flex-1 min-h-[20px]",
              stage.state === "complete" ? "bg-emerald-400" : "bg-sg-border",
            ].join(" ")}
          />
        )}
      </div>

      {/* Label */}
      <div className="pb-4">
        <p
          className={[
            "text-sm font-medium",
            stage.state === "complete"
              ? "text-emerald-700"
              : stage.state === "running"
                ? "text-sg-blue font-semibold"
                : stage.state === "error"
                  ? "text-red-600"
                  : "text-sg-slate/50",
          ].join(" ")}
        >
          {t(stage.labelKey)}
        </p>
        <p className="text-xs text-sg-slate/50">
          {(t as (key: string, values?: Record<string, unknown>) => string)("stageGate", { number: stage.gateNumber })}
        </p>
      </div>
    </div>
  );
}

// ── StageIcon ──────────────────────────────────────────────────────────

function StageIcon({ state }: { state: StageState }) {
  switch (state) {
    case "complete":
      return (
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500">
          <svg viewBox="0 0 12 12" fill="none" className="h-3.5 w-3.5">
            <path
              d="M3 6L5.5 8.5L9 3.5"
              stroke="white"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      );
    case "running":
      return (
        <div className="flex h-6 w-6 items-center justify-center">
          <Spinner size="sm" label="Stage running" />
        </div>
      );
    case "error":
      return (
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-red-500">
          <svg viewBox="0 0 12 12" fill="none" className="h-3.5 w-3.5">
            <path
              d="M3 3L9 9M9 3L3 9"
              stroke="white"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </div>
      );
    case "pending":
    default:
      return (
        <div className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-sg-border bg-sg-white" />
      );
  }
}
