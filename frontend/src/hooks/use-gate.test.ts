import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useGate } from "./use-gate";

const mockDecideGate = vi.fn().mockResolvedValue(undefined);

const mockStore = {
  sessionId: "session-123",
  currentGate: {
    gate_number: 3,
    agent_name: "reviewer",
    payload_type: "source_book_review" as const,
    gate_data: {},
    available_actions: ["approve", "reject"],
  },
  completedGates: [],
  isDecidingGate: false,
  setDecidingGate: vi.fn(),
  recordGateDecision: vi.fn(),
  setError: vi.fn(),
};

vi.mock("@/stores/pipeline-store", () => ({
  usePipelineStore: () => mockStore,
}));

vi.mock("@/lib/api/pipeline", () => ({
  decideGate: (...args: unknown[]) => mockDecideGate(...args),
}));

describe("useGate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStore.currentGate.gate_number = 3;
  });

  it("fires gate 3 callback on approve and records decision", async () => {
    const onGate3DecisionComplete = vi.fn();
    const { result } = renderHook(() =>
      useGate({ onGate3DecisionComplete }),
    );

    await result.current.approve();

    expect(mockStore.setDecidingGate).toHaveBeenCalledWith(true);
    expect(mockDecideGate).toHaveBeenCalledWith("session-123", 3, { approved: true });
    expect(mockStore.recordGateDecision).toHaveBeenCalledWith(
      expect.objectContaining({ gate_number: 3, approved: true }),
    );
    expect(onGate3DecisionComplete).toHaveBeenCalledWith("approved");
    expect(mockStore.setDecidingGate).toHaveBeenLastCalledWith(false);
  });

  it("fires gate 3 callback on reject with feedback", async () => {
    const onGate3DecisionComplete = vi.fn();
    const { result } = renderHook(() =>
      useGate({ onGate3DecisionComplete }),
    );

    await result.current.reject("needs more evidence");

    expect(mockDecideGate).toHaveBeenCalledWith("session-123", 3, {
      approved: false,
      feedback: "needs more evidence",
    });
    expect(mockStore.recordGateDecision).toHaveBeenCalledWith(
      expect.objectContaining({ gate_number: 3, approved: false }),
    );
    expect(onGate3DecisionComplete).toHaveBeenCalledWith("rejected");
  });

  it("does not fire gate 3 callback for non-gate-3 decisions", async () => {
    mockStore.currentGate.gate_number = 2;
    const onGate3DecisionComplete = vi.fn();
    const { result } = renderHook(() =>
      useGate({ onGate3DecisionComplete }),
    );

    await result.current.approve();
    expect(onGate3DecisionComplete).not.toHaveBeenCalled();
  });
});
