"""Tests for RFP routing — classifier, pack selection, and merge."""

import pytest

from src.models.routing import ContextPack, RFPClassification, RoutingReport
from src.models.state import DeckForgeState
from src.services.routing import (
    _load_pack,
    classify_rfp,
    merge_packs,
    route_rfp,
    select_packs,
)


# ──────────────────────────────────────────────────────────────
# Helper to build a minimal DeckForgeState with RFP context
# ──────────────────────────────────────────────────────────────

def _make_state_with_rfp(
    rfp_name_ar: str = "",
    rfp_name_en: str = "",
    mandate_ar: str = "",
    mandate_en: str = "",
    scope_texts_en: list[str] | None = None,
) -> DeckForgeState:
    """Create a DeckForgeState with synthetic RFP context for routing tests."""
    from src.models.rfp import (
        BilingualText,
        Completeness,
        Language,
        RFPContext,
        ScopeItem,
    )

    scope_items = []
    for i, text in enumerate(scope_texts_en or []):
        scope_items.append(
            ScopeItem(
                id=f"S{i+1}",
                description=BilingualText(en=text, ar=""),
                category="scope",
            )
        )

    rfp = RFPContext(
        rfp_name=BilingualText(en=rfp_name_en, ar=rfp_name_ar),
        issuing_entity=BilingualText(en="Test Entity", ar="جهة اختبار"),
        mandate=BilingualText(en=mandate_en, ar=mandate_ar),
        scope_items=scope_items,
        source_language=Language.AR,
        completeness=Completeness(),
    )

    return DeckForgeState(rfp_context=rfp)


# ──────────────────────────────────────────────────────────────
# 1. Pack loading
# ──────────────────────────────────────────────────────────────


class TestPackLoading:
    def test_load_saudi_public_sector(self):
        pack = _load_pack("saudi_public_sector")
        assert pack is not None
        assert pack.pack_id == "saudi_public_sector"
        assert pack.pack_type == "jurisdiction"
        assert len(pack.regulatory_references) >= 5
        assert len(pack.compliance_patterns) >= 2
        assert len(pack.evaluator_insights) >= 3

    def test_load_saudi_private_sector(self):
        pack = _load_pack("saudi_private_sector")
        assert pack is not None
        assert pack.pack_id == "saudi_private_sector"
        assert pack.pack_type == "jurisdiction"

    def test_load_qatar_public_sector(self):
        pack = _load_pack("qatar_public_sector")
        assert pack is not None
        assert pack.pack_id == "qatar_public_sector"
        assert pack.pack_type == "jurisdiction"
        assert len(pack.regulatory_references) >= 3

    def test_load_investment_promotion(self):
        pack = _load_pack("investment_promotion")
        assert pack is not None
        assert pack.pack_type == "domain"
        assert len(pack.benchmark_references) >= 3

    def test_load_generic_fallback(self):
        pack = _load_pack("generic_mena_public_sector")
        assert pack is not None
        assert pack.pack_type == "generic_fallback"

    def test_load_nonexistent_pack(self):
        pack = _load_pack("nonexistent_pack")
        assert pack is None


# ──────────────────────────────────────────────────────────────
# 2. RFP Classification
# ──────────────────────────────────────────────────────────────


class TestClassification:
    def test_saudi_public_sector_investment(self):
        """SIPA-like RFP: Saudi authority, investment promotion domain."""
        state = _make_state_with_rfp(
            rfp_name_ar="دليل باقة الخدمات التي ستقدم للشركات لدعمها في التوسع الخارجي",
            rfp_name_en="Guide to the Service Package for Companies International Expansion",
            mandate_ar="تصميم وتطوير دليل متكامل يحدد باقة الخدمات التي ستقدمها الهيئة للشركات للتوسع الخارجي والاستثمار",
            scope_texts_en=[
                "Analyze priorities and identify needs for investment promotion",
                "Design a supporting services ecosystem for international expansion and export",
            ],
        )
        cls = classify_rfp(state)
        assert cls.jurisdiction == "saudi_arabia"
        assert cls.sector == "public_sector"
        # Domain may be investment_promotion or service_design depending on keyword overlap
        assert cls.domain in ("investment_promotion", "service_design")
        assert cls.confidence > 0

    def test_saudi_private_sector(self):
        """Saudi private sector company RFP."""
        state = _make_state_with_rfp(
            rfp_name_ar="تطوير استراتيجية التحول الرقمي لشركة الراجحي",
            rfp_name_en="Digital Transformation Strategy for Al Rajhi Company",
            mandate_ar="تطوير استراتيجية شاملة للتحول الرقمي لشركة الراجحي في الرياض",
            scope_texts_en=[
                "Assess current digital maturity",
                "Design target digital operating model",
            ],
        )
        cls = classify_rfp(state)
        assert cls.jurisdiction == "saudi_arabia"
        assert cls.sector == "private_sector"
        assert cls.domain == "digital_transformation"

    def test_qatari_public_sector(self):
        """Qatari government ministry RFP."""
        state = _make_state_with_rfp(
            rfp_name_ar="تطوير الخطة الاستراتيجية لوزارة المواصلات والاتصالات في قطر",
            rfp_name_en="Strategic Plan Development for Qatar MOTC",
            mandate_ar="إعداد خطة استراتيجية شاملة لوزارة المواصلات والاتصالات في الدوحة",
            scope_texts_en=[
                "Develop five-year strategic plan",
                "Align with Qatar National Vision 2030",
            ],
        )
        cls = classify_rfp(state)
        assert cls.jurisdiction == "qatar"
        assert cls.sector == "public_sector"
        assert "ministry" in cls.client_type or cls.client_type == ""

    def test_unknown_jurisdiction(self):
        """RFP with no clear jurisdiction markers."""
        state = _make_state_with_rfp(
            rfp_name_en="Management Consulting Advisory Services",
            mandate_en="Provide advisory services for organizational development",
            scope_texts_en=["Organizational assessment", "Change management"],
        )
        cls = classify_rfp(state)
        # Should have low confidence when jurisdiction is unclear
        assert cls.confidence < 0.7

    def test_empty_rfp(self):
        """Empty state — should return low confidence."""
        state = DeckForgeState()
        cls = classify_rfp(state)
        # No RFP context → zero or near-zero confidence
        assert cls.confidence <= 0.1


# ──────────────────────────────────────────────────────────────
# 3. Pack Selection
# ──────────────────────────────────────────────────────────────


class TestPackSelection:
    def test_saudi_public_selects_correct_packs(self):
        cls = RFPClassification(
            jurisdiction="saudi_arabia",
            sector="public_sector",
            domain="investment_promotion",
        )
        selected, fallbacks = select_packs(cls)
        assert "saudi_public_sector" in selected
        assert "investment_promotion" in selected
        assert len(fallbacks) == 0

    def test_saudi_private_selects_correct_pack(self):
        cls = RFPClassification(
            jurisdiction="saudi_arabia",
            sector="private_sector",
        )
        selected, fallbacks = select_packs(cls)
        assert "saudi_private_sector" in selected
        assert len(fallbacks) == 0

    def test_qatar_public_selects_correct_pack(self):
        cls = RFPClassification(
            jurisdiction="qatar",
            sector="public_sector",
        )
        selected, fallbacks = select_packs(cls)
        assert "qatar_public_sector" in selected
        assert len(fallbacks) == 0

    def test_unknown_jurisdiction_uses_fallback(self):
        cls = RFPClassification(
            jurisdiction="unknown",
            sector="public_sector",
        )
        selected, fallbacks = select_packs(cls)
        assert "generic_mena_public_sector" in fallbacks
        assert len(selected) == 0


# ──────────────────────────────────────────────────────────────
# 4. Pack Merge
# ──────────────────────────────────────────────────────────────


class TestPackMerge:
    def test_merge_jurisdiction_and_domain(self):
        merged = merge_packs(
            ["saudi_public_sector", "investment_promotion"],
            [],
        )
        assert len(merged["active_packs"]) == 2
        assert len(merged["regulatory_references"]) >= 5
        assert len(merged["benchmark_references"]) >= 3
        # Forbidden assumptions are cumulative
        assert len(merged["forbidden_assumptions"]) >= 5

    def test_merge_with_fallback(self):
        merged = merge_packs([], ["generic_mena_public_sector"])
        assert "generic_mena_public_sector" in merged["active_packs"]
        assert len(merged["compliance_patterns"]) >= 1


# ──────────────────────────────────────────────────────────────
# 5. Full Routing Pipeline
# ──────────────────────────────────────────────────────────────


class TestFullRouting:
    def test_sipa_routing(self):
        """Full routing for SIPA-like RFP."""
        state = _make_state_with_rfp(
            rfp_name_ar="دليل باقة الخدمات التي ستقدم للشركات لدعمها في التوسع الخارجي",
            mandate_ar="تصميم وتطوير دليل متكامل يحدد باقة الخدمات التي ستقدمها الهيئة",
            scope_texts_en=[
                "Analyze priorities and identify needs",
                "Design supporting services ecosystem for international expansion",
            ],
        )
        report, merged = route_rfp(state)

        assert isinstance(report, RoutingReport)
        assert report.routing_confidence > 0
        assert "saudi_public_sector" in report.selected_packs
        assert len(merged["regulatory_references"]) > 0

    def test_low_confidence_generates_warning(self):
        """Unknown RFP should generate routing warning."""
        state = _make_state_with_rfp(
            rfp_name_en="Generic Advisory Services",
            mandate_en="Advisory services",
        )
        report, _ = route_rfp(state)

        if report.routing_confidence < 0.7:
            assert any("confidence" in w.lower() for w in report.warnings)

    def test_routing_report_fields(self):
        """Routing report must have all required fields."""
        state = _make_state_with_rfp(
            rfp_name_ar="مشروع حكومي سعودي",
        )
        report, _ = route_rfp(state)

        assert hasattr(report, "classification")
        assert hasattr(report, "selected_packs")
        assert hasattr(report, "fallback_packs_used")
        assert hasattr(report, "warnings")
        assert hasattr(report, "routing_confidence")
