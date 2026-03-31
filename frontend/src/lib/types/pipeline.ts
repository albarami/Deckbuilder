/**
 * Pipeline API types — mirrors `backend/models/api_models.py`.
 */

export type PipelineStatus = "running" | "gate_pending" | "complete" | "error";
export type ProposalMode = "lite" | "standard" | "full" | "source_book_only";
export type RendererMode = "legacy" | "template_v2";
export type ThumbnailMode = "rendered" | "metadata_only" | "draft";
export type ExportFormat =
  | "pptx" | "docx" | "source_index" | "gap_report"
  | "source_book" | "evidence_ledger" | "slide_blueprint"
  | "external_evidence" | "routing_report"
  | "research_query_log" | "query_execution_log";
export type GatePayloadType =
  | "context_review"
  | "source_review"
  | "source_book_review"
  | "report_review"
  | "assembly_plan_review"
  | "slide_review"
  | "qa_review";
export type AgentRunStatus = "waiting" | "running" | "complete" | "error";
export type ReadinessStatus = "ready" | "review" | "needs_fixes" | "blocked";

export interface UploadedDocumentRef {
  upload_id: string;
  filename: string;
}

export interface UploadedFileInfo {
  upload_id: string;
  filename: string;
  size_bytes: number;
  content_type: string;
  extracted_text_length: number;
  detected_language: "en" | "ar" | "unknown";
}

export interface UploadResponse {
  uploads: UploadedFileInfo[];
}

export interface LocalizedTextInput {
  en: string;
  ar: string;
}

export interface EvaluationSubWeightInput {
  label: string;
  weight?: number | null;
}

export interface EvaluationCriterionInput {
  criterion: string;
  weight?: number | null;
  sub_weights: EvaluationSubWeightInput[];
}

export interface KeyDatesInput {
  inquiry_deadline: string;
  submission_deadline: string;
  opening_date: string;
  expected_award_date: string;
  service_start_date: string;
}

export interface SubmissionFormatInput {
  format: string;
  delivery_method: string;
  file_requirements: string[];
  additional_instructions: string;
}

export interface RfpBriefInput {
  rfp_name: LocalizedTextInput;
  issuing_entity: string;
  procurement_platform: string;
  mandate_summary: string;
  scope_requirements: string[];
  deliverables: string[];
  technical_evaluation: EvaluationCriterionInput[];
  financial_evaluation: EvaluationCriterionInput[];
  mandatory_compliance: string[];
  key_dates: KeyDatesInput;
  submission_format: SubmissionFormatInput;
}

export interface StartPipelineRequest {
  documents: UploadedDocumentRef[];
  text_input?: string;
  rfp_brief?: RfpBriefInput | null;
  user_notes?: string;
  language: "en" | "ar";
  proposal_mode: ProposalMode;
  sector: string;
  geography: string;
  renderer_mode?: RendererMode;
}

export interface StartPipelineResponse {
  session_id: string;
  status: PipelineStatus;
  created_at: string;
  stream_url: string;
  pipeline_url?: string | null;
}

export interface GapItem {
  gap_id: string;
  label: string;
  description: string;
  severity: string;
  status: string;
}

export interface SourceIndexItem {
  source_id: string;
  title: string;
  location: string;
  url?: string | null;
}

export interface SensitivitySummary {
  tag: string;
  count: number;
}

export interface ReportSectionSummary {
  section_id: string;
  title: string;
  claim_count: number;
  gap_count: number;
}

export interface SourceReviewItem {
  source_id: string;
  title: string;
  url?: string | null;
  relevance_score: number;
  snippet: string;
  matched_criteria: string[];
  permission_status: string;
  owner_hint?: string | null;
  selected: boolean;
}

export interface Gate1ContextData {
  rfp_brief: RfpBriefInput;
  missing_fields: string[];
  selected_output_language: string;
  user_notes: string;
  evaluation_highlights: string[];
}

export interface Gate2SourceReviewData {
  sources: SourceReviewItem[];
  retrieval_strategies: string[];
  source_count: number;
}

export interface Gate3ReportReviewData {
  report_markdown: string;
  sections: ReportSectionSummary[];
  gaps: GapItem[];
  sensitivity_summary: SensitivitySummary[];
  source_index: SourceIndexItem[];
}

export interface MethodologyPhaseSummary {
  phase_name: string;
  activities_count: number;
  deliverables_count: number;
}

export interface CaseStudySummary {
  asset_id: string;
  score: number;
}

export interface TeamBioSummary {
  asset_id: string;
  score: number;
}

export interface SlideBudgetSummary {
  a1_clone: number;
  a2_shell: number;
  b_variable: number;
  pool_clone: number;
  total: number;
}

export interface ManifestCompositionSummary {
  total_entries: number;
  entry_type_counts: Record<string, number>;
}

export interface Gate3AssemblyPlanData {
  proposal_mode: string;
  geography: string;
  sector: string;
  methodology_phases: MethodologyPhaseSummary[];
  slide_budget: SlideBudgetSummary;
  case_studies: CaseStudySummary[];
  team_bios: TeamBioSummary[];
  selected_service_divider: string;
  manifest_composition: ManifestCompositionSummary;
  win_themes: string[];
}

export interface SourceBookSectionPreview {
  section_id: string;
  title: string;
  preview_paragraph: string;
  word_count?: number;
}

export interface SourceBookQualitySummary {
  reviewer_score?: number;
  benchmark_passed?: boolean;
  evidence_count?: number;
  blueprint_count?: number;
}

export interface SourceBookEvidenceSummary {
  evidence_ledger_entries: number;
  external_source_count: number;
}

export interface SourceBookBlueprintSummary {
  total_entries: number;
  covered_sections: string[];
}

export interface SectionCritiqueSummary {
  section_id: string;
  score: number;
  issues: string[];
  rewrite_instructions: string[];
}

export interface Gate3SourceBookData {
  // Review-centric payload (matches backend Gate3SourceBookData)
  reviewer_score: number;
  threshold_met: boolean;
  competitive_viability: string;
  pass_number: number;
  rewrite_required: boolean;
  section_critiques: SectionCritiqueSummary[];
  coherence_issues: string[];
  word_count: number;
  evidence_count: number;
  blueprint_count: number;
  docx_preview_url: string;
  // Legacy fields (for backward compat with old gate payloads)
  source_book_title?: string;
  total_word_count?: number;
  section_count?: number;
  sections?: SourceBookSectionPreview[];
  quality_summary?: SourceBookQualitySummary;
  evidence_summary?: SourceBookEvidenceSummary;
  blueprint_summary?: SourceBookBlueprintSummary;
  docx_ready?: boolean;
}

/**
 * Unified slide type used by both the slides API and gate-4 preview.
 *
 * Fields unique to the slides API (entry_type, asset_id, etc.) are optional
 * so gate-4 preview data (which only has section/slide_type) also conforms.
 */
export interface SlideInfo {
  slide_id: string;
  slide_number: number;
  title: string;
  key_message: string;
  layout_type: string;
  body_content_preview: string[];
  source_claims: string[];
  source_refs: string[];
  report_section_ref?: string | null;
  rfp_criterion_ref?: string | null;
  speaker_notes_preview: string;
  sensitivity_tags: string[];
  content_guidance: string;
  change_history_count: number;
  thumbnail_url?: string | null;
  preview_kind: ThumbnailMode;
  // Gate-4 preview fields
  section?: string;
  slide_type?: string;
  // Slides API fields
  entry_type?: string;
  asset_id?: string;
  semantic_layout_id?: string;
  section_id?: string;
  shape_count?: number;
  fonts?: string[];
  text_preview?: string;
}

/** @deprecated Use SlideInfo instead */
export type SlidePreviewItem = SlideInfo;

export interface Gate4SlideReviewData {
  slides: SlideInfo[];
  slide_count: number;
  thumbnail_mode: ThumbnailMode;
  preview_ready: boolean;
}

export interface QaCheckRow {
  slide_index: number;
  check: string;
  status: string;
  details: string;
}

export interface WaiverSummaryItem {
  waiver_id: string;
  label: string;
  status: string;
}

export interface DeliverableInfo {
  key: string;
  label: string;
  ready: boolean;
  filename?: string | null;
  download_url?: string | null;
}

export interface Gate5QaReviewData {
  submission_readiness: ReadinessStatus;
  fail_close: boolean;
  critical_gaps: GapItem[];
  lint_status: ReadinessStatus;
  density_status: ReadinessStatus;
  template_compliance: ReadinessStatus;
  language_status: ReadinessStatus;
  coverage_status: ReadinessStatus;
  waivers: WaiverSummaryItem[];
  results: QaCheckRow[];
  deliverables: DeliverableInfo[];
}

export type GatePayload =
  | Gate1ContextData
  | Gate2SourceReviewData
  | Gate3SourceBookData
  | Gate3ReportReviewData
  | Gate3AssemblyPlanData
  | Gate4SlideReviewData
  | Gate5QaReviewData
  | Record<string, unknown>;

export interface GateInfo {
  gate_number: number;
  summary: string;
  prompt: string;
  payload_type: GatePayloadType;
  gate_data?: GatePayload | null;
}

export interface GateRecord {
  gate_number: number;
  approved: boolean;
  feedback: string;
  decided_at: string;
  payload_type?: GatePayloadType | null;
}

export interface AgentRunInfo {
  agent_key: string;
  agent_label: string;
  model: string;
  status: AgentRunStatus;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  metric_label?: string | null;
  metric_value?: string | null;
  step_key?: string | null;
  step_number?: number | null;
}

export interface SessionMetadata {
  total_llm_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  updated_at?: string | null;
}

export interface PipelineOutputs {
  // Deck mode outputs
  pptx_ready: boolean;
  docx_ready: boolean;
  source_index_ready: boolean;
  gap_report_ready: boolean;
  slide_count: number;
  preview_ready: boolean;
  deliverables: DeliverableInfo[];
  // Source Book mode outputs
  source_book_ready: boolean;
  evidence_ledger_ready: boolean;
  slide_blueprint_ready: boolean;
  external_evidence_ready: boolean;
  routing_report_ready: boolean;
  research_query_log_ready: boolean;
  query_execution_log_ready: boolean;
}

export interface SourceBookSummary {
  word_count: number;
  reviewer_score: number;
  threshold_met: boolean;
  competitive_viability: string;
  evidence_ledger_entries: number;
  slide_blueprint_entries: number;
  external_sources: number;
  capability_mappings: number;
  consultant_count: number;
  real_consultant_names: string[];
  project_count: number;
  pass_number: number;
}

export interface SessionHistoryItem {
  session_id: string;
  rfp_name: string;
  issuing_entity: string;
  language: string;
  proposal_mode: ProposalMode;
  status: PipelineStatus;
  current_stage: string;
  current_gate_number?: number | null;
  started_at: string;
  updated_at: string;
  elapsed_ms: number;
  slide_count: number;
  llm_calls: number;
  cost_usd: number;
  deliverables: DeliverableInfo[];
}

export interface SessionHistoryResponse {
  sessions: SessionHistoryItem[];
}

export interface PipelineStatusResponse {
  session_id: string;
  status: PipelineStatus;
  proposal_mode: ProposalMode;
  current_stage: string;
  current_stage_label: string;
  current_step_number?: number | null;
  current_gate_number?: number | null;
  current_gate: GateInfo | null;
  completed_gates: GateRecord[];
  started_at: string;
  elapsed_ms: number;
  error: { agent: string; message: string } | null;
  outputs: PipelineOutputs | null;
  source_book_summary: SourceBookSummary | null;
  session_metadata: SessionMetadata;
  agent_runs: AgentRunInfo[];
  deliverables: DeliverableInfo[];
  rfp_name: string;
  issuing_entity: string;
}

export interface SourceDecisionModifications {
  included_sources: string[];
  excluded_sources: string[];
  prioritized_sources: string[];
  requested_searches: string[];
}

export interface GateDecisionRequest {
  approved: boolean;
  feedback?: string;
  modifications?: SourceDecisionModifications | Record<string, unknown>;
}

export interface GateDecisionResponse {
  gate_number: number;
  decision: "approved" | "rejected";
  pipeline_status: PipelineStatus;
}

export interface SlidesResponse {
  session_id: string;
  slide_count: number;
  thumbnail_mode: ThumbnailMode;
  session_status: PipelineStatus;
  preview_kind: ThumbnailMode;
  slides: SlideInfo[];
}

export type SSEEventType =
  | "stage_change"
  | "agent_start"
  | "agent_complete"
  | "gate_pending"
  | "render_progress"
  | "pipeline_complete"
  | "pipeline_error"
  | "heartbeat";

export interface SSEEvent {
  event_id?: string;
  type: SSEEventType;
  timestamp: string;
  stage?: string;
  stage_key?: string | null;
  stage_label?: string | null;
  step_number?: number | null;
  agent?: string;
  agent_key?: string | null;
  agent_label?: string | null;
  model?: string | null;
  duration_ms?: number | null;
  metric_label?: string | null;
  metric_value?: string | null;
  gate_number?: number | null;
  gate_payload_type?: GatePayloadType | null;
  summary?: string | null;
  prompt?: string | null;
  gate_data?: GatePayload | null;
  slide_index?: number | null;
  total?: number | null;
  session_id?: string | null;
  slide_count?: number | null;
  error?: string | null;
  message?: string | null;
}
