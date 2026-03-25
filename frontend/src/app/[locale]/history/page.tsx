"use client";

import { useEffect, useMemo, useState } from "react";
import { Clock3, FileOutput, FileStack, Workflow } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { listSessions } from "@/lib/api/pipeline";

interface HistorySession {
  sessionId: string;
  status: string;
  startedAt: string;
  language: string;
}

const STATUS_BADGE_MAP: Record<string, BadgeVariant> = {
  running: "info",
  gate_pending: "warning",
  complete: "success",
  error: "error",
};

export default function HistoryPage() {
  const t = useTranslations("history");
  const tDashboard = useTranslations("dashboard");
  const tPipeline = useTranslations("pipeline");
  const [sessions, setSessions] = useState<HistorySession[]>([]);

  useEffect(() => {
    let mounted = true;

    async function loadSessions() {
      try {
        const response = await listSessions();
        if (!mounted) return;
        setSessions(
          response.sessions.map((s) => ({
            sessionId: s.session_id,
            status: s.status,
            startedAt: s.started_at ?? "",
            language: s.language ?? "en",
          })),
        );
      } catch {
        // Backend unavailable — show empty state
        if (mounted) setSessions([]);
      }
    }

    void loadSessions();
    return () => { mounted = false; };
  }, []);

  const summary = useMemo(() => {
    const active = sessions.filter((session) =>
      session.status === "running" || session.status === "gate_pending",
    ).length;
    const complete = sessions.filter((session) => session.status === "complete").length;

    return [
      {
        label: tDashboard("statsActive"),
        value: String(active),
        icon: <Workflow className="h-4 w-4" aria-hidden="true" />,
      },
      {
        label: tDashboard("statsCompleted"),
        value: String(complete),
        icon: <FileStack className="h-4 w-4" aria-hidden="true" />,
      },
      {
        label: tDashboard("statsTotal"),
        value: String(sessions.length),
        icon: <FileOutput className="h-4 w-4" aria-hidden="true" />,
      },
    ];
  }, [sessions, tDashboard]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-sg-navy dark:text-slate-100">
          {t("title")}
        </h1>
        <p className="mt-2 max-w-3xl text-sg-slate/70 dark:text-slate-300">
          {t("subtitle")}
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {summary.map((item) => (
          <Card
            key={item.label}
            variant="default"
            className="rounded-2xl dark:border-slate-800 dark:bg-slate-900"
          >
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-sg-slate/55 dark:text-slate-400">
              <span className="text-sg-blue dark:text-sky-300">{item.icon}</span>
              {item.label}
            </div>
            <p className="mt-3 text-xl font-semibold text-sg-navy dark:text-slate-100">
              {item.value}
            </p>
          </Card>
        ))}
      </div>

      {sessions.length === 0 ? (
        <Card variant="default" className="rounded-2xl text-center dark:border-slate-800 dark:bg-slate-900">
          <Clock3 className="mx-auto h-10 w-10 text-sg-slate/35 dark:text-slate-500" aria-hidden="true" />
          <p className="mt-4 text-sg-slate/70 dark:text-slate-300">{t("empty")}</p>
          <Link href="/new">
            <Button variant="primary" size="md" className="mt-4 bg-sg-teal hover:bg-sg-navy">
              {t("openPipeline")}
            </Button>
          </Link>
        </Card>
      ) : (
        <div className="space-y-3">
          {sessions.map((session) => (
            <Card
              key={session.sessionId}
              variant="default"
              className="rounded-2xl dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-sg-navy px-3 py-1 font-mono text-xs text-white/75">
                      {t("session")} {session.sessionId.slice(0, 8)}
                    </span>
                    <Badge variant={STATUS_BADGE_MAP[session.status] ?? "default"}>
                      {formatStatus(session.status, tPipeline)}
                    </Badge>
                  </div>
                  <div className="grid gap-2 text-sm text-sg-slate/70 dark:text-slate-300 sm:grid-cols-3">
                    <p>
                      <span className="font-medium text-sg-navy dark:text-slate-100">{t("started")}:</span>{" "}
                      {formatDate(session.startedAt, t("noTimestamp"))}
                    </p>
                    <p>
                      <span className="font-medium text-sg-navy dark:text-slate-100">{t("language")}:</span>{" "}
                      {session.language.toUpperCase()}
                    </p>
                    <p>
                      <span className="font-medium text-sg-navy dark:text-slate-100">{t("currentStage")}:</span>{" "}
                      {formatStatus(session.status, tPipeline)}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Link href={`/pipeline/${session.sessionId}`}>
                    <Button variant="primary" size="sm" className="bg-sg-teal hover:bg-sg-navy">
                      {t("openPipeline")}
                    </Button>
                  </Link>
                  <Link href={`/pipeline/${session.sessionId}/slides`}>
                    <Button variant="secondary" size="sm">
                      {t("openSlides")}
                    </Button>
                  </Link>
                  <Link href={`/pipeline/${session.sessionId}/export`}>
                    <Button variant="ghost" size="sm">
                      {t("openExport")}
                    </Button>
                  </Link>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function formatDate(value: string, fallback: string): string {
  if (!value) return fallback;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? fallback : date.toLocaleString();
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
