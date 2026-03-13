/**
 * Slides API module — fetch slide metadata and thumbnails.
 *
 * Endpoints:
 * - GET /api/pipeline/{id}/slides          → SlidesResponse
 * - GET /api/pipeline/{id}/slides/{n}/thumbnail.png → PNG image
 */

import { get, BASE_URL } from "./client";
import type { SlidesResponse } from "@/lib/types/slides";

/**
 * Fetch slide metadata for a completed pipeline session.
 * Returns 409 if pipeline has not completed yet.
 *
 * GET /api/pipeline/{id}/slides
 */
export function getSlides(sessionId: string): Promise<SlidesResponse> {
  return get<SlidesResponse>(`/api/pipeline/${sessionId}/slides`);
}

/**
 * Build the full thumbnail URL for a given slide.
 * Used by SlideThumbnail for <img> src.
 */
export function getThumbnailUrl(
  sessionId: string,
  slideNumber: number,
): string {
  return `${BASE_URL}/api/pipeline/${sessionId}/slides/${slideNumber}/thumbnail.png`;
}
