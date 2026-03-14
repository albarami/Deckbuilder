/**
 * PipelineErrorBanner — Dismissible error banner for pipeline failures.
 *
 * Shows agent name + error message. Can be dismissed by the user.
 */

"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

export interface PipelineErrorBannerProps {
  /** Error details from pipeline store */
  error: { agent: string; message: string };
}

export function PipelineErrorBanner({ error }: PipelineErrorBannerProps) {
  const t = useTranslations("pipeline");
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const agentDisplay = error.agent
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  return (
    <div
      role="alert"
      className="relative rounded-lg border border-red-200 bg-red-50 px-4 py-3"
    >
      <div className="flex items-start gap-3">
        {/* Error icon */}
        <svg
          viewBox="0 0 20 20"
          fill="currentColor"
          className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
            clipRule="evenodd"
          />
        </svg>

        {/* Error content */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-red-800">
            {t("errorTitle")}
          </p>
          <p className="mt-0.5 text-sm text-red-700">
            <span className="font-medium">{agentDisplay}:</span>{" "}
            {error.message}
          </p>
        </div>

        {/* Dismiss button */}
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="rounded p-1 text-red-400 transition-colors hover:bg-red-100 hover:text-red-600"
          aria-label={t("dismissError")}
        >
          <svg viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4">
            <path d="M5.28 4.22a.75.75 0 00-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 101.06 1.06L8 9.06l2.72 2.72a.75.75 0 101.06-1.06L9.06 8l2.72-2.72a.75.75 0 00-1.06-1.06L8 6.94 5.28 4.22z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
