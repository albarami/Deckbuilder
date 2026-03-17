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
import { CheckCircle2, PencilLine, XCircle } from "lucide-react";
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
  const tCommon = useTranslations("common");
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
      {showFeedback && (
        <div className="mb-5 rounded-xl border border-sg-border bg-sg-white/80 p-4">
          <FeedbackInput
            value={feedback}
            onChange={setFeedback}
            disabled={isLoading}
            minLength={10}
          />
        </div>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3">
        {!showFeedback ? (
          <>
            <Button
              variant="primary"
              size="lg"
              onClick={handleApprove}
              loading={actionType === "approve"}
              disabled={isLoading}
              data-testid="gate-approve-btn"
              className="order-3 bg-sg-teal px-6 shadow-sg-glow-teal hover:bg-sg-navy"
            >
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              {t("approveLabel")}
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={handleRejectClick}
              disabled={isLoading}
              data-testid="gate-request-changes-btn"
              className="order-2 border-sg-border text-sg-slate hover:border-sg-navy/20 hover:bg-sg-mist"
            >
              <PencilLine className="h-4 w-4" aria-hidden="true" />
              {t("requestChanges")}
            </Button>
            <Button
              variant="ghost"
              size="md"
              onClick={handleRejectClick}
              disabled={isLoading}
              data-testid="gate-reject-btn"
              className="order-1 border border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
            >
              <XCircle className="h-4 w-4" aria-hidden="true" />
              {tCommon("reject")}
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
              className="bg-red-600 hover:bg-red-700"
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
