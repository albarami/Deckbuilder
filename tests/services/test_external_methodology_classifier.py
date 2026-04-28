"""External-methodology classifier — Slice 3.1.

Verifies that ExternalSource records become ClaimProvenance entries with
a correct relevance_class and the right evidence_role to participate as
methodology proof. analogical sources cannot be promoted; primary-topic
matches outrank adjacent matches.
"""
from __future__ import annotations

from src.models.claim_provenance import ClaimRegistry
from src.models.external_evidence import ExternalEvidencePack, ExternalSource
from src.services.external_methodology_classifier import (
    classify_external_evidence_pack,
    classify_external_source,
)


def _src(
    source_id: str,
    title: str,
    *,
    abstract: str = "",
    mapped_rfp_theme: str = "",
    evidence_tier: str = "primary",
    relevance_score: float = 0.7,
    source_type: str = "industry_report",
) -> ExternalSource:
    return ExternalSource(
        source_id=source_id,
        title=title,
        abstract=abstract,
        mapped_rfp_theme=mapped_rfp_theme,
        evidence_tier=evidence_tier,  # type: ignore[arg-type]
        relevance_score=relevance_score,
        source_type=source_type,  # type: ignore[arg-type]
    )


# ── Direct topic matches ───────────────────────────────────────────────


def test_primary_topic_keyword_in_title_yields_direct_topic() -> None:
    src = _src("EXT-001", "UNESCO RAM AI ethics country review")
    claim = classify_external_source(
        src,
        primary_topics=["unesco ram", "ai ethics"],
        adjacent_topics=[],
    )
    assert claim.claim_kind == "external_methodology"
    assert claim.source_kind == "external_source"
    assert claim.verification_status == "externally_verified"
    assert claim.relevance_class == "direct_topic"
    assert claim.evidence_role == "methodology_support"


def test_primary_topic_in_abstract_yields_direct_topic() -> None:
    src = _src(
        "EXT-002",
        "Generic title",
        abstract="This study evaluates UNESCO Recommendation on AI ethics.",
    )
    claim = classify_external_source(
        src,
        primary_topics=["unesco recommendation", "ai ethics"],
    )
    assert claim.relevance_class == "direct_topic"


def test_primary_topic_in_mapped_rfp_theme() -> None:
    src = _src(
        "EXT-003",
        "Generic title",
        mapped_rfp_theme="ai_governance_ethics",
    )
    claim = classify_external_source(
        src,
        primary_topics=["ai_governance_ethics"],
    )
    assert claim.relevance_class == "direct_topic"


# ── Adjacent topic matches ─────────────────────────────────────────────


def test_adjacent_topic_match_when_no_primary_match() -> None:
    src = _src(
        "EXT-010",
        "Digital transformation playbook for ministries",
    )
    claim = classify_external_source(
        src,
        primary_topics=["unesco ram", "ai ethics"],
        adjacent_topics=["digital transformation"],
    )
    assert claim.relevance_class == "adjacent_domain"


def test_primary_outranks_adjacent_when_both_present() -> None:
    src = _src(
        "EXT-011",
        "AI ethics in public sector digital transformation",
    )
    claim = classify_external_source(
        src,
        primary_topics=["ai ethics"],
        adjacent_topics=["digital transformation"],
    )
    assert claim.relevance_class == "direct_topic"


# ── Analogical fallback ────────────────────────────────────────────────


def test_no_match_falls_through_to_analogical() -> None:
    src = _src(
        "EXT-020",
        "Coffee shop loyalty program study",
    )
    claim = classify_external_source(
        src,
        primary_topics=["ai ethics"],
        adjacent_topics=["digital transformation"],
    )
    assert claim.relevance_class == "analogical"


def test_evidence_tier_analogical_cannot_be_promoted() -> None:
    """A source already tagged analogical in the pack stays analogical
    even if its title contains a primary keyword. The writer's own
    tier discipline outranks the topical heuristic."""
    src = _src(
        "EXT-021",
        "AI ethics analogical case study",
        evidence_tier="analogical",
    )
    claim = classify_external_source(
        src,
        primary_topics=["ai ethics"],
    )
    assert claim.relevance_class == "analogical"


# ── ClaimProvenance fields propagated ──────────────────────────────────


def test_claim_id_and_text_match_source() -> None:
    src = _src("EXT-030", "Title goes here", relevance_score=0.92)
    claim = classify_external_source(src, primary_topics=[])
    assert claim.claim_id == "EXT-030"
    assert claim.text == "Title goes here"
    assert claim.confidence == 0.92


def test_source_ref_records_url_and_evidence_id() -> None:
    src = ExternalSource(
        source_id="EXT-040",
        title="Reference doc",
        url="https://example.org/doc",
        source_type="academic_paper",
    )
    claim = classify_external_source(src, primary_topics=[])
    assert len(claim.source_refs) == 1
    assert claim.source_refs[0].evidence_id == "EXT-040"
    assert claim.source_refs[0].file == "https://example.org/doc"


# ── Pack-level classification ─────────────────────────────────────────


def test_classify_pack_returns_registry_with_every_source() -> None:
    pack = ExternalEvidencePack(sources=[
        _src("EXT-100", "UNESCO RAM"),
        _src("EXT-101", "Generic source", evidence_tier="analogical"),
        _src("EXT-102", "Digital transformation"),
    ])
    registry = classify_external_evidence_pack(
        pack,
        primary_topics=["unesco ram"],
        adjacent_topics=["digital transformation"],
    )
    ids = {c.claim_id for c in registry.external_methodology}
    assert ids == {"EXT-100", "EXT-101", "EXT-102"}
    relevances = {c.claim_id: c.relevance_class for c in registry.external_methodology}
    assert relevances["EXT-100"] == "direct_topic"
    assert relevances["EXT-101"] == "analogical"
    assert relevances["EXT-102"] == "adjacent_domain"


def test_classify_pack_into_existing_registry() -> None:
    pack = ExternalEvidencePack(sources=[_src("EXT-200", "AI ethics report")])
    registry = ClaimRegistry()
    classify_external_evidence_pack(
        pack, primary_topics=["ai ethics"], registry=registry,
    )
    assert registry.get("EXT-200") is not None


# ── External-methodology gate interactions ─────────────────────────────


def test_direct_topic_methodology_passes_proof_point_gate() -> None:
    from src.services.artifact_gates import can_use_as_proof_point

    src = _src("EXT-300", "Direct topic source")
    claim = classify_external_source(src, primary_topics=["direct topic"])
    assert claim.relevance_class == "direct_topic"
    assert can_use_as_proof_point(claim) is True


def test_adjacent_methodology_passes_proof_point_gate() -> None:
    from src.services.artifact_gates import can_use_as_proof_point

    src = _src("EXT-301", "Adjacent topic source")
    claim = classify_external_source(
        src,
        primary_topics=["primary"],
        adjacent_topics=["adjacent"],
    )
    assert claim.relevance_class == "adjacent_domain"
    assert can_use_as_proof_point(claim) is True


def test_analogical_methodology_fails_proof_point_gate() -> None:
    from src.services.artifact_gates import can_use_as_proof_point

    src = _src("EXT-302", "Analogical source", evidence_tier="analogical")
    claim = classify_external_source(src, primary_topics=["analogical"])
    assert claim.relevance_class == "analogical"
    assert can_use_as_proof_point(claim) is False
