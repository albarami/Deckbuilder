/**
 * Upload API module — document upload for RFP intake.
 */

import { postFormData } from "./client";
import type { UploadResponse } from "@/lib/types/pipeline";

/**
 * Upload one or more documents.
 * POST /api/upload (multipart/form-data)
 *
 * Accepted types: PDF, DOCX, TXT
 * Max: 50MB per file, 200MB total
 */
export function uploadDocuments(
  files: File[],
): Promise<UploadResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return postFormData<UploadResponse>("/api/upload", formData);
}
