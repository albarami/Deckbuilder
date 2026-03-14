/**
 * GateActions — Approve/Reject action buttons with feedback input.
 *
 * Handles the gate decision workflow:
 * 1. Default state: Approve and Reject buttons visible
 * 2. On "Reject" click: shows FeedbackInput, requires feedback
 * 3. On "Approve" click: calls approve immediately
 * 4. On "Submit Rejection" click: calls reject with feedback
 *
 * Uses the useGate hook for API calls with optimistic UI.
 */

"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { FeedbackInput } from "./shared/FeedbackInput";

export interface GateActionsProps {
  /** Called when the gate is approved */
  onApprove: () => Promise<void>;
  /** Called when the gate is rejected with feedback */
  onReject: (feedback: string) => Promise<void>;
  /** Optional modifications to include with the decision */
  modifications?: unknown;
  /** Whether a decision is being processed */
  isDeciding?: boolean;
  /** Optional CSS class */
  className?: string;
}

export function GateActions({
  onApprove,
  onReject,
  isDeciding = false,
  className = "",
}: GateActionsProps) {
  const t = useTranslations("gate");
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [actionType, setActionType] = useState<"approve" | "reject" | null>(null);

  const handleApprove = useCallback(async () => {
    setActionType("approve");
    try {
      await onApprove();
    } finally {
      setActionType(null);
    }
  }, [onApprove]);

  const handleRejectClick = useCallback(() => {
    setShowFeedback(true);
  }, []);

  const handleSubmitRejection = useCallback(async () => {
    if (feedback.trim().length < 10) return;
    setActionType("reject");
    try {
      await onReject(feedback.trim());
    } finally {
      setActionType(null);
      setShowFeedback(false);
      setFeedback("");
    }
  }, [feedback, onReject]);

  const handleCancelRejection = useCallback(() => {
    setShowFeedback(false);
    setFeedback("");
  }, []);

  const isLoading = isDeciding || actionType !== null;

  return (
    <div className={className} data-testid="gate-actions">
      {/* Feedback area (shown when rejecting) */}
      {showFeedback && (
        <div className="mb-4">
          <FeedbackInput
            value={feedback}
            onChange={setFeedback}
            disabled={isLoading}
            minLength={10}
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        {!showFeedback ? (
          <>
            <Button
              variant="primary"
              size="md"
              onClick={handleApprove}
              loading={actionType === "approve"}
              disabled={isLoading}
              data-testid="gate-approve-btn"
            >
              <CheckIcon />
              {t("approveLabel")}
            </Button>
            <Button
              variant="danger"
              size="md"
              onClick={handleRejectClick}
              disabled={isLoading}
              data-testid="gate-reject-btn"
            >
              <XIcon />
              {t("rejectLabel")}
            </Button>
          </>
        ) : (
          <>
            <Button
              variant="danger"
              size="md"
              onClick={handleSubmitRejection}
              loading={actionType === "reject"}
              disabled={isLoading || feedback.trim().length < 10}
              data-testid="gate-submit-reject-btn"
            >
              {t("submitRejection")}
            </Button>
            <Button
              variant="ghost"
              size="md"
              onClick={handleCancelRejection}
              disabled={isLoading}
              data-testid="gate-cancel-reject-btn"
            >
              {t("cancelRejection")}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Icons ──────────────────────────────────────────────────────────────

function CheckIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function XIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
    </svg>
  );
}
