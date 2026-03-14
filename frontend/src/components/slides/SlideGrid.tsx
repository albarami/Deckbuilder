/**
 * SlideGrid — Thumbnail grid that handles both rendered and metadata_only modes.
 *
 * When `thumbnail_mode === "rendered"`: renders SlideThumbnail with images.
 * When `thumbnail_mode === "metadata_only"`: renders SlideMetadataCard.
 *
 * Supports selection for detail view.
 */

"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";
import { SlideThumbnail } from "./SlideThumbnail";
import { SlideMetadataCard } from "./SlideMetadataCard";
import { getThumbnailUrl } from "@/lib/api/slides";
import { Spinner } from "@/components/ui/Spinner";
import type { SlideInfo, ThumbnailMode } from "@/lib/types/slides";

export interface SlideGridProps {
  /** Slides to display */
  slides: SlideInfo[];
  /** How thumbnails are served */
  thumbnailMode: ThumbnailMode;
  /** Session ID for constructing thumbnail URLs */
  sessionId: string;
  /** Currently selected slide number (if any) */
  selectedSlideNumber?: number | null;
  /** Called when a slide is clicked */
  onSlideClick?: (slide: SlideInfo) => void;
  /** Whether slides are loading */
  isLoading?: boolean;
  /** Error message */
  error?: string | null;
}

export function SlideGrid({
  slides,
  thumbnailMode,
  sessionId,
  selectedSlideNumber = null,
  onSlideClick,
  isLoading = false,
  error = null,
}: SlideGridProps) {
  const t = useTranslations("slides");

  const handleSlideClick = useCallback(
    (slide: SlideInfo) => {
      onSlideClick?.(slide);
    },
    [onSlideClick],
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="flex min-h-[200px] items-center justify-center" data-testid="slide-grid-loading">
        <Spinner size="lg" label={t("loading")} />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className="flex min-h-[200px] items-center justify-center rounded-lg border border-red-200 bg-red-50 p-6"
        data-testid="slide-grid-error"
      >
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  // Empty state
  if (slides.length === 0) {
    return (
      <div
        className="flex min-h-[200px] items-center justify-center rounded-lg border border-sg-border p-6"
        data-testid="slide-grid-empty"
      >
        <p className="text-sm text-sg-slate/50">{t("noSlides")}</p>
      </div>
    );
  }

  return (
    <div data-testid="slide-grid">
      {/* Grid header */}
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm text-sg-slate/60">
          {t("slideCount", { count: slides.length })}
        </p>
        <p className="text-xs text-sg-slate/40">
          {thumbnailMode === "rendered" ? t("modeRendered") : t("modeMetadata")}
        </p>
      </div>

      {/* Grid */}
      <div
        className={[
          "grid gap-3",
          thumbnailMode === "rendered"
            ? "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
            : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
        ].join(" ")}
        role="list"
        aria-label={t("gridLabel")}
      >
        {slides.map((slide) => (
          <div key={slide.slide_number} role="listitem">
            {thumbnailMode === "rendered" ? (
              <SlideThumbnail
                slide={slide}
                thumbnailUrl={
                  slide.thumbnail_url ??
                  getThumbnailUrl(sessionId, slide.slide_number)
                }
                isSelected={selectedSlideNumber === slide.slide_number}
                onClick={handleSlideClick}
              />
            ) : (
              <SlideMetadataCard
                slide={slide}
                isSelected={selectedSlideNumber === slide.slide_number}
                onClick={handleSlideClick}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
