/**
 * LoadingSkeleton — Content loading skeleton placeholders.
 *
 * Provides shimmer-animated skeleton shapes for async content:
 * - line: text line placeholder
 * - card: full card skeleton
 * - grid: grid of card skeletons
 * - form: form field skeletons
 * - table: table row skeletons
 *
 * Uses Tailwind animate-pulse with SG brand mist color.
 */

"use client";

export type SkeletonVariant = "line" | "card" | "grid" | "form" | "table";

export interface LoadingSkeletonProps {
  /** Skeleton shape variant */
  variant?: SkeletonVariant;
  /** Number of items to show (for line, grid, table) */
  count?: number;
  /** Optional CSS class */
  className?: string;
}

export function LoadingSkeleton({
  variant = "card",
  count = 3,
  className = "",
}: LoadingSkeletonProps) {
  return (
    <div
      className={`animate-pulse ${className}`}
      role="status"
      aria-label="Loading"
      data-testid="loading-skeleton"
    >
      {variant === "line" && <LinesSkeleton count={count} />}
      {variant === "card" && <CardSkeleton />}
      {variant === "grid" && <GridSkeleton count={count} />}
      {variant === "form" && <FormSkeleton />}
      {variant === "table" && <TableSkeleton count={count} />}
      <span className="sr-only">Loading...</span>
    </div>
  );
}

// ── Skeleton Shapes ──────────────────────────────────────────────────

function LinesSkeleton({ count }: { count: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded bg-sg-mist"
          style={{ width: `${85 - i * 15}%` }}
        />
      ))}
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="rounded-lg border border-sg-border bg-sg-white p-card">
      {/* Header */}
      <div className="mb-4 flex items-center gap-3">
        <div className="h-10 w-10 rounded-full bg-sg-mist" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-3/4 rounded bg-sg-mist" />
          <div className="h-3 w-1/2 rounded bg-sg-mist" />
        </div>
      </div>
      {/* Body lines */}
      <div className="space-y-2">
        <div className="h-3 w-full rounded bg-sg-mist" />
        <div className="h-3 w-5/6 rounded bg-sg-mist" />
        <div className="h-3 w-4/6 rounded bg-sg-mist" />
      </div>
      {/* Footer */}
      <div className="mt-4 flex gap-2">
        <div className="h-8 w-24 rounded-lg bg-sg-mist" />
        <div className="h-8 w-24 rounded-lg bg-sg-mist" />
      </div>
    </div>
  );
}

function GridSkeleton({ count }: { count: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-lg border border-sg-border bg-sg-white p-4"
        >
          {/* Thumbnail area */}
          <div className="mb-3 aspect-video w-full rounded bg-sg-mist" />
          {/* Text lines */}
          <div className="space-y-2">
            <div className="h-4 w-3/4 rounded bg-sg-mist" />
            <div className="h-3 w-1/2 rounded bg-sg-mist" />
          </div>
        </div>
      ))}
    </div>
  );
}

function FormSkeleton() {
  return (
    <div className="space-y-5">
      {/* Field 1 */}
      <div className="space-y-2">
        <div className="h-4 w-24 rounded bg-sg-mist" />
        <div className="h-10 w-full rounded-lg bg-sg-mist" />
      </div>
      {/* Field 2 */}
      <div className="space-y-2">
        <div className="h-4 w-32 rounded bg-sg-mist" />
        <div className="h-10 w-full rounded-lg bg-sg-mist" />
      </div>
      {/* Field 3 — textarea */}
      <div className="space-y-2">
        <div className="h-4 w-28 rounded bg-sg-mist" />
        <div className="h-24 w-full rounded-lg bg-sg-mist" />
      </div>
      {/* Button */}
      <div className="h-10 w-36 rounded-lg bg-sg-mist" />
    </div>
  );
}

function TableSkeleton({ count }: { count: number }) {
  return (
    <div className="w-full">
      {/* Header row */}
      <div className="mb-3 flex gap-4 border-b border-sg-border pb-3">
        <div className="h-4 w-1/4 rounded bg-sg-mist" />
        <div className="h-4 w-1/4 rounded bg-sg-mist" />
        <div className="h-4 w-1/4 rounded bg-sg-mist" />
        <div className="h-4 w-1/4 rounded bg-sg-mist" />
      </div>
      {/* Data rows */}
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex gap-4 py-3">
          <div className="h-3 w-1/4 rounded bg-sg-mist" />
          <div className="h-3 w-1/4 rounded bg-sg-mist" />
          <div className="h-3 w-1/4 rounded bg-sg-mist" />
          <div className="h-3 w-1/4 rounded bg-sg-mist" />
        </div>
      ))}
    </div>
  );
}
