/**
 * 404 Not Found page — shown when a route doesn't match.
 *
 * Branded DeckForge 404 with navigation back to dashboard.
 */

import { Card } from "@/components/ui/Card";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card variant="default" className="max-w-md text-center">
        {/* 404 illustration */}
        <div className="mb-4 flex justify-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-sg-mist">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="h-10 w-10 text-sg-slate/40"
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

        {/* Error code */}
        <p className="text-4xl font-bold text-sg-navy">404</p>

        {/* Title */}
        <h1 className="mt-2 text-lg font-semibold text-sg-navy">
          Page Not Found
        </h1>

        {/* Message */}
        <p className="mt-2 text-sm text-sg-slate/70">
          The page you are looking for does not exist or has been moved.
        </p>

        {/* Action */}
        <a
          href="/"
          className="mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-sg-blue px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-sg-teal"
        >
          Go to Dashboard
        </a>
      </Card>
    </div>
  );
}
