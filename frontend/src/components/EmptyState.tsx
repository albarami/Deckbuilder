/**
 * EmptyState — No-data state with illustration and action.
 *
 * Used when a list/view has no content to display.
 * Provides branded empty state with optional icon, message, and CTA.
 */

"use client";

import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";

export type EmptyStateIcon = "document" | "slides" | "search" | "inbox" | "folder";

export interface EmptyStateProps {
  /** Title text */
  title: string;
  /** Description text */
  description?: string;
  /** Icon to show */
  icon?: EmptyStateIcon;
  /** Optional action button */
  action?: {
    label: string;
    onClick: () => void;
  };
  /** Optional custom illustration */
  children?: ReactNode;
  /** Optional CSS class */
  className?: string;
}

export function EmptyState({
  title,
  description,
  icon = "document",
  action,
  children,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex min-h-[200px] flex-col items-center justify-center py-12 text-center ${className}`}
      data-testid="empty-state"
    >
      {/* Icon or custom illustration */}
      {children ?? (
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-sg-mist">
          <EmptyIcon variant={icon} />
        </div>
      )}

      {/* Title */}
      <h3 className="mt-2 text-base font-semibold text-sg-navy">{title}</h3>

      {/* Description */}
      {description && (
        <p className="mt-1 max-w-sm text-sm text-sg-slate/60">{description}</p>
      )}

      {/* Action button */}
      {action && (
        <Button
          variant="primary"
          size="md"
          onClick={action.onClick}
          className="mt-4"
        >
          {action.label}
        </Button>
      )}
    </div>
  );
}

// ── Icons ────────────────────────────────────────────────────────────────

function EmptyIcon({ variant }: { variant: EmptyStateIcon }) {
  const iconClass = "h-8 w-8 text-sg-slate/40";

  switch (variant) {
    case "document":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
      );
    case "slides":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
        </svg>
      );
    case "search":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
      );
    case "inbox":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-17.399 0V5.507c0-.621.504-1.125 1.125-1.125h15.75c.621 0 1.125.504 1.125 1.125v7.993" />
        </svg>
      );
    case "folder":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={iconClass} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
        </svg>
      );
  }
}
