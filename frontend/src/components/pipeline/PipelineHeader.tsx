/**
 * PipelineHeader — Session info bar at the top of the pipeline view.
 *
 * Shows: session ID (short), started time, elapsed time, status badge.
 */

"use client";

import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Info, StopCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import type { PipelineStatus } from "@/lib/types/pipeline";

export interface PipelineHeaderProps {
  sessionId: string;
  status: PipelineStatus | "idle";
  startedAt: string | null;
  elapsedMs: number;
  onCancel?: () => Promise<boolean>;
}

const STATUS_BADGE: Record<
  string,
  { labelKey: string; className: string; icon?: ReactNode }
> = {
  idle: {
    labelKey: "pipeline.idle",
    className: "bg-sg-mist text-sg-slate dark:bg-slate-950 dark:text-slate-300",
  },
  running: {
    labelKey: "pipeline.running",
    className: "bg-sg-blue/10 text-sg-blue",
  },
  gate_pending: {
    labelKey: "pipeline.gatePending",
    className: "bg-sg-orange/10 text-sg-orange",
    icon: <Info className="h-3.5 w-3.5" aria-hidden="true" />,
  },
  complete: {
    labelKey: "pipeline.complete",
    className: "bg-emerald-50 text-emerald-700",
  },
  error: {
    labelKey: "pipeline.error",
    className: "bg-red-50 text-red-700",
  },
};

export function PipelineHeader({
  sessionId,
  status,
  startedAt,
  elapsedMs,
  onCancel,
}: PipelineHeaderProps) {
  const t = useTranslations();
  const badge = STATUS_BADGE[status] ?? STATUS_BADGE.idle;
  const shortId = sessionId.slice(0, 8);
  const [isStopping, setIsStopping] = useState(false);

  const canCancel = status === "running" || status === "gate_pending";

  const handleStop = useCallback(async () => {
    if (!onCancel || !canCancel) return;
    const confirmed = window.confirm(t("pipeline.stopConfirm"));
    if (!confirmed) return;
    setIsStopping(true);
    try {
      await onCancel();
    } finally {
      setIsStopping(false);
    }
  }, [onCancel, canCancel, t]);

  // Live elapsed timer
  const [liveElapsed, setLiveElapsed] = useState(elapsedMs);

  useEffect(() => {
    if (status !== "running" && status !== "gate_pending") {
      setLiveElapsed(elapsedMs);
      return;
    }

    // Update every second while running
    const interval = setInterval(() => {
      if (startedAt) {
        setLiveElapsed(Date.now() - new Date(startedAt).getTime());
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [status, startedAt, elapsedMs]);

  return (
    <div className="flex flex-wrap items-center gap-3 animate-fade-in-down">
      <div className="inline-flex items-center gap-2 rounded-full bg-sg-navy px-3 py-1.5 text-xs text-white/70 shadow-sg-card dark:bg-slate-900">
        <span className="font-medium">{t("pipeline.sessionId")}</span>
        <span className="font-mono font-semibold tracking-wide text-white">
          {shortId}
        </span>
      </div>

      <span
        className={[
          "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold",
          badge.className,
        ].join(" ")}
      >
        {badge.icon}
        {t(badge.labelKey)}
      </span>

      {startedAt && (
        <span className="font-mono text-xs text-sg-slate/60 dark:text-slate-400">
          {formatElapsed(liveElapsed)}
        </span>
      )}

      {canCancel && onCancel && (
        <button
          type="button"
          onClick={handleStop}
          disabled={isStopping}
          className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 transition-colors hover:bg-red-100 disabled:opacity-50 dark:border-red-800 dark:bg-red-950/40 dark:text-red-400 dark:hover:bg-red-950/60"
        >
          <StopCircle className="h-3.5 w-3.5" aria-hidden="true" />
          {isStopping ? t("pipeline.stopping") : t("pipeline.stopRun")}
        </button>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;

  if (min === 0) return `${sec}s`;
  return `${min}m ${sec.toString().padStart(2, "0")}s`;
}
