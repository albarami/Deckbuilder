"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import type { AgentRunInfo } from "@/lib/types/pipeline";
import { usePipelineStore } from "@/stores/pipeline-store";

interface AgentStatusGridProps {
  agentRuns: AgentRunInfo[];
}

const AGENT_ORDER = [
  "context_agent",
  "retrieval_planner",
  "retrieval_ranker",
  "analysis_agent",
  "research_agent",
  "draft_agent",
  "review_agent",
  "refine_agent",
  "final_review_agent",
  "presentation_agent",
  "qa_agent",
] as const;

const SB_AGENT_ORDER = [
  "context_agent",
  "retrieval_planner",
  "retrieval_ranker",
  "evidence_curator",
  "routing_agent",
  "proposal_strategist",
  "sb_writer",
  "sb_reviewer",
  "sb_evidence_extractor",
];

export function AgentStatusGrid({ agentRuns }: AgentStatusGridProps) {
  const t = useTranslations("pipeline");
  const proposalMode = usePipelineStore((s) => s.proposalMode);

  const agentOrder = proposalMode === "source_book_only" ? SB_AGENT_ORDER : AGENT_ORDER;

  const orderedRuns = useMemo(() => {
    const byKey = new Map(agentRuns.map((run) => [run.agent_key, run]));
    return agentOrder.map((key) => byKey.get(key)).filter(
      (run): run is AgentRunInfo => Boolean(run),
    );
  }, [agentRuns, agentOrder]);

  const completeCount = orderedRuns.filter((run) => run.status === "complete").length;
  const activeCount = orderedRuns.filter((run) => run.status === "running").length;
  const waitingCount = orderedRuns.filter((run) => run.status === "waiting").length;

  return (
    <section className="space-y-4" data-testid="agent-status-grid">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-sg-navy dark:text-slate-100">
            {t("agentStatus")}
          </h3>
          <p className="mt-1 text-xs text-sg-slate/60 dark:text-slate-400">
            {t("agentSummary", {
              complete: completeCount,
              active: activeCount,
              waiting: waitingCount,
            })}
          </p>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {orderedRuns.map((run) => (
          <Card
            key={run.agent_key}
            variant="default"
            className={[
              "relative overflow-hidden border border-sg-border p-4 dark:border-slate-800 dark:bg-slate-900",
              run.status === "waiting" && "opacity-55",
              run.status === "running" && "sg-agent-active",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span
              className={[
                "absolute inset-x-0 top-0 h-1",
                run.status === "complete"
                  ? "bg-sg-navy"
                  : run.status === "running"
                    ? "animate-shimmer-bar bg-[linear-gradient(90deg,#156082,#0F9ED5,#156082)] bg-[length:200%_100%]"
                    : "bg-sg-border dark:bg-slate-800",
              ].join(" ")}
            />

            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-sg-navy dark:text-slate-100">
                  {mapAgentLabel(run.agent_key, t)}
                </p>
                <p className="mt-1 font-mono text-[11px] text-sg-slate/55 dark:text-slate-400">
                  {run.model}
                </p>
              </div>
              <span
                className={[
                  "rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]",
                  run.status === "complete"
                    ? "bg-sg-navy/10 text-sg-navy"
                    : run.status === "running"
                      ? "bg-sg-blue/10 text-sg-blue"
                      : run.status === "error"
                        ? "bg-red-50 text-red-700"
                        : "bg-sg-mist text-sg-slate/60 dark:bg-slate-950 dark:text-slate-400",
                ].join(" ")}
              >
                {run.status === "complete"
                  ? t("statusDone")
                  : run.status === "running"
                    ? t("statusActive")
                    : run.status === "error"
                      ? t("error")
                      : t("statusWaiting")}
              </span>
            </div>

            <div
              className={[
                "mt-4 rounded-lg px-3 py-2 text-xs",
                run.status === "waiting"
                  ? "border border-dashed border-sg-border bg-transparent dark:border-slate-800"
                  : "bg-sg-mist/80 dark:bg-slate-950/70",
              ].join(" ")}
            >
              <div className="flex items-center gap-3">
                <span className="text-sg-slate/60 dark:text-slate-400">
                  {run.metric_label ?? t("agentMetricReady")}
                </span>
                <span className="ms-auto font-mono font-semibold text-sg-navy dark:text-slate-100">
                  {run.metric_value ?? "—"}
                </span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}

function mapAgentLabel(
  agentKey: string,
  t: (key: string) => string,
): string {
  switch (agentKey) {
    case "context_agent":
      return t("agents.context");
    case "retrieval_planner":
      return t("agents.retrievalPlanner");
    case "retrieval_ranker":
      return t("agents.ranker");
    case "analysis_agent":
      return t("agents.analysis");
    case "research_agent":
      return t("agents.research");
    case "draft_agent":
      return t("agents.draft");
    case "review_agent":
      return t("agents.review");
    case "refine_agent":
      return t("agents.refine");
    case "final_review_agent":
      return t("agents.finalReview");
    case "presentation_agent":
      return t("agents.presentation");
    case "qa_agent":
      return t("agents.qa");
    case "evidence_curator":
      return t("agents.evidenceCurator");
    case "routing_agent":
      return t("agents.routingAgent");
    case "proposal_strategist":
      return t("agents.proposalStrategist");
    case "sb_writer":
      return t("agents.sbWriter");
    case "sb_reviewer":
      return t("agents.sbReviewer");
    case "sb_evidence_extractor":
      return t("agents.sbEvidenceExtractor");
    default:
      return agentKey;
  }
}
