/**
 * Pipeline session page — hero view for the end-to-end proposal workflow.
 *
 * On mount:
 * 1. Extracts session_id from URL
 * 2. Calls GET /status to restore state (session resume)
 * 3. Connects SSE for real-time updates
 *
 * Renders different content based on status:
 * - idle/loading: loading spinner
 * - running: active stage detail + live activity timeline
 * - gate_pending: gate review UI + live activity timeline
 * - complete: export actions + live activity timeline
 * - error: error state + live activity timeline
 * - not found: session expired message
 */

"use client";

import { type ReactNode, useEffect, useState } from "react";
import { AlertTriangle, Clock3, Sparkles, Workflow } from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { usePipeline } from "@/hooks/use-pipeline";
import { useSSE } from "@/hooks/use-sse";
import { PipelineHeader } from "@/components/pipeline/PipelineHeader";
import { PipelineProgressBar } from "@/components/pipeline/PipelineProgressBar";
import { ActivityTimeline } from "@/components/pipeline/ActivityTimeline";
import { AgentStatusGrid } from "@/components/pipeline/AgentStatusGrid";
import { JourneyLegend } from "@/components/pipeline/JourneyLegend";
import { PipelineErrorBanner } from "@/components/pipeline/PipelineErrorBanner";
import { PipelineComplete } from "@/components/pipeline/PipelineComplete";
import { GatePanel } from "@/components/gates/GatePanel";
import { Spinner } from "@/components/ui/Spinner";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Link } from "@/i18n/routing";
import type { GateInfo, PipelineOutputs, PipelineStatus } from "@/lib/types/pipeline";

export default function PipelineSessionPage() {
  const t = useTranslations("pipeline");
  const params = useParams<{ id: string }>();
  const sessionId = params.id;

  const pipeline = usePipeline();
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const sseEnabled =
    pipeline.status === "running" || pipeline.status === "gate_pending";

  useSSE({
    sessionId: pipeline.sessionId,
    enabled: sseEnabled,
  });

  useEffect(() => {
    async function restoreSession() {
      if (!sessionId) return;

      if (pipeline.sessionId === sessionId && pipeline.status !== "idle") {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      const found = await pipeline.resume(sessionId);
      if (!found) {
        setNotFound(true);
      }
      setIsLoading(false);
    }

    restoreSession();
    // Only run once on mount with this session_id
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    if (pipeline.sessionId && pipeline.status !== "idle") {
      try {
        sessionStorage.setItem(
          `deckforge_session_${pipeline.sessionId}`,
          JSON.stringify({
            status: pipeline.status,
            startedAt: pipeline.startedAt,
          }),
        );
      } catch {
        // sessionStorage may be unavailable
      }
    }
  }, [pipeline.sessionId, pipeline.status, pipeline.startedAt]);

  if (isLoading) {
    return (
      <div className="flex min-h-[420px] items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" label={t("loading")} />
          <p className="mt-4 text-sm text-sg-slate/60">{t("loading")}</p>
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="flex min-h-[420px] items-center justify-center">
        <Card variant="default" className="max-w-md rounded-2xl text-center shadow-sg-card">
          <div className="flex justify-center">
            <div className="rounded-full bg-sg-mist p-4">
              <AlertTriangle
                className="h-10 w-10 text-sg-slate/35"
                aria-hidden="true"
              />
            </div>
          </div>
          <h2 className="mt-4 text-lg font-semibold text-sg-navy">
            {t("sessionExpired")}
          </h2>
          <p className="mt-2 text-sm text-sg-slate/70">
            {t("sessionExpiredMessage")}
          </p>
          <Link href="/new">
            <Button variant="primary" size="md" className="mt-4 bg-sg-teal hover:bg-sg-navy">
              {t("startNewProposal")}
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PipelineHeader
        sessionId={pipeline.sessionId ?? sessionId}
        status={pipeline.status}
        startedAt={pipeline.startedAt}
        elapsedMs={pipeline.elapsedMs}
      />

      {pipeline.error && pipeline.status === "error" && (
        <PipelineErrorBanner error={pipeline.error} />
      )}

      <PipelineProgressBar
        currentStage={pipeline.currentStage}
        status={pipeline.status}
        completedGates={pipeline.completedGates}
        currentGate={pipeline.currentGate}
      />

      <JourneyLegend />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_380px]">
        <div className="min-w-0">
          <PipelinePrimaryPanel
            sessionId={pipeline.sessionId ?? sessionId}
            status={pipeline.status}
            currentStage={pipeline.currentStage}
            currentGate={pipeline.currentGate}
            outputs={pipeline.outputs}
            error={pipeline.error}
            llmCalls={pipeline.sessionMetadata.total_llm_calls}
            totalCostUsd={pipeline.sessionMetadata.total_cost_usd}
          />
        </div>

        <ActivityTimeline
          events={pipeline.events}
          startedAt={pipeline.startedAt}
        />
      </div>

      <AgentStatusGrid
        agentRuns={pipeline.agentRuns}
      />
    </div>
  );
}

interface PipelinePrimaryPanelProps {
  sessionId: string;
  status: PipelineStatus | "idle";
  currentStage: string;
  currentGate: GateInfo | null;
  outputs: PipelineOutputs | null;
  error: { agent: string; message: string } | null;
  llmCalls: number;
  totalCostUsd: number;
}

function PipelinePrimaryPanel({
  sessionId,
  status,
  currentStage,
  currentGate,
  outputs,
  error,
  llmCalls,
  totalCostUsd,
}: PipelinePrimaryPanelProps) {
  const t = useTranslations("pipeline");

  if (status === "gate_pending" && currentGate) {
    return <GatePanel gate={currentGate} />;
  }

  if (status === "complete" && outputs) {
    return (
      <PipelineComplete
        sessionId={sessionId}
        outputs={outputs}
      />
    );
  }

  if (status === "error" && error) {
    return (
      <Card variant="elevated" className="space-y-4 rounded-2xl dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-red-100 p-3 text-red-700 dark:bg-red-500/10 dark:text-red-400">
            <Workflow className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-sg-navy dark:text-slate-100">
              {t("errorTitle")}
            </h2>
            <p className="mt-1 text-sm text-sg-slate/70 dark:text-slate-300">{error.message}</p>
          </div>
        </div>
      </Card>
    );
  }

  if (status === "idle") {
    return (
      <Card variant="elevated" className="rounded-2xl dark:border-slate-800 dark:bg-slate-900">
        <p className="text-sm text-sg-slate/60 dark:text-slate-400">{t("waitingForPipeline")}</p>
      </Card>
    );
  }

  return (
    <Card variant="elevated" noPadding className="overflow-hidden rounded-2xl dark:border-slate-800 dark:bg-slate-900">
      <div className="sg-brand-surface border-b border-sg-border px-6 py-5 dark:border-slate-800">
        <div className="flex items-start gap-4">
          <div className="rounded-xl bg-sg-teal p-3 text-white shadow-sg-card">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-sg-navy dark:text-slate-100">
              {formatStageLabel(currentStage, t)}
            </h2>
            <p className="mt-1 text-sm text-sg-slate/70 dark:text-slate-300">
              {status === "running" ? t("running") : t("gatePending")}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 px-6 py-5 sm:grid-cols-3">
        <MetricCard
          icon={<Clock3 className="h-4 w-4" aria-hidden="true" />}
          label={t("metricLlmCalls")}
          value={String(llmCalls)}
        />
        <MetricCard
          icon={<Workflow className="h-4 w-4" aria-hidden="true" />}
          label={t("metricStatus")}
          value={status === "running" ? t("metricLive") : t("metricReview")}
        />
        <MetricCard
          icon={<Sparkles className="h-4 w-4" aria-hidden="true" />}
          label={t("metricCost")}
          value={`$${totalCostUsd.toFixed(2)}`}
        />
      </div>
    </Card>
  );
}

function MetricCard({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-sg-border bg-sg-mist/70 p-4 dark:border-slate-800 dark:bg-slate-950/60">
      <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-sg-slate/55 dark:text-slate-400">
        <span className="text-sg-blue dark:text-sky-300">{icon}</span>
        {label}
      </div>
      <p className="mt-2 text-base font-semibold text-sg-navy dark:text-slate-100">{value}</p>
    </div>
  );
}

function formatStageLabel(
  stage: string,
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
    default:
      return stage
        .split("_")
        .filter(Boolean)
        .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
        .join(" ");
  }
}
