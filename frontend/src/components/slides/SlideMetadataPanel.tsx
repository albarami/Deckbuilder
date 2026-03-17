/**
 * SlideMetadataPanel — Detailed metadata display for a selected slide.
 *
 * Shows entry type, layout, section, shape count, fonts, and text preview
 * in a structured panel. Used in the detail modal side panel.
 */

"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import type { SlideInfo } from "@/lib/types/slides";

export interface SlideMetadataPanelProps {
  slide: SlideInfo;
  className?: string;
}

/** Entry type → badge variant */
const ENTRY_TYPE_VARIANTS: Record<string, "navy" | "info" | "success" | "default"> = {
  a1_clone: "navy",
  a2_shell: "info",
  b_variable: "success",
  pool_clone: "default",
};

export function SlideMetadataPanel({ slide, className = "" }: SlideMetadataPanelProps) {
  const t = useTranslations("slides");

  return (
    <div className={`space-y-4 ${className}`} data-testid="slide-metadata-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-sg-navy dark:text-slate-100">
          {t("slideNumber", { number: slide.slide_number })}
        </h3>
        <Badge variant={ENTRY_TYPE_VARIANTS[slide.entry_type ?? ""] ?? "default"}>
          {formatEntryType(slide.entry_type ?? "")}
        </Badge>
      </div>

      {/* Metadata fields */}
      <dl className="divide-y divide-sg-border rounded-lg border border-sg-border text-sm dark:divide-slate-800 dark:border-slate-800">
        <MetadataRow label="Slide ID" value={slide.slide_id} />
        <MetadataRow label={t("metaSection")} value={slide.section_id ?? slide.section ?? ""} />
        <MetadataRow
          label={t("metaLayout")}
          value={slide.layout_type || slide.semantic_layout_id || ""}
        />
        <MetadataRow label={t("metaAssetId")} value={slide.asset_id ?? ""} />
        <MetadataRow
          label={t("metaShapes")}
          value={String(slide.shape_count ?? 0)}
        />
        <MetadataRow label="Report Section" value={slide.report_section_ref ?? "—"} />
        <MetadataRow label="Criterion" value={slide.rfp_criterion_ref ?? "—"} />
        <MetadataRow label="Refs" value={String(slide.source_refs.length)} />
        <MetadataRow
          label={t("metaFonts")}
          value={
            (slide.fonts?.length ?? 0) > 0
              ? slide.fonts!.join(", ")
              : t("noFonts")
          }
        />
      </dl>

      {slide.key_message && (
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-sg-slate/60 dark:text-slate-400">
            Key Message
          </h4>
          <p className="rounded-lg bg-sg-mist/50 p-3 text-sm text-sg-slate dark:bg-slate-950/70 dark:text-slate-200">
            {slide.key_message}
          </p>
        </div>
      )}

      {/* Text preview */}
      {(slide.text_preview || slide.body_content_preview.length > 0) && (
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-sg-slate/60 dark:text-slate-400">
            {t("metaTextPreview")}
          </h4>
          <p className="rounded-lg bg-sg-mist/50 p-3 text-sm text-sg-slate dark:bg-slate-950/70 dark:text-slate-200">
            {slide.text_preview || slide.body_content_preview.join(" • ")}
          </p>
        </div>
      )}

      {slide.speaker_notes_preview && (
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-sg-slate/60 dark:text-slate-400">
            Speaker Notes
          </h4>
          <p className="rounded-lg bg-sg-mist/50 p-3 text-sm text-sg-slate dark:bg-slate-950/70 dark:text-slate-200">
            {slide.speaker_notes_preview}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

function MetadataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 px-3 py-2.5">
      <dt className="min-w-[80px] text-xs font-semibold uppercase tracking-wider text-sg-slate/60 dark:text-slate-400">
        {label}
      </dt>
      <dd className="flex-1 break-all text-sm text-sg-navy dark:text-slate-100">{value}</dd>
    </div>
  );
}

function formatEntryType(type: string): string {
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
