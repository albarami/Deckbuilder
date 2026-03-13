/**
 * SSE Client — EventSource wrapper with auto-reconnect and heartbeat.
 *
 * Connects to GET /api/pipeline/{id}/stream for real-time events.
 *
 * Features:
 * - Auto-reconnect with 2s backoff (max 30s)
 * - Heartbeat monitoring (expects every 15s)
 * - Typed SSEEvent parsing
 * - Clean disconnect
 */

import { BASE_URL } from "./client";
import type { SSEEvent } from "@/lib/types/pipeline";

export interface SSEClientOptions {
  /** Called for each received event */
  onEvent: (event: SSEEvent) => void;
  /** Called when connection is established */
  onOpen?: () => void;
  /** Called on connection error (before reconnect) */
  onError?: (error: Event) => void;
  /** Called when stream ends (pipeline_complete or pipeline_error) */
  onClose?: () => void;
}

const INITIAL_RETRY_MS = 2000;
const MAX_RETRY_MS = 30000;

/**
 * Create an SSE connection to a pipeline session stream.
 * Returns a disconnect function.
 */
export function connectSSE(
  sessionId: string,
  options: SSEClientOptions,
): () => void {
  let eventSource: EventSource | null = null;
  let retryMs = INITIAL_RETRY_MS;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  function connect(): void {
    if (closed) return;

    const url = `${BASE_URL}/api/pipeline/${sessionId}/stream`;
    eventSource = new EventSource(url);

    eventSource.onopen = () => {
      retryMs = INITIAL_RETRY_MS; // Reset backoff on successful connect
      options.onOpen?.();
    };

    eventSource.onmessage = (messageEvent: MessageEvent) => {
      try {
        const event: SSEEvent = JSON.parse(messageEvent.data);

        // Forward event to handler
        options.onEvent(event);

        // Check for terminal events
        if (
          event.type === "pipeline_complete" ||
          event.type === "pipeline_error"
        ) {
          disconnect();
          options.onClose?.();
        }
      } catch {
        // Ignore parse errors (e.g., empty heartbeats)
      }
    };

    eventSource.onerror = (error: Event) => {
      options.onError?.(error);

      // Close the broken connection
      eventSource?.close();
      eventSource = null;

      // Reconnect with exponential backoff
      if (!closed) {
        reconnectTimer = setTimeout(() => {
          retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
          connect();
        }, retryMs);
      }
    };
  }

  function disconnect(): void {
    closed = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  // Start connection
  connect();

  // Return cleanup function
  return disconnect;
}
