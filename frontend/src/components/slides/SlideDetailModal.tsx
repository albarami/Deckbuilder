/**
 * SlideDetailModal — Full-size slide view with metadata panel.
 *
 * Opens when a slide thumbnail/card is clicked.
 * Shows:
 * - Full-size image (rendered mode) or expanded metadata (metadata_only)
 * - SlideMetadataPanel side panel
 * - Prev/Next navigation
 * - Close button
 */

"use client";

import { useCallback, useEffect } from "react";
import { useTranslations } from "next-intl";
import { SlideMetadataPanel } from "./SlideMetadataPanel";
import { getThumbnailUrl } from "@/lib/api/slides";
import type { SlideInfo, ThumbnailMode } from "@/lib/types/slides";

export interface SlideDetailModalProps {
  /** The currently selected slide */
  slide: SlideInfo;
  /** All slides (for prev/next navigation) */
  allSlides: SlideInfo[];
  /** Thumbnail display mode */
  thumbnailMode: ThumbnailMode;
  /** Session ID for thumbnail URLs */
  sessionId: string;
  /** Called when modal should close */
  onClose: () => void;
  /** Called when navigating to a different slide */
  onNavigate: (slide: SlideInfo) => void;
}

export function SlideDetailModal({
  slide,
  allSlides,
  thumbnailMode,
  sessionId,
  onClose,
  onNavigate,
}: SlideDetailModalProps) {
  const t = useTranslations("slides");

  const currentIndex = allSlides.findIndex(
    (s) => s.slide_number === slide.slide_number,
  );
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < allSlides.length - 1;

  const handlePrev = useCallback(() => {
    if (hasPrev) onNavigate(allSlides[currentIndex - 1]);
  }, [hasPrev, currentIndex, allSlides, onNavigate]);

  const handleNext = useCallback(() => {
    if (hasNext) onNavigate(allSlides[currentIndex + 1]);
  }, [hasNext, currentIndex, allSlides, onNavigate]);

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") handlePrev();
      if (e.key === "ArrowRight") handleNext();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, handlePrev, handleNext]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  const thumbnailUrl =
    slide.thumbnail_url ?? getThumbnailUrl(sessionId, slide.slide_number);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      data-testid="slide-detail-modal"
      role="dialog"
      aria-modal="true"
      aria-label={t("slideNumber", { number: slide.slide_number })}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-sg-navy/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal content */}
      <div className="relative z-10 mx-4 flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl lg:flex-row">
        {/* Left: image/placeholder area */}
        <div className="flex flex-1 items-center justify-center bg-sg-mist/30 p-6">
          {thumbnailMode === "rendered" ? (
            <img
              src={thumbnailUrl}
              alt={`Slide ${slide.slide_number}`}
              className="max-h-[60vh] w-full rounded-lg object-contain shadow-md"
            />
          ) : (
            <div className="flex h-64 w-full items-center justify-center rounded-lg border-2 border-dashed border-sg-border">
              <div className="text-center">
                <SlideIconLarge />
                <p className="mt-2 text-sm text-sg-slate/50">
                  {t("noThumbnailAvailable")}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Right: metadata panel */}
        <div className="w-full overflow-y-auto border-t border-sg-border p-5 lg:w-80 lg:border-s lg:border-t-0">
          <SlideMetadataPanel slide={slide} />
        </div>

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute end-3 top-3 rounded-full bg-white/80 p-1.5 text-sg-slate/70 shadow hover:bg-white hover:text-sg-navy"
          aria-label={t("close")}
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5" aria-hidden="true">
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>

        {/* Navigation arrows */}
        {hasPrev && (
          <button
            onClick={handlePrev}
            className="absolute start-3 top-1/2 -translate-y-1/2 rounded-full bg-white/80 p-2 text-sg-slate/70 shadow hover:bg-white hover:text-sg-navy"
            aria-label={t("prevSlide")}
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 rtl:rotate-180" aria-hidden="true">
              <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
            </svg>
          </button>
        )}
        {hasNext && (
          <button
            onClick={handleNext}
            className="absolute end-3 top-1/2 -translate-y-1/2 rounded-full bg-white/80 p-2 text-sg-slate/70 shadow hover:bg-white hover:text-sg-navy lg:end-[21rem]"
            aria-label={t("nextSlide")}
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 rtl:rotate-180" aria-hidden="true">
              <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
            </svg>
          </button>
        )}

        {/* Slide counter */}
        <div className="absolute bottom-3 start-1/2 -translate-x-1/2 rounded-full bg-sg-navy/70 px-3 py-1 text-xs font-medium text-white lg:start-[calc(50%-10rem)]">
          {currentIndex + 1} / {allSlides.length}
        </div>
      </div>
    </div>
  );
}

function SlideIconLarge() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1"
      className="mx-auto h-16 w-16 text-sg-slate/20"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5"
      />
    </svg>
  );
}
