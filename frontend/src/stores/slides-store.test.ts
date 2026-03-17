/**
 * Tests for slides-store.
 *
 * Pure store logic — no HTTP calls.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useSlidesStore } from "./slides-store";
import type { SlideInfo } from "@/lib/types/slides";

beforeEach(() => {
  useSlidesStore.getState().reset();
});

const mockSlides: SlideInfo[] = [
  {
    slide_id: "s1",
    slide_number: 1,
    title: "Intro",
    key_message: "",
    layout_type: "layout_1",
    body_content_preview: [],
    source_claims: [],
    source_refs: [],
    speaker_notes_preview: "",
    sensitivity_tags: [],
    content_guidance: "",
    change_history_count: 0,
    preview_kind: "metadata_only",
    entry_type: "a1_clone",
    asset_id: "slide_1",
    semantic_layout_id: "layout_1",
    section_id: "section_1",
    thumbnail_url: null,
    shape_count: 5,
    fonts: ["IBM Plex Sans"],
    text_preview: "Introduction slide",
  },
  {
    slide_id: "s2",
    slide_number: 2,
    title: "Content",
    key_message: "",
    layout_type: "layout_2",
    body_content_preview: [],
    source_claims: [],
    source_refs: [],
    speaker_notes_preview: "",
    sensitivity_tags: [],
    content_guidance: "",
    change_history_count: 0,
    preview_kind: "metadata_only",
    entry_type: "b_variable",
    asset_id: "slide_2",
    semantic_layout_id: "layout_2",
    section_id: "section_1",
    thumbnail_url: null,
    shape_count: 8,
    fonts: ["IBM Plex Sans", "IBM Plex Mono"],
    text_preview: "Content slide with data",
  },
];

describe("SlidesStore", () => {
  it("starts with empty state", () => {
    const state = useSlidesStore.getState();
    expect(state.slides).toHaveLength(0);
    expect(state.slideCount).toBe(0);
    expect(state.thumbnailMode).toBeNull();
    expect(state.selectedSlide).toBeNull();
    expect(state.isLoading).toBe(false);
  });

  it("setSlides populates slides data", () => {
    useSlidesStore.getState().setSlides(mockSlides, 2, "metadata_only");

    const state = useSlidesStore.getState();
    expect(state.slides).toHaveLength(2);
    expect(state.slideCount).toBe(2);
    expect(state.thumbnailMode).toBe("metadata_only");
    expect(state.isLoading).toBe(false);
  });

  it("selectSlide sets selected slide", () => {
    useSlidesStore.getState().setSlides(mockSlides, 2, "metadata_only");
    useSlidesStore.getState().selectSlide(mockSlides[0]);

    expect(useSlidesStore.getState().selectedSlide).toEqual(mockSlides[0]);
  });

  it("selectSlide(null) clears selection", () => {
    useSlidesStore.getState().setSlides(mockSlides, 2, "metadata_only");
    useSlidesStore.getState().selectSlide(mockSlides[0]);
    useSlidesStore.getState().selectSlide(null);

    expect(useSlidesStore.getState().selectedSlide).toBeNull();
  });

  it("setLoading updates loading state", () => {
    useSlidesStore.getState().setLoading(true);
    expect(useSlidesStore.getState().isLoading).toBe(true);

    useSlidesStore.getState().setLoading(false);
    expect(useSlidesStore.getState().isLoading).toBe(false);
  });

  it("setError sets error and clears loading", () => {
    useSlidesStore.getState().setLoading(true);
    useSlidesStore.getState().setError("Failed to load slides");

    const state = useSlidesStore.getState();
    expect(state.error).toBe("Failed to load slides");
    expect(state.isLoading).toBe(false);
  });

  it("reset clears all state", () => {
    useSlidesStore.getState().setSlides(mockSlides, 2, "rendered");
    useSlidesStore.getState().selectSlide(mockSlides[1]);
    useSlidesStore.getState().reset();

    const state = useSlidesStore.getState();
    expect(state.slides).toHaveLength(0);
    expect(state.selectedSlide).toBeNull();
    expect(state.thumbnailMode).toBeNull();
  });
});
