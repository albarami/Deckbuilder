/**
 * SlideGrid component tests.
 *
 * Tests both rendering modes, loading/error/empty states, and slide selection.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SlideGrid } from "./SlideGrid";
import type { SlideInfo } from "@/lib/types/slides";

// ── Mocks ──────────────────────────────────────────────────────────────

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const t = (key: string, values?: Record<string, unknown>) => {
      const messages: Record<string, string> = {
        loading: "Loading slides...",
        noSlides: "No slides available",
        slideCount: `${values?.count ?? 0} slides`,
        modeRendered: "Image Thumbnails",
        modeMetadata: "Metadata View",
        gridLabel: "Slide grid",
        shapeCount: `${values?.count ?? 0} shapes`,
        noFonts: "No fonts",
        slideNumber: `Slide ${values?.number ?? ""}`,
        metaSection: "Section",
        metaLayout: "Layout",
        metaAssetId: "Asset ID",
        metaShapes: "Shapes",
        metaFonts: "Fonts",
        metaTextPreview: "Text Preview",
        noThumbnailAvailable: "No thumbnail available",
        close: "Close",
        prevSlide: "Previous slide",
        nextSlide: "Next slide",
      };
      return messages[key] ?? key;
    };
    return t;
  },
}));

vi.mock("@/stores/locale-store", () => ({
  useLocaleStore: () => ({
    locale: "en",
    direction: "ltr",
    isRtl: false,
  }),
}));

vi.mock("@/lib/api/slides", () => ({
  getThumbnailUrl: (sessionId: string, slideNumber: number) =>
    `http://localhost:8000/api/pipeline/${sessionId}/slides/${slideNumber}/thumbnail.png`,
}));

// Mock IntersectionObserver for SlideThumbnail
class MockIntersectionObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  constructor(callback: IntersectionObserverCallback) {
    // Immediately trigger visibility for tests
    setTimeout(() => {
      callback(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        this as unknown as IntersectionObserver,
      );
    }, 0);
  }
}

beforeEach(() => {
  vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
});

// ── Helpers ────────────────────────────────────────────────────────────

const mockSlides: SlideInfo[] = [
  {
    slide_id: "s1",
    slide_number: 1,
    title: "Cover",
    key_message: "",
    layout_type: "proposal_cover",
    body_content_preview: [],
    source_claims: [],
    source_refs: [],
    speaker_notes_preview: "",
    sensitivity_tags: [],
    content_guidance: "",
    change_history_count: 0,
    preview_kind: "metadata_only",
    entry_type: "a1_clone",
    asset_id: "cover",
    semantic_layout_id: "proposal_cover",
    section_id: "Cover",
    thumbnail_url: "/api/pipeline/abc/slides/1/thumbnail.png",
    shape_count: 5,
    fonts: ["Euclid Flex"],
    text_preview: "Cover slide",
  },
  {
    slide_id: "s2",
    slide_number: 2,
    title: "Understanding",
    key_message: "",
    layout_type: "content_heading_desc",
    body_content_preview: [],
    source_claims: [],
    source_refs: [],
    speaker_notes_preview: "",
    sensitivity_tags: [],
    content_guidance: "",
    change_history_count: 0,
    preview_kind: "metadata_only",
    entry_type: "b_variable",
    asset_id: "understanding_1",
    semantic_layout_id: "content_heading_desc",
    section_id: "Section 01",
    thumbnail_url: "/api/pipeline/abc/slides/2/thumbnail.png",
    shape_count: 8,
    fonts: ["Euclid Flex", "Euclid Flex Light"],
    text_preview: "Understanding the RFP requirements",
  },
  {
    slide_id: "s3",
    slide_number: 3,
    title: "Section Divider",
    key_message: "",
    layout_type: "section_divider_01",
    body_content_preview: [],
    source_claims: [],
    source_refs: [],
    speaker_notes_preview: "",
    sensitivity_tags: [],
    content_guidance: "",
    change_history_count: 0,
    preview_kind: "metadata_only",
    entry_type: "a2_shell",
    asset_id: "divider_01",
    semantic_layout_id: "section_divider_01",
    section_id: "Section 01",
    thumbnail_url: null,
    shape_count: 3,
    fonts: ["Euclid Flex"],
    text_preview: "Section divider",
  },
];

// ── Tests ──────────────────────────────────────────────────────────────

describe("SlideGrid", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state", () => {
    render(
      <SlideGrid
        slides={[]}
        thumbnailMode="rendered"
        sessionId="abc"
        isLoading={true}
      />,
    );
    expect(screen.getByTestId("slide-grid-loading")).toBeInTheDocument();
  });

  it("renders error state", () => {
    render(
      <SlideGrid
        slides={[]}
        thumbnailMode="rendered"
        sessionId="abc"
        error="Pipeline not complete"
      />,
    );
    expect(screen.getByTestId("slide-grid-error")).toBeInTheDocument();
    expect(screen.getByText("Pipeline not complete")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(
      <SlideGrid
        slides={[]}
        thumbnailMode="rendered"
        sessionId="abc"
      />,
    );
    expect(screen.getByTestId("slide-grid-empty")).toBeInTheDocument();
    expect(screen.getByText("No slides available")).toBeInTheDocument();
  });

  it("renders image thumbnails in rendered mode", () => {
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="rendered"
        sessionId="abc"
      />,
    );
    expect(screen.getByTestId("slide-grid")).toBeInTheDocument();
    expect(screen.getByTestId("slide-thumbnail-1")).toBeInTheDocument();
    expect(screen.getByTestId("slide-thumbnail-2")).toBeInTheDocument();
    expect(screen.getByTestId("slide-thumbnail-3")).toBeInTheDocument();
    expect(screen.getByText("Image Thumbnails")).toBeInTheDocument();
  });

  it("renders metadata cards in metadata_only mode", () => {
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="metadata_only"
        sessionId="abc"
      />,
    );
    expect(screen.getByTestId("slide-grid")).toBeInTheDocument();
    expect(screen.getByTestId("slide-metadata-1")).toBeInTheDocument();
    expect(screen.getByTestId("slide-metadata-2")).toBeInTheDocument();
    expect(screen.getByTestId("slide-metadata-3")).toBeInTheDocument();
    expect(screen.getByText("Metadata View")).toBeInTheDocument();
  });

  it("shows slide count", () => {
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="rendered"
        sessionId="abc"
      />,
    );
    expect(screen.getByText("3 slides")).toBeInTheDocument();
  });

  it("calls onSlideClick when a metadata card is clicked", () => {
    const onClick = vi.fn();
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="metadata_only"
        sessionId="abc"
        onSlideClick={onClick}
      />,
    );
    fireEvent.click(screen.getByTestId("slide-metadata-2"));
    expect(onClick).toHaveBeenCalledWith(mockSlides[1]);
  });

  it("calls onSlideClick when a thumbnail is clicked", () => {
    const onClick = vi.fn();
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="rendered"
        sessionId="abc"
        onSlideClick={onClick}
      />,
    );
    fireEvent.click(screen.getByTestId("slide-thumbnail-1"));
    expect(onClick).toHaveBeenCalledWith(mockSlides[0]);
  });

  it("highlights selected slide in metadata mode", () => {
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="metadata_only"
        sessionId="abc"
        selectedSlideNumber={2}
      />,
    );
    const selected = screen.getByTestId("slide-metadata-2");
    expect(selected.className).toContain("border-sg-blue");
  });

  it("highlights selected slide in rendered mode", () => {
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="rendered"
        sessionId="abc"
        selectedSlideNumber={1}
      />,
    );
    const selected = screen.getByTestId("slide-thumbnail-1");
    expect(selected.className).toContain("border-sg-blue");
  });

  it("shows entry type badges in metadata mode", () => {
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="metadata_only"
        sessionId="abc"
      />,
    );
    expect(screen.getByText("A1 Clone")).toBeInTheDocument();
    expect(screen.getByText("B Variable")).toBeInTheDocument();
    expect(screen.getByText("A2 Shell")).toBeInTheDocument();
  });

  it("shows section and layout info in metadata mode", () => {
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="metadata_only"
        sessionId="abc"
      />,
    );
    expect(screen.getByText("Cover")).toBeInTheDocument();
    // "Section 01" appears on two slides (slide 2 and 3)
    const sectionLabels = screen.getAllByText("Section 01");
    expect(sectionLabels.length).toBeGreaterThanOrEqual(1);
  });

  it("has accessible list role", () => {
    render(
      <SlideGrid
        slides={mockSlides}
        thumbnailMode="rendered"
        sessionId="abc"
      />,
    );
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });
});
