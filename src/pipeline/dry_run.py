"""Dry-run mock factories — agent-specific LLMResponse objects for offline demo.

Each factory returns a realistic LLMResponse with a properly typed .parsed
object, matching what the corresponding agent expects from call_llm().

Based on fixtures from tests/integration/test_pipeline.py.
"""

from unittest.mock import AsyncMock, patch

from src.models.claims import (
    ClaimObject,
    GapObject,
    ReferenceIndex,
    SourceManifestEntry,
)
from src.models.common import BilingualText
from src.models.enums import (
    ClaimCategory,
    GapSeverity,
    Language,
    LayoutType,
    QASlideStatus,
    QueryPriority,
    SearchStrategy,
    SensitivityTag,
)
from src.models.qa import DeckValidationSummary, QAResult, SlideValidation
from src.models.report import ReportSection, ResearchReport
from src.models.retrieval import (
    RankedSourcesOutput,
    RetrievalQueries,
    RetrievalSummary,
    SearchQuery,
)
from src.models.rfp import RFPContext
from src.models.slides import (
    BodyContent,
    SlideObject,
    SlideOutline,
    WrittenSlides,
)
from src.models.state import RetrievedSource
from src.services.llm import LLMResponse


def _wrap(parsed: object) -> LLMResponse:
    """Wrap a parsed model in an LLMResponse."""
    return LLMResponse(
        parsed=parsed,
        input_tokens=100,
        output_tokens=50,
        model="dry-run",
        latency_ms=1.0,
    )


def _context_response() -> LLMResponse:
    return _wrap(RFPContext(
        rfp_name=BilingualText(en="SAP Support Renewal"),
        issuing_entity=BilingualText(en="SIDF"),
        mandate=BilingualText(en="Renew SAP licenses for 24 months."),
    ))


def _planner_response() -> LLMResponse:
    return _wrap(RetrievalQueries(
        search_queries=[
            SearchQuery(
                query="SAP support experience",
                strategy=SearchStrategy.RFP_ALIGNED,
                language=Language.EN,
                priority=QueryPriority.HIGH,
            ),
        ],
        retrieval_summary=RetrievalSummary(
            total_queries=1,
            by_strategy={"rfp_aligned": 1},
        ),
    ))


def _ranker_response() -> LLMResponse:
    return _wrap(RankedSourcesOutput(
        ranked_sources=[
            RetrievedSource(
                doc_id="DOC-001",
                title="SAP Case Study",
                relevance_score=95,
            ),
        ],
    ))


def _analysis_response() -> LLMResponse:
    return _wrap(ReferenceIndex(
        claims=[
            ClaimObject(
                claim_id="CLM-001",
                claim_text="Delivered SAP migration in 6 months",
                source_doc_id="DOC-001",
                source_location="Slide 3",
                evidence_span="Completed migration in 6 months",
                sensitivity_tag=SensitivityTag.CAPABILITY,
                category=ClaimCategory.PROJECT_REFERENCE,
                confidence=0.95,
            ),
        ],
        gaps=[
            GapObject(
                gap_id="GAP-001",
                description="No ISO 27001 evidence",
                rfp_criterion="Compliance",
                severity=GapSeverity.MEDIUM,
                action_required="Request certification docs",
            ),
        ],
        source_manifest=[
            SourceManifestEntry(
                doc_id="DOC-001",
                title="SAP Case Study",
                sharepoint_path="/test_docs/sap_case.pdf",
            ),
        ],
    ))


def _research_response() -> LLMResponse:
    return _wrap(ResearchReport(
        title="SAP Support Renewal — Research Report",
        language=Language.EN,
        sections=[
            ReportSection(
                section_id="SEC-001",
                heading="Executive Summary",
                content_markdown=(
                    "Strategic Gears has deep SAP expertise."
                    " [Ref: CLM-001]"
                ),
            ),
        ],
        full_markdown="# SAP Support Renewal\n\nResearch report content.",
    ))


def _structure_response() -> LLMResponse:
    return _wrap(SlideOutline(
        slides=[
            SlideObject(
                slide_id="S-001",
                title="Executive Summary",
                layout_type=LayoutType.TITLE,
            ),
            SlideObject(
                slide_id="S-002",
                title="Our SAP Experience",
                layout_type=LayoutType.CONTENT_1COL,
            ),
        ],
    ))


def _content_response() -> LLMResponse:
    return _wrap(WrittenSlides(
        slides=[
            SlideObject(
                slide_id="S-001",
                title="Executive Summary",
                layout_type=LayoutType.TITLE,
                body_content=BodyContent(
                    text_elements=["Strategic Gears — SAP expertise"],
                ),
            ),
            SlideObject(
                slide_id="S-002",
                title="Our SAP Experience",
                layout_type=LayoutType.CONTENT_1COL,
                body_content=BodyContent(
                    text_elements=["6-month SAP migration [Ref: CLM-001]"],
                ),
            ),
        ],
    ))


def _qa_response() -> LLMResponse:
    return _wrap(QAResult(
        slide_validations=[
            SlideValidation(slide_id="S-001", status=QASlideStatus.PASS),
            SlideValidation(slide_id="S-002", status=QASlideStatus.PASS),
        ],
        deck_summary=DeckValidationSummary(
            total_slides=2,
            passed=2,
            failed=0,
        ),
    ))


_SEARCH_RESULTS = [
    {
        "doc_id": "DOC-001",
        "title": "SAP Case Study",
        "excerpt": "Delivered SAP migration in 6 months.",
        "metadata": {},
        "search_score": 0.95,
    },
]

_LOADED_DOCUMENTS = [
    {
        "doc_id": "DOC-001",
        "title": "SAP Case Study",
        "content_text": "SAP migration content for analysis.",
        "metadata": {},
    },
]


def get_dry_run_patches() -> list:
    """Return mock patches with agent-specific typed responses.

    Each agent's call_llm is patched with a mock that returns the
    correct parsed type. Search and load_documents are also patched.

    Caller is responsible for starting/stopping the patches.
    """
    targets = [
        ("src.agents.context.agent.call_llm", _context_response()),
        ("src.agents.retrieval.planner.call_llm", _planner_response()),
        ("src.agents.retrieval.ranker.call_llm", _ranker_response()),
        ("src.agents.analysis.agent.call_llm", _analysis_response()),
        ("src.agents.research.agent.call_llm", _research_response()),
        ("src.agents.structure.agent.call_llm", _structure_response()),
        ("src.agents.content.agent.call_llm", _content_response()),
        ("src.agents.qa.agent.call_llm", _qa_response()),
        ("src.pipeline.graph.local_search", _SEARCH_RESULTS),
        ("src.pipeline.graph.load_documents", _LOADED_DOCUMENTS),
    ]

    patches = []
    for target, return_val in targets:
        mock = AsyncMock(return_value=return_val)
        p = patch(target, mock)
        patches.append(p)
    return patches
