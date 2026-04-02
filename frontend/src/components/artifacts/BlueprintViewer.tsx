/**
 * BlueprintViewer — Grouped card layout for the slide blueprint artifact.
 *
 * Displays contract entries grouped by section_id, with:
 * - Ownership badges (house/dynamic/hybrid)
 * - Slide title, key message, bullet points, evidence refs, visual guidance
 * - Validation violations banner when present
 * - Stats line at bottom
 */

"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { BadgeVariant } from "@/components/ui/Badge";
import type { BlueprintData, BlueprintContractEntry } from "./types";

const OWNERSHIP_VARIANT: Record<BlueprintContractEntry["ownership"], BadgeVariant> = {
  house: "info",
  dynamic: "success",
  hybrid: "warning",
};

/** Group entries by section_id preserving first-seen order. */
function groupBySectionId(entries: BlueprintContractEntry[]) {
  const groups: { sectionId: string; sectionName: string; entries: BlueprintContractEntry[] }[] = [];
  const indexMap = new Map<string, number>();

  for (const entry of entries) {
    const idx = indexMap.get(entry.section_id);
    if (idx !== undefined) {
      groups[idx].entries.push(entry);
    } else {
      indexMap.set(entry.section_id, groups.length);
      groups.push({ sectionId: entry.section_id, sectionName: entry.section_name, entries: [entry] });
    }
  }

  return groups;
}

export function BlueprintViewer({ data }: { data: BlueprintData }) {
  const t = useTranslations("artifacts");
  const groups = groupBySectionId(data.contract_entries);

  return (
    <div className="space-y-6">
      {/* Validation violations banner */}
      {data.validation_violations.length > 0 && (
        <div
          className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-700 dark:bg-amber-950/40"
          role="alert"
        >
          <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            <span className="text-sm font-semibold">{t("blueprint.violationsTitle")}</span>
          </div>
          <ul className="mt-2 list-disc space-y-1 pl-6">
            {data.validation_violations.map((v) => (
              <li key={v} className="text-sm text-amber-800 dark:text-amber-200">
                {v}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Section groups */}
      {groups.map((group) => (
        <section key={group.sectionId} className="space-y-3">
          <h3 className="text-lg font-bold text-sg-slate dark:text-slate-100">
            {group.sectionName}
          </h3>

          {group.entries.map((entry, i) => (
            <EntryCard key={`${entry.section_id}-${i}`} entry={entry} t={t} />
          ))}
        </section>
      ))}

      {/* Stats line */}
      <p className="text-sm text-sg-slate/70 dark:text-slate-400">
        {t("blueprint.stats", {
          contract: data.contract_count,
          legacy: data.legacy_count,
        })}
      </p>
    </div>
  );
}

// ── Entry card ────────────────────────────────────────────────────────────

function EntryCard({
  entry,
  t,
}: {
  entry: BlueprintContractEntry;
  t: ReturnType<typeof useTranslations>;
}) {
  return (
    <div className="rounded-lg border border-sg-border bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
      {/* Ownership badge */}
      <div className="mb-2">
        <Badge variant={OWNERSHIP_VARIANT[entry.ownership]}>
          {t(`blueprint.ownership.${entry.ownership}` as Parameters<typeof t>[0])}
        </Badge>
      </div>

      {/* Slide title */}
      {entry.slide_title && (
        <p className="text-sm font-bold text-sg-slate dark:text-slate-100">
          {entry.slide_title}
        </p>
      )}

      {/* Key message */}
      {entry.key_message && (
        <p className="mt-1 text-sm text-sg-slate dark:text-slate-200">
          {entry.key_message}
        </p>
      )}

      {/* Bullet points */}
      {entry.bullet_points.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5">
          {entry.bullet_points.map((bp) => (
            <li key={bp} className="text-sm text-sg-slate dark:text-slate-300">
              {bp}
            </li>
          ))}
        </ul>
      )}

      {/* Evidence references */}
      {entry.evidence_ids.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {entry.evidence_ids.map((eid) => (
            <Badge key={eid} variant="info">
              {eid}
            </Badge>
          ))}
        </div>
      )}

      {/* Visual guidance */}
      {entry.visual_guidance && (
        <p className="mt-2 text-xs italic text-sg-slate/60 dark:text-slate-400">
          {entry.visual_guidance}
        </p>
      )}
    </div>
  );
}
