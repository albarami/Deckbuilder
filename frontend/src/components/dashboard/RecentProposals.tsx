/**
 * RecentProposals — List of recent pipeline sessions from backend API.
 *
 * Shows each session with RFP name, status badge, and a resume link.
 */

"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { Card } from "@/components/ui/Card";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { listSessions } from "@/lib/api/pipeline";

interface RecentSession {
  sessionId: string;
  rfpName: string;
  status: string;
  startedAt: string;
  slideCount: number;
}

const STATUS_BADGE_MAP: Record<string, BadgeVariant> = {
  running: "info",
  gate_pending: "warning",
  complete: "success",
  error: "error",
};

async function getRecentSessions(): Promise<RecentSession[]> {
  try {
    const response = await listSessions();
    return response.sessions.slice(0, 10).map((s) => ({
      sessionId: s.session_id,
      rfpName: s.rfp_name || `Session ${s.session_id.slice(0, 8)}`,
      status: s.status,
      startedAt: s.started_at,
      slideCount: s.slide_count ?? 0,
    }));
  } catch {
    // Backend unavailable — return empty list
    return [];
  }
}

export function RecentProposals() {
  const t = useTranslations("dashboard");
  const tPipeline = useTranslations("pipeline");
  const [sessions, setSessions] = useState<RecentSession[]>([]);

  useEffect(() => {
    getRecentSessions().then(setSessions);
  }, []);

  if (sessions.length === 0) {
    return (
      <Card variant="default" className="rounded-2xl text-center dark:border-slate-800 dark:bg-slate-900">
        <p className="text-sg-slate/60 dark:text-slate-400">{t("noProposals")}</p>
        <Link href="/new">
          <Button variant="primary" size="md" className="mt-4 bg-sg-teal hover:bg-sg-navy">
            {t("startNew")}
          </Button>
        </Link>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-sg-navy dark:text-slate-100">
        {t("recentProposals")}
      </h2>
      <div className="space-y-2">
        {sessions.map((session) => (
          <Link
            key={session.sessionId}
            href={`/pipeline/${session.sessionId}`}
            className="block"
          >
            <Card
              variant="flat"
              className="flex items-center justify-between rounded-2xl transition-colors hover:bg-sg-mist/50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800/80"
            >
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-sg-navy dark:text-slate-200">
                  {session.rfpName}
                </span>
                <Badge variant={STATUS_BADGE_MAP[session.status] ?? "default"}>
                  {formatStatus(session.status, tPipeline)}
                </Badge>
              </div>
              <div className="flex items-center gap-3">
                {session.slideCount > 0 && (
                  <span className="text-xs text-sg-slate/50 dark:text-slate-400">
                    {session.slideCount} slides
                  </span>
                )}
                {session.startedAt && (
                  <span className="text-xs text-sg-slate/50 dark:text-slate-400">
                    {new Date(session.startedAt).toLocaleDateString()}
                  </span>
                )}
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

function formatStatus(
  status: string,
  tPipeline: (key: string) => string,
): string {
  switch (status) {
    case "running":
      return tPipeline("running");
    case "gate_pending":
      return tPipeline("gatePending");
    case "complete":
      return tPipeline("complete");
    case "error":
      return tPipeline("error");
    default:
      return status;
  }
}
