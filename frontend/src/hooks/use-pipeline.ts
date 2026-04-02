/**
 * usePipeline — Pipeline lifecycle hook.
 *
 * Provides:
 * - startPipeline: create session and begin SSE
 * - resumeSession: restore from URL session ID on page load
 * - Pipeline state from Zustand store
 */

"use client";

import { useCallback } from "react";
import {
  isSourceBookGatePending,
  isSourceBookReadyCheckpoint,
  usePipelineStore,
} from "@/stores/pipeline-store";
import {
  startPipeline as apiStartPipeline,
  getStatus as apiGetStatus,
} from "@/lib/api/pipeline";
import type { StartPipelineRequest } from "@/lib/types/pipeline";
import { APIError } from "@/lib/types/api";

export function usePipeline() {
  const store = usePipelineStore();
  const sourceBookGatePending = isSourceBookGatePending(store);
  const sourceBookReadyCheckpoint = isSourceBookReadyCheckpoint(store);

  /**
   * Start a new pipeline session.
   * Sets session in store and returns session_id for navigation.
   */
  const start = useCallback(
    async (request: StartPipelineRequest): Promise<string> => {
      store.setStarting(true);
      try {
        const response = await apiStartPipeline(request);
        store.setSession(response.session_id, response.created_at, request.proposal_mode);
        return response.session_id;
      } catch (err) {
        if (err instanceof APIError) {
          store.setError({ agent: "start", message: err.message });
        } else {
          store.setError({
            agent: "start",
            message: "Failed to start pipeline",
          });
        }
        throw err;
      } finally {
        store.setStarting(false);
      }
    },
    [store],
  );

  /**
   * Resume a session from a session ID (e.g., from URL path).
   * Calls GET /status and restores store state.
   * Returns true if session was found and restored.
   */
  const resume = useCallback(
    async (sessionId: string): Promise<boolean> => {
      try {
        const status = await apiGetStatus(sessionId);
        store.restoreFromStatus(status);
        return true;
      } catch (err) {
        if (err instanceof APIError && err.status === 404) {
          // Session expired or not found
          return false;
        }
        throw err;
      }
    },
    [store],
  );

  return {
    // State (readonly convenience accessors)
    sessionId: store.sessionId,
    status: store.status,
    proposalMode: store.proposalMode,
    currentStage: store.currentStage,
    currentGate: store.currentGate,
    completedGates: store.completedGates,
    outputs: store.outputs,
    sourceBookSummary: store.sourceBookSummary,
    error: store.error,
    startedAt: store.startedAt,
    elapsedMs: store.elapsedMs,
    sessionMetadata: store.sessionMetadata,
    agentRuns: store.agentRuns,
    events: store.events,
    isStarting: store.isStarting,
    isSourceBookGatePending: sourceBookGatePending,
    isSourceBookReadyCheckpoint: sourceBookReadyCheckpoint,

    // Actions
    start,
    resume,
    reset: store.reset,
  };
}
