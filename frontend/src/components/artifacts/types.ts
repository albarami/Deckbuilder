/**
 * Artifact viewer typed contracts.
 *
 * Viewer-normalized types consumed by each artifact renderer.
 * These are NOT raw backend dumps -- they match the exported artifact JSON shapes.
 */

// -- Evidence Ledger (from evidence_ledger.json) --------------------------

export interface LedgerEntry {
  claim_id: string;
  claim_text: string;
  source_type: "internal" | "external";
  source_reference: string;
  confidence: number;
  verifiability_status: "verified" | "partially_verified" | "unverified" | "gap";
  verification_note: string;
}

export interface EvidenceLedgerData {
  entries: LedgerEntry[];
}

// -- Slide Blueprint (from slide_blueprint.json -- TRANSFORMED contract) --

export interface BlueprintContractEntry {
  section_id: string;
  section_name: string;
  ownership: "house" | "dynamic" | "hybrid";
  slide_title: string | null;
  key_message: string | null;
  bullet_points: string[];
  evidence_ids: string[];
  visual_guidance: string | null;
}

/** Targets the TRANSFORMED blueprint export from blueprint_transform.py,
 *  NOT legacy raw SlideBlueprintEntry lists. */
export interface BlueprintData {
  contract_entries: BlueprintContractEntry[];
  validation_violations: string[];
  legacy_count: number;
  contract_count: number;
}

// -- External Evidence Pack (from external_evidence.json) -----------------

export interface EvidenceSource {
  source_id: string;
  provider: string;
  title: string;
  authors: string[];
  source_type: string;
  year: number;
  url: string;
  relevance_score: number;
  mapped_rfp_theme: string;
  key_findings: string[];
  evidence_tier: "primary" | "secondary" | "analogical";
  evidence_class: string;
  query_used?: string;
  how_to_use_in_proposal?: string;
  citation_count?: number;
}

export interface EvidencePackData {
  sources: EvidenceSource[];
  search_queries_used: string[];
  coverage_assessment: string;
}

// -- Routing Report (from routing_report.json) ----------------------------

export interface RoutingReportData {
  classification: {
    jurisdiction: string;
    sector: string;
    domain: string;
    client_type: string;
    confidence: number;
    regulatory_frame?: string;
  };
  selected_packs: string[];
  fallback_packs_used: string[];
  warnings: string[];
  routing_confidence: number;
}

// -- Artifact tab identifiers ---------------------------------------------

export type ArtifactTab = "evidence_ledger" | "slide_blueprint" | "external_evidence" | "routing_report";
