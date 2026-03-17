/**
 * Gate4Slides — Slide Rendering review panel.
 *
 * Shows the slide outline as a tree view with section → slide hierarchy.
 * Gate data contains { slides: SlideOutline[] } with title, section, and type.
 */

"use client";

import { FolderOpen, Image as ImageIcon, Layers3, Presentation } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import type { GateInfo } from "@/lib/types/pipeline";

export interface Gate4SlidesProps {
  gate: GateInfo;
}

interface SlideOutline {
  slide_id: string;
  index: number;
  title: string;
  key_message: string;
  layout_type: string;
  section: string;
  slide_type: string;
  report_section_ref?: string;
  source_refs: string[];
}

interface SectionGroup {
  section: string;
  slides: SlideOutline[];
}

export function Gate4Slides({ gate }: Gate4SlidesProps) {
  const t = useTranslations("gate");
  const slides = extractSlides(gate.gate_data);
  const sections = groupBySection(slides);

  return (
    <div data-testid="gate-4-slides">
      <p className="mb-4 text-sm text-sg-slate/70 dark:text-slate-300">{gate.summary}</p>

      {sections.length === 0 ? (
        <p className="text-sm italic text-sg-slate/50 dark:text-slate-400">{t("noData")}</p>
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-sg-slate/60 dark:text-slate-400">
            {t("slideCount", { count: slides.length })}
          </p>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {slides.map((slide) => (
              <div
                key={slide.index}
                className="overflow-hidden rounded-xl border border-sg-border bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="relative aspect-video border-b border-sg-border bg-sg-mist dark:border-slate-800 dark:bg-slate-950">
                  <div className="absolute inset-0 flex items-center justify-center">
                    <ImageIcon className="h-9 w-9 text-sg-blue/35" aria-hidden="true" />
                  </div>
                  <div className="absolute bottom-3 left-3 rounded-full bg-sg-navy/80 px-2 py-0.5 text-[11px] font-medium text-white">
                    #{slide.index + 1}
                  </div>
                </div>
                <div className="space-y-2 px-4 py-3">
                  <p className="truncate text-sm font-semibold text-sg-navy dark:text-slate-100">
                    {slide.title}
                  </p>
                  {slide.key_message && (
                    <p className="line-clamp-2 text-xs text-sg-slate/70 dark:text-slate-300">
                      {slide.key_message}
                    </p>
                  )}
                  <div className="flex items-center justify-between gap-2 text-xs text-sg-slate/60 dark:text-slate-400">
                    <span className="inline-flex min-w-0 items-center gap-1.5 truncate">
                      <Layers3 className="h-3.5 w-3.5" aria-hidden="true" />
                      {slide.section}
                    </span>
                    <Badge variant="info" className="text-[10px] uppercase">
                      {slide.layout_type || slide.slide_type}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-sg-slate/55 dark:text-slate-400">
                    <span>{slide.slide_id}</span>
                    <span>·</span>
                    <span>{slide.source_refs.length} refs</span>
                    {slide.report_section_ref && (
                      <>
                        <span>·</span>
                        <span>{slide.report_section_ref}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-sg-border bg-white dark:border-slate-800 dark:bg-slate-900">
            {sections.map((group, gi) => (
              <div
                key={group.section}
                className={gi > 0 ? "border-t border-sg-border" : ""}
              >
                {/* Section header */}
                <div className="flex items-center gap-2 bg-sg-mist/50 px-4 py-2 dark:bg-slate-950/70">
                  <FolderIcon />
                  <span className="text-sm font-semibold text-sg-navy dark:text-slate-100">
                    {group.section}
                  </span>
                  <Badge variant="default">{group.slides.length}</Badge>
                </div>

                {/* Slides in section */}
                <ul className="divide-y divide-sg-border/50 dark:divide-slate-800">
                  {group.slides.map((slide) => (
                    <li
                      key={slide.index}
                      className="flex items-center gap-3 px-4 py-2 ps-8"
                    >
                      <SlideIcon />
                      <span className="flex-1 truncate text-sm text-sg-slate dark:text-slate-300">
                        {slide.title}
                      </span>
                      <Badge
                        variant="info"
                        className="text-[10px] uppercase"
                      >
                        {slide.slide_type}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

function extractSlides(data: unknown): SlideOutline[] {
  if (!data || typeof data !== "object") return [];
  const obj = data as Record<string, unknown>;
  const slides = obj.slides;
  if (!Array.isArray(slides)) return [];

  return slides.map((s: Record<string, unknown>, i: number) => ({
    slide_id: String(s.slide_id ?? `S-${String(i + 1).padStart(3, "0")}`),
    index: typeof s.index === "number" ? s.index : i,
    title: String(s.title ?? `Slide ${i + 1}`),
    key_message: String(s.key_message ?? ""),
    layout_type: String(s.layout_type ?? ""),
    section: String(s.section ?? "Other"),
    slide_type: String(s.slide_type ?? "content"),
    report_section_ref: typeof s.report_section_ref === "string" ? s.report_section_ref : undefined,
    source_refs: Array.isArray(s.source_refs)
      ? s.source_refs.map((value) => String(value))
      : [],
  }));
}

function groupBySection(slides: SlideOutline[]): SectionGroup[] {
  const map = new Map<string, SlideOutline[]>();
  for (const slide of slides) {
    const list = map.get(slide.section) ?? [];
    list.push(slide);
    map.set(slide.section, list);
  }
  return Array.from(map.entries()).map(([section, sectionSlides]) => ({
    section,
    slides: sectionSlides,
  }));
}

function FolderIcon() {
  return <FolderOpen className="h-4 w-4 text-sg-teal" aria-hidden="true" />;
}

function SlideIcon() {
  return <Presentation className="h-3.5 w-3.5 text-sg-slate/40" aria-hidden="true" />;
}
