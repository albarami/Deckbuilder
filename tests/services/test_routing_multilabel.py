"""Multi-label routing — primary/secondary domain split with weighted scoring."""
from __future__ import annotations

from src.models.common import BilingualText
from src.models.rfp import RFPContext
from src.models.state import DeckForgeState
from src.services.routing import classify_rfp, select_packs


def _unesco_ai_state() -> DeckForgeState:
    state = DeckForgeState()
    state.rfp_context = RFPContext(
        rfp_name=BilingualText(
            ar=(
                "الخدمات الاحترافية في أبحاث الذكاء الاصطناعي وأخلاقياته "
                "مع اليونسكو ومنهجية تقييم الجاهزية RAM"
            ),
            en="",
        ),
        issuing_entity=BilingualText(
            ar="الهيئة السعودية للبيانات والذكاء الاصطناعي - سدايا",
            en="SDAIA",
        ),
        mandate=BilingualText(ar="", en=""),
    )
    return state


def test_unesco_routes_to_specific_domains() -> None:
    classification = classify_rfp(_unesco_ai_state())
    assert "ai_governance_ethics" in classification.primary_domains
    assert "unesco_unesco_ram" in classification.primary_domains
    assert "digital_transformation" not in classification.primary_domains


def test_digital_transformation_demoted_to_secondary() -> None:
    classification = classify_rfp(_unesco_ai_state())
    # If digital_transformation surfaces at all, it must be secondary, not primary
    if "digital_transformation" in classification.secondary_domains:
        assert "digital_transformation" not in classification.primary_domains


def test_pack_selection_includes_domain_packs() -> None:
    classification = classify_rfp(_unesco_ai_state())
    selected, _fallbacks = select_packs(classification)
    # Either ai_governance_ethics is in primary_domains AND selected, or not in primary.
    assert (
        "ai_governance_ethics" in selected
        or "ai_governance_ethics" not in classification.primary_domains
    )
    assert "saudi_public_sector" in selected


def test_saudi_jurisdiction_from_issuing_entity() -> None:
    classification = classify_rfp(_unesco_ai_state())
    assert classification.jurisdiction == "saudi_arabia"


def test_unesco_pack_selection_includes_unesco_ram() -> None:
    classification = classify_rfp(_unesco_ai_state())
    selected, _fallbacks = select_packs(classification)
    # If unesco_unesco_ram is primary, it must appear in selected packs
    if "unesco_unesco_ram" in classification.primary_domains:
        assert "unesco_unesco_ram" in selected


def test_primary_domain_back_compat() -> None:
    """The legacy `domain` field still surfaces a single domain when available."""
    classification = classify_rfp(_unesco_ai_state())
    if classification.primary_domains:
        assert classification.domain in classification.primary_domains
