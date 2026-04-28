"""ComplianceIndex-first conformance validation.

Verifies that when validate_conformance receives a built ComplianceIndex,
the 6 NCNP compliance false-negatives (HR-L1-009..014) no longer appear
in `missing_required_commitments` because the structured index resolves
them through Arabic alias matching.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.source_book.conformance_validator import validate_conformance
from src.models.common import BilingualText
from src.models.conformance import HardRequirement
from src.models.rfp import RFPContext
from src.models.source_book import RFPInterpretation, SourceBook
from src.services.hard_requirement_extractor import build_compliance_index


_ARABIC_COMPLIANCE_TEXT = (
    "السجل التجاري ساري المفعول. شهادة الزكاة معتمدة. "
    "شهادة الضريبة سارية. التأمينات الاجتماعية مفعلة. "
    "اشتراك الغرفة التجارية ساري. السعودة مستوفاة."
)


def _ncnp_compliance_hrs() -> list[HardRequirement]:
    return [
        HardRequirement(
            requirement_id="HR-L1-009",
            category="compliance",
            subject="Commercial registration",
            value_text="Valid commercial registration",
            validation_scope="source_book",
            severity="critical",
        ),
        HardRequirement(
            requirement_id="HR-L1-010",
            category="compliance",
            subject="Zakat certificate",
            value_text="Zakat certificate",
            validation_scope="source_book",
            severity="critical",
        ),
        HardRequirement(
            requirement_id="HR-L1-011",
            category="compliance",
            subject="Tax certificate",
            value_text="Tax certificate",
            validation_scope="source_book",
            severity="critical",
        ),
        HardRequirement(
            requirement_id="HR-L1-012",
            category="compliance",
            subject="Social insurance certificate",
            value_text="Social insurance certificate",
            validation_scope="source_book",
            severity="critical",
        ),
        HardRequirement(
            requirement_id="HR-L1-013",
            category="compliance",
            subject="Chamber of Commerce subscription certificate",
            value_text="Chamber of Commerce subscription certificate",
            validation_scope="source_book",
            severity="critical",
        ),
        HardRequirement(
            requirement_id="HR-L1-014",
            category="compliance",
            subject="Saudization certificate",
            value_text="Saudization certificate",
            validation_scope="source_book",
            severity="critical",
        ),
    ]


def _ncnp_source_book() -> SourceBook:
    return SourceBook(
        rfp_name="NCNP",
        client_name="NCNP",
        language="ar",
        rfp_interpretation=RFPInterpretation(
            constraints_and_compliance=_ARABIC_COMPLIANCE_TEXT,
        ),
    )


def _minimal_rfp() -> RFPContext:
    return RFPContext(
        rfp_name=BilingualText(ar="", en=""),
        issuing_entity=BilingualText(ar="", en=""),
        mandate=BilingualText(ar="", en=""),
    )


@pytest.mark.asyncio
async def test_compliance_index_built_from_ncnp_text_passes_all_six() -> None:
    hrs = _ncnp_compliance_hrs()
    index = build_compliance_index(hrs, _ARABIC_COMPLIANCE_TEXT)
    by_id = {e.requirement_id: e for e in index.entries}
    for rid in [
        "HR-L1-009", "HR-L1-010", "HR-L1-011",
        "HR-L1-012", "HR-L1-013", "HR-L1-014",
    ]:
        assert by_id[rid].content_conformance_pass is True


@pytest.mark.asyncio
async def test_validate_conformance_with_compliance_index_clears_six_false_negatives() -> None:
    hrs = _ncnp_compliance_hrs()
    sb = _ncnp_source_book()
    rfp = _minimal_rfp()
    sb_text = sb.model_dump_json()  # Same serialization the validator scans
    index = build_compliance_index(hrs, sb_text)

    with patch(
        "src.agents.source_book.conformance_validator._pass3_semantic_checks",
        AsyncMock(return_value=[]),
    ):
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=hrs,
            rfp_context=rfp,
            uploaded_documents=[],
            compliance_index=index,
        )

    # The 6 compliance HRs should not appear as missing commitments.
    failed_ids = {f.requirement_id for f in report.missing_required_commitments}
    for rid in [
        "HR-L1-009", "HR-L1-010", "HR-L1-011",
        "HR-L1-012", "HR-L1-013", "HR-L1-014",
    ]:
        assert rid not in failed_ids, (
            f"{rid} still flagged as missing despite ComplianceIndex pass"
        )


@pytest.mark.asyncio
async def test_validate_conformance_without_compliance_index_falls_back() -> None:
    """Without a ComplianceIndex, behavior matches legacy (English keyword scan)."""
    hrs = _ncnp_compliance_hrs()
    sb = _ncnp_source_book()  # Arabic terms only — English keyword scan misses
    rfp = _minimal_rfp()

    with patch(
        "src.agents.source_book.conformance_validator._pass3_semantic_checks",
        AsyncMock(return_value=[]),
    ):
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=hrs,
            rfp_context=rfp,
            uploaded_documents=[],
        )

    # Legacy behavior preserved: at least one of the 6 still flagged because
    # the English keyword scan can't resolve Arabic compliance terms.
    failed_ids = {f.requirement_id for f in report.missing_required_commitments}
    assert any(
        rid in failed_ids
        for rid in [
            "HR-L1-009", "HR-L1-010", "HR-L1-011",
            "HR-L1-012", "HR-L1-013", "HR-L1-014",
        ]
    ), "Legacy path should still produce false negatives without ComplianceIndex"


@pytest.mark.asyncio
async def test_compliance_index_entry_marked_missing_blocks_pass() -> None:
    """A compliance HR with response_status=missing in the index must remain failing."""
    hrs = _ncnp_compliance_hrs()[:1]  # Just commercial registration
    sb = SourceBook(
        rfp_name="X",
        client_name="X",
        language="ar",
        rfp_interpretation=RFPInterpretation(constraints_and_compliance=""),
    )
    rfp = _minimal_rfp()
    # ComplianceIndex built from empty text → entry marked missing
    index = build_compliance_index(hrs, "")
    assert index.entries[0].response_status == "missing"

    with patch(
        "src.agents.source_book.conformance_validator._pass3_semantic_checks",
        AsyncMock(return_value=[]),
    ):
        report = await validate_conformance(
            source_book=sb,
            hard_requirements=hrs,
            rfp_context=rfp,
            uploaded_documents=[],
            compliance_index=index,
        )

    failed_ids = {f.requirement_id for f in report.missing_required_commitments}
    assert "HR-L1-009" in failed_ids
