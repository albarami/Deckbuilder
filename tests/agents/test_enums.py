"""Tests for src/models/enums.py — validates all 19 StrEnum classes against Prompt Library Appendix A."""

from enum import StrEnum


def test_layout_type_values():
    from src.models.enums import LayoutType
    assert issubclass(LayoutType, StrEnum)
    expected = {"TITLE", "AGENDA", "SECTION", "CONTENT_1COL", "CONTENT_2COL", "DATA_CHART",
                "FRAMEWORK", "COMPARISON", "STAT_CALLOUT", "TEAM", "TIMELINE", "COMPLIANCE_MATRIX", "CLOSING"}
    assert {e.value for e in LayoutType} == expected


def test_sensitivity_tag_values():
    from src.models.enums import SensitivityTag
    expected = {"compliance", "financial", "client_specific", "capability", "general"}
    assert {e.value for e in SensitivityTag} == expected


def test_gap_severity_values():
    from src.models.enums import GapSeverity
    expected = {"critical", "medium", "low"}
    assert {e.value for e in GapSeverity} == expected


def test_qa_issue_type_values():
    from src.models.enums import QAIssueType
    expected = {"UNGROUNDED_CLAIM", "INCONSISTENCY", "EMBELLISHMENT", "TEMPLATE_VIOLATION",
                "TEXT_OVERFLOW", "UNCOVERED_CRITERION", "CRITICAL_GAP_UNRESOLVED"}
    assert {e.value for e in QAIssueType} == expected


def test_action_type_values():
    from src.models.enums import ActionType
    expected = {"rewrite_slide", "add_slide", "remove_slide", "reorder_slides",
                "additional_retrieval", "show_sources", "change_language", "export",
                "fill_gap", "waive_gap", "update_report"}
    assert {e.value for e in ActionType} == expected


def test_pipeline_stage_values():
    from src.models.enums import PipelineStage
    expected = {"intake", "context_review", "source_review", "analysis", "report_review",
                "outline_review", "slide_building", "content_generation", "qa", "deck_review", "finalized", "error"}
    assert {e.value for e in PipelineStage} == expected


def test_language_values():
    from src.models.enums import Language
    expected = {"en", "ar", "bilingual", "mixed"}
    assert {e.value for e in Language} == expected


def test_document_type_values():
    from src.models.enums import DocumentType
    expected = {"proposal", "case_study", "capability_statement", "technical_report",
                "client_presentation", "internal_framework", "rfp_response", "financial_report",
                "team_profile", "methodology_document", "certificate", "other"}
    assert {e.value for e in DocumentType} == expected


def test_claim_category_values():
    from src.models.enums import ClaimCategory
    expected = {"project_reference", "team_profile", "certification", "methodology",
                "financial_data", "compliance_evidence", "company_metric"}
    assert {e.value for e in ClaimCategory} == expected


def test_all_enums_are_str_serializable():
    from src.models.enums import Language, LayoutType, SensitivityTag
    assert str(LayoutType.TITLE) == "TITLE"
    assert str(SensitivityTag.COMPLIANCE) == "compliance"
    assert str(Language.AR) == "ar"


def test_enum_count():
    """Verify we have exactly 20 StrEnum classes (19 original + RendererMode)."""
    import src.models.enums as enums_module
    enum_classes = [v for v in vars(enums_module).values()
                    if isinstance(v, type) and issubclass(v, StrEnum) and v is not StrEnum]
    msg = f"Expected 20 enums, found {len(enum_classes)}: {[c.__name__ for c in enum_classes]}"
    assert len(enum_classes) == 20, msg
