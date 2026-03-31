/**
 * Pipeline Store — Zustand state for pipeline session lifecycle.
 *
 * Manages:
 * - Session ID and status
 * - Current stage and gate info
 * - Completed gates history
 * - SSE event log
 * - Error state
 * - Pipeline outputs
 * - Session metadata (LLM calls, tokens, cost)
 *
 * Lifecycle: idle → running → gate_pending → running → ... → complete | error
 */

import { create } from "zustand";
import type {
  PipelineStatus,
  PipelineStatusResponse,
  GateInfo,
  GateRecord,
  PipelineOutputs,
  SessionMetadata,
  SSEEvent,
  AgentRunInfo,
  ProposalMode,
  SourceBookSummary,
} from "@/lib/types/pipeline";
import { getStatus } from "@/lib/api/pipeline";

// ── Store Shape ───────────────────────────────────────────────────────

interface PipelineState {
  // Session
  sessionId: string | null;
  status: PipelineStatus | "idle";
  proposalMode: ProposalMode;
  currentStage: string;

  // Gate
  currentGate: GateInfo | null;
  completedGates: GateRecord[];

  // Outputs
  outputs: PipelineOutputs | null;
  sourceBookSummary: SourceBookSummary | null;

  // Error
  error: { agent: string; message: string } | null;

  // Metadata
  startedAt: string | null;
  elapsedMs: number;
  sessionMetadata: SessionMetadata;
  agentRuns: AgentRunInfo[];

  // SSE events (capped at 200 for memory)
  events: SSEEvent[];

  // Loading states
  isStarting: boolean;
  isDecidingGate: boolean;
}

interface PipelineActions {
  /** Initialize from a start pipeline response */
  setSession: (sessionId: string, startedAt: string) => void;

  /** Restore full state from GET /status response (session resume) */
  restoreFromStatus: (response: PipelineStatusResponse) => void;

  /** Update status */
  setStatus: (status: PipelineStatus) => void;

  /** Update current stage */
  setStage: (stage: string) => void;

  /** Set gate pending */
  setGatePending: (gate: GateInfo) => void;

  /** Record completed gate and resume running */
  recordGateDecision: (record: GateRecord) => void;

  /** Set pipeline complete with outputs */
  setComplete: (outputs: PipelineOutputs) => void;

  /** Set pipeline error */
  setError: (error: { agent: string; message: string }) => void;

  /** Append SSE event */
  pushEvent: (event: SSEEvent) => void;

  /** Process an SSE event and update store accordingly */
  handleSSEEvent: (event: SSEEvent) => void;

  /** Update metadata */
  setMetadata: (metadata: SessionMetadata) => void;

  /** Loading states */
  setStarting: (v: boolean) => void;
  setDecidingGate: (v: boolean) => void;

  /** Reset to idle */
  reset: () => void;
}

export type PipelineStore = PipelineState & PipelineActions;

// ── Initial State ─────────────────────────────────────────────────────

const initialState: PipelineState = {
  sessionId: null,
  status: "idle",
  proposalMode: "standard",
  currentStage: "",
  currentGate: null,
  completedGates: [],
  outputs: null,
  sourceBookSummary: null,
  error: null,
  startedAt: null,
  elapsedMs: 0,
  sessionMetadata: {
    total_llm_calls: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
    total_cost_usd: 0,
  },
  agentRuns: [],
  events: [],
  isStarting: false,
  isDecidingGate: false,
};

const MAX_EVENTS = 200;

type SourceBookCheckpointState = Pick<
  PipelineState,
  "status" | "currentGate" | "completedGates" | "outputs"
>;

const isDocxReady = (state: SourceBookCheckpointState): boolean => {
  if (state.outputs?.docx_ready) return true;
  return Boolean(state.outputs?.deliverables?.some((d) => d.key === "docx" && d.ready));
};

export const isSourceBookGatePending = (state: SourceBookCheckpointState): boolean =>
  state.status === "gate_pending" && state.currentGate?.gate_number === 3;

export const isSourceBookReadyCheckpoint = (state: SourceBookCheckpointState): boolean => {
  const gate3Approved = state.completedGates.some(
    (gate) => gate.gate_number === 3 && gate.approved,
  );
  return gate3Approved && isDocxReady(state);
};

// ── Store ─────────────────────────────────────────────────────────────

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  ...initialState,

  setSession: (sessionId, startedAt) =>
    set({
      sessionId,
      status: "running",
      proposalMode: "standard",
      startedAt,
      currentStage: "intake",
      error: null,
      events: [],
      completedGates: [],
      currentGate: null,
      outputs: null,
      sourceBookSummary: null,
      agentRuns: [],
    }),

  restoreFromStatus: (response) =>
    set({
      sessionId: response.session_id,
      status: response.status,
      proposalMode: (response.proposal_mode as ProposalMode) || "standard",
      currentStage: response.current_stage,
      currentGate: response.current_gate,
      completedGates: response.completed_gates,
      startedAt: response.started_at,
      elapsedMs: response.elapsed_ms,
      error: response.error,
      outputs: response.outputs,
      sourceBookSummary: response.source_book_summary || null,
      sessionMetadata: response.session_metadata,
      agentRuns: response.agent_runs,
    }),

  setStatus: (status) => set({ status }),

  setStage: (stage) => set({ currentStage: stage }),

  setGatePending: (gate) =>
    set({ status: "gate_pending", currentGate: gate }),

  recordGateDecision: (record) =>
    set((state) => ({
      completedGates: [...state.completedGates, record],
      currentGate: null,
      status: "running",  // Both approve and reject keep pipeline running (revision loop)
    })),

  setComplete: (outputs) =>
    set({
      status: "complete",
      currentStage: "finalized",
      currentGate: null,
      outputs,
    }),

  setError: (error) =>
    set({
      status: "error",
      currentStage: "error",
      error,
    }),

  pushEvent: (event) =>
    set((state) => ({
      events:
        state.events.length >= MAX_EVENTS
          ? [...state.events.slice(-MAX_EVENTS + 1), event]
          : [...state.events, event],
    })),

  handleSSEEvent: (event) => {
    const store = get();
    store.pushEvent(event);

    switch (event.type) {
      case "stage_change":
        if (event.stage) store.setStage(event.stage);
        break;

      case "gate_pending":
        if (event.gate_number != null) {
          store.setGatePending({
            gate_number: event.gate_number,
            summary: event.summary ?? "",
            prompt: event.prompt ?? "",
            payload_type: event.gate_payload_type ?? "context_review",
            gate_data: event.gate_data,
          });
        }
        break;

      case "pipeline_complete": {
        // Hydrate from backend status to get real readiness values
        const sessionId = event.session_id ?? store.sessionId;
        if (sessionId) {
          void (async () => {
            try {
              const statusResponse = await getStatus(sessionId);
              if (statusResponse.outputs) {
                store.setComplete({
                  // Deck mode
                  pptx_ready: statusResponse.outputs.pptx_ready,
                  docx_ready: statusResponse.outputs.docx_ready,
                  source_index_ready: statusResponse.outputs.source_index_ready,
                  gap_report_ready: statusResponse.outputs.gap_report_ready,
                  slide_count: statusResponse.outputs.slide_count,
                  preview_ready: statusResponse.outputs.preview_ready,
                  deliverables: statusResponse.deliverables ?? [],
                  // Source Book mode
                  source_book_ready: statusResponse.outputs.source_book_ready,
                  evidence_ledger_ready: statusResponse.outputs.evidence_ledger_ready,
                  slide_blueprint_ready: statusResponse.outputs.slide_blueprint_ready,
                  external_evidence_ready: statusResponse.outputs.external_evidence_ready,
                  routing_report_ready: statusResponse.outputs.routing_report_ready,
                  research_query_log_ready: statusResponse.outputs.research_query_log_ready,
                  query_execution_log_ready: statusResponse.outputs.query_execution_log_ready,
                });
                // Also store Source Book summary if available
                if (statusResponse.source_book_summary) {
                  set({ sourceBookSummary: statusResponse.source_book_summary });
                }
              } else {
                // No outputs from backend — show empty state, not fake readiness
                store.setComplete({
                  pptx_ready: false,
                  docx_ready: false,
                  source_index_ready: false,
                  gap_report_ready: false,
                  slide_count: event.slide_count ?? 0,
                  preview_ready: false,
                  deliverables: [],
                  source_book_ready: false,
                  evidence_ledger_ready: false,
                  slide_blueprint_ready: false,
                  external_evidence_ready: false,
                  routing_report_ready: false,
                  research_query_log_ready: false,
                  query_execution_log_ready: false,
                });
              }
            } catch {
              // Network error — show empty state, not fake readiness
              store.setComplete({
                pptx_ready: false,
                docx_ready: false,
                source_index_ready: false,
                gap_report_ready: false,
                slide_count: event.slide_count ?? 0,
                preview_ready: false,
                deliverables: [],
                source_book_ready: false,
                evidence_ledger_ready: false,
                slide_blueprint_ready: false,
                external_evidence_ready: false,
                routing_report_ready: false,
                research_query_log_ready: false,
                query_execution_log_ready: false,
              });
            }
          })();
        }
        break;
      }

      case "pipeline_error":
        store.setError({
          agent: event.agent ?? "unknown",
          message: event.error ?? "Pipeline failed",
        });
        break;

      // agent_start, agent_complete, render_progress, heartbeat
      // are tracked via events array only
    }
  },

  setMetadata: (metadata) => set({ sessionMetadata: metadata }),

  setStarting: (v) => set({ isStarting: v }),
  setDecidingGate: (v) => set({ isDecidingGate: v }),

  reset: () => set(initialState),
}));
