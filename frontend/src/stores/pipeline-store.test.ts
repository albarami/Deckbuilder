/**
 * Tests for pipeline-store.
 *
 * Tests the full lifecycle: idle → running → gate_pending → complete
 * and error paths. No HTTP calls — pure store logic.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { usePipelineStore } from "./pipeline-store";
import type { PipelineStatusResponse } from "@/lib/types/pipeline";

// Reset store between tests
beforeEach(() => {
  usePipelineStore.getState().reset();
});

describe("PipelineStore", () => {
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

  it("recordGateDecision (rejected) transitions to complete", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");
    store.setGatePending({
      gate_number: 2,
      summary: "Sources",
      prompt: "Approve?",
    });
    store.recordGateDecision({
      gate_number: 2,
      approved: false,
      feedback: "Not enough sources",
      decided_at: "2024-01-01T00:01:00Z",
    });

    const state = usePipelineStore.getState();
    expect(state.status).toBe("complete");
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
      slide_count: 12,
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
      current_gate: {
        gate_number: 1,
        summary: "Context ready",
        prompt: "Approve?",
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

  it("handleSSEEvent processes pipeline_complete", () => {
    const store = usePipelineStore.getState();
    store.setSession("sess-123", "2024-01-01T00:00:00Z");

    store.handleSSEEvent({
      type: "pipeline_complete",
      session_id: "sess-123",
      slide_count: 15,
      timestamp: "2024-01-01T00:05:00Z",
    });

    const state = usePipelineStore.getState();
    expect(state.status).toBe("complete");
    expect(state.outputs?.slide_count).toBe(15);
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

  it("full lifecycle: idle → running → gate → running → complete", () => {
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
    expect(usePipelineStore.getState().status).toBe("complete");
    expect(usePipelineStore.getState().completedGates).toHaveLength(1);
  });
});
