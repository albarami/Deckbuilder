/**
 * Pipeline API module — start, status, and gate decision calls.
 */

import { get, post, postEmpty, del } from "./client";
import type {
  StartPipelineRequest,
  StartPipelineResponse,
  PipelineStatusResponse,
  GateDecisionRequest,
  GateDecisionResponse,
  SessionHistoryResponse,
} from "@/lib/types/pipeline";
import type { HealthResponse } from "@/lib/types/api";

/**
 * Start a new pipeline session.
 * POST /api/pipeline/start
 */
export function startPipeline(
  request: StartPipelineRequest,
): Promise<StartPipelineResponse> {
  return post<StartPipelineResponse>("/api/pipeline/start", request);
}

/**
 * Get pipeline session status.
 * GET /api/pipeline/{id}/status
 */
export function getStatus(
  sessionId: string,
): Promise<PipelineStatusResponse> {
  return get<PipelineStatusResponse>(`/api/pipeline/${sessionId}/status`);
}

/**
 * Submit a gate decision (approve or reject).
 * POST /api/pipeline/{id}/gate/{n}/decide
 */
export function decideGate(
  sessionId: string,
  gateNumber: number,
  decision: GateDecisionRequest,
): Promise<GateDecisionResponse> {
  return post<GateDecisionResponse>(
    `/api/pipeline/${sessionId}/gate/${gateNumber}/decide`,
    decision,
  );
}

/**
 * List all pipeline sessions.
 * GET /api/pipeline/sessions
 */
export function listSessions(): Promise<SessionHistoryResponse> {
  return get<SessionHistoryResponse>("/api/pipeline/sessions");
}

/**
 * Cancel a running pipeline session.
 * POST /api/pipeline/{id}/cancel
 */
export function cancelPipeline(
  sessionId: string,
): Promise<{ status: string; session_id: string }> {
  return postEmpty<{ status: string; session_id: string }>(
    `/api/pipeline/${sessionId}/cancel`,
  );
}

/**
 * Remove a session from the store.
 * DELETE /api/pipeline/{id}
 */
export function removePipeline(
  sessionId: string,
): Promise<{ status: string; session_id: string }> {
  return del<{ status: string; session_id: string }>(
    `/api/pipeline/${sessionId}`,
  );
}

/**
 * Health check.
 * GET /api/health
 */
export function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>("/api/health");
}
