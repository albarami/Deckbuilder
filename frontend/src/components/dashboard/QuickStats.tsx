/**
 * QuickStats — Row of stat cards showing proposal counts.
 *
 * Reads from the backend sessions API (with sessionStorage fallback).
 */

"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { listSessions } from "@/lib/api/pipeline";

interface Stats {
  active: number;
  completed: number;
  total: number;
}

/**
 * Fetch session counts from the backend API.
 * Falls back to sessionStorage if the API is unavailable.
 */
async function getSessionStats(): Promise<Stats> {
  try {
    const response = await listSessions();
    let active = 0;
    let completed = 0;

    for (const session of response.sessions) {
      if (session.status === "complete") {
        completed++;
      } else if (session.status === "running" || session.status === "gate_pending") {
        active++;
      }
    }

    return { active, completed, total: active + completed };
  } catch {
    // Fallback to sessionStorage if backend unavailable
    return getSessionStatsFromStorage();
  }
}

function getSessionStatsFromStorage(): Stats {
  if (typeof window === "undefined") {
    return { active: 0, completed: 0, total: 0 };
  }

  let active = 0;
  let completed = 0;

  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (!key?.startsWith("deckforge_session_")) continue;

    try {
      const data = JSON.parse(sessionStorage.getItem(key) ?? "{}");
      if (data.status === "complete") {
        completed++;
      } else if (data.status === "running" || data.status === "gate_pending") {
        active++;
      }
    } catch {
      // Skip invalid entries
    }
  }

  return { active, completed, total: active + completed };
}

export function QuickStats() {
  const t = useTranslations("dashboard");
  const [stats, setStats] = useState<Stats>({ active: 0, completed: 0, total: 0 });

  useEffect(() => {
    getSessionStats().then(setStats);
  }, []);

  const cards = [
    { label: t("statsActive"), value: stats.active, accent: "text-sg-blue" },
    { label: t("statsCompleted"), value: stats.completed, accent: "text-sg-teal" },
    { label: t("statsTotal"), value: stats.total, accent: "text-sg-navy" },
  ];

  return (
    <div className="grid grid-cols-1 gap-compact sm:grid-cols-3">
      {cards.map((card) => (
        <Card
          key={card.label}
          variant="default"
          className="rounded-2xl dark:border-slate-800 dark:bg-slate-900"
        >
          <p className="text-sm font-medium text-sg-slate/60 dark:text-slate-400">
            {card.label}
          </p>
          <p className={`mt-1 text-2xl font-bold ${card.accent} dark:text-slate-100`}>
            {card.value}
          </p>
        </Card>
      ))}
    </div>
  );
}
