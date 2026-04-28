"""DeckForgeState — the master LangGraph state passed between all agents."""

from datetime import UTC, datetime
from typing import Any as TypingAny
from typing import Literal

from pydantic import Field

from .actions import ConversationResponse
from .claim_provenance import ClaimRegistry, ProposalOptionRegistry
from .claims import ReferenceIndex
from .common import DeckForgeBaseModel
from .conformance import ConformanceReport
from .enums import DeckMode, Language, PipelineStage, PresentationType, RendererMode, UserRole
from .external_evidence import ExternalEvidencePack
from .knowledge import KnowledgeGraph
from .methodology_blueprint import MethodologyBlueprint
from .proposal_manifest import ProposalManifest
from .proposal_strategy import ProposalStrategy
from .qa import QAResult
from .report import ResearchReport
from .rfp import RFPContext
from .slide_blueprint import SlideBlueprint
from .slides import SlideObject, SlideOutline, WrittenSlides
from .source_book import SourceBook, SourceBookReview
from .submission import InternalNotePack, SubmissionQAResult, SubmissionSourcePack, UnresolvedIssueRegistry
from .waiver import WaiverObject


class UploadedDocument(DeckForgeBaseModel):
    """A document uploaded by the user as part of the RFP intake."""
    filename: str
    content_text: str
    language: Language = Language.EN


class ConversationTurn(DeckForgeBaseModel):
    """A single turn in the conversation history."""
    role: Literal["user", "assistant"]
    content: str


class GateDecision(DeckForgeBaseModel):
    """Record of a human decision at an approval gate."""
    gate_number: int  # 1-5
    approved: bool
    feedback: str = ""  # User's feedback or rejection reason
    decided_by: str = ""  # User identity
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RetrievedSource(DeckForgeBaseModel):
    """A source document retrieved and ranked by the Retrieval Agent."""
    doc_id: str  # DOC-NNN
    title: str
    relevance_score: int = 0  # 0-100
    summary: str = ""
    matched_criteria: list[str] = Field(default_factory=list)
    is_duplicate: bool = False
    duplicate_of: str | None = None
    recommendation: Literal["include", "exclude"] = "include"


class SessionMetadata(DeckForgeBaseModel):
    """Session-level metadata for tracking and auditing."""
    session_id: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    user_id: str = ""
    user_role: UserRole = UserRole.CONSULTANT
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0


class ErrorInfo(DeckForgeBaseModel):
    """Error state when an agent fails."""
    agent: str
    error_type: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    retries_attempted: int = 0


class DeckForgeState(DeckForgeBaseModel):
    """
    Master state for the DeckForge pipeline.

    Every agent reads from and writes to this object.
    LangGraph manages state transitions between agents.
    State is persisted after each agent:
      - Local dev: JSON file at ./state/session.json
      - Production: Redis with TTL (72 hours)
    """

    # ─── Session ───
    session: SessionMetadata = Field(default_factory=SessionMetadata)
    current_stage: PipelineStage = PipelineStage.INTAKE

    # ─── Inputs ───
    ai_assist_summary: str = ""  # Raw input from BD Station
    uploaded_documents: list[UploadedDocument] = Field(default_factory=list)
    user_notes: str = ""
    output_language: Language = Language.EN
    presentation_type: PresentationType = PresentationType.TECHNICAL_PROPOSAL
    proposal_mode: str = "standard"
    sector: str = ""
    geography: str = ""

    # ─── Gate 1: Context ───
    rfp_context: RFPContext | None = None
    claim_registry: ClaimRegistry = Field(default_factory=ClaimRegistry)
    proposal_options: ProposalOptionRegistry = Field(
        default_factory=ProposalOptionRegistry,
    )
    gate_1: GateDecision | None = None

    # ─── Gate 2: Retrieval ───
    retrieved_sources: list[RetrievedSource] = Field(default_factory=list)
    approved_source_ids: list[str] = Field(default_factory=list)  # DOC-NNN ids user approved
    gate_2: GateDecision | None = None

    # ─── Routing ───
    routing_report: dict | None = None  # RoutingReport as dict
    pack_context: dict | None = None  # Merged pack context

    # ─── External methodology coverage (Slice 3.5) ───
    # Stored as JSON-safe dict (serialized EvidenceCoverageReport) for
    # parity with routing_report. Populated by the evidence_curation
    # node after the external_evidence_pack is built; consumed by the
    # final artifact gate.
    evidence_coverage_report: dict | None = None

    # ─── Analysis / Evidence Curation ───
    reference_index: ReferenceIndex | None = None
    external_evidence_pack: ExternalEvidencePack | None = None
    full_text_documents: list[dict] = Field(default_factory=list)  # from load_full_documents()
    knowledge_graph: KnowledgeGraph | None = None
    proposal_strategy: ProposalStrategy | None = None
    source_book: SourceBook | None = None
    source_book_review: SourceBookReview | None = None
    conformance_report: ConformanceReport | None = None
    fallback_events: list[dict] = Field(default_factory=list)

    # ─── Gate 3: Research Report ───
    research_report: ResearchReport | None = None
    report_markdown: str = ""  # The full approved report as markdown
    gate_3: GateDecision | None = None

    # ─── Blueprint Extraction (post gate_3, pre section_fill) ───
    slide_blueprint: SlideBlueprint | None = None

    # ─── Gate 4: Slide Outline / Built Slides ───
    slide_outline: SlideOutline | None = None
    slide_blueprint: SlideBlueprint | None = None
    gate_4: GateDecision | None = None

    # ─── Iterative Builder (M10) ───
    evidence_mode: str = "strict"  # "strict" | "general"
    deck_drafts: list[dict] = Field(default_factory=list)  # Intermediate DeckDraft JSONs
    deck_reviews: list[dict] = Field(default_factory=list)  # Intermediate DeckReview JSONs

    # ─── Content + QA ───
    written_slides: WrittenSlides | None = None
    qa_result: QAResult | None = None

    # ─── Gate 5: Final Deck ───
    final_slides: list[SlideObject] = Field(default_factory=list)
    gate_5: GateDecision | None = None

    # ─── Waivers ───
    waivers: list[WaiverObject] = Field(default_factory=list)

    # ─── Deck Mode & Submission Layer (M10.6) ───
    deck_mode: DeckMode = DeckMode.INTERNAL_REVIEW
    submission_source_pack: SubmissionSourcePack | None = None
    internal_notes: InternalNotePack | None = None
    unresolved_issues: UnresolvedIssueRegistry | None = None
    submission_qa_result: SubmissionQAResult | None = None

    # ─── Assembly Plan (template-first pipeline) ───
    assembly_plan: TypingAny = None  # AssemblyPlanResult from assembly_plan agent
    methodology_blueprint: MethodologyBlueprint | None = None
    slide_budget: TypingAny = None  # SlideBudget from slide_budgeter
    selected_service_divider: str = ""  # semantic_id of selected service divider

    # ─── Section filler outputs (G2 typed schemas for quality gate) ───
    filler_outputs: dict[str, TypingAny] = Field(default_factory=dict)

    # ─── Renderer mode (feature flag) ───
    renderer_mode: RendererMode = RendererMode.TEMPLATE_V2
    proposal_manifest: ProposalManifest | None = None

    # ─── Output (Deck mode) ───
    pptx_path: str | None = None  # Path to rendered PPTX
    report_docx_path: str | None = None  # Path to exported report
    source_index_path: str | None = None  # Path to source index document
    gap_report_path: str | None = None  # Path to gap report document

    # ─── Output (Source Book mode) ───
    source_book_docx_path: str | None = None  # Path to exported Source Book DOCX
    evidence_ledger_path: str | None = None  # Path to evidence ledger JSON
    slide_blueprint_path: str | None = None  # Path to slide blueprint JSON
    external_evidence_path: str | None = None  # Path to external evidence pack JSON
    routing_report_path: str | None = None  # Path to routing report JSON
    research_query_log_path: str | None = None  # Path to research query log JSON
    query_execution_log_path: str | None = None  # Path to query execution log JSON

    # ─── Session-safe query telemetry (captured at call site) ───
    # These are snapshots of process-global data from the external research agent,
    # captured into graph state right after the agent completes. This makes them
    # safe for multi-session FastAPI servers where globals can be overwritten.
    captured_query_execution_log: list[dict] = Field(default_factory=list)
    captured_query_theme_map: dict[str, str] = Field(default_factory=dict)

    # ─── Conversation ───
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    last_action: ConversationResponse | None = None

    # ─── Error ───
    errors: list[ErrorInfo] = Field(default_factory=list)
    last_error: ErrorInfo | None = None
