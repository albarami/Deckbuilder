/**
 * SourceBookModeSelector — Two-card mode selector for proposal generation.
 *
 * Lets the user choose between:
 *   - Full Proposal Deck (standard pipeline)
 *   - Source Book Only (Source Book pipeline)
 *
 * Updates config.proposalMode, which flows to StartPipelineRequest.
 */

"use client";

import { BookOpen, Presentation } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ProposalMode } from "@/lib/types/pipeline";

export interface SourceBookModeSelectorProps {
  /** Currently selected proposal mode */
  value: ProposalMode;
  /** Called when the user selects a mode */
  onChange: (mode: ProposalMode) => void;
  /** Disable during pipeline start */
  disabled?: boolean;
}

interface ModeOption {
  mode: ProposalMode;
  icon: React.ReactNode;
  titleKey: string;
  descriptionKey: string;
}

/**
 * The selector has two visual cards: "deck" and "source_book_only".
 * The "deck" card maps to whatever non-SB mode is active (lite/standard/full).
 * Clicking "deck" sets mode to "standard" (the default deck sub-mode).
 * The old ProposalConfig dropdown lets users pick lite/standard/full within deck mode.
 */
const DECK_CARD: ModeOption = {
  mode: "standard",
  icon: <Presentation className="h-6 w-6" aria-hidden="true" />,
  titleKey: "modeSelector.deckTitle",
  descriptionKey: "modeSelector.deckDescription",
};

const SB_CARD: ModeOption = {
  mode: "source_book_only",
  icon: <BookOpen className="h-6 w-6" aria-hidden="true" />,
  titleKey: "modeSelector.sourceBookTitle",
  descriptionKey: "modeSelector.sourceBookDescription",
};

/** Any mode that is not source_book_only is considered "deck" for card selection. */
function isDeckMode(mode: ProposalMode): boolean {
  return mode !== "source_book_only";
}

const MODE_OPTIONS: ModeOption[] = [DECK_CARD, SB_CARD];

export function SourceBookModeSelector({
  value,
  onChange,
  disabled = false,
}: SourceBookModeSelectorProps) {
  const t = useTranslations("intake");

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-sg-navy dark:text-slate-100">
        {t("modeSelector.title")}
      </h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {MODE_OPTIONS.map((option) => {
          const isSelected =
            option.mode === "source_book_only"
              ? value === "source_book_only"
              : isDeckMode(value);

          return (
            <button
              key={option.mode}
              type="button"
              onClick={() => onChange(option.mode)}
              disabled={disabled}
              data-testid={`mode-card-${option.mode}`}
              className={[
                "group relative flex items-start gap-4 rounded-xl border-2 px-5 py-4 text-left transition-all",
                isSelected
                  ? "border-sg-teal bg-sg-teal/5 shadow-sm dark:border-sky-400 dark:bg-sky-500/10"
                  : "border-sg-border bg-white hover:border-sg-blue/40 hover:bg-sg-mist/40 dark:border-slate-800 dark:bg-slate-950 dark:hover:border-sky-300/40 dark:hover:bg-slate-900",
                disabled
                  ? "cursor-not-allowed opacity-60"
                  : "cursor-pointer",
              ].join(" ")}
              aria-pressed={isSelected}
            >
              {/* Selection indicator */}
              <div
                className={[
                  "mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-colors",
                  isSelected
                    ? "bg-sg-teal text-white dark:bg-sky-500"
                    : "bg-sg-mist text-sg-slate/60 group-hover:bg-sg-blue/10 group-hover:text-sg-blue dark:bg-slate-800 dark:text-slate-400 dark:group-hover:bg-sky-500/10 dark:group-hover:text-sky-300",
                ].join(" ")}
              >
                {option.icon}
              </div>

              <div className="min-w-0 flex-1">
                <p
                  className={[
                    "text-sm font-semibold",
                    isSelected
                      ? "text-sg-teal dark:text-sky-300"
                      : "text-sg-navy dark:text-slate-100",
                  ].join(" ")}
                >
                  {t(option.titleKey)}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-sg-slate/70 dark:text-slate-400">
                  {t(option.descriptionKey)}
                </p>
              </div>

              {/* Selected check */}
              {isSelected && (
                <div className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-sg-teal text-white dark:bg-sky-500">
                  <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                    <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
