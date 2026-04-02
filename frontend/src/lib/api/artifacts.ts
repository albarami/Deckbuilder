/**
 * Artifact API module — fetch parsed JSON artifacts for viewer rendering.
 *
 * These endpoints return inline JSON (not file downloads) so the frontend
 * can render artifact viewers (evidence ledger, blueprint, etc.).
 *
 * GET /api/pipeline/{id}/artifact/{name}
 */

import { get } from "./client";

export type ArtifactName =
  | "evidence_ledger"
  | "slide_blueprint"
  | "external_evidence"
  | "routing_report"
  | "research_query_log"
  | "query_execution_log";

/**
 * Fetch a Source Book artifact as parsed JSON.
 */
export async function getArtifact<T = unknown>(
  sessionId: string,
  artifactName: ArtifactName,
): Promise<T> {
  return get<T>(`/api/pipeline/${sessionId}/artifact/${artifactName}`);
}

/** Fetch the evidence ledger JSON. */
export async function getEvidenceLedger(sessionId: string) {
  return getArtifact(sessionId, "evidence_ledger");
}

/** Fetch the slide blueprint JSON. */
export async function getSlideBlueprint(sessionId: string) {
  return getArtifact(sessionId, "slide_blueprint");
}

/** Fetch the external evidence pack JSON. */
export async function getExternalEvidence(sessionId: string) {
  return getArtifact(sessionId, "external_evidence");
}

/** Fetch the routing report JSON. */
export async function getRoutingReport(sessionId: string) {
  return getArtifact(sessionId, "routing_report");
}

/** Fetch the research query log JSON. */
export async function getResearchQueryLog(sessionId: string) {
  return getArtifact(sessionId, "research_query_log");
}

/** Fetch the query execution log JSON. */
export async function getQueryExecutionLog(sessionId: string) {
  return getArtifact(sessionId, "query_execution_log");
}
