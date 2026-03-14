/**
 * ErrorBoundary — Catch-all error UI for React component tree errors.
 *
 * Wraps children and catches rendering errors, displaying a branded
 * fallback UI with retry option. Used at page and section levels.
 */

"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export interface ErrorBoundaryProps {
  /** Content to render when no error */
  children: ReactNode;
  /** Optional fallback to show instead of default error UI */
  fallback?: ReactNode;
  /** Optional error handler callback */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  /** Title text for the error card */
  title?: string;
  /** Message text for the error card */
  message?: string;
  /** Whether to show retry button (default: true) */
  showRetry?: boolean;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.props.onError?.(error, errorInfo);

    // Log to console in development
    if (process.env.NODE_ENV === "development") {
      console.error("[ErrorBoundary]", error, errorInfo);
    }
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default branded error UI
      return (
        <div
          className="flex min-h-[200px] items-center justify-center p-6"
          data-testid="error-boundary"
        >
          <Card variant="default" className="max-w-md text-center">
            {/* Error icon */}
            <div className="mb-4 flex justify-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="h-6 w-6 text-red-600"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
            </div>

            {/* Title */}
            <h2 className="text-lg font-semibold text-sg-navy">
              {this.props.title ?? "Something went wrong"}
            </h2>

            {/* Message */}
            <p className="mt-2 text-sm text-sg-slate/70">
              {this.props.message ??
                "An unexpected error occurred. Please try again."}
            </p>

            {/* Error details in development */}
            {process.env.NODE_ENV === "development" && this.state.error && (
              <pre className="mt-3 max-h-32 overflow-auto rounded bg-sg-mist p-2 text-left text-xs text-red-600">
                {this.state.error.message}
              </pre>
            )}

            {/* Retry button */}
            {(this.props.showRetry ?? true) && (
              <Button
                variant="primary"
                size="md"
                onClick={this.handleRetry}
                className="mt-4"
              >
                Try Again
              </Button>
            )}
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}
