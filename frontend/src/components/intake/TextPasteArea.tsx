/**
 * TextPasteArea — Textarea for pasting RFP text directly.
 *
 * Alternative to file upload. Supports Arabic RTL text input.
 * Shows character count.
 */

"use client";

import { useTranslations } from "next-intl";
import { useLocaleStore } from "@/stores/locale-store";

export interface TextPasteAreaProps {
  /** Controlled text value */
  value: string;
  /** Called on text change */
  onChange: (value: string) => void;
  /** Disable during pipeline start */
  disabled?: boolean;
}

export function TextPasteArea({
  value,
  onChange,
  disabled = false,
}: TextPasteAreaProps) {
  const t = useTranslations("intake");
  const { direction } = useLocaleStore();

  const charCount = value.length;
  const hasContent = charCount > 0;

  return (
    <div className="space-y-2">
      <label
        htmlFor="rfp-text-paste"
        className="block text-sm font-semibold text-sg-navy"
      >
        {t("orPasteText")}
      </label>

      <div className="relative">
        <textarea
          id="rfp-text-paste"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={t("pasteHere")}
          disabled={disabled}
          dir={direction}
          rows={6}
          className={[
            "w-full resize-y rounded-lg border bg-sg-white px-4 py-3 text-sm text-sg-slate transition-colors",
            "placeholder:text-sg-slate/40",
            "focus:border-sg-blue focus:outline-none focus:ring-2 focus:ring-sg-blue/20",
            disabled
              ? "cursor-not-allowed border-sg-border/50 bg-sg-mist/50 opacity-60"
              : "border-sg-border hover:border-sg-blue/40",
          ].join(" ")}
          aria-describedby="text-paste-char-count"
        />

        {/* Character count */}
        {hasContent && (
          <span
            id="text-paste-char-count"
            className="absolute bottom-3 text-xs text-sg-slate/50 ltr:right-3 rtl:left-3"
          >
            {charCount.toLocaleString()} chars
          </span>
        )}
      </div>
    </div>
  );
}
