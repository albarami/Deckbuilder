"use client";

import { useMemo } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import type { SSEEvent } from "@/lib/types/pipeline";

interface ActivityTimelineProps {
  events: SSEEvent[];
  startedAt: string | null;
}

type ActivityTone = "done" | "active" | "gate" | "error" | "info";

interface ActivityItem {
  id: string;
  label: string;
  timestamp: string;
  tone: ActivityTone;
  meta?: string;
}

export function ActivityTimeline({
  events,
  startedAt,
}: ActivityTimelineProps) {
  const t = useTranslations("pipeline");
  const locale = useLocale();

  const items = useMemo<ActivityItem[]>(() => {
    const derivedItems = events
      .filter((event) => event.type !== "heartbeat")
      .map((event, index) => mapEventToItem(event, index, t))
      .filter((item): item is ActivityItem => item !== null);

    if (startedAt) {
      derivedItems.push({
        id: "pipeline-started",
        label: t("timelinePipelineStarted"),
        timestamp: startedAt,
        tone: "info",
      });
    }

    return derivedItems
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 12);
  }, [events, startedAt, t]);

  return (
    <Card
      variant="default"
      noPadding
      className="overflow-hidden rounded-2xl shadow-sg-card dark:border-slate-800 dark:bg-slate-900"
      data-testid="activity-timeline"
    >
      <div className="flex items-center justify-between border-b border-sg-border px-5 py-4 dark:border-slate-800">
        <h3 className="text-sm font-semibold tracking-tight text-sg-navy dark:text-slate-100">
          {t("activityTimeline")}
        </h3>
        <span className="rounded-full bg-sg-mist px-2.5 py-1 font-mono text-[11px] text-sg-slate/55 dark:bg-slate-950 dark:text-slate-400">
          {items.length}
        </span>
      </div>

      {items.length === 0 ? (
        <p className="px-5 py-5 text-sm text-sg-slate/60 dark:text-slate-400">{t("activityEmpty")}</p>
      ) : (
        <div className="divide-y divide-sg-border/60 dark:divide-slate-800">
          {items.map((item) => (
            <div
              key={item.id}
              className="sg-interactive flex gap-3 px-5 py-3"
              data-testid={`activity-item-${item.id}`}
            >
              <span
                className={[
                  "mt-1.5 inline-flex h-2.5 w-2.5 rounded-full",
                  toneClassName(item.tone),
                ].join(" ")}
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-sg-navy dark:text-slate-100">{item.label}</p>
                <p className="mt-1 text-xs text-sg-slate/55 dark:text-slate-400">
                  {formatRelativeTime(item.timestamp, locale)}
                  {item.meta ? ` · ${item.meta}` : ""}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function mapEventToItem(
  event: SSEEvent,
  index: number,
  t: (key: string, values?: Record<string, string | number>) => string,
): ActivityItem | null {
  switch (event.type) {
    case "stage_change": {
      const stageLabel = formatStageLabel(event.stage, t);
      const isLongStage = event.stage === "evidence_curation" || event.stage === "source_book_generation";
      return {
        id: `stage-${index}`,
        label: isLongStage
          ? `${t("timelineStageChanged", { stage: stageLabel })} ${t("longStageHint")}`
          : t("timelineStageChanged", { stage: stageLabel }),
        timestamp: event.timestamp,
        tone: "info",
      };
    }
    case "agent_start":
      return {
        id: `agent-start-${index}`,
        label: t("timelineAgentStarted", {
          agent: formatBackendAgentName(event.agent, t),
        }),
        timestamp: event.timestamp,
        tone: "active",
      };
    case "agent_complete":
      return {
        id: `agent-complete-${index}`,
        label: t("timelineAgentCompleted", {
          agent: formatBackendAgentName(event.agent, t),
        }),
        timestamp: event.timestamp,
        tone: "done",
        meta: event.duration_ms ? formatDuration(event.duration_ms) : undefined,
      };
    case "gate_pending":
      return {
        id: `gate-${index}`,
        label: t("timelineGatePending", {
          number: event.gate_number ?? 0,
        }),
        timestamp: event.timestamp,
        tone: "gate",
      };
    case "pipeline_complete":
      return {
        id: `complete-${index}`,
        label: t("timelinePipelineComplete"),
        timestamp: event.timestamp,
        tone: "done",
      };
    case "pipeline_error":
      return {
        id: `error-${index}`,
        label: t("timelinePipelineError"),
        timestamp: event.timestamp,
        tone: "error",
        meta: event.error ?? undefined,
      };
    case "render_progress":
      return {
        id: `render-${index}`,
        label: t("timelineRenderProgress", {
          current: event.slide_index ?? 0,
          total: event.total ?? 0,
        }),
        timestamp: event.timestamp,
        tone: "active",
      };
    default:
      return null;
  }
}

function toneClassName(tone: ActivityTone): string {
  switch (tone) {
    case "done":
      return "bg-emerald-500";
    case "active":
      return "bg-sg-blue animate-pulse";
    case "gate":
      return "bg-sg-orange";
    case "error":
      return "bg-red-500";
    case "info":
    default:
      return "bg-sg-border";
  }
}

function formatStageLabel(
  stage: string | undefined,
  t: (key: string) => string,
): string {
  switch (stage) {
    case "intake":
    case "context_analysis":
    case "context":
      return t("stages.context");
    case "source_research":
    case "sources":
      return t("stages.sources");
    case "report_generation":
    case "report":
      return t("stages.report");
    case "slide_rendering":
    case "slides":
    case "rendering":
      return t("stages.slides");
    case "quality_assurance":
    case "qa":
    case "finalized":
      return t("stages.qa");
    case "evidence_curation":
      return t("stages.evidenceCuration");
    case "proposal_strategy":
      return t("stages.proposalStrategy");
    case "source_book_generation":
      return t("stages.sourceBookGeneration");
    case "source_book_review":
      return t("stages.sourceBookReview");
    default:
      return formatSnakeCase(stage ?? "Unknown stage");
  }
}

function formatBackendAgentName(
  agent: string | undefined,
  t: (key: string) => string,
): string {
  switch (agent) {
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
      return formatSnakeCase(agent ?? "Unknown agent");
  }
}

function formatSnakeCase(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatDuration(durationMs: number): string {
  const totalSeconds = Math.max(1, Math.round(durationMs / 1000));
  if (totalSeconds < 60) return `${totalSeconds}s`;

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

function formatRelativeTime(timestamp: string, locale: string): string {
  const diffSeconds = Math.round((new Date(timestamp).getTime() - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  const intervals: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
    ["second", 1],
  ];

  for (const [unit, size] of intervals) {
    if (Math.abs(diffSeconds) >= size || unit === "second") {
      return rtf.format(Math.round(diffSeconds / size), unit);
    }
  }

  return new Date(timestamp).toLocaleTimeString(locale);
}
