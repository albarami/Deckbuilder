/**
 * FeedbackInput — Textarea for gate rejection feedback.
 *
 * Shows when a reviewer clicks "Reject" and requires
 * a reason/feedback before the rejection is submitted.
 * RTL-aware via locale store direction.
 */

"use client";

import { useTranslations } from "next-intl";
import { useLocaleStore } from "@/stores/locale-store";

export interface FeedbackInputProps {
  /** Current feedback value */
  value: string;
  /** Change handler */
  onChange: (value: string) => void;
  /** Whether the input is disabled */
  disabled?: boolean;
  /** Optional minimum length required */
  minLength?: number;
  /** Optional CSS class */
  className?: string;
}

export function FeedbackInput({
  value,
  onChange,
  disabled = false,
  minLength = 10,
  className = "",
}: FeedbackInputProps) {
  const t = useTranslations("gate");
  const { direction } = useLocaleStore();
  const isValid = value.trim().length >= minLength;

  return (
    <div className={className} data-testid="feedback-input">
      <label
        htmlFor="gate-feedback"
        className="mb-1.5 block text-sm font-medium text-sg-navy"
      >
        {t("feedbackLabel")}
      </label>
      <textarea
        id="gate-feedback"
        dir={direction}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        rows={3}
        placeholder={t("feedbackPlaceholder")}
        className={[
          "w-full rounded-lg border px-3 py-2 text-sm text-sg-slate",
          "placeholder:text-sg-slate/40",
          "focus:border-sg-blue focus:outline-none focus:ring-2 focus:ring-sg-blue/20",
          "disabled:cursor-not-allowed disabled:bg-sg-mist/50",
          isValid || value.length === 0
            ? "border-sg-border"
            : "border-amber-400",
        ].join(" ")}
      />
      {value.length > 0 && !isValid && (
        <p className="mt-1 text-xs text-amber-600">
          {t("feedbackMinLength", { count: minLength })}
        </p>
      )}
    </div>
  );
}
