/**
 * ProposalConfig — Proposal parameter configuration form.
 *
 * Fields: Language, Proposal Mode, Sector, Geography.
 * All select inputs with i18n labels.
 * Validation: all fields required before pipeline start.
 */

"use client";

import { useTranslations } from "next-intl";
import type { ProposalMode } from "@/lib/types/pipeline";

// ── Types ──────────────────────────────────────────────────────────────

export interface ProposalConfigValues {
  language: "en" | "ar";
  proposalMode: ProposalMode;
  sector: string;
  geography: string;
}

export interface ProposalConfigProps {
  /** Controlled config values */
  values: ProposalConfigValues;
  /** Called when any field changes */
  onChange: (values: ProposalConfigValues) => void;
  /** Disable during pipeline start */
  disabled?: boolean;
}

// ── Options ────────────────────────────────────────────────────────────

const LANGUAGE_OPTIONS: { value: "en" | "ar"; labelKey: string }[] = [
  { value: "en", labelKey: "config.languageEn" },
  { value: "ar", labelKey: "config.languageAr" },
];

const MODE_OPTIONS: { value: ProposalMode; labelKey: string }[] = [
  { value: "lite", labelKey: "config.modeLite" },
  { value: "standard", labelKey: "config.modeStandard" },
  { value: "full", labelKey: "config.modeFull" },
];

const SECTOR_OPTIONS = [
  "Technology",
  "Healthcare",
  "Financial Services",
  "Energy",
  "Government",
  "Education",
  "Real Estate",
  "Retail",
  "Manufacturing",
  "Other",
];

const GEOGRAPHY_OPTIONS = [
  "Saudi Arabia",
  "UAE",
  "Gulf (GCC)",
  "Middle East",
  "North Africa",
  "Global",
];

// ── Component ──────────────────────────────────────────────────────────

export function ProposalConfig({
  values,
  onChange,
  disabled = false,
}: ProposalConfigProps) {
  const t = useTranslations("intake");

  const update = (field: keyof ProposalConfigValues, value: string) => {
    onChange({ ...values, [field]: value });
  };

  // Hide the old mode dropdown when Source Book mode is active —
  // the SourceBookModeSelector card above is the single mode control.
  const isSourceBookMode = values.proposalMode === "source_book_only";

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-sg-navy dark:text-slate-100">
        {t("configuration")}
      </h3>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Language */}
        <SelectField
          id="config-language"
          label={t("language")}
          value={values.language}
          onChange={(v) => update("language", v)}
          disabled={disabled}
        >
          {LANGUAGE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {t(opt.labelKey)}
            </option>
          ))}
        </SelectField>

        {/* Proposal Mode — hidden when Source Book mode is set via SourceBookModeSelector */}
        {!isSourceBookMode && (
          <SelectField
            id="config-mode"
            label={t("proposalMode")}
            value={values.proposalMode}
            onChange={(v) => update("proposalMode", v)}
            disabled={disabled}
          >
            {MODE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {t(opt.labelKey)}
              </option>
            ))}
          </SelectField>
        )}

        {/* Sector */}
        <SelectField
          id="config-sector"
          label={t("sector")}
          value={values.sector}
          onChange={(v) => update("sector", v)}
          disabled={disabled}
          placeholder={t("selectSector")}
        >
          {SECTOR_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </SelectField>

        {/* Geography */}
        <SelectField
          id="config-geography"
          label={t("geography")}
          value={values.geography}
          onChange={(v) => update("geography", v)}
          disabled={disabled}
          placeholder={t("selectGeography")}
        >
          {GEOGRAPHY_OPTIONS.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </SelectField>
      </div>
    </div>
  );
}

// ── Validation ─────────────────────────────────────────────────────────

/**
 * Validate that all config fields are filled.
 * Returns true if config is valid for pipeline start.
 * Sector and geography are free-form strings that start empty.
 */
export function isConfigValid(config: ProposalConfigValues): boolean {
  return (
    config.language.length > 0 &&
    config.proposalMode.length > 0 &&
    config.sector.length > 0 &&
    config.geography.length > 0
  );
}

// ── SelectField ────────────────────────────────────────────────────────

function SelectField({
  id,
  label,
  value,
  onChange,
  disabled,
  placeholder,
  children,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  placeholder?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-sg-slate dark:text-slate-300">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={[
          "w-full rounded-lg border bg-sg-white px-3 py-2 text-sm text-sg-slate transition-colors dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100",
          "focus:border-sg-blue focus:outline-none focus:ring-2 focus:ring-sg-blue/20 dark:focus:border-sky-300 dark:focus:ring-sky-400/20",
          disabled
            ? "cursor-not-allowed border-sg-border/50 bg-sg-mist/50 opacity-60 dark:border-slate-800 dark:bg-slate-900/70"
            : "border-sg-border hover:border-sg-blue/40 dark:hover:border-sky-300/50",
          !value && placeholder ? "text-sg-slate/40 dark:text-slate-500" : "",
        ].join(" ")}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {children}
      </select>
    </div>
  );
}
