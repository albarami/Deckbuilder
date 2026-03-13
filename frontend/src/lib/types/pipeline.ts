/**
 * Pipeline API types — all request/response shapes for pipeline endpoints.
 * Mirrors backend/models/api_models.py exactly.
 */

// ── Enums ─────────────────────────────────────────────────────────────

export type PipelineStatus = "running" | "gate_pending" | "complete" | "error";
export type ProposalMode = "lite" | "standard" | "full";
export type RendererMode = "legacy" | "template_v2";

// ── Upload ────────────────────────────────────────────────────────────

export interface UploadedDocumentRef {
  upload_id: string;
  filename: string;
}

export interface UploadedFileInfo {
  upload_id: string;
  filename: string;
  size_bytes: number;
  content_type: string;
  extracted_text_length: number;
  detected_language: "en" | "ar" | "unknown";
}

export interface UploadResponse {
  uploads: UploadedFileInfo[];
}

// ── Pipeline Start ────────────────────────────────────────────────────

export interface StartPipelineRequest {
  documents: UploadedDocumentRef[];
  text_input?: string;
  language: "en" | "ar";
  proposal_mode: ProposalMode;
  sector: string;
  geography: string;
  renderer_mode?: RendererMode;
}

export interface StartPipelineResponse {
  session_id: string;
  status: PipelineStatus;
  created_at: string;
  stream_url: string;
}

// ── Pipeline Status ───────────────────────────────────────────────────

export interface GateInfo {
  gate_number: number;
  summary: string;
  prompt: string;
  gate_data?: unknown;
}

export interface GateRecord {
  gate_number: number;
  approved: boolean;
  feedback: string;
  decided_at: string;
}

export interface SessionMetadata {
  total_llm_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
}

export interface PipelineOutputs {
  pptx_ready: boolean;
  docx_ready: boolean;
  slide_count: number;
}

export interface PipelineStatusResponse {
  session_id: string;
  status: PipelineStatus;
  current_stage: string;
  current_gate: GateInfo | null;
  completed_gates: GateRecord[];
  started_at: string;
  elapsed_ms: number;
  error: { agent: string; message: string } | null;
  outputs: PipelineOutputs | null;
  session_metadata: SessionMetadata;
}

// ── Gate Decision ─────────────────────────────────────────────────────

export interface GateDecisionRequest {
  approved: boolean;
  feedback?: string;
  modifications?: unknown;
}

export interface GateDecisionResponse {
  gate_number: number;
  decision: "approved" | "rejected";
  pipeline_status: PipelineStatus;
}

// ── SSE Events ────────────────────────────────────────────────────────

export type SSEEventType =
  | "stage_change"
  | "agent_start"
  | "agent_complete"
  | "gate_pending"
  | "render_progress"
  | "pipeline_complete"
  | "pipeline_error"
  | "heartbeat";

export interface SSEEvent {
  type: SSEEventType;
  timestamp: string;
  // stage_change
  stage?: string;
  // agent_start / agent_complete
  agent?: string;
  duration_ms?: number;
  // gate_pending
  gate_number?: number;
  summary?: string;
  prompt?: string;
  gate_data?: unknown;
  // render_progress
  slide_index?: number;
  total?: number;
  // pipeline_complete
  session_id?: string;
  slide_count?: number;
  // pipeline_error
  error?: string;
}
