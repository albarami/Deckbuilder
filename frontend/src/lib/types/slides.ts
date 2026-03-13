/**
 * Slides API types — slide metadata and thumbnail responses.
 * Mirrors backend/models/api_models.py exactly.
 */

export type ThumbnailMode = "rendered" | "metadata_only";

export interface SlideInfo {
  slide_number: number;
  entry_type: string;
  asset_id: string;
  semantic_layout_id: string;
  section_id: string;
  thumbnail_url: string | null;
  shape_count: number;
  fonts: string[];
  text_preview: string;
}

export interface SlidesResponse {
  session_id: string;
  slide_count: number;
  thumbnail_mode: ThumbnailMode;
  slides: SlideInfo[];
}
