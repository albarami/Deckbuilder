/**
 * Tests for pipeline-store.
 *
 * Tests the full lifecycle: idle → running → gate_pending → complete
 * and error paths. No HTTP calls — pure store logic.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  isSourceBookGatePending,
  isSourceBookReadyCheckpoint,
  usePipelineStore,
} from "./pipeline-store";
import type { PipelineStatusResponse } from "@/lib/types/pipeline";

// Mock the pipeline API to prevent real HTTP calls in the pipeline_complete handler
vi.mock("@/lib/api/pipeline", () => ({
  getStatus: vi.fn().mockResolvedValue({
    session_id: "mock",
    status: "complete",
    current_stage: "finalized",
    outputs: {
      pptx_ready: true,
      docx_ready: true,
      source_index_ready: false,
      gap_report_ready: false,
      slide_count: 15,
      preview_ready: true,
      deliverables: [],
    },
    deliverables: [],
    completed_gates: [],
    started_at: "2024-01-01T00:00:00Z",
    elapsed_ms: 0,
    error: null,
    session_metadata: {
      total_llm_calls: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      total_cost_usd: 0,
    },
    agent_runs: [],
    rfp_name: "",
    issuing_entity: "",
  }),
}));

// Reset store between tests
beforeEach(() => {
  usePipelineStore.getState().reset();
});

describe("PipelineStore", () => {
  it("source-book state split: gate 3 pending + DOCX ready => pending true, ready false", () => {
    const state = {
      status: "gate_pending" as const,
      currentGate: {
        gate_number: 3,
        summary: "Source Book ready for review",
        prompt: "Review and approve",
        payload_type: "source_book_review" as const,
      },
      completedGates: [],
      outputs: {
        pptx_ready: false,
        docx_ready: true,
        source_index_ready: false,
        gap_report_ready: false,
        slide_count: 0,
        preview_ready: false,
        deliverables: [],
      },
    };

    expect(isSourceBookGatePending(state)).toBe(true);
    expect(isSourceBookReadyCheckpoint(state)).toBe(false);
  });

  it("source-book state split: gate 3 approved + DOCX ready => pending false, ready true", () => {
    const state = {
      status: "running" as const,
      currentGate: null,
      completedGates: [
        {
          gate_number: 3,
          approved: true,
          feedback: "",
          decided_at: "2024-01-01T00:00:00Z",
        },
      ],
      outputs: {
        pptx_ready: false,
        docx_ready: true,
        source_index_ready: false,
        gap_report_ready: false,
        slide_count: 0,
        preview_ready: false,
        deliverables: [],
      },
    };

    expect(isSourceBookGatePending(state)).toBe(false);
    expect(isSourceBookReadyCheckpoint(state)).toBe(true);
  });

  it("source-book state split: gate 3 approved + DOCX not ready => ready false", () => {
    const state = {
      status: "running" as const,
      currentGate: null,
      completedGates: [
        {
          gate_number: 3,
          approved: true,
          feedback: "",
          decided_at: "2024-01-01T00:00:00Z",
        },
      ],
      outputs: {
        pptx_ready: false,
        docx_ready: false,
        source_index_ready: false,
        gap_report_ready: false,
        slide_count: 0,
        preview_ready: false,
        deliverables: [],
      },
    };

    expect(isSourceBookReadyCheckpoint(state)).toBe(false);
  });

  it("source-book state split: no gate 3 => both false", () => {
    const state = {
      status: "running" as const,
      currentGate: null,
      completedGates: [],
      outputs: {
        pptx_ready: false,
        docx_ready: false,
        source_index_ready: false,
        gap_report_ready: false,
        slide_count: 0,
        preview_ready: false,
        deliverables: [],
      },
    };

    expect(isSourceBookGatePending(state)).toBe(false);
    expect(isSourceBookReadyCheckpoint(state)).toBe(false);
  });

  it("starts in idle state", () => {
    const state = usePipelineStore.getState();
    expect(state.status).toBe("idle");
    expect(state.sessionId).toBeNull();
    expect(state.currentGate).toBeNull();
    expect(state.events).toHaveLength(0);
  });

  it("setSession transitions to running", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");

    const state = usePipelineStore.getState();
    expect(state.sessionId).toBe("sess-123");
    expect(state.status).toBe("running");
    expect(state.startedAt).toBe("2024-01-01T00:00:00Z");
    expect(state.currentStage).toBe("intake");
  });

  it("setGatePending transitions to gate_pending", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");
    store.setGatePending({
      gate_number: 1,
      summary: "RFP parsed",
      prompt: "Approve?",
      payload_type: "context_review",
    });

    const state = usePipelineStore.getState();
    expect(state.status).toBe("gate_pending");
    expect(state.currentGate).not.toBeNull();
    expect(state.currentGate!.gate_number).toBe(1);
    expect(state.currentGate!.summary).toBe("RFP parsed");
  });

  it("recordGateDecision (approved) transitions to running", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");
    store.setGatePending({
      gate_number: 1,
      summary: "Test",
      prompt: "Approve?",
      payload_type: "context_review",
    });
    store.recordGateDecision({
      gate_number: 1,
      approved: true,
      feedback: "",
      decided_at: "2024-01-01T00:01:00Z",
    });

    const state = usePipelineStore.getState();
    expect(state.status).toBe("running");
    expect(state.currentGate).toBeNull();
    expect(state.completedGates).toHaveLength(1);
    expect(state.completedGates[0].approved).toBe(true);
  });

  it("recordGateDecision (rejected) transitions to running (revision loop)", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");
    store.setGatePending({
      gate_number: 2,
      summary: "Sources",
      prompt: "Approve?",
      payload_type: "source_review",
    });
    store.recordGateDecision({
      gate_number: 2,
      approved: false,
      feedback: "Not enough sources",
      decided_at: "2024-01-01T00:01:00Z",
    });

    const state = usePipelineStore.getState();
    // Rejection keeps pipeline running — backend loops back to preceding agent
    expect(state.status).toBe("running");
    expect(state.completedGates).toHaveLength(1);
    expect(state.completedGates[0].approved).toBe(false);
    expect(state.completedGates[0].feedback).toBe("Not enough sources");
  });

  it("setComplete sets status and outputs", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");
    store.setComplete({
      pptx_ready: true,
      docx_ready: true,
      source_index_ready: false,
      gap_report_ready: false,
      slide_count: 12,
      preview_ready: true,
      deliverables: [],
    });

    const state = usePipelineStore.getState();
    expect(state.status).toBe("complete");
    expect(state.currentStage).toBe("finalized");
    expect(state.outputs).not.toBeNull();
    expect(state.outputs!.pptx_ready).toBe(true);
    expect(state.outputs!.slide_count).toBe(12);
  });

  it("setError sets error state", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");
    store.setError({ agent: "research", message: "LLM timeout" });

    const state = usePipelineStore.getState();
    expect(state.status).toBe("error");
    expect(state.error).toEqual({
      agent: "research",
      message: "LLM timeout",
    });
  });

  it("restoreFromStatus restores full state", () => {
    const response: PipelineStatusResponse = {
      session_id: "restored-id",
      status: "gate_pending",
      current_stage: "context_review",
      current_stage_label: "Context Review",
      current_gate: {
        gate_number: 1,
        summary: "Context ready",
        prompt: "Approve?",
        payload_type: "context_review",
      },
      completed_gates: [],
      started_at: "2024-01-01T00:00:00Z",
      elapsed_ms: 5000,
      error: null,
      outputs: null,
      session_metadata: {
        total_llm_calls: 3,
        total_input_tokens: 1000,
        total_output_tokens: 500,
        total_cost_usd: 0.05,
      },
      agent_runs: [],
      deliverables: [],
      rfp_name: "Test RFP",
      issuing_entity: "Test Entity",
    };

    usePipelineStore.getState().restoreFromStatus(response);

    const state = usePipelineStore.getState();
    expect(state.sessionId).toBe("restored-id");
    expect(state.status).toBe("gate_pending");
    expect(state.currentStage).toBe("context_review");
    expect(state.currentGate?.gate_number).toBe(1);
    expect(state.sessionMetadata.total_llm_calls).toBe(3);
  });

  it("handleSSEEvent processes stage_change", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");

    store.handleSSEEvent({
      type: "stage_change",
      stage: "analysis",
      timestamp: "2024-01-01T00:01:00Z",
    });

    const state = usePipelineStore.getState();
    expect(state.currentStage).toBe("analysis");
    expect(state.events).toHaveLength(1);
  });

  it("handleSSEEvent processes gate_pending", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");

    store.handleSSEEvent({
      type: "gate_pending",
      gate_number: 3,
      summary: "Report ready",
      prompt: "Approve report?",
      timestamp: "2024-01-01T00:01:00Z",
    });

    const state = usePipelineStore.getState();
    expect(state.status).toBe("gate_pending");
    expect(state.currentGate?.gate_number).toBe(3);
  });

  it("handleSSEEvent processes pipeline_complete", async () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");

    store.handleSSEEvent({
      type: "pipeline_complete",
      session_id: "sess-123",
      slide_count: 15,
      timestamp: "2024-01-01T00:05:00Z",
    });

    // Wait for the async getStatus call to resolve
    await vi.waitFor(() => {
      const state = usePipelineStore.getState();
      expect(state.status).toBe("complete");
      expect(state.outputs?.slide_count).toBe(15);
    });
  });

  it("handleSSEEvent processes pipeline_error", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");

    store.handleSSEEvent({
      type: "pipeline_error",
      error: "Timeout",
      agent: "qa_agent",
      timestamp: "2024-01-01T00:05:00Z",
    });

    const state = usePipelineStore.getState();
    expect(state.status).toBe("error");
    expect(state.error?.agent).toBe("qa_agent");
  });

  it("pushEvent caps at MAX_EVENTS (200)", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");

    // Push 210 events
    for (let i = 0; i < 210; i++) {
      store.pushEvent({
        type: "heartbeat",
        timestamp: `2024-01-01T00:00:${String(i).padStart(2, "0")}Z`,
      });
    }

    const state = usePipelineStore.getState();
    expect(state.events.length).toBeLessThanOrEqual(200);
  });

  it("reset returns to idle state", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");
    store.setStage("analysis");
    store.pushEvent({
      type: "heartbeat",
      timestamp: "2024-01-01T00:00:00Z",
    });

    store.reset();

    const state = usePipelineStore.getState();
    expect(state.status).toBe("idle");
    expect(state.sessionId).toBeNull();
    expect(state.events).toHaveLength(0);
  });

  it("full lifecycle: idle → running → gate → running → complete", async () => {
    const store = usePipelineStore.getState();

    // Start
    store.setSession("lifecycle-test", "2024-01-01T00:00:00Z");
    expect(usePipelineStore.getState().status).toBe("running");

    // Gate 1
    store.handleSSEEvent({
      type: "gate_pending",
      gate_number: 1,
      summary: "Context",
      prompt: "OK?",
      timestamp: "t1",
    });
    expect(usePipelineStore.getState().status).toBe("gate_pending");

    // Approve gate 1
    store.recordGateDecision({
      gate_number: 1,
      approved: true,
      feedback: "",
      decided_at: "t2",
    });
    expect(usePipelineStore.getState().status).toBe("running");

    // Complete
    store.handleSSEEvent({
      type: "pipeline_complete",
      session_id: "lifecycle-test",
      slide_count: 10,
      timestamp: "t3",
    });

    // Wait for async getStatus to resolve
    await vi.waitFor(() => {
      expect(usePipelineStore.getState().status).toBe("complete");
      expect(usePipelineStore.getState().completedGates).toHaveLength(1);
    });
  });
});
