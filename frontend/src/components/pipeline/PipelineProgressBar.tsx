"use client";

import { useMemo } from "react";
import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useIsPptEnabled } from "@/hooks/use-is-ppt-enabled";
import type { GateInfo, GateRecord, PipelineStatus } from "@/lib/types/pipeline";

interface PipelineProgressBarProps {
  currentStage: string;
  status: PipelineStatus | "idle";
  completedGates: GateRecord[];
  currentGate: GateInfo | null;
}

type StageId = "context" | "sources" | "sourceBook" | "slides" | "qa";

interface StageDefinition {
  id: StageId;
  gateNumber: number;
  labelKey: string;
  stageKeys: string[];
}

const STAGES: StageDefinition[] = [
  {
    id: "context",
    gateNumber: 1,
    labelKey: "stages.context",
    stageKeys: ["intake", "context_analysis", "context"],
  },
  {
    id: "sources",
    gateNumber: 2,
    labelKey: "stages.sources",
    stageKeys: ["source_research", "sources"],
  },
  {
    id: "sourceBook",
    gateNumber: 3,
    labelKey: "stages.sourceBook",
    stageKeys: [
      "report_generation", "report", "source_book_generation", "source_book",
      "evidence_curation", "proposal_strategy", "source_book_review",
    ],
  },
  {
    id: "slides",
    gateNumber: 4,
    labelKey: "stages.slides",
    stageKeys: ["slide_rendering", "slides", "rendering"],
  },
  {
    id: "qa",
    gateNumber: 5,
    labelKey: "stages.qa",
    stageKeys: ["quality_assurance", "qa", "finalized"],
  },
];

export function PipelineProgressBar({
  currentStage,
  status,
  completedGates,
  currentGate,
}: PipelineProgressBarProps) {
  const t = useTranslations("pipeline");
  const isPptEnabled = useIsPptEnabled();
  const visibleStages = useMemo(
    () => (isPptEnabled ? STAGES : STAGES.slice(0, 3)),
    [isPptEnabled],
  );

  const activeStageId = useMemo<StageId>(() => {
    if (status === "gate_pending" && currentGate) {
      if (!isPptEnabled && currentGate.gate_number >= 3) return "sourceBook";
      return stageIdFromGate(currentGate.gate_number);
    }

    if (currentStage === "finalized" || status === "complete") {
      return isPptEnabled ? "qa" : "sourceBook";
    }

    const matchedStage = STAGES.find((stage) =>
      stage.stageKeys.includes(currentStage),
    );

    return matchedStage?.id ?? "context";
  }, [currentGate, currentStage, isPptEnabled, status]);

  const activeIndex = visibleStages.findIndex((stage) => stage.id === activeStageId);
  const completedGateNumbers = new Set(completedGates.map((gate) => gate.gate_number));

  return (
    <section
      aria-label={t("stageTracker")}
      className="overflow-hidden rounded-2xl border border-sg-border bg-sg-white shadow-sg-card dark:border-slate-800 dark:bg-slate-900"
    >
      <div
        className={[
          "grid gap-px bg-sg-border dark:bg-slate-800 sm:grid-cols-2",
          isPptEnabled ? "xl:grid-cols-5" : "xl:grid-cols-3",
        ].join(" ")}
      >
        {visibleStages.map((stage, index) => {
          const isComplete =
            completedGateNumbers.has(stage.gateNumber) ||
            status === "complete" ||
            (status !== "idle" && index < activeIndex);
          const isActive = !isComplete && index === activeIndex;
          const stateClass = isComplete
            ? "sg-stage-complete"
            : isActive
              ? "sg-stage-active"
              : "sg-stage-pending";

          const subtitle = isComplete
            ? t("complete")
            : isActive
              ? status === "gate_pending"
                ? t("gatePending")
                : t("running")
              : t("stageGate", { number: stage.gateNumber });

          return (
            <div
              key={stage.id}
              className={`min-h-[104px] px-5 py-4 ${stateClass}`}
              data-testid={`pipeline-stage-${stage.id}`}
            >
              <div className="flex h-full items-start gap-3">
                <div
                  className={[
                    "flex h-9 w-9 items-center justify-center rounded-full border text-sm font-bold",
                    isComplete
                      ? "border-white/15 bg-white/10 text-white"
                      : isActive
                        ? "border-transparent bg-sg-blue text-white shadow-sg-glow-blue"
                        : "border-sg-border bg-sg-mist text-sg-slate/60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300",
                  ].join(" ")}
                >
                  {isComplete ? <Check className="h-4 w-4" aria-hidden="true" /> : stage.gateNumber}
                </div>

                <div className="min-w-0">
                  <p
                    className={[
                      "truncate text-sm font-semibold tracking-tight",
                      isComplete || isActive ? "text-white" : "text-sg-navy dark:text-slate-100",
                    ].join(" ")}
                  >
                    {t(stage.labelKey)}
                  </p>
                  <p
                    className={[
                      "mt-1 text-xs",
                      isComplete
                        ? "text-white/65"
                        : isActive
                          ? "text-white/75"
                          : "text-sg-slate/55 dark:text-slate-400",
                    ].join(" ")}
                  >
                    {subtitle}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {!isPptEnabled ? (
        <div className="border-t border-sg-border bg-sg-mist/45 px-5 py-2 text-xs text-sg-slate/65 dark:border-slate-800 dark:bg-slate-950/70 dark:text-slate-300">
          {t("sourceBook.pptComingSoon")}
        </div>
      ) : null}
    </section>
  );
}

function stageIdFromGate(gateNumber: number): StageId {
  switch (gateNumber) {
    case 1:
      return "context";
    case 2:
      return "sources";
    case 3:
      return "sourceBook";
    case 4:
      return "slides";
    case 5:
    default:
      return "qa";
  }
}
