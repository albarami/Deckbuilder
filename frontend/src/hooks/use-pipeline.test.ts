import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { usePipeline } from "./use-pipeline";
import { APIError } from "@/lib/types/api";

const mockStore = {
  sessionId: "sess-1",
  status: "running" as const,
  currentStage: "source_book_generation",
  currentGate: null,
  completedGates: [],
  outputs: null,
  error: null,
  startedAt: "2026-03-25T10:00:00Z",
  elapsedMs: 1000,
  sessionMetadata: {
    total_llm_calls: 1,
    total_input_tokens: 1,
    total_output_tokens: 1,
    total_cost_usd: 0.1,
  },
  agentRuns: [],
  events: [],
  proposalMode: "standard" as const,
  sourceBookSummary: null,
  isStarting: false,
  setStarting: vi.fn(),
  setSession: vi.fn(),
  setError: vi.fn(),
  restoreFromStatus: vi.fn(),
  reset: vi.fn(),
};

const mockStartPipeline = vi.fn();
const mockGetStatus = vi.fn();
const mockIsPending = vi.fn(() => false);
const mockIsReady = vi.fn(() => false);

vi.mock("@/stores/pipeline-store", () => ({
  usePipelineStore: () => mockStore,
  isSourceBookGatePending: () => mockIsPending(),
  isSourceBookReadyCheckpoint: () => mockIsReady(),
}));

vi.mock("@/lib/api/pipeline", () => ({
  startPipeline: (...args: unknown[]) => mockStartPipeline(...args),
  getStatus: (...args: unknown[]) => mockGetStatus(...args),
}));

describe("usePipeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsPending.mockReturnValue(true);
    mockIsReady.mockReturnValue(false);
  });

  it("exposes source-book derived selectors", () => {
    const { result } = renderHook(() => usePipeline());

    expect(result.current.isSourceBookGatePending).toBe(true);
    expect(result.current.isSourceBookReadyCheckpoint).toBe(false);
    expect(mockIsPending).toHaveBeenCalled();
    expect(mockIsReady).toHaveBeenCalled();
  });

  it("starts pipeline and stores session id", async () => {
    mockStartPipeline.mockResolvedValue({
      session_id: "sess-new",
      created_at: "2026-03-25T10:00:01Z",
    });

    const { result } = renderHook(() => usePipeline());
    const sessionId = await result.current.start({
      documents: [{ upload_id: "up1", filename: "rfp.pdf" }],
      renderer_mode: "template_v2",
      language: "en",
      proposal_mode: "standard",
      sector: "technology",
      geography: "saudi_arabia",
    });

    expect(sessionId).toBe("sess-new");
    expect(mockStore.setStarting).toHaveBeenCalledWith(true);
    expect(mockStore.setSession).toHaveBeenCalledWith("sess-new", "2026-03-25T10:00:01Z", "standard");
    expect(mockStore.setStarting).toHaveBeenLastCalledWith(false);
  });

  it("returns false when resume gets 404", async () => {
    mockGetStatus.mockRejectedValue(new APIError(404, { code: "SESSION_NOT_FOUND", message: "Not found" }));
    const { result } = renderHook(() => usePipeline());
    await expect(result.current.resume("missing")).resolves.toBe(false);
  });
});
