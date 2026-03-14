/**
 * PipelineHeader — Session info bar at the top of the pipeline view.
 *
 * Shows: session ID (short), started time, elapsed time, status badge.
 */

"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import type { PipelineStatus } from "@/lib/types/pipeline";

export interface PipelineHeaderProps {
  sessionId: string;
  status: PipelineStatus | "idle";
  startedAt: string | null;
  elapsedMs: number;
}

const STATUS_BADGE: Record<string, { variant: BadgeVariant; labelKey: string }> = {
  idle: { variant: "default", labelKey: "pipeline.idle" },
  running: { variant: "info", labelKey: "pipeline.running" },
  gate_pending: { variant: "warning", labelKey: "pipeline.gatePending" },
  complete: { variant: "success", labelKey: "pipeline.complete" },
  error: { variant: "error", labelKey: "pipeline.error" },
};

export function PipelineHeader({
  sessionId,
  status,
  startedAt,
  elapsedMs,
}: PipelineHeaderProps) {
  const t = useTranslations();
  const badge = STATUS_BADGE[status] ?? STATUS_BADGE.idle;
  const shortId = sessionId.slice(0, 8);

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
    <div className="flex flex-wrap items-center gap-3">
      {/* Session ID */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-sg-slate/60">
          {t("pipeline.sessionId")}:
        </span>
        <span className="rounded bg-sg-mist px-2 py-0.5 font-mono text-sm text-sg-navy">
          {shortId}
        </span>
      </div>

      {/* Status badge */}
      <Badge variant={badge.variant}>{t(badge.labelKey)}</Badge>

      {/* Elapsed time */}
      {startedAt && (
        <span className="text-sm text-sg-slate/60">
          {formatElapsed(liveElapsed)}
        </span>
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
