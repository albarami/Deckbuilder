"""Tests for src/models/state.py — validates DeckForgeState against State Schema Section 11."""

import pytest


def test_empty_state_creation():
    from src.models.state import DeckForgeState

    state = DeckForgeState()
    assert state.current_stage == "intake"
    assert state.output_language == "en"
    assert state.rfp_context is None
    assert state.errors == []


def test_state_serialization_roundtrip():
    from src.models.state import DeckForgeState

    state = DeckForgeState()
    json_str = state.model_dump_json()
    restored = DeckForgeState.model_validate_json(json_str)
    assert restored.current_stage == state.current_stage
    assert restored.output_language == state.output_language


def test_state_with_nested_rfp_context():
    from src.models.common import BilingualText
    from src.models.rfp import RFPContext
    from src.models.state import DeckForgeState

    rfp = RFPContext(
        rfp_name=BilingualText(en="Test RFP"),
        issuing_entity=BilingualText(en="Test Entity"),
        mandate=BilingualText(en="Test mandate"),
    )
    state = DeckForgeState(rfp_context=rfp)
    assert state.rfp_context is not None
    assert state.rfp_context.rfp_name.en == "Test RFP"


def test_state_with_gate_decision():
    from src.models.state import DeckForgeState, GateDecision

    gate = GateDecision(gate_number=1, approved=True, feedback="LGTM")
    state = DeckForgeState(gate_1=gate)
    assert state.gate_1.approved is True
    assert state.gate_1.gate_number == 1


def test_state_rejects_extra_fields():
    from src.models.state import DeckForgeState

    with pytest.raises(Exception):
        DeckForgeState(nonexistent_field="value")


def test_state_full_roundtrip_with_nested_models():
    from src.models.common import BilingualText
    from src.models.rfp import RFPContext
    from src.models.state import DeckForgeState, GateDecision, RetrievedSource

    state = DeckForgeState(
        rfp_context=RFPContext(
            rfp_name=BilingualText(en="SAP Renewal"),
            issuing_entity=BilingualText(en="SIDF"),
            mandate=BilingualText(en="Renew SAP licenses"),
        ),
        gate_1=GateDecision(gate_number=1, approved=True),
        retrieved_sources=[
            RetrievedSource(doc_id="DOC-001", title="Test Doc", relevance_score=85),
        ],
    )
    json_str = state.model_dump_json()
    restored = DeckForgeState.model_validate_json(json_str)
    assert restored.rfp_context.rfp_name.en == "SAP Renewal"
    assert restored.gate_1.approved is True
    assert len(restored.retrieved_sources) == 1
    assert restored.retrieved_sources[0].doc_id == "DOC-001"
