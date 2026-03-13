/**
 * Export API module — download PPTX/DOCX deliverables.
 *
 * Uses blob download to trigger browser file save.
 */

import { getBlob } from "./client";

/**
 * Download the rendered PPTX presentation.
 * GET /api/pipeline/{id}/export/pptx
 */
export async function downloadPptx(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/pptx`,
  );
  triggerDownload(blob, filename);
}

/**
 * Download the research report DOCX.
 * GET /api/pipeline/{id}/export/docx
 */
export async function downloadDocx(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/docx`,
  );
  triggerDownload(blob, filename);
}

/**
 * Trigger a browser file download from a Blob.
 */
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
