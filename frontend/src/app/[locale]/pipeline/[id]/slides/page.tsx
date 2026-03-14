/**
 * Slide Browser Page — full-page slide grid with export bar.
 *
 * Fetches slide metadata from GET /api/pipeline/{id}/slides on mount.
 * Handles 409 (pipeline not complete) gracefully.
 * Opens SlideDetailModal on slide click.
 */

"use client";

import { useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useSlidesStore } from "@/stores/slides-store";
import { getSlides } from "@/lib/api/slides";
import { APIError } from "@/lib/types/api";
import { SlideGrid } from "@/components/slides/SlideGrid";
import { SlideDetailModal } from "@/components/slides/SlideDetailModal";
import { SlideExportBar } from "@/components/slides/SlideExportBar";
import { Button } from "@/components/ui/Button";
import { Link } from "@/i18n/routing";
import type { SlideInfo } from "@/lib/types/slides";

export default function SlideBrowserPage() {
  const t = useTranslations("slides");
  const params = useParams<{ id: string }>();
  const sessionId = params.id;

  const store = useSlidesStore();

  // Fetch slides on mount
  useEffect(() => {
    async function fetchSlides() {
      if (!sessionId) return;

      store.setLoading(true);
      store.setError(null);

      try {
        const response = await getSlides(sessionId);
        store.setSlides(response.slides, response.slide_count, response.thumbnail_mode);
      } catch (err) {
        if (err instanceof APIError && err.status === 409) {
          store.setError(t("pipelineNotComplete"));
        } else if (err instanceof APIError) {
          store.setError(err.message);
        } else {
          store.setError(t("loadError"));
        }
      }
    }

    fetchSlides();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      useSlidesStore.getState().reset();
    };
  }, []);

  const handleSlideClick = useCallback(
    (slide: SlideInfo) => {
      store.selectSlide(slide);
    },
    [store],
  );

  const handleCloseModal = useCallback(() => {
    store.selectSlide(null);
  }, [store]);

  const handleNavigate = useCallback(
    (slide: SlideInfo) => {
      store.selectSlide(slide);
    },
    [store],
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-sg-navy">{t("title")}</h1>
          <p className="text-sm text-sg-slate/60">
            {t("sessionLabel")}: {sessionId.slice(0, 8)}
          </p>
        </div>
        <Link href={`/pipeline/${sessionId}`}>
          <Button variant="ghost" size="sm">
            {t("backToPipeline")}
          </Button>
        </Link>
      </div>

      {/* Export bar (only when slides are loaded) */}
      {store.slides.length > 0 && (
        <SlideExportBar
          sessionId={sessionId}
          pptxReady={true}
          docxReady={true}
          slideCount={store.slideCount}
        />
      )}

      {/* Slide grid */}
      <SlideGrid
        slides={store.slides}
        thumbnailMode={store.thumbnailMode ?? "metadata_only"}
        sessionId={sessionId}
        selectedSlideNumber={store.selectedSlide?.slide_number}
        onSlideClick={handleSlideClick}
        isLoading={store.isLoading}
        error={store.error}
      />

      {/* Detail modal */}
      {store.selectedSlide && (
        <SlideDetailModal
          slide={store.selectedSlide}
          allSlides={store.slides}
          thumbnailMode={store.thumbnailMode ?? "metadata_only"}
          sessionId={sessionId}
          onClose={handleCloseModal}
          onNavigate={handleNavigate}
        />
      )}
    </div>
  );
}
