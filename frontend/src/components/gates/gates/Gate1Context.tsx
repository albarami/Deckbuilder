/**
 * Gate1Context — RFP Context Analysis review panel.
 *
 * Renders the structured Gate1ContextData payload from the backend:
 * rfp_brief (nested RfpBriefInput), missing_fields, output_language,
 * user_notes, and evaluation_highlights.
 */

"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import type { GateInfo, Gate1ContextData } from "@/lib/types/pipeline";

export interface Gate1ContextProps {
  gate: GateInfo;
}

interface ContextEntry {
  key: string;
  value: string;
}

export function Gate1Context({ gate }: Gate1ContextProps) {
  const t = useTranslations("gate");
  const data = gate.gate_data as Gate1ContextData | null | undefined;
  const entries = extractContextEntries(data);
  const missingFields = data?.missing_fields ?? [];
  const highlights = data?.evaluation_highlights ?? [];

  return (
    <div data-testid="gate-1-context">
      <p className="mb-4 text-sm text-sg-slate/70 dark:text-slate-300">{gate.summary}</p>

      {/* Missing fields warning */}
      {missingFields.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800/50 dark:bg-amber-900/20">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-400">
            {t("missingFields")}
          </p>
          <div className="mt-1 flex flex-wrap gap-1">
            {missingFields.map((field) => (
              <Badge key={field} variant="warning">{formatKey(field)}</Badge>
            ))}
          </div>
        </div>
      )}

      {entries.length === 0 ? (
        <p className="text-sm italic text-sg-slate/50 dark:text-slate-400">{t("noData")}</p>
      ) : (
        <div className="divide-y divide-sg-border rounded-lg border border-sg-border dark:divide-slate-800 dark:border-slate-800">
          {entries.map((entry) => (
            <div
              key={entry.key}
              className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-start sm:gap-4"
            >
              <dt className="min-w-[140px] text-xs font-semibold uppercase tracking-wider text-sg-slate/60 dark:text-slate-400">
                {formatKey(entry.key)}
              </dt>
              <dd className="flex-1 text-sm text-sg-navy dark:text-slate-100">{entry.value}</dd>
            </div>
          ))}
        </div>
      )}

      {/* Evaluation highlights */}
      {highlights.length > 0 && (
        <div className="mt-4 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-sg-slate/60 dark:text-slate-400">
            {t("evaluationHighlights")}
          </p>
          <ul className="list-inside list-disc text-sm text-sg-slate/70 dark:text-slate-300">
            {highlights.map((hl, i) => (
              <li key={i}>{hl}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

/**
 * Extract displayable key-value pairs from Gate1ContextData.
 * Flattens the nested rfp_brief into human-readable rows.
 */
function extractContextEntries(data: Gate1ContextData | null | undefined): ContextEntry[] {
  if (!data) return [];

  const entries: ContextEntry[] = [];
  const brief = data.rfp_brief;

  if (brief) {
    if (brief.rfp_name?.en) entries.push({ key: "rfp_name", value: brief.rfp_name.en });
    if (brief.rfp_name?.ar) entries.push({ key: "rfp_name_ar", value: brief.rfp_name.ar });
    if (brief.issuing_entity) entries.push({ key: "issuing_entity", value: brief.issuing_entity });
    if (brief.procurement_platform) entries.push({ key: "procurement_platform", value: brief.procurement_platform });
    if (brief.mandate_summary) entries.push({ key: "mandate_summary", value: brief.mandate_summary });
    if (brief.scope_requirements?.length) {
      entries.push({ key: "scope_requirements", value: brief.scope_requirements.join("; ") });
    }
    if (brief.deliverables?.length) {
      entries.push({ key: "deliverables", value: brief.deliverables.join("; ") });
    }
    if (brief.mandatory_compliance?.length) {
      entries.push({ key: "mandatory_compliance", value: brief.mandatory_compliance.join("; ") });
    }
    const dates = brief.key_dates;
    if (dates) {
      const dateParts = [
        dates.submission_deadline && `Submission: ${dates.submission_deadline}`,
        dates.inquiry_deadline && `Inquiry: ${dates.inquiry_deadline}`,
        dates.expected_award_date && `Award: ${dates.expected_award_date}`,
        dates.service_start_date && `Start: ${dates.service_start_date}`,
      ].filter(Boolean);
      if (dateParts.length) entries.push({ key: "key_dates", value: dateParts.join(" · ") });
    }
  }

  if (data.selected_output_language) {
    entries.push({ key: "output_language", value: data.selected_output_language.toUpperCase() });
  }
  if (data.user_notes) {
    entries.push({ key: "user_notes", value: data.user_notes });
  }

  return entries;
}

/** Convert snake_case keys to Title Case labels */
function formatKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
