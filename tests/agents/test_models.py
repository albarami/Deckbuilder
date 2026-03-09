"""Tests for src/models/ — validates all Pydantic models against State Schema v1.1."""

import pytest

# ── common.py tests ──

def test_deckforge_base_model_rejects_extra_fields():
    from src.models.common import DeckForgeBaseModel

    class Sample(DeckForgeBaseModel):
        name: str

    with pytest.raises(Exception):
        Sample(name="test", unexpected="field")


def test_bilingual_text():
    from src.models.common import BilingualText

    bt = BilingualText(en="Hello", ar="مرحبا")
    assert bt.en == "Hello"
    assert bt.ar == "مرحبا"
    bt_en_only = BilingualText(en="Hello")
    assert bt_en_only.ar is None


def test_date_range():
    from src.models.common import DateRange

    dr = DateRange(start="2023-02", end="2023-11")
    assert dr.start == "2023-02"
    dr_empty = DateRange()
    assert dr_empty.start is None


def test_changelog_entry_has_timestamp():
    from src.models.common import ChangeLogEntry

    entry = ChangeLogEntry(agent="test", description="test change")
    assert entry.timestamp is not None
    assert entry.timestamp.tzinfo is not None


# ── rfp.py tests ──

def test_rfp_context_creation():
    from src.models.common import BilingualText
    from src.models.rfp import RFPContext

    rfp = RFPContext(
        rfp_name=BilingualText(en="SAP Renewal"),
        issuing_entity=BilingualText(en="SIDF"),
        mandate=BilingualText(en="Renew SAP licenses"),
    )
    assert rfp.rfp_name.en == "SAP Renewal"
    assert rfp.scope_items == []
    assert rfp.source_language == "en"


def test_rfp_gap_severity_enum():
    from src.models.rfp import RFPGap

    gap = RFPGap(field="evaluation_criteria.financial", description="Missing", severity="critical")
    assert gap.severity == "critical"


def test_rfp_nested_evaluation_criteria():
    from src.models.rfp import EvaluationCategory, EvaluationCriteria, EvaluationSubCriterion, EvaluationSubItem

    criteria = EvaluationCriteria(
        technical=EvaluationCategory(
            weight_pct=80,
            sub_criteria=[
                EvaluationSubCriterion(
                    name="Previous Experience",
                    weight_pct=60,
                    sub_items=[EvaluationSubItem(name="Years in field", weight_pct=40)],
                )
            ],
        ),
        passing_score=60,
    )
    assert criteria.technical.weight_pct == 80
    assert criteria.technical.sub_criteria[0].sub_items[0].name == "Years in field"


def test_rfp_context_rejects_extra_fields():
    from src.models.common import BilingualText
    from src.models.rfp import RFPContext

    with pytest.raises(Exception):
        RFPContext(
            rfp_name=BilingualText(en="Test"),
            issuing_entity=BilingualText(en="Test"),
            mandate=BilingualText(en="Test"),
            nonexistent_field="bad",
        )


# ── claims.py tests ──

def test_claim_object_confidence_minimum():
    from src.models.claims import ClaimObject

    with pytest.raises(Exception):
        ClaimObject(
            claim_id="CLM-0001",
            claim_text="Test",
            source_doc_id="DOC-001",
            source_location="Slide 1",
            evidence_span="Test evidence",
            sensitivity_tag="capability",
            category="project_reference",
            confidence=0.5,
        )


def test_claim_object_confidence_valid():
    from src.models.claims import ClaimObject

    claim = ClaimObject(
        claim_id="CLM-0001",
        claim_text="Test claim",
        source_doc_id="DOC-001",
        source_location="Slide 1",
        evidence_span="Test evidence",
        sensitivity_tag="capability",
        category="project_reference",
        confidence=0.95,
    )
    assert claim.confidence == 0.95


def test_reference_index_empty():
    from src.models.claims import ReferenceIndex

    index = ReferenceIndex()
    assert index.claims == []
    assert index.gaps == []
    assert index.source_manifest == []


def test_case_study_optional_fields():
    from src.models.claims import CaseStudy

    cs = CaseStudy(project_name="SAP Migration", client="SIDF", scope="12 modules")
    assert cs.team_size is None
    assert cs.value is None
    assert cs.domain_tags == []


# ── report.py tests ──

def test_research_report_creation():
    from src.models.report import ResearchReport

    report = ResearchReport(title="Test Report", language="en")
    assert report.title == "Test Report"
    assert report.sections == []
    assert report.full_markdown == ""


def test_report_section_sensitivity_tags():
    from src.models.report import ReportSection

    section = ReportSection(
        section_id="SEC-01",
        heading="Executive Summary",
        content_markdown="# Summary",
        sensitivity_tags=["capability", "client_specific"],
    )
    assert len(section.sensitivity_tags) == 2


# ── slides.py tests ──

def test_slide_object_with_layout_enum():
    from src.models.slides import SlideObject

    slide = SlideObject(slide_id="S-001", title="Test Slide", layout_type="TITLE")
    assert slide.layout_type == "TITLE"
    assert slide.body_content is None


def test_chart_spec_literal_type():
    from src.models.slides import ChartSpec

    chart = ChartSpec(type="bar", title="Test Chart")
    assert chart.type == "bar"
    assert chart.legend is False

    with pytest.raises(Exception):
        ChartSpec(type="invalid_type", title="Bad Chart")


def test_slide_outline_with_slides():
    from src.models.slides import SlideObject, SlideOutline

    outline = SlideOutline(
        slides=[SlideObject(slide_id="S-001", title="Title", layout_type="TITLE")],
        slide_count=1,
    )
    assert len(outline.slides) == 1


# ── actions.py tests ──

def test_rewrite_slide_action():
    from src.models.actions import RewriteSlideAction

    action = RewriteSlideAction(target="S-007", scope="slide_only", instruction="Add data")
    assert action.type == "rewrite_slide"


def test_slide_move_from_alias_raw_json():
    from src.models.actions import SlideMove

    raw = {"from": "S-004", "to": "S-005"}
    move = SlideMove.model_validate(raw)
    assert move.from_ == "S-004"
    assert move.to == "S-005"


def test_slide_move_from_alias_python_name():
    from src.models.actions import SlideMove

    move = SlideMove(from_="S-001", to="S-002")
    assert move.from_ == "S-001"


def test_conversation_action_discriminated_union_rewrite():
    from src.models.actions import ConversationResponse

    raw = {
        "response_to_user": "Rewriting slide 7.",
        "action": {
            "type": "rewrite_slide",
            "target": "S-007",
            "scope": "slide_only",
            "instruction": "Add data",
        },
    }
    resp = ConversationResponse.model_validate(raw)
    assert resp.action.type == "rewrite_slide"
    assert resp.action.target == "S-007"


def test_conversation_action_discriminated_union_export():
    from src.models.actions import ConversationResponse

    raw = {
        "response_to_user": "Exporting deck.",
        "action": {"type": "export", "format": "pptx", "scope": "system_export"},
    }
    resp = ConversationResponse.model_validate(raw)
    assert resp.action.type == "export"


def test_conversation_action_discriminated_union_waive_gap():
    from src.models.actions import ConversationResponse

    raw = {
        "response_to_user": "Waiving gap.",
        "action": {"type": "waive_gap", "gap_id": "GAP-001", "requires_confirmation": True},
    }
    resp = ConversationResponse.model_validate(raw)
    assert resp.action.type == "waive_gap"
    assert resp.action.gap_id == "GAP-001"


def test_all_11_action_types_deserialize():
    from src.models.actions import ConversationResponse

    action_payloads = [
        {"type": "rewrite_slide", "target": "S-001", "scope": "slide_only"},
        {"type": "add_slide", "topic": "cybersecurity", "scope": "requires_report_update"},
        {"type": "remove_slide", "target": "S-012", "requires_confirmation": True},
        {"type": "reorder_slides", "moves": [{"from": "S-004", "to": "S-005"}]},
        {"type": "additional_retrieval", "query": "Egypt project", "scope": "requires_report_update"},
        {"type": "show_sources", "target": "S-007"},
        {"type": "change_language", "language": "ar", "scope": "full_rerender"},
        {"type": "export", "format": "pptx", "scope": "system_export"},
        {"type": "fill_gap", "gap_id": "GAP-002", "scope": "awaiting_user_input"},
        {"type": "waive_gap", "gap_id": "GAP-001", "requires_confirmation": True},
        {"type": "update_report", "section": "Executive Summary", "scope": "requires_report_update"},
    ]
    for payload in action_payloads:
        raw = {"response_to_user": "Test.", "action": payload}
        resp = ConversationResponse.model_validate(raw)
        assert resp.action.type == payload["type"]


# ── waiver.py tests ──

def test_waiver_object_creation():
    from src.models.waiver import WaiverObject

    waiver = WaiverObject(
        waiver_id="WVR-001",
        gap_id="GAP-001",
        gap_description="Missing ISO 22301",
        rfp_criterion="Compliance",
        severity="critical",
        waived_by="salim@sg.com",
        waiver_reason="In progress",
        approval_level="pillar_lead",
    )
    assert waiver.severity == "critical"
    assert waiver.waiver_timestamp is not None
    assert waiver.waiver_timestamp.tzinfo is not None


# ── qa.py tests ──

def test_qa_result_defaults():
    from src.models.qa import QAResult

    result = QAResult()
    assert result.slide_validations == []
    assert result.deck_summary.total_slides == 0
    assert result.deck_summary.fail_close is False


def test_deck_validation_summary_defaults():
    from src.models.qa import DeckValidationSummary

    summary = DeckValidationSummary()
    assert summary.passed == 0
    assert summary.ungrounded_claims == 0
    assert summary.fail_close_reason == ""


def test_qa_issue_types():
    from src.models.qa import QAIssue

    issue = QAIssue(
        type="UNGROUNDED_CLAIM",
        location="body_content bullet 3",
        claim="NCA compliance",
        explanation="No evidence",
        action="REMOVE",
    )
    assert issue.type == "UNGROUNDED_CLAIM"


# ── indexing.py tests ──

def test_indexed_date_range_from_alias_raw_json():
    from src.models.indexing import IndexedDateRange

    raw = {"from": "2023-02", "to": "2023-11"}
    dr = IndexedDateRange.model_validate(raw)
    assert dr.from_date == "2023-02"
    assert dr.to_date == "2023-11"


def test_indexing_output_quality_score_bounds():
    from src.models.indexing import IndexingOutput

    output = IndexingOutput(doc_type="proposal", quality_score=4, summary="Test")
    assert output.quality_score == 4

    with pytest.raises(Exception):
        IndexingOutput(doc_type="proposal", quality_score=6, summary="Bad")

    with pytest.raises(Exception):
        IndexingOutput(doc_type="proposal", quality_score=-1, summary="Bad")


def test_indexing_output_duplicate_likelihood_literal():
    from src.models.indexing import IndexingOutput

    output = IndexingOutput(doc_type="proposal", duplicate_likelihood="possible_duplicate", summary="Test")
    assert output.duplicate_likelihood == "possible_duplicate"


def test_indexing_output_rejects_extra_fields():
    from src.models.indexing import IndexingOutput

    with pytest.raises(Exception):
        IndexingOutput(doc_type="proposal", summary="Test", fake_field="bad")


# ── __init__.py re-export smoke test ──

def test_models_reexport():
    """Verify all public symbols are importable from src.models."""
    from src.models import (
        BilingualText,
        BodyContent,
        ChartSpec,
        ClaimObject,
        ConversationAction,
        ConversationResponse,
        ConversationTurn,
        DeckForgeBaseModel,
        DeckForgeState,
        DeckValidationSummary,
        ErrorInfo,
        GapObject,
        GateDecision,
        IndexedDateRange,
        IndexingInput,
        IndexingOutput,
        LayoutType,
        QAResult,
        ReportSection,
        ResearchReport,
        RetrievedSource,
        RFPContext,
        SensitivityTag,
        SessionMetadata,
        SlideObject,
        SlideOutline,
        SlideValidation,
        UploadedDocument,
        WaiverObject,
        WrittenSlides,
    )
    exports = [
        BodyContent, BilingualText, ChartSpec, ClaimObject, ConversationAction,
        ConversationResponse, ConversationTurn, DeckForgeBaseModel, DeckForgeState,
        DeckValidationSummary, ErrorInfo, GateDecision, GapObject, IndexedDateRange,
        IndexingInput, IndexingOutput, LayoutType, QAResult, RFPContext, ReportSection,
        ResearchReport, RetrievedSource, SensitivityTag, SessionMetadata, SlideObject,
        SlideOutline, SlideValidation, UploadedDocument, WaiverObject, WrittenSlides,
    ]
    for symbol in exports:
        assert symbol is not None


# ── retrieval.py tests ──

def test_search_query_creation():
    from src.models.retrieval import SearchQuery

    sq = SearchQuery(
        query="SAP HANA implementation project",
        strategy="rfp_aligned",
        target_criterion="Technical > Previous Experience",
        language="en",
        priority="high",
    )
    assert sq.query == "SAP HANA implementation project"
    assert sq.strategy == "rfp_aligned"
    assert sq.language == "en"
    assert sq.priority == "high"


def test_search_query_uses_enums():
    from src.models.retrieval import SearchQuery

    sq = SearchQuery(
        query="test query",
        strategy="capability_match",
        target_criterion=None,
        language="ar",
        priority="critical",
    )
    assert sq.strategy == "capability_match"
    assert sq.language == "ar"
    assert sq.priority == "critical"


def test_search_query_rejects_extra_fields():
    from src.models.retrieval import SearchQuery

    with pytest.raises(Exception):
        SearchQuery(
            query="test",
            strategy="rfp_aligned",
            target_criterion=None,
            language="en",
            priority="high",
            fake_field="bad",
        )


def test_retrieval_summary_creation():
    from src.models.retrieval import RetrievalSummary

    summary = RetrievalSummary(
        total_queries=22,
        by_strategy={"rfp_aligned": 8, "capability_match": 5, "similar_rfp": 3, "team_resource": 3, "framework": 3},
        highest_priority_criteria=["Previous Experience (60% of Technical)", "Compliance Requirements"],
    )
    assert summary.total_queries == 22
    assert summary.by_strategy["rfp_aligned"] == 8
    assert len(summary.highest_priority_criteria) == 2


def test_retrieval_queries_creation():
    from src.models.retrieval import RetrievalQueries, RetrievalSummary, SearchQuery

    queries = RetrievalQueries(
        search_queries=[
            SearchQuery(
                query="SAP HANA implementation project",
                strategy="rfp_aligned",
                target_criterion="Technical > Previous Experience",
                language="en",
                priority="high",
            ),
            SearchQuery(
                query="SAP Gold partner certificate",
                strategy="capability_match",
                target_criterion="Compliance > SAP Gold Partnership",
                language="en",
                priority="critical",
            ),
        ],
        retrieval_summary=RetrievalSummary(
            total_queries=2,
            by_strategy={"rfp_aligned": 1, "capability_match": 1},
            highest_priority_criteria=["Previous Experience"],
        ),
    )
    assert len(queries.search_queries) == 2
    assert queries.retrieval_summary.total_queries == 2


def test_retrieval_queries_rejects_extra_fields():
    from src.models.retrieval import RetrievalQueries, RetrievalSummary

    with pytest.raises(Exception):
        RetrievalQueries(
            search_queries=[],
            retrieval_summary=RetrievalSummary(
                total_queries=0,
                by_strategy={},
                highest_priority_criteria=[],
            ),
            unexpected_field="bad",
        )


def test_excluded_document_creation():
    from src.models.retrieval import ExcludedDocument

    excluded = ExcludedDocument(
        doc_id="DOC-022",
        reason="Duplicate of DOC-047 (older version)",
    )
    assert excluded.doc_id == "DOC-022"
    assert "Duplicate" in excluded.reason


def test_ranked_sources_output_creation():
    from src.models.retrieval import ExcludedDocument, RankedSourcesOutput
    from src.models.state import RetrievedSource

    output = RankedSourcesOutput(
        ranked_sources=[
            RetrievedSource(
                doc_id="DOC-047",
                title="SIDF SAP Migration Report",
                relevance_score=95,
                summary="Directly relevant.",
                matched_criteria=["Technical > Previous Experience"],
                recommendation="include",
            ),
        ],
        excluded_documents=[
            ExcludedDocument(doc_id="DOC-022", reason="Duplicate of DOC-047"),
        ],
    )
    assert len(output.ranked_sources) == 1
    assert output.ranked_sources[0].doc_id == "DOC-047"
    assert len(output.excluded_documents) == 1
    assert output.excluded_documents[0].doc_id == "DOC-022"


def test_ranked_sources_output_empty():
    from src.models.retrieval import RankedSourcesOutput

    output = RankedSourcesOutput()
    assert output.ranked_sources == []
    assert output.excluded_documents == []


def test_retrieval_models_reexport():
    """Verify retrieval models are importable from src.models."""
    from src.models import (
        ExcludedDocument,
        RankedSourcesOutput,
        RetrievalQueries,
        RetrievalSummary,
        SearchQuery,
    )
    assert SearchQuery is not None
    assert RetrievalSummary is not None
    assert RetrievalQueries is not None
    assert ExcludedDocument is not None
    assert RankedSourcesOutput is not None
