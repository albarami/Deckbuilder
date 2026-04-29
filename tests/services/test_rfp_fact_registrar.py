"""Tests for RFP fact registrar — generic compatibility."""

from src.models.claim_provenance import ClaimRegistry
from src.models.common import BilingualText
from src.models.rfp import RFPContext
from src.services.rfp_fact_registrar import register_rfp_facts

_REQUIRED = {
    "rfp_name": BilingualText(en="Test RFP", ar="منافسة تجريبية"),
    "issuing_entity": BilingualText(en="Test Entity", ar="جهة تجريبية"),
    "mandate": BilingualText(en="Test mandate", ar="نطاق تجريبي"),
}


def test_register_rfp_facts_handles_string_source_language():
    """source_language may be a plain string due to use_enum_values=True.

    DeckForgeBaseModel uses use_enum_values=True, which stores Language
    enum values as plain strings ("en", "ar"). The registrar must not
    crash when .value is called on a string.
    """
    rfp = RFPContext(**_REQUIRED)
    # use_enum_values=True means rfp.source_language is already "en" (string)
    assert isinstance(rfp.source_language, str), (
        f"Expected string due to use_enum_values=True, got {type(rfp.source_language)}"
    )

    registry = ClaimRegistry()
    # Must not raise AttributeError: 'str' object has no attribute 'value'
    register_rfp_facts(rfp, registry)

    # Should have registered at least the language fact
    lang_claims = [c for c in registry.rfp_facts if "language" in c.text.lower()]
    assert len(lang_claims) == 1
    assert "en" in lang_claims[0].text


def test_register_rfp_facts_with_arabic_language():
    """Test with Arabic language setting."""
    rfp = RFPContext(**_REQUIRED, source_language="ar")
    registry = ClaimRegistry()
    register_rfp_facts(rfp, registry)

    lang_claims = [c for c in registry.rfp_facts if "language" in c.text.lower()]
    assert len(lang_claims) == 1
    assert "ar" in lang_claims[0].text
