/**
 * Slides API types — thin wrappers around the shared pipeline contract.
 */

import type { PipelineStatus, SlideInfo, SlidesResponse as SharedSlidesResponse, ThumbnailMode } from "./pipeline";

export { type SlideInfo, type ThumbnailMode };

export interface SlidesResponse extends SharedSlidesResponse {
  session_status: PipelineStatus;
  preview_kind: ThumbnailMode;
}
