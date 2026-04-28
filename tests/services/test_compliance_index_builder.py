"""build_compliance_index — structured compliance check from hard requirements."""
from __future__ import annotations

from src.models.conformance import HardRequirement
from src.services.hard_requirement_extractor import build_compliance_index


def _hr(req_id: str, subject: str, value_text: str = "") -> HardRequirement:
    return HardRequirement(
        requirement_id=req_id,
        category="compliance",
        subject=subject,
        value_text=value_text or subject,
        validation_scope="source_book",
        severity="critical",
    )


def test_compliance_index_built_from_hard_requirements() -> None:
    hrs = [
        _hr("HR-L1-002", "Commercial registration", "Valid commercial registration"),
    ]
    source_book_text = "السجل التجاري ساري المفعول"
    index = build_compliance_index(hrs, source_book_text)
    assert len(index.entries) >= 1
    entry = index.entries[0]
    assert entry.requirement_id == "HR-L1-002"
    assert entry.content_conformance_pass is True


def test_missing_compliance_item() -> None:
    hrs = [
        _hr("HR-L1-099", "Unknown item", "Some unknown requirement"),
    ]
    index = build_compliance_index(hrs, "no match here")
    entry = next(e for e in index.entries if e.requirement_id == "HR-L1-099")
    assert entry.response_status == "missing"
    assert entry.content_conformance_pass is False


def test_zakat_alias_arabic() -> None:
    hrs = [_hr("HR-L1-010", "Zakat certificate")]
    index = build_compliance_index(hrs, "نقدم شهادة الزكاة سارية المفعول")
    entry = index.entries[0]
    assert entry.content_conformance_pass is True


def test_saudization_alias_arabic() -> None:
    hrs = [_hr("HR-L1-014", "Saudization certificate")]
    index = build_compliance_index(hrs, "ملتزمون بنسبة السعودة المطلوبة")
    entry = index.entries[0]
    assert entry.content_conformance_pass is True


def test_chamber_alias_arabic() -> None:
    hrs = [_hr("HR-L1-013", "Chamber of Commerce subscription certificate")]
    index = build_compliance_index(hrs, "اشتراك الغرفة التجارية ساري")
    entry = index.entries[0]
    assert entry.content_conformance_pass is True


def test_social_insurance_alias_arabic() -> None:
    hrs = [_hr("HR-L1-012", "Social insurance certificate")]
    index = build_compliance_index(hrs, "نملك شهادة التأمينات الاجتماعية")
    entry = index.entries[0]
    assert entry.content_conformance_pass is True


def test_tax_alias_arabic() -> None:
    hrs = [_hr("HR-L1-011", "Tax certificate")]
    index = build_compliance_index(hrs, "شهادة الضريبة سارية")
    entry = index.entries[0]
    assert entry.content_conformance_pass is True


def test_non_compliance_category_skipped() -> None:
    hrs = [
        HardRequirement(
            requirement_id="HR-L1-001",
            category="award_mechanism",
            subject="Award mechanism",
            value_text="pass_fail_then_lowest_price",
            validation_scope="source_book",
            severity="critical",
        ),
        _hr("HR-L1-002", "Commercial registration"),
    ]
    index = build_compliance_index(hrs, "السجل التجاري")
    # Only the compliance HR is indexed
    ids = {e.requirement_id for e in index.entries}
    assert ids == {"HR-L1-002"}


def test_arabic_aliases_recorded_in_entry() -> None:
    hrs = [_hr("HR-L1-009", "Commercial registration")]
    index = build_compliance_index(hrs, "السجل التجاري")
    entry = index.entries[0]
    assert any("السجل" in alias for alias in entry.arabic_aliases)


def test_ncnp_six_compliance_items_pass_via_aliases() -> None:
    """All 6 NCNP compliance items resolve through Arabic aliases."""
    hrs = [
        _hr("HR-L1-009", "Commercial registration"),
        _hr("HR-L1-010", "Zakat certificate"),
        _hr("HR-L1-011", "Tax certificate"),
        _hr("HR-L1-012", "Social insurance certificate"),
        _hr("HR-L1-013", "Chamber of Commerce subscription certificate"),
        _hr("HR-L1-014", "Saudization certificate"),
    ]
    sb_text = (
        "السجل التجاري ساري المفعول. شهادة الزكاة معتمدة. "
        "شهادة الضريبة سارية. التأمينات الاجتماعية مفعلة. "
        "الغرفة التجارية مشتركة. السعودة مستوفاة."
    )
    index = build_compliance_index(hrs, sb_text)
    by_id = {e.requirement_id: e for e in index.entries}
    for rid in [
        "HR-L1-009", "HR-L1-010", "HR-L1-011",
        "HR-L1-012", "HR-L1-013", "HR-L1-014",
    ]:
        assert by_id[rid].content_conformance_pass is True, (
            f"{rid} should pass via alias match"
        )
