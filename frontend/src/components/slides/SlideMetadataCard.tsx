/**
 * SlideMetadataCard — Fallback card for metadata_only thumbnail mode.
 *
 * When rendered thumbnails aren't available, shows a compact card
 * with slide number, entry type, section, layout, and text preview.
 */

"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import type { SlideInfo } from "@/lib/types/slides";

export interface SlideMetadataCardProps {
  slide: SlideInfo;
  /** Whether this slide is currently selected */
  isSelected?: boolean;
  /** Click handler */
  onClick?: (slide: SlideInfo) => void;
}

/** Entry type → badge variant mapping */
const ENTRY_TYPE_VARIANTS: Record<string, "navy" | "info" | "success" | "default"> = {
  a1_clone: "navy",
  a2_shell: "info",
  b_variable: "success",
  pool_clone: "default",
};

export function SlideMetadataCard({
  slide,
  isSelected = false,
  onClick,
}: SlideMetadataCardProps) {
  const t = useTranslations("slides");

  const handleClick = useCallback(() => {
    onClick?.(slide);
  }, [onClick, slide]);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleClick();
        }
      }}
      className={[
        "group cursor-pointer rounded-lg border-2 p-3 transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sg-blue focus-visible:ring-offset-2",
        isSelected
          ? "border-sg-blue bg-sg-blue/5 shadow-md"
          : "border-sg-border bg-white hover:border-sg-teal hover:shadow-sm",
      ].join(" ")}
      data-testid={`slide-metadata-${slide.slide_number}`}
      aria-label={`Slide ${slide.slide_number}: ${slide.text_preview}`}
    >
      {/* Top row: number + entry type */}
      <div className="flex items-center justify-between">
        <span className="text-lg font-bold text-sg-navy">
          {slide.slide_number}
        </span>
        <Badge variant={ENTRY_TYPE_VARIANTS[slide.entry_type] ?? "default"}>
          {formatEntryType(slide.entry_type)}
        </Badge>
      </div>

      {/* Section and layout */}
      <div className="mt-2 space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-sg-slate/60">
          <FolderIcon />
          <span className="truncate">{slide.section_id}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-sg-slate/60">
          <LayoutIcon />
          <span className="truncate">{slide.semantic_layout_id}</span>
        </div>
      </div>

      {/* Text preview */}
      {slide.text_preview && (
        <p className="mt-2 line-clamp-2 text-xs text-sg-slate/70">
          {slide.text_preview}
        </p>
      )}

      {/* Bottom: shapes + fonts */}
      <div className="mt-2 flex items-center gap-2 text-[10px] text-sg-slate/50">
        <span>{t("shapeCount", { count: slide.shape_count })}</span>
        <span>·</span>
        <span className="truncate">
          {slide.fonts.length > 0 ? slide.fonts.join(", ") : t("noFonts")}
        </span>
      </div>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatEntryType(type: string): string {
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function FolderIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3 flex-shrink-0" aria-hidden="true">
      <path d="M1.75 1A1.75 1.75 0 000 2.75v10.5C0 14.216.784 15 1.75 15h12.5A1.75 1.75 0 0016 13.25v-8.5A1.75 1.75 0 0014.25 3H7.5a.25.25 0 01-.2-.1l-.9-1.2c-.33-.44-.85-.7-1.4-.7H1.75z" />
    </svg>
  );
}

function LayoutIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3 flex-shrink-0" aria-hidden="true">
      <path fillRule="evenodd" d="M2 3.75A.75.75 0 012.75 3h10.5a.75.75 0 010 1.5H2.75A.75.75 0 012 3.75zM2 7.5a.75.75 0 01.75-.75h7.508a.75.75 0 010 1.5H2.75A.75.75 0 012 7.5zm0 3.75a.75.75 0 01.75-.75h4.993a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75z" clipRule="evenodd" />
    </svg>
  );
}
