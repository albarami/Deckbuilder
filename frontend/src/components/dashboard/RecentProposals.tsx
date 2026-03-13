/**
 * RecentProposals — List of recent pipeline sessions from sessionStorage.
 *
 * Shows each session with ID, status badge, and a resume link.
 * If no sessions exist, shows an empty state prompting to start a new one.
 */

"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { Card } from "@/components/ui/Card";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface RecentSession {
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

function getRecentSessions(): RecentSession[] {
  if (typeof window === "undefined") return [];

  const sessions: RecentSession[] = [];

  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (!key?.startsWith("deckforge_session_")) continue;

    try {
      const data = JSON.parse(sessionStorage.getItem(key) ?? "{}");
      const sessionId = key.replace("deckforge_session_", "");
      sessions.push({
        sessionId,
        status: data.status ?? "unknown",
        startedAt: data.startedAt ?? "",
        language: data.language ?? "en",
      });
    } catch {
      // Skip invalid entries
    }
  }

  // Sort by started time, newest first
  sessions.sort((a, b) => {
    if (!a.startedAt || !b.startedAt) return 0;
    return new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime();
  });

  return sessions.slice(0, 10); // Show max 10
}

export function RecentProposals() {
  const t = useTranslations("dashboard");
  const [sessions, setSessions] = useState<RecentSession[]>([]);

  useEffect(() => {
    setSessions(getRecentSessions());
  }, []);

  if (sessions.length === 0) {
    return (
      <Card variant="default" className="text-center">
        <p className="text-sg-slate/60">{t("noProposals")}</p>
        <Link href="/new">
          <Button variant="primary" size="md" className="mt-4">
            {t("startNew")}
          </Button>
        </Link>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-sg-navy">
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
              className="flex items-center justify-between transition-colors hover:bg-sg-mist/50"
            >
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm text-sg-slate/70">
                  {session.sessionId.slice(0, 8)}...
                </span>
                <Badge variant={STATUS_BADGE_MAP[session.status] ?? "default"}>
                  {session.status}
                </Badge>
              </div>
              {session.startedAt && (
                <span className="text-xs text-sg-slate/50">
                  {new Date(session.startedAt).toLocaleDateString()}
                </span>
              )}
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
