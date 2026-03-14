/**
 * Core API types — error responses and shared primitives.
 * Mirrors backend/models/api_models.py exactly.
 */

// ── Error Response ────────────────────────────────────────────────────

export type APIErrorCode =
  | "SESSION_NOT_FOUND"
  | "GATE_NOT_PENDING"
  | "INVALID_INPUT"
  | "PIPELINE_FAILED"
  | "EXPORT_NOT_READY"
  | "FILE_NOT_FOUND"
  | "FILE_TOO_LARGE"
  | "CAPACITY_EXCEEDED"
  | "SESSION_EXPIRED";

export interface APIErrorDetail {
  code: APIErrorCode;
  message: string;
  details?: unknown;
}

export interface APIErrorResponse {
  error: APIErrorDetail;
}

/**
 * Typed API error thrown by the fetch wrapper.
 */
export class APIError extends Error {
  public readonly code: APIErrorCode;
  public readonly status: number;
  public readonly details?: unknown;

  constructor(status: number, detail: APIErrorDetail) {
    super(detail.message);
    this.name = "APIError";
    this.code = detail.code;
    this.status = status;
    this.details = detail.details;
  }
}

// ── Health ─────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: "ok";
  pipeline_mode: "dry_run" | "live";
  active_sessions: number;
  version: string;
}
