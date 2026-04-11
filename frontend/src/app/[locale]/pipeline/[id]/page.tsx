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

import { type ReactNode, useCallback, useEffect, useState } from "react";
import { AlertTriangle, Clock3, Sparkles, Workflow } from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { usePipeline } from "@/hooks/use-pipeline";
import { useSSE } from "@/hooks/use-sse";
import { useIsPptEnabled } from "@/hooks/use-is-ppt-enabled";
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
import { downloadDocx } from "@/lib/api/export";
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

  // Session state is managed server-side via SessionManager.
  // No client-side sessionStorage mirroring needed.

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
        onCancel={pipeline.cancel}
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
            completedGates={pipeline.completedGates}
            outputs={pipeline.outputs}
            error={pipeline.error}
            llmCalls={pipeline.sessionMetadata.total_llm_calls}
            totalCostUsd={pipeline.sessionMetadata.total_cost_usd}
            events={pipeline.events}
            isSourceBookGatePending={pipeline.isSourceBookGatePending}
            isSourceBookReadyCheckpoint={pipeline.isSourceBookReadyCheckpoint}
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
  completedGates: { gate_number: number; approved: boolean }[];
  outputs: PipelineOutputs | null;
  error: { agent: string; message: string } | null;
  llmCalls: number;
  totalCostUsd: number;
  events: Array<{ gate_number?: number | null; gate_data?: unknown | null }>;
  isSourceBookGatePending: boolean;
  isSourceBookReadyCheckpoint: boolean;
}

function PipelinePrimaryPanel({
  sessionId,
  status,
  currentStage,
  currentGate,
  completedGates,
  outputs,
  error,
  llmCalls,
  totalCostUsd,
  events,
  isSourceBookGatePending,
  isSourceBookReadyCheckpoint,
}: PipelinePrimaryPanelProps) {
  const t = useTranslations("pipeline");
  const isPptEnabled = useIsPptEnabled();
  const latestSourceBookSummary =
    extractSourceBookSummary(currentGate?.gate_data) ??
    extractSourceBookSummaryFromEvents(events);

  if (status === "gate_pending" && currentGate) {
    if (currentGate.gate_number === 3 && isSourceBookGatePending) {
      return (
        <div className="space-y-4">
          <SourceBookCheckpointCard
            sessionId={sessionId}
            title={t("gatePendingTitle", { number: 3 })}
            summary={latestSourceBookSummary}
          />
          <GatePanel gate={currentGate} />
        </div>
      );
    }
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

  if (!isPptEnabled && isSourceBookReadyCheckpoint) {
    return (
      <SourceBookCheckpointCard
        sessionId={sessionId}
        title={t("sourceBook.readyTitle")}
        summary={latestSourceBookSummary}
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
          value={
            status === "running"
              ? t("metricLive")
              : completedGates.some((gate) => gate.gate_number === 3 && gate.approved)
                ? t("sourceBook.readyTitle")
                : t("metricReview")
          }
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

function SourceBookCheckpointCard({
  sessionId,
  title,
  summary,
}: {
  sessionId: string;
  title: string;
  summary: SourceBookSummary | null;
}) {
  const t = useTranslations("sourceBook");
  const tExport = useTranslations("export");
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = useCallback(async () => {
    setError(null);
    setIsDownloading(true);
    try {
      await downloadDocx(sessionId);
    } catch {
      setError(tExport("downloadError"));
    } finally {
      setIsDownloading(false);
    }
  }, [sessionId, tExport]);

  return (
    <Card variant="elevated" className="space-y-4 rounded-2xl dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-sg-navy dark:text-slate-100">{title}</h3>
          <p className="text-sm text-sg-slate/70 dark:text-slate-300">{t("readyTitle")}</p>
        </div>
        <Button
          variant="primary"
          size="md"
          onClick={handleDownload}
          loading={isDownloading}
          disabled={isDownloading}
          className="bg-sg-teal hover:bg-sg-navy"
          data-testid="source-book-session-docx-btn"
        >
          {t("downloadDocxNow")}
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard
          icon={<Sparkles className="h-4 w-4" aria-hidden="true" />}
          label={t("sectionPreview")}
          value={summary ? String(summary.sectionCount) : "0"}
        />
        <MetricCard
          icon={<Workflow className="h-4 w-4" aria-hidden="true" />}
          label={t("evidenceSummary")}
          value={summary ? String(summary.evidenceCount) : "0"}
        />
        <MetricCard
          icon={<Clock3 className="h-4 w-4" aria-hidden="true" />}
          label={t("wordCount")}
          value={summary ? String(summary.wordCount) : "0"}
        />
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
    </Card>
  );
}

interface SourceBookSummary {
  sectionCount: number;
  wordCount: number;
  evidenceCount: number;
}

function extractSourceBookSummary(gateData: unknown): SourceBookSummary | null {
  if (!gateData || typeof gateData !== "object") return null;
  const data = gateData as Record<string, unknown>;

  if (!Array.isArray(data.sections)) return null;

  const quality = toRecord(data.quality_summary);
  const evidence = toRecord(data.evidence_summary);

  return {
    sectionCount: typeof data.section_count === "number" ? data.section_count : data.sections.length,
    wordCount: typeof data.total_word_count === "number" ? data.total_word_count : 0,
    evidenceCount:
      (typeof quality?.evidence_count === "number" && quality.evidence_count) ||
      (typeof evidence?.evidence_ledger_entries === "number" && evidence.evidence_ledger_entries) ||
      0,
  };
}

function extractSourceBookSummaryFromEvents(
  events: Array<{ gate_number?: number | null; gate_data?: unknown | null }>,
): SourceBookSummary | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (event.gate_number === 3) {
      const summary = extractSourceBookSummary(event.gate_data);
      if (summary) return summary;
    }
  }
  return null;
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
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
    case "evidence_curation":
    case "proposal_strategy":
    case "report_generation":
    case "report":
    case "source_book_generation":
    case "source_book":
    case "source_book_review":
      return t("stages.sourceBook");
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
