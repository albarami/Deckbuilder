/**
 * Error boundary page — shown when an unhandled error occurs in a route segment.
 *
 * Next.js error boundary for the [locale] layout. Catches runtime errors
 * and displays a branded recovery UI with retry option.
 */

"use client";

import { useEffect } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  // Log error in development
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.error("[ErrorPage]", error);
    }
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card variant="default" className="max-w-md text-center">
        {/* Error icon */}
        <div className="mb-4 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="h-8 w-8 text-red-600"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
              />
            </svg>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-lg font-semibold text-sg-navy">
          Something went wrong
        </h1>

        {/* Message */}
        <p className="mt-2 text-sm text-sg-slate/70">
          An unexpected error occurred. You can try again or return to the
          dashboard.
        </p>

        {/* Error digest (for support) */}
        {error.digest && (
          <p className="mt-2 text-xs text-sg-slate/40">
            Error ID: {error.digest}
          </p>
        )}

        {/* Error details in development */}
        {process.env.NODE_ENV === "development" && (
          <pre className="mt-3 max-h-32 overflow-auto rounded bg-sg-mist p-2 text-left text-xs text-red-600">
            {error.message}
          </pre>
        )}

        {/* Actions */}
        <div className="mt-6 flex justify-center gap-3">
          <Button variant="primary" size="md" onClick={reset}>
            Try Again
          </Button>
          <a
            href="/"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-sg-navy px-4 py-2 text-sm font-semibold text-sg-navy transition-colors hover:bg-sg-navy hover:text-white"
          >
            Go to Dashboard
          </a>
        </div>
      </Card>
    </div>
  );
}
