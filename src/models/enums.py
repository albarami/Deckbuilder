"""Canonical enums for the DeckForge pipeline."""

from enum import StrEnum


class LayoutType(StrEnum):
    TITLE = "TITLE"
    AGENDA = "AGENDA"
    SECTION = "SECTION"
    CONTENT_1COL = "CONTENT_1COL"
    CONTENT_2COL = "CONTENT_2COL"
    DATA_CHART = "DATA_CHART"
    FRAMEWORK = "FRAMEWORK"
    COMPARISON = "COMPARISON"
    STAT_CALLOUT = "STAT_CALLOUT"
    TEAM = "TEAM"
    TIMELINE = "TIMELINE"
    COMPLIANCE_MATRIX = "COMPLIANCE_MATRIX"
    CLOSING = "CLOSING"


class SensitivityTag(StrEnum):
    COMPLIANCE = "compliance"
    FINANCIAL = "financial"
    CLIENT_SPECIFIC = "client_specific"
    CAPABILITY = "capability"
    GENERAL = "general"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    MEDIUM = "medium"
    LOW = "low"


class QAIssueType(StrEnum):
    UNGROUNDED_CLAIM = "UNGROUNDED_CLAIM"
    INCONSISTENCY = "INCONSISTENCY"
    EMBELLISHMENT = "EMBELLISHMENT"
    TEMPLATE_VIOLATION = "TEMPLATE_VIOLATION"
    TEXT_OVERFLOW = "TEXT_OVERFLOW"
    UNCOVERED_CRITERION = "UNCOVERED_CRITERION"
    CRITICAL_GAP_UNRESOLVED = "CRITICAL_GAP_UNRESOLVED"


class QASlideStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class ActionScope(StrEnum):
    SLIDE_ONLY = "slide_only"
    REQUIRES_REPORT_UPDATE = "requires_report_update"
    FULL_RERENDER = "full_rerender"
    AWAITING_USER_INPUT = "awaiting_user_input"
    SYSTEM_EXPORT = "system_export"


class ActionType(StrEnum):
    REWRITE_SLIDE = "rewrite_slide"
    ADD_SLIDE = "add_slide"
    REMOVE_SLIDE = "remove_slide"
    REORDER_SLIDES = "reorder_slides"
    ADDITIONAL_RETRIEVAL = "additional_retrieval"
    SHOW_SOURCES = "show_sources"
    CHANGE_LANGUAGE = "change_language"
    EXPORT = "export"
    FILL_GAP = "fill_gap"
    WAIVE_GAP = "waive_gap"
    UPDATE_REPORT = "update_report"


class Language(StrEnum):
    EN = "en"
    AR = "ar"
    BILINGUAL = "bilingual"
    MIXED = "mixed"


class DocumentType(StrEnum):
    PROPOSAL = "proposal"
    CASE_STUDY = "case_study"
    CAPABILITY_STATEMENT = "capability_statement"
    TECHNICAL_REPORT = "technical_report"
    CLIENT_PRESENTATION = "client_presentation"
    INTERNAL_FRAMEWORK = "internal_framework"
    RFP_RESPONSE = "rfp_response"
    FINANCIAL_REPORT = "financial_report"
    TEAM_PROFILE = "team_profile"
    METHODOLOGY_DOCUMENT = "methodology_document"
    CERTIFICATE = "certificate"
    OTHER = "other"


class ClaimCategory(StrEnum):
    PROJECT_REFERENCE = "project_reference"
    TEAM_PROFILE = "team_profile"
    CERTIFICATION = "certification"
    METHODOLOGY = "methodology"
    FINANCIAL_DATA = "financial_data"
    COMPLIANCE_EVIDENCE = "compliance_evidence"
    COMPANY_METRIC = "company_metric"


class SearchStrategy(StrEnum):
    RFP_ALIGNED = "rfp_aligned"
    CAPABILITY_MATCH = "capability_match"
    SIMILAR_RFP = "similar_rfp"
    TEAM_RESOURCE = "team_resource"
    FRAMEWORK = "framework"


class QueryPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PipelineStage(StrEnum):
    """Current stage of the pipeline — used for session state."""
    INTAKE = "intake"
    CONTEXT_REVIEW = "context_review"
    SOURCE_REVIEW = "source_review"
    ANALYSIS = "analysis"
    ASSEMBLY_PLAN_REVIEW = "assembly_plan_review"
    REPORT_REVIEW = "report_review"
    OUTLINE_REVIEW = "outline_review"
    SLIDE_BUILDING = "slide_building"
    CONTENT_GENERATION = "content_generation"
    QA = "qa"
    DECK_REVIEW = "deck_review"
    FINALIZED = "finalized"
    ERROR = "error"


class PresentationType(StrEnum):
    TECHNICAL_PROPOSAL = "technical_proposal"
    COMMERCIAL_PROPOSAL = "commercial_proposal"
    CAPABILITY_STATEMENT = "capability_statement"
    EXECUTIVE_SUMMARY = "executive_summary"
    CUSTOM = "custom"


class UserRole(StrEnum):
    VIEWER = "viewer"
    CONSULTANT = "consultant"
    ADMIN = "admin"


class ApprovalLevel(StrEnum):
    CONSULTANT = "consultant"
    PILLAR_LEAD = "pillar_lead"
    PRACTICE_LEAD = "practice_lead"
    EXECUTIVE = "executive"


class ConfidentialityLevel(StrEnum):
    CLIENT_CONFIDENTIAL = "client_confidential"
    INTERNAL_ONLY = "internal_only"
    PUBLIC = "public"
    UNKNOWN = "unknown"


class ExtractionQuality(StrEnum):
    CLEAN = "clean"
    PARTIAL_OCR = "partial_ocr"
    DEGRADED = "degraded"
    MANUAL_REVIEW_NEEDED = "manual_review_needed"


class RenderStatus(StrEnum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class RendererMode(StrEnum):
    """Feature flag controlling which renderer is used.

    TEMPLATE_V2 — template-anchored renderer_v2.py (official .potx, production default).
    LEGACY  — the original renderer.py (kept for backward compat).
    """

    LEGACY = "legacy"
    TEMPLATE_V2 = "template_v2"


class DeckMode(StrEnum):
    INTERNAL_REVIEW = "internal_review"
    CLIENT_SUBMISSION = "client_submission"


class DensityBudget(StrEnum):
    LIGHT = "light"
    STANDARD = "standard"
    DENSE = "dense"


class DensityViolationSeverity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


class ContentRouting(StrEnum):
    SLIDE_BODY = "slide_body"
    SPEAKER_NOTES = "speaker_notes"
    NOTES_ONLY = "notes_only"
    QA_ONLY = "qa_only"
    APPENDIX = "appendix"
    EXCLUDED = "excluded"


class BundleType(StrEnum):
    CASE_STUDY = "case_study"
    TEAM_PROFILE = "team_profile"
    COMPLIANCE = "compliance"
    FRAMEWORK = "framework"
    METRIC = "metric"


class EvidenceStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    PLACEHOLDER = "placeholder"


class SlideTone(StrEnum):
    PROFESSIONAL = "professional"
    TECHNICAL = "technical"
    EXECUTIVE = "executive"
    CONVERSATIONAL = "conversational"


class NoteSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class BlockerType(StrEnum):
    MISSING_EVIDENCE = "missing_evidence"
    UNRESOLVED_GAP = "unresolved_gap"
    COMPLIANCE_FAILURE = "compliance_failure"
    QUALITY_GATE = "quality_gate"


class LintSeverity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


class SubmissionQAStatus(StrEnum):
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class CompositionRuleCategory(StrEnum):
    OVERLAP = "overlap"
    MARGIN = "margin"
    FONT = "font"
    SPACING = "spacing"
    ALIGNMENT = "alignment"
