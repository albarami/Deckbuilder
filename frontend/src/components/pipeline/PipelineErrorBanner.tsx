/**
 * PipelineErrorBanner — Dismissible error banner for pipeline failures.
 *
 * Shows agent name + error message. Can be dismissed by the user.
 */

"use client";

import { useState } from "react";
import { AlertCircle, X } from "lucide-react";
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
      className="relative rounded-xl border border-red-200 bg-red-50 px-4 py-3 shadow-sm"
    >
      <div className="flex items-start gap-3">
        <AlertCircle
          className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500"
          aria-hidden="true"
        />

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-red-800">
            {t("errorTitle")}
          </p>
          <p className="mt-0.5 text-sm text-red-700">
            <span className="font-medium">{agentDisplay}:</span>{" "}
            {error.message}
          </p>
        </div>

        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="rounded p-1 text-red-400 transition-colors hover:bg-red-100 hover:text-red-600"
          aria-label={t("dismissError")}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
