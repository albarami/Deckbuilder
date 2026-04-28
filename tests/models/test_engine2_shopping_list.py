"""Engine 2 shopping list contract — Slice 2.1.

`build_engine2_shopping_list` was implemented in Slice 1.5 because Slice 1's
acceptance criterion required proving RFP facts never enter Engine 2. This
test file documents the shopping-list contract on its own terms:

  * filter is property-based, never ID-prefix-based
  * only `internal_company_claim` + `internal_backend` + `internal_unverified`
  * RFP facts, external methodology, proposal options, generated inferences,
    and already-verified internal claims are all excluded
  * `requested_external_contexts` survives from claim → request unmodified
  * defensive invariant: no non-bidder claim ever appears in the result
"""
from __future__ import annotations

from src.models.claim_provenance import (
    ClaimProvenance,
    ClaimRegistry,
    SourceReference,
)
from src.models.engine2_contract import (
    Engine2ProofRequest,
    build_engine2_shopping_list,
)


def _bidder_claim(
    claim_id: str = "BIDDER-001",
    *,
    text: str = "Prior project",
    verification_status: str = "internal_unverified",
    requested_external_contexts: list[str] | None = None,
    requires_client_naming_permission: bool = False,
    requires_partner_naming_permission: bool = False,
    source_refs: list[SourceReference] | None = None,
) -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status=verification_status,  # type: ignore[arg-type]
        requested_external_contexts=requested_external_contexts or [],  # type: ignore[arg-type]
        requires_client_naming_permission=requires_client_naming_permission,
        requires_partner_naming_permission=requires_partner_naming_permission,
        source_refs=source_refs or [],
    )


# ── Inclusion criteria ─────────────────────────────────────────────────


def test_unverified_internal_bidder_claim_is_included() -> None:
    reg = ClaimRegistry()
    reg.register(_bidder_claim())
    shopping = build_engine2_shopping_list(reg)
    assert len(shopping) == 1
    assert shopping[0].claim_id == "BIDDER-001"
    assert isinstance(shopping[0], Engine2ProofRequest)


def test_requested_external_contexts_pass_through() -> None:
    reg = ClaimRegistry()
    reg.register(_bidder_claim(
        requested_external_contexts=["source_book", "slide_blueprint"],
    ))
    req = build_engine2_shopping_list(reg)[0]
    assert req.requested_external_contexts == ["source_book", "slide_blueprint"]


def test_default_request_context_when_claim_has_none() -> None:
    """Empty `requested_external_contexts` defaults to ["source_book"]."""
    reg = ClaimRegistry()
    reg.register(_bidder_claim())
    req = build_engine2_shopping_list(reg)[0]
    assert req.requested_external_contexts == ["source_book"]


def test_naming_permission_flags_propagate() -> None:
    reg = ClaimRegistry()
    reg.register(_bidder_claim(
        requires_client_naming_permission=True,
        requires_partner_naming_permission=True,
    ))
    req = build_engine2_shopping_list(reg)[0]
    assert req.requires_client_naming_permission is True
    assert req.requires_partner_naming_permission is True


def test_internal_ref_picked_up_from_first_source_ref() -> None:
    reg = ClaimRegistry()
    reg.register(_bidder_claim(
        source_refs=[SourceReference(file="backend", evidence_id="EV-42")],
    ))
    req = build_engine2_shopping_list(reg)[0]
    assert req.internal_ref == "EV-42"


# ── Exclusion criteria — by claim_kind ─────────────────────────────────


def test_rfp_fact_never_emitted() -> None:
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="RFP-FACT-001", text="contract = 12 months",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    assert build_engine2_shopping_list(reg) == []


def test_external_methodology_never_emitted() -> None:
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="EXT-001", text="UNESCO RAM",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
    ))
    assert build_engine2_shopping_list(reg) == []


def test_proposal_option_never_emitted() -> None:
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="OPT-001", text="5-8 countries",
        claim_kind="proposal_option", source_kind="model_generated",
        verification_status="proposal_option",
    ))
    assert build_engine2_shopping_list(reg) == []


def test_generated_inference_never_emitted() -> None:
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="INF-001", text="Portal: EXPRO",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
    ))
    assert build_engine2_shopping_list(reg) == []


# ── Exclusion criteria — by verification_status ────────────────────────


def test_already_verified_bidder_claim_skipped() -> None:
    reg = ClaimRegistry()
    reg.register(_bidder_claim(
        claim_id="BIDDER-VERIFIED",
        verification_status="internal_verified",
    ))
    assert build_engine2_shopping_list(reg) == []


# ── Exclusion criteria — by source_kind ────────────────────────────────


def test_wrong_source_kind_skipped() -> None:
    """A claim_kind=internal_company_claim but source_kind=model_generated
    is malformed — the shopping list must defensively skip it rather than
    relying on ID prefixes."""
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="MALFORMED-001",
        text="malformed bidder claim with wrong source_kind",
        claim_kind="internal_company_claim",
        source_kind="model_generated",  # Wrong — must be internal_backend
        verification_status="internal_unverified",
    ))
    assert build_engine2_shopping_list(reg) == []


# ── Mixed registry: ordering and isolation ─────────────────────────────


def test_mixed_registry_only_emits_unverified_bidder() -> None:
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="RFP-FACT-001", text="x",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    reg.register(ClaimProvenance(
        claim_id="EXT-001", text="x",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
    ))
    reg.register(_bidder_claim("BIDDER-A"))
    reg.register(_bidder_claim(
        "BIDDER-VERIFIED", verification_status="internal_verified",
    ))
    reg.register(_bidder_claim("BIDDER-B"))
    shopping = build_engine2_shopping_list(reg)
    ids = {r.claim_id for r in shopping}
    assert ids == {"BIDDER-A", "BIDDER-B"}


# ── ID-prefix audit — filter must be property-based ────────────────────


def test_filter_does_not_use_id_prefix() -> None:
    """A claim with id 'RFP-FACT-001' but properties of an unverified bidder
    claim MUST be included — the filter is property-based, not prefix-based."""
    reg = ClaimRegistry()
    reg.register(_bidder_claim(claim_id="RFP-FACT-001"))
    assert {r.claim_id for r in build_engine2_shopping_list(reg)} == {
        "RFP-FACT-001"
    }


def test_filter_excludes_actual_rfp_fact_with_bidder_like_id() -> None:
    """Conversely, an actual rfp_fact with id 'BIDDER-007' must STILL be
    excluded — claim_kind dominates over ID."""
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="BIDDER-007",
        text="actually an RFP fact",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    assert build_engine2_shopping_list(reg) == []


# ── Defensive invariant ───────────────────────────────────────────────


def test_defensive_assertion_protects_invariant() -> None:
    """build_engine2_shopping_list asserts every emitted request maps back
    to a real internal_company_claim in the registry."""
    reg = ClaimRegistry()
    reg.register(_bidder_claim("BIDDER-X"))
    shopping = build_engine2_shopping_list(reg)
    for req in shopping:
        c = reg.get(req.claim_id)
        assert c is not None
        assert c.claim_kind == "internal_company_claim"
