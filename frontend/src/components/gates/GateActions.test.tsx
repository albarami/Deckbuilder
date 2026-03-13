/**
 * GateActions component tests.
 *
 * Tests approve/reject workflow, feedback requirement, and button states.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GateActions } from "./GateActions";

// ── Mocks ──────────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const t = (key: string, values?: Record<string, unknown>) => {
      const messages: Record<string, string> = {
        approveLabel: "Approve & Continue",
        rejectLabel: "Reject & Revise",
        submitRejection: "Submit Rejection",
        cancelRejection: "Cancel",
        feedbackLabel: "Feedback",
        feedbackPlaceholder: "Provide feedback for revision...",
        feedbackMinLength: `Minimum ${values?.count ?? 10} characters`,
      };
      return messages[key] ?? key;
    };
    return t;
  },
}));

vi.mock("@/stores/locale-store", () => ({
  useLocaleStore: () => ({
    locale: "en",
    direction: "ltr",
    isRtl: false,
  }),
}));

// ── Helpers ────────────────────────────────────────────────────────────

function renderActions(overrides: Partial<React.ComponentProps<typeof GateActions>> = {}) {
  const defaultProps = {
    onApprove: vi.fn().mockResolvedValue(undefined),
    onReject: vi.fn().mockResolvedValue(undefined),
    isDeciding: false,
    ...overrides,
  };
  return { ...render(<GateActions {...defaultProps} />), props: defaultProps };
}

// ── Tests ──────────────────────────────────────────────────────────────

describe("GateActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows approve and reject buttons by default", () => {
    renderActions();
    expect(screen.getByTestId("gate-approve-btn")).toBeInTheDocument();
    expect(screen.getByTestId("gate-reject-btn")).toBeInTheDocument();
  });

  it("calls onApprove when approve button is clicked", async () => {
    const { props } = renderActions();
    fireEvent.click(screen.getByTestId("gate-approve-btn"));
    await waitFor(() => {
      expect(props.onApprove).toHaveBeenCalledOnce();
    });
  });

  it("shows feedback input when reject button is clicked", async () => {
    renderActions();
    fireEvent.click(screen.getByTestId("gate-reject-btn"));

    // Feedback area should appear
    expect(screen.getByTestId("feedback-input")).toBeInTheDocument();
    // Buttons should switch
    expect(screen.getByTestId("gate-submit-reject-btn")).toBeInTheDocument();
    expect(screen.getByTestId("gate-cancel-reject-btn")).toBeInTheDocument();
    // Original buttons should be gone
    expect(screen.queryByTestId("gate-approve-btn")).not.toBeInTheDocument();
  });

  it("disables submit rejection when feedback is too short", () => {
    renderActions();
    fireEvent.click(screen.getByTestId("gate-reject-btn"));

    const submitBtn = screen.getByTestId("gate-submit-reject-btn");
    expect(submitBtn).toBeDisabled();
  });

  it("enables submit rejection when feedback meets minimum length", async () => {
    const user = userEvent.setup();
    renderActions();
    fireEvent.click(screen.getByTestId("gate-reject-btn"));

    const textarea = screen.getByPlaceholderText("Provide feedback for revision...");
    await user.type(textarea, "This needs more detailed analysis of the market sector");

    const submitBtn = screen.getByTestId("gate-submit-reject-btn");
    expect(submitBtn).not.toBeDisabled();
  });

  it("calls onReject with feedback when submit rejection is clicked", async () => {
    const user = userEvent.setup();
    const { props } = renderActions();

    fireEvent.click(screen.getByTestId("gate-reject-btn"));

    const textarea = screen.getByPlaceholderText("Provide feedback for revision...");
    await user.type(textarea, "Please add more context about the RFP requirements");

    fireEvent.click(screen.getByTestId("gate-submit-reject-btn"));

    await waitFor(() => {
      expect(props.onReject).toHaveBeenCalledWith(
        "Please add more context about the RFP requirements",
      );
    });
  });

  it("hides feedback when cancel is clicked", () => {
    renderActions();
    fireEvent.click(screen.getByTestId("gate-reject-btn"));
    expect(screen.getByTestId("feedback-input")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("gate-cancel-reject-btn"));

    expect(screen.queryByTestId("feedback-input")).not.toBeInTheDocument();
    expect(screen.getByTestId("gate-approve-btn")).toBeInTheDocument();
    expect(screen.getByTestId("gate-reject-btn")).toBeInTheDocument();
  });

  it("disables all buttons when isDeciding is true", () => {
    renderActions({ isDeciding: true });
    expect(screen.getByTestId("gate-approve-btn")).toBeDisabled();
    expect(screen.getByTestId("gate-reject-btn")).toBeDisabled();
  });

  it("shows minimum length warning for short feedback", async () => {
    const user = userEvent.setup();
    renderActions();
    fireEvent.click(screen.getByTestId("gate-reject-btn"));

    const textarea = screen.getByPlaceholderText("Provide feedback for revision...");
    await user.type(textarea, "Too short");

    expect(screen.getByText("Minimum 10 characters")).toBeInTheDocument();
  });
});
