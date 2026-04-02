/**
 * Export API module — download deliverables (PPTX, DOCX, Source Index, Gap Report).
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
 * Download the source index DOCX.
 * GET /api/pipeline/{id}/export/source_index
 */
export async function downloadSourceIndex(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/source_index`,
  );
  triggerDownload(blob, filename);
}

/**
 * Download the gap report DOCX.
 * GET /api/pipeline/{id}/export/gap_report
 */
export async function downloadGapReport(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/gap_report`,
  );
  triggerDownload(blob, filename);
}

// ── Source Book Mode Downloads ─────────────────────────────────────────

/**
 * Download the Source Book DOCX.
 * GET /api/pipeline/{id}/export/source_book
 */
export async function downloadSourceBook(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/source_book`,
  );
  triggerDownload(blob, filename);
}

/**
 * Download the Evidence Ledger JSON.
 * GET /api/pipeline/{id}/export/evidence_ledger
 */
export async function downloadEvidenceLedger(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/evidence_ledger`,
  );
  triggerDownload(blob, filename);
}

/**
 * Download the Slide Blueprint JSON.
 * GET /api/pipeline/{id}/export/slide_blueprint
 */
export async function downloadSlideBlueprint(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/slide_blueprint`,
  );
  triggerDownload(blob, filename);
}

/**
 * Download the External Evidence Pack JSON.
 * GET /api/pipeline/{id}/export/external_evidence
 */
export async function downloadExternalEvidence(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/external_evidence`,
  );
  triggerDownload(blob, filename);
}

/**
 * Download the Routing Report JSON.
 * GET /api/pipeline/{id}/export/routing_report
 */
export async function downloadRoutingReport(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/routing_report`,
  );
  triggerDownload(blob, filename);
}

/**
 * Download the Research Query Log JSON.
 * GET /api/pipeline/{id}/export/research_query_log
 */
export async function downloadResearchQueryLog(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/research_query_log`,
  );
  triggerDownload(blob, filename);
}

/**
 * Download the Query Execution Log JSON.
 * GET /api/pipeline/{id}/export/query_execution_log
 */
export async function downloadQueryExecutionLog(sessionId: string): Promise<void> {
  const { blob, filename } = await getBlob(
    `/api/pipeline/${sessionId}/export/query_execution_log`,
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
