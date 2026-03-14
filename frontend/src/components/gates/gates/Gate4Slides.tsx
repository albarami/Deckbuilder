/**
 * Gate4Slides — Slide Rendering review panel.
 *
 * Shows the slide outline as a tree view with section → slide hierarchy.
 * Gate data contains { slides: SlideOutline[] } with title, section, and type.
 */

"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/Badge";
import type { GateInfo } from "@/lib/types/pipeline";

export interface Gate4SlidesProps {
  gate: GateInfo;
}

interface SlideOutline {
  index: number;
  title: string;
  section: string;
  slide_type: string;
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
      <p className="mb-4 text-sm text-sg-slate/70">{gate.summary}</p>

      {sections.length === 0 ? (
        <p className="text-sm text-sg-slate/50 italic">{t("noData")}</p>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-sg-slate/60">
            {t("slideCount", { count: slides.length })}
          </p>
          <div className="rounded-lg border border-sg-border">
            {sections.map((group, gi) => (
              <div
                key={group.section}
                className={gi > 0 ? "border-t border-sg-border" : ""}
              >
                {/* Section header */}
                <div className="flex items-center gap-2 bg-sg-mist/50 px-4 py-2">
                  <FolderIcon />
                  <span className="text-sm font-semibold text-sg-navy">
                    {group.section}
                  </span>
                  <Badge variant="default">{group.slides.length}</Badge>
                </div>

                {/* Slides in section */}
                <ul className="divide-y divide-sg-border/50">
                  {group.slides.map((slide) => (
                    <li
                      key={slide.index}
                      className="flex items-center gap-3 px-4 py-2 ps-8"
                    >
                      <SlideIcon />
                      <span className="flex-1 text-sm text-sg-slate truncate">
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
    index: typeof s.index === "number" ? s.index : i,
    title: String(s.title ?? `Slide ${i + 1}`),
    section: String(s.section ?? "Other"),
    slide_type: String(s.slide_type ?? "content"),
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
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4 flex-shrink-0 text-sg-teal"
      aria-hidden="true"
    >
      <path d="M3.75 3A1.75 1.75 0 002 4.75v3.26a3.235 3.235 0 011.75-.51h12.5c.644 0 1.245.188 1.75.51V6.75A1.75 1.75 0 0016.25 5h-4.836a.25.25 0 01-.177-.073L9.823 3.513A1.75 1.75 0 008.586 3H3.75zM3.75 9A1.75 1.75 0 002 10.75v4.5c0 .966.784 1.75 1.75 1.75h12.5A1.75 1.75 0 0018 15.25v-4.5A1.75 1.75 0 0016.25 9H3.75z" />
    </svg>
  );
}

function SlideIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-3.5 w-3.5 flex-shrink-0 text-sg-slate/40"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M4.5 2A1.5 1.5 0 003 3.5v13A1.5 1.5 0 004.5 18h11a1.5 1.5 0 001.5-1.5V7.621a1.5 1.5 0 00-.44-1.06l-4.12-4.122A1.5 1.5 0 0011.378 2H4.5z"
        clipRule="evenodd"
      />
    </svg>
  );
}
