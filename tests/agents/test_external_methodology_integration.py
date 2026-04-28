"""External-methodology writer/gate integration — Slice 3.3.

End-to-end checks that slide proof gating and source-book analysis gates
treat external_methodology claims correctly:

  * analogical external sources cannot be slide proof points
  * direct/adjacent external sources are only proof points when
    evidence_role == "methodology_support"
  * analogical externally-verified sources may still appear in
    client-facing analysis text (where `can_use_in_source_book_analysis`
    permits them) — they just cannot anchor a proof point
  * a mixed registry yields exactly the right surviving proof_points
    after gate_slide_proof_points
"""
from __future__ import annotations

from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.models.source_book import SlideBlueprintEntry
from src.services.artifact_gates import (
    can_use_as_proof_point,
    can_use_in_source_book_analysis,
    gate_slide_proof_points,
)


def _ext_methodology(
    claim_id: str,
    text: str,
    *,
    relevance: str,
    role: str = "methodology_support",
    verification: str = "externally_verified",
) -> ClaimProvenance:
    return ClaimProvenance(
        claim_id=claim_id,
        text=text,
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status=verification,  # type: ignore[arg-type]
        relevance_class=relevance,  # type: ignore[arg-type]
        evidence_role=role,  # type: ignore[arg-type]
    )


# ── Slide proof gating ─────────────────────────────────────────────────


def test_slide_gate_drops_analogical_external() -> None:
    bp = SlideBlueprintEntry(
        slide_number=3,
        title="Methodology",
        proof_points=["EXT-ANALOG"],
    )
    reg = ClaimRegistry()
    reg.register(_ext_methodology(
        "EXT-ANALOG",
        "WHO health workforce governance",
        relevance="analogical",
    ))
    gated, violations = gate_slide_proof_points([bp], reg)
    assert gated[0].proof_points == []
    assert len(violations) == 1
    assert violations[0].claim_id == "EXT-ANALOG"
    assert violations[0].reason == "not_a_proof_point"


def test_slide_gate_drops_direct_external_with_wrong_role() -> None:
    """Acceptance #5: direct/adjacent methodology claims survive ONLY
    when evidence_role == "methodology_support". A wrong role (e.g.
    bidder_capability_proof) blocks the proof point."""
    bp = SlideBlueprintEntry(
        slide_number=4,
        title="Capability",
        proof_points=["EXT-WRONGROLE"],
    )
    reg = ClaimRegistry()
    reg.register(_ext_methodology(
        "EXT-WRONGROLE",
        "Direct topic source",
        relevance="direct_topic",
        role="bidder_capability_proof",
    ))
    gated, violations = gate_slide_proof_points([bp], reg)
    assert gated[0].proof_points == []
    assert len(violations) == 1


def test_slide_gate_keeps_direct_methodology_support() -> None:
    bp = SlideBlueprintEntry(
        slide_number=5,
        title="UNESCO RAM",
        proof_points=["EXT-DIRECT"],
    )
    reg = ClaimRegistry()
    reg.register(_ext_methodology(
        "EXT-DIRECT",
        "UNESCO RAM country review",
        relevance="direct_topic",
    ))
    gated, violations = gate_slide_proof_points([bp], reg)
    assert gated[0].proof_points == ["EXT-DIRECT"]
    assert violations == []


def test_slide_gate_keeps_adjacent_methodology_support() -> None:
    bp = SlideBlueprintEntry(
        slide_number=6,
        title="Adjacent reference",
        proof_points=["EXT-ADJ"],
    )
    reg = ClaimRegistry()
    reg.register(_ext_methodology(
        "EXT-ADJ",
        "Adjacent topic methodology",
        relevance="adjacent_domain",
    ))
    gated, violations = gate_slide_proof_points([bp], reg)
    assert gated[0].proof_points == ["EXT-ADJ"]
    assert violations == []


def test_slide_gate_drops_partially_verified_analogical() -> None:
    bp = SlideBlueprintEntry(
        slide_number=7,
        title="Partial",
        proof_points=["EXT-PV-ANALOG"],
    )
    reg = ClaimRegistry()
    reg.register(_ext_methodology(
        "EXT-PV-ANALOG",
        "Partially verified analogical",
        relevance="analogical",
        verification="partially_verified",
    ))
    gated, violations = gate_slide_proof_points([bp], reg)
    assert gated[0].proof_points == []
    assert violations[0].verification_status == "partially_verified"


def test_slide_gate_mixed_registry_keeps_only_eligible() -> None:
    bp = SlideBlueprintEntry(
        slide_number=10,
        title="Mixed proof",
        proof_points=[
            "EXT-DIRECT",       # kept
            "EXT-ADJ",          # kept
            "EXT-ANALOG",       # dropped
            "EXT-WRONG-ROLE",   # dropped
        ],
    )
    reg = ClaimRegistry()
    reg.register(_ext_methodology("EXT-DIRECT", "Direct UNESCO RAM", relevance="direct_topic"))
    reg.register(_ext_methodology("EXT-ADJ", "Adjacent governance source", relevance="adjacent_domain"))
    reg.register(_ext_methodology("EXT-ANALOG", "Analogical case", relevance="analogical"))
    reg.register(_ext_methodology(
        "EXT-WRONG-ROLE",
        "Direct topic but wrong role",
        relevance="direct_topic",
        role="bidder_capability_proof",
    ))
    gated, violations = gate_slide_proof_points([bp], reg)
    assert sorted(gated[0].proof_points) == sorted(["EXT-DIRECT", "EXT-ADJ"])
    dropped = {v.claim_id for v in violations}
    assert dropped == {"EXT-ANALOG", "EXT-WRONG-ROLE"}


# ── Source-book analysis gates ─────────────────────────────────────────


def test_externally_verified_analogical_allowed_in_client_body_for_analysis() -> None:
    """Analogical externally-verified sources may support client-facing
    analysis text (NOT proof points). This is the 'may support analysis
    only where allowed' bucket."""
    claim = _ext_methodology(
        "EXT-ANALYSIS-ANALOG",
        "Analogical externally verified",
        relevance="analogical",
    )
    assert can_use_in_source_book_analysis(claim, "client_facing_body") is True
    # But never as proof point:
    assert can_use_as_proof_point(claim) is False


def test_partially_verified_analogical_blocked_in_client_body() -> None:
    """Slice 3 acceptance: analogical + partially_verified is too weak
    even for analysis text."""
    claim = _ext_methodology(
        "EXT-PV-ANALOG-2",
        "Partial-verified analogical",
        relevance="analogical",
        verification="partially_verified",
    )
    assert can_use_in_source_book_analysis(claim, "client_facing_body") is False


def test_partially_verified_adjacent_methodology_allowed_in_client_body() -> None:
    claim = _ext_methodology(
        "EXT-PV-ADJ",
        "Partial-verified adjacent methodology",
        relevance="adjacent_domain",
        verification="partially_verified",
    )
    assert can_use_in_source_book_analysis(claim, "client_facing_body") is True
    # But still not a proof point because it's only partially_verified:
    assert can_use_as_proof_point(claim) is False


def test_analogical_allowed_only_in_analysis_not_in_slide_blueprint() -> None:
    from src.services.artifact_gates import can_use_in_slide_blueprint

    claim = _ext_methodology(
        "EXT-NO-SLIDE",
        "Analogical externally verified",
        relevance="analogical",
    )
    # Analysis text: yes
    assert can_use_in_source_book_analysis(claim, "client_facing_body") is True
    # Slide blueprint: no
    assert can_use_in_slide_blueprint(claim) is False


def test_internal_gap_appendix_accepts_anything() -> None:
    """Sanity: even an analogical, even a partially_verified one, can
    appear in the internal_gap_appendix — the most permissive bucket."""
    claim = _ext_methodology(
        "EXT-APPENDIX",
        "Edge case",
        relevance="analogical",
        verification="partially_verified",
    )
    assert can_use_in_source_book_analysis(claim, "internal_gap_appendix") is True
