/**
 * Pipeline session page — dispatches view by pipeline status.
 *
 * On mount:
 * 1. Extracts session_id from URL
 * 2. Calls GET /status to restore state (session resume)
 * 3. Connects SSE for real-time updates
 *
 * Renders different content based on status:
 * - idle/loading: loading spinner
 * - running: StageTracker + AgentStatusCard
 * - gate_pending: StageTracker + gate info (M11.6 placeholder)
 * - complete: PipelineComplete
 * - error: PipelineErrorBanner
 * - not found: session expired message
 */

"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { usePipeline } from "@/hooks/use-pipeline";
import { useSSE } from "@/hooks/use-sse";
import { PipelineHeader } from "@/components/pipeline/PipelineHeader";
import { StageTracker } from "@/components/pipeline/StageTracker";
import { AgentStatusCard } from "@/components/pipeline/AgentStatusCard";
import { PipelineErrorBanner } from "@/components/pipeline/PipelineErrorBanner";
import { PipelineComplete } from "@/components/pipeline/PipelineComplete";
import { GatePanel } from "@/components/gates/GatePanel";
import { Spinner } from "@/components/ui/Spinner";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Link } from "@/i18n/routing";

export default function PipelineSessionPage() {
  const t = useTranslations("pipeline");
  const params = useParams<{ id: string }>();
  const sessionId = params.id;

  const pipeline = usePipeline();
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  // Connect SSE when pipeline is running or gate_pending
  const sseEnabled =
    pipeline.status === "running" || pipeline.status === "gate_pending";
  useSSE({
    sessionId: pipeline.sessionId,
    enabled: sseEnabled,
  });

  // On mount: restore session from backend
  useEffect(() => {
    async function restoreSession() {
      if (!sessionId) return;

      // If we already have this session loaded, skip restore
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

  // Save session to sessionStorage for dashboard
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

  // ── Loading state ──────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" label={t("loading")} />
          <p className="mt-4 text-sm text-sg-slate/60">{t("loading")}</p>
        </div>
      </div>
    );
  }

  // ── Not found state ────────────────────────────────────────────────

  if (notFound) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Card variant="default" className="max-w-md text-center">
          <div className="flex justify-center">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="h-12 w-12 text-sg-slate/30"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
              />
            </svg>
          </div>
          <h2 className="mt-4 text-lg font-semibold text-sg-navy">
            {t("sessionExpired")}
          </h2>
          <p className="mt-2 text-sm text-sg-slate/70">
            {t("sessionExpiredMessage")}
          </p>
          <Link href="/new">
            <Button variant="primary" size="md" className="mt-4">
              {t("startNewProposal")}
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  // ── Main pipeline view ─────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <PipelineHeader
        sessionId={pipeline.sessionId ?? sessionId}
        status={pipeline.status}
        startedAt={pipeline.startedAt}
        elapsedMs={pipeline.elapsedMs}
      />

      {/* Error banner */}
      {pipeline.error && pipeline.status === "error" && (
        <PipelineErrorBanner error={pipeline.error} />
      )}

      {/* Two-column layout: stage tracker + content */}
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Left column: Stage tracker */}
        <div className="w-full lg:w-64 lg:flex-shrink-0">
          <Card variant="flat">
            <StageTracker
              currentStage={pipeline.currentStage}
              status={pipeline.status}
              completedGates={pipeline.completedGates}
              error={pipeline.error}
            />
          </Card>
        </div>

        {/* Right column: Status-dependent content */}
        <div className="flex-1 space-y-4">
          {/* Running: agent status */}
          {pipeline.status === "running" && (
            <AgentStatusCard
              events={pipeline.events}
              status={pipeline.status}
            />
          )}

          {/* Gate pending: gate approval UI */}
          {pipeline.status === "gate_pending" && pipeline.currentGate && (
            <GatePanel gate={pipeline.currentGate} />
          )}

          {/* Complete: export buttons */}
          {pipeline.status === "complete" && pipeline.outputs && (
            <PipelineComplete
              sessionId={pipeline.sessionId ?? sessionId}
              outputs={pipeline.outputs}
            />
          )}

          {/* Idle (shouldn't normally happen on this page) */}
          {pipeline.status === "idle" && (
            <Card variant="flat" className="text-center">
              <p className="text-sg-slate/60">{t("waitingForPipeline")}</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
