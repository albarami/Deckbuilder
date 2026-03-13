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

export function useGate() {
  const store = usePipelineStore();

  /**
   * Approve the current pending gate.
   */
  const approve = useCallback(async () => {
    const { sessionId, currentGate } = store;
    if (!sessionId || !currentGate) return;

    const gateNumber = currentGate.gate_number;
    store.setDecidingGate(true);

    try {
      const response = await decideGate(sessionId, gateNumber, {
        approved: true,
      });

      store.recordGateDecision({
        gate_number: gateNumber,
        approved: true,
        feedback: "",
        decided_at: new Date().toISOString(),
      });
    } catch (err) {
      // Revert to gate_pending on failure
      if (err instanceof APIError) {
        store.setError({ agent: `gate_${gateNumber}`, message: err.message });
      }
      throw err;
    } finally {
      store.setDecidingGate(false);
    }
  }, [store]);

  /**
   * Reject the current pending gate with feedback.
   */
  const reject = useCallback(
    async (feedback: string) => {
      const { sessionId, currentGate } = store;
      if (!sessionId || !currentGate) return;

      const gateNumber = currentGate.gate_number;
      store.setDecidingGate(true);

      try {
        const response = await decideGate(sessionId, gateNumber, {
          approved: false,
          feedback,
        });

        store.recordGateDecision({
          gate_number: gateNumber,
          approved: false,
          feedback,
          decided_at: new Date().toISOString(),
        });
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
    [store],
  );

  return {
    currentGate: store.currentGate,
    completedGates: store.completedGates,
    isDecidingGate: store.isDecidingGate,
    approve,
    reject,
  };
}
