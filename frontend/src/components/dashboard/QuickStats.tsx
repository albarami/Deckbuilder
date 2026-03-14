/**
 * QuickStats — Row of stat cards showing proposal counts.
 *
 * Reads from sessionStorage to count recent sessions.
 * M11 has no persistent backend state, so this is a local-only display.
 */

"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";

interface Stats {
  active: number;
  completed: number;
  total: number;
}

/**
 * Read session counts from sessionStorage.
 * Sessions are stored as deckforge_session_{id} keys.
 */
function getSessionStats(): Stats {
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
    setStats(getSessionStats());
  }, []);

  const cards = [
    { label: t("statsActive"), value: stats.active, accent: "text-sg-blue" },
    { label: t("statsCompleted"), value: stats.completed, accent: "text-sg-teal" },
    { label: t("statsTotal"), value: stats.total, accent: "text-sg-navy" },
  ];

  return (
    <div className="grid grid-cols-1 gap-compact sm:grid-cols-3">
      {cards.map((card) => (
        <Card key={card.label} variant="default">
          <p className="text-sm font-medium text-sg-slate/60">{card.label}</p>
          <p className={`mt-1 text-2xl font-bold ${card.accent}`}>
            {card.value}
          </p>
        </Card>
      ))}
    </div>
  );
}
