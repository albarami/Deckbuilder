from backend.services.pipeline_runtime import _build_gate1_payload
from src.models.common import BilingualText
from src.models.enums import Language
from src.models.rfp import Completeness, KeyDates, RFPContext
from src.models.state import DeckForgeState


def test_build_gate1_payload_normalizes_missing_key_dates() -> None:
    state = DeckForgeState(
        output_language=Language.EN,
        user_notes="Focus on SAP support delivery.",
        rfp_context=RFPContext(
            rfp_name=BilingualText(en="SAP Support Renewal"),
            issuing_entity=BilingualText(en="SIDF"),
            mandate=BilingualText(en="Renew SAP licenses for 24 months."),
            key_dates=KeyDates(
                inquiry_deadline=None,
                submission_deadline=None,
                bid_opening=None,
                expected_award=None,
                service_start=None,
            ),
            completeness=Completeness(top_level_missing=[]),
        ),
    )

    payload = _build_gate1_payload(state)

    assert payload.rfp_brief.key_dates.inquiry_deadline == ""
    assert payload.rfp_brief.key_dates.submission_deadline == ""
    assert payload.rfp_brief.key_dates.opening_date == ""
    assert payload.rfp_brief.key_dates.expected_award_date == ""
    assert payload.rfp_brief.key_dates.service_start_date == ""
