/**
 * AgentStatusCard — Shows the currently running agent with elapsed time.
 *
 * Appears when pipeline status is "running" and an agent_start SSE event
 * has been received. Shows spinner + agent name + elapsed time.
 */

"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { Card } from "@/components/ui/Card";
import type { SSEEvent } from "@/lib/types/pipeline";

export interface AgentStatusCardProps {
  /** Full SSE event log — used to extract latest agent_start/agent_complete */
  events: SSEEvent[];
  /** Current pipeline status */
  status: string;
}

interface AgentInfo {
  name: string;
  startedAt: number;
  completed: boolean;
  durationMs?: number;
}

/**
 * Extract the latest agent info from the SSE event stream.
 */
function getLatestAgent(events: SSEEvent[]): AgentInfo | null {
  let latestStart: AgentInfo | null = null;

  for (const event of events) {
    if (event.type === "agent_start" && event.agent) {
      latestStart = {
        name: event.agent,
        startedAt: new Date(event.timestamp).getTime(),
        completed: false,
      };
    } else if (event.type === "agent_complete" && event.agent) {
      if (latestStart !== null && latestStart.name === event.agent) {
        latestStart = {
          name: latestStart.name,
          startedAt: latestStart.startedAt,
          completed: true,
          durationMs: event.duration_ms,
        };
      }
    }
  }

  return latestStart;
}

export function AgentStatusCard({ events, status }: AgentStatusCardProps) {
  const t = useTranslations("pipeline");
  const agent = getLatestAgent(events);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!agent || agent.completed || status !== "running") {
      return;
    }

    // Update elapsed timer every second
    const interval = setInterval(() => {
      setElapsed(Date.now() - agent.startedAt);
    }, 1000);

    return () => clearInterval(interval);
  }, [agent, status]);

  if (!agent || status === "idle") {
    return null;
  }

  const displayName = formatAgentName(agent.name);
  const isRunning = !agent.completed && status === "running";

  return (
    <Card variant="flat" className="flex items-center gap-3">
      {isRunning ? (
        <Spinner size="sm" label={`${displayName} running`} />
      ) : (
        <CheckIcon />
      )}

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-sg-navy truncate">
          {displayName}
        </p>
        <p className="text-xs text-sg-slate/60">
          {isRunning
            ? t("agentRunning", { time: formatDuration(elapsed) })
            : t("agentCompleted", {
                time: formatDuration(agent.durationMs ?? 0),
              })}
        </p>
      </div>
    </Card>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

/**
 * Convert snake_case agent names to readable form.
 * e.g. "context_agent" → "Context Agent"
 */
function formatAgentName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatDuration(ms: number): string {
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const remSec = sec % 60;
  return `${min}m ${remSec.toString().padStart(2, "0")}s`;
}

function CheckIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-5 w-5 flex-shrink-0 text-emerald-500"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
        clipRule="evenodd"
      />
    </svg>
  );
}
