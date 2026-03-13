/**
 * Slides Store — Zustand state for slide preview data.
 *
 * Manages:
 * - Slide metadata list
 * - Thumbnail mode (rendered vs metadata_only)
 * - Selected slide for detail view
 * - Loading state
 */

import { create } from "zustand";
import type { SlideInfo, ThumbnailMode } from "@/lib/types/slides";

interface SlidesState {
  slides: SlideInfo[];
  slideCount: number;
  thumbnailMode: ThumbnailMode | null;
  selectedSlide: SlideInfo | null;
  isLoading: boolean;
  error: string | null;
}

interface SlidesActions {
  /** Set slides data from API response */
  setSlides: (
    slides: SlideInfo[],
    slideCount: number,
    thumbnailMode: ThumbnailMode,
  ) => void;

  /** Select a slide for detail view */
  selectSlide: (slide: SlideInfo | null) => void;

  /** Set loading state */
  setLoading: (v: boolean) => void;

  /** Set error */
  setError: (error: string | null) => void;

  /** Reset to initial state */
  reset: () => void;
}

export type SlidesStore = SlidesState & SlidesActions;

const initialState: SlidesState = {
  slides: [],
  slideCount: 0,
  thumbnailMode: null,
  selectedSlide: null,
  isLoading: false,
  error: null,
};

export const useSlidesStore = create<SlidesStore>((set) => ({
  ...initialState,

  setSlides: (slides, slideCount, thumbnailMode) =>
    set({ slides, slideCount, thumbnailMode, isLoading: false, error: null }),

  selectSlide: (slide) => set({ selectedSlide: slide }),

  setLoading: (v) => set({ isLoading: v }),

  setError: (error) => set({ error, isLoading: false }),

  reset: () => set(initialState),
}));
