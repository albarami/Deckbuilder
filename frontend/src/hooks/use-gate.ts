/**
 * useGate — Gate decision hook with optimistic UI.
 *
 * Provides approve/reject actions that update the store
 * optimistically before the API call completes.
 */

"use client";

import { useCallback } from "react";
import { usePipelineStore } from "@/stores/pipeline-store";
import { decideGate } from "@/lib/api/pipeline";
import { APIError } from "@/lib/types/api";
import type { GateDecisionRequest } from "@/lib/types/pipeline";

interface UseGateOptions {
  onGate3DecisionComplete?: (
    decision: "approved" | "rejected",
  ) => void | Promise<void>;
}

export function useGate(options: UseGateOptions = {}) {
  const store = usePipelineStore();
  const onGate3DecisionComplete = options.onGate3DecisionComplete;

  /**
   * Approve the current pending gate.
   */
  const approve = useCallback(async (modifications?: GateDecisionRequest["modifications"]) => {
    const { sessionId, currentGate } = store;
    if (!sessionId || !currentGate) return;

    const gateNumber = currentGate.gate_number;
    store.setDecidingGate(true);

    try {
      await decideGate(sessionId, gateNumber, {
        approved: true,
        ...(modifications ? { modifications } : {}),
      });

      store.recordGateDecision({
        gate_number: gateNumber,
        approved: true,
        feedback: "",
        decided_at: new Date().toISOString(),
      });

      if (gateNumber === 3 && onGate3DecisionComplete) {
        await onGate3DecisionComplete("approved");
      }
    } catch (err) {
      // Revert to gate_pending on failure
      if (err instanceof APIError) {
        store.setError({ agent: `gate_${gateNumber}`, message: err.message });
      }
      throw err;
    } finally {
      store.setDecidingGate(false);
    }
  }, [onGate3DecisionComplete, store]);

  /**
   * Reject the current pending gate with feedback.
   */
  const reject = useCallback(
    async (feedback: string, modifications?: GateDecisionRequest["modifications"]) => {
      const { sessionId, currentGate } = store;
      if (!sessionId || !currentGate) return;

      const gateNumber = currentGate.gate_number;
      store.setDecidingGate(true);

      try {
        await decideGate(sessionId, gateNumber, {
          approved: false,
          feedback,
          ...(modifications ? { modifications } : {}),
        });

        store.recordGateDecision({
          gate_number: gateNumber,
          approved: false,
          feedback,
          decided_at: new Date().toISOString(),
        });

        if (gateNumber === 3 && onGate3DecisionComplete) {
          await onGate3DecisionComplete("rejected");
        }
      } catch (err) {
        if (err instanceof APIError) {
          store.setError({
            agent: `gate_${gateNumber}`,
            message: err.message,
          });
        }
        throw err;
      } finally {
        store.setDecidingGate(false);
      }
    },
    [onGate3DecisionComplete, store],
  );

  return {
    currentGate: store.currentGate,
    completedGates: store.completedGates,
    isDecidingGate: store.isDecidingGate,
    approve,
    reject,
  };
}
