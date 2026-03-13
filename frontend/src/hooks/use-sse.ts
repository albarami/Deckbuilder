/**
 * useSSE — SSE subscription hook with auto-reconnect.
 *
 * Connects to the pipeline SSE stream and dispatches events
 * to the pipeline store. Manages connection lifecycle.
 *
 * Features:
 * - Auto-connect when sessionId changes
 * - Auto-disconnect on unmount
 * - 2s backoff reconnect (handled by sse.ts)
 * - Updates pipeline store on each event
 */

"use client";

import { useEffect, useRef, useCallback } from "react";
import { usePipelineStore } from "@/stores/pipeline-store";
import { connectSSE } from "@/lib/api/sse";

interface UseSSEOptions {
  /** Pipeline session ID to subscribe to */
  sessionId: string | null;
  /** Whether to enable the SSE connection */
  enabled?: boolean;
}

export function useSSE({ sessionId, enabled = true }: UseSSEOptions) {
  const disconnectRef = useRef<(() => void) | null>(null);
  const handleSSEEvent = usePipelineStore((s) => s.handleSSEEvent);

  const disconnect = useCallback(() => {
    if (disconnectRef.current) {
      disconnectRef.current();
      disconnectRef.current = null;
    }
  }, []);

  useEffect(() => {
    // Don't connect if no session or disabled
    if (!sessionId || !enabled) {
      disconnect();
      return;
    }

    // Clean up any existing connection
    disconnect();

    // Connect to SSE stream
    disconnectRef.current = connectSSE(sessionId, {
      onEvent: handleSSEEvent,
      onOpen: () => {
        // Connection established
      },
      onError: () => {
        // Error handled internally by connectSSE (auto-reconnect)
      },
      onClose: () => {
        // Stream ended (pipeline complete or error)
        disconnectRef.current = null;
      },
    });

    // Cleanup on unmount or dependency change
    return disconnect;
  }, [sessionId, enabled, handleSSEEvent, disconnect]);

  return { disconnect };
}
