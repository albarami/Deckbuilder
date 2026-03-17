/**
 * Export Page — full-page export view with download buttons and session summary.
 *
 * Fetches pipeline status on mount to populate outputs and metadata.
 * Handles session not found and pipeline not complete gracefully.
 */

"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { getStatus } from "@/lib/api/pipeline";
import { APIError } from "@/lib/types/api";
import { ExportPanel } from "@/components/export/ExportPanel";
import { Spinner } from "@/components/ui/Spinner";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Link } from "@/i18n/routing";
import type { PipelineStatusResponse } from "@/lib/types/pipeline";

export default function ExportPage() {
  const t = useTranslations("export");
  const tPipeline = useTranslations("pipeline");
  const params = useParams<{ id: string }>();
  const sessionId = params.id;

  const [isLoading, setIsLoading] = useState(true);
  const [statusData, setStatusData] = useState<PipelineStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStatus() {
      if (!sessionId) return;

      setIsLoading(true);
      setError(null);

      try {
        const response = await getStatus(sessionId);
        setStatusData(response);
      } catch (err) {
        if (err instanceof APIError && err.status === 404) {
          setError("not_found");
        } else if (err instanceof APIError) {
          setError(err.message);
        } else {
          setError(t("loadError"));
        }
      } finally {
        setIsLoading(false);
      }
    }

    fetchStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // ── Loading state ──────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" label={t("loadingExport")} />
          <p className="mt-4 text-sm text-sg-slate/60 dark:text-slate-400">{t("loadingExport")}</p>
        </div>
      </div>
    );
  }

  // ── Error / Not Found state ────────────────────────────────────────

  if (error === "not_found" || !statusData) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Card variant="default" className="max-w-md rounded-2xl text-center dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-lg font-semibold text-sg-navy dark:text-slate-100">
            {tPipeline("sessionExpired")}
          </h2>
          <p className="mt-2 text-sm text-sg-slate/70 dark:text-slate-300">
            {tPipeline("sessionExpiredMessage")}
          </p>
          <Link href="/new">
            <Button variant="primary" size="md" className="mt-4 bg-sg-teal hover:bg-sg-navy">
              {tPipeline("startNewProposal")}
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Card variant="default" className="max-w-md rounded-2xl text-center dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-lg font-semibold text-red-600">{error}</h2>
          <Link href={`/pipeline/${sessionId}`}>
            <Button variant="secondary" size="md" className="mt-4">
              {t("backToPipeline")}
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  // ── Main export view ────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-sg-navy dark:text-slate-100">{t("title")}</h1>
          <p className="text-sm text-sg-slate/60 dark:text-slate-400">
            {t("sessionLabel")}: {sessionId.slice(0, 8)}
          </p>
        </div>
        <div className="flex gap-2">
          <Link href={`/pipeline/${sessionId}/slides`}>
            <Button variant="ghost" size="sm" className="dark:text-slate-200 dark:hover:bg-slate-800">
              {t("viewSlides")}
            </Button>
          </Link>
          <Link href={`/pipeline/${sessionId}`}>
            <Button variant="ghost" size="sm" className="dark:text-slate-200 dark:hover:bg-slate-800">
              {t("backToPipeline")}
            </Button>
          </Link>
        </div>
      </div>

      <ExportPanel
        sessionId={sessionId}
        outputs={statusData.status === "complete" ? statusData.outputs : null}
        metadata={statusData.session_metadata}
        completedGates={statusData.completed_gates}
        startedAt={statusData.started_at}
        elapsedMs={statusData.elapsed_ms}
      />
    </div>
  );
}
