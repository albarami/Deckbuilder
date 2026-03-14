/**
 * ErrorBoundary component tests.
 *
 * Tests the catch-all error boundary UI with retry behavior.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

// ── Helpers ────────────────────────────────────────────────────────────

function ThrowingComponent({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error("Test error message");
  }
  return <div data-testid="child-content">Content renders fine</div>;
}

// Suppress console.error from ErrorBoundary in tests
beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
});

// ── Tests ──────────────────────────────────────────────────────────────

describe("ErrorBoundary", () => {
  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.queryByTestId("error-boundary")).not.toBeInTheDocument();
  });

  it("renders error UI when child throws", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("error-boundary")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("shows custom title and message", () => {
    render(
      <ErrorBoundary title="Custom Error" message="Custom message text">
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Custom Error")).toBeInTheDocument();
    expect(screen.getByText("Custom message text")).toBeInTheDocument();
  });

  it("shows retry button by default", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Try Again")).toBeInTheDocument();
  });

  it("hides retry button when showRetry is false", () => {
    render(
      <ErrorBoundary showRetry={false}>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.queryByText("Try Again")).not.toBeInTheDocument();
  });

  it("calls onError callback when error occurs", () => {
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0]).toBeInstanceOf(Error);
    expect(onError.mock.calls[0][0].message).toBe("Test error message");
  });

  it("renders custom fallback when provided", () => {
    render(
      <ErrorBoundary fallback={<div data-testid="custom-fallback">Custom fallback</div>}>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
    expect(screen.queryByTestId("error-boundary")).not.toBeInTheDocument();
  });

  it("recovers after retry click", () => {
    // We need a component that we can control to stop throwing
    let shouldThrow = true;
    function ControlledComponent() {
      if (shouldThrow) throw new Error("Test error");
      return <div data-testid="recovered">Recovered</div>;
    }

    const { rerender } = render(
      <ErrorBoundary>
        <ControlledComponent />
      </ErrorBoundary>,
    );

    // Error state
    expect(screen.getByTestId("error-boundary")).toBeInTheDocument();

    // Fix the throw condition
    shouldThrow = false;

    // Click retry
    fireEvent.click(screen.getByText("Try Again"));

    // Re-render after state reset - children should render now
    rerender(
      <ErrorBoundary>
        <ControlledComponent />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("recovered")).toBeInTheDocument();
  });
});
