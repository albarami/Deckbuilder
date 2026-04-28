"""External-methodology classifier — Slice 3.1.

Converts ExternalSource records (from the External Research Agent's
ExternalEvidencePack) into ClaimProvenance records with explicit
relevance_class:
  * direct_topic     — the source title/abstract/theme matches a
                       primary RFP topic keyword
  * adjacent_domain  — matches an adjacent/secondary topic keyword
  * analogical       — neither (or evidence_tier already == "analogical")

The legacy ExternalSource.evidence_tier (`primary`/`secondary`/`analogical`)
is honored as a hard lower bound: any source already tagged analogical
in the pack is preserved as analogical. Otherwise relevance is derived
from topical keyword matching.
"""
from __future__ import annotations

from src.models.claim_provenance import (
    ClaimProvenance,
    ClaimRegistry,
    SourceReference,
)
from src.models.external_evidence import ExternalEvidencePack, ExternalSource


def _searchable_text(source: ExternalSource) -> str:
    parts = [
        source.title or "",
        source.abstract or "",
        source.mapped_rfp_theme or "",
        source.relevance_reason or "",
        source.raw_excerpt or "",
    ]
    parts.extend(source.key_findings or [])
    return " ".join(parts).lower()


def classify_external_source(
    source: ExternalSource,
    *,
    primary_topics: list[str],
    adjacent_topics: list[str] | None = None,
) -> ClaimProvenance:
    """Convert one ExternalSource to a ClaimProvenance.

    Topic keywords are case-insensitive substrings. ``primary_topics`` is
    matched first; if none match, ``adjacent_topics`` is tried; else the
    source is analogical. Sources whose evidence_tier is already
    ``analogical`` cannot be promoted to direct/adjacent — the writer's
    own tiering wins to preserve the agent's discrimination.
    """
    adjacent_topics = adjacent_topics or []

    if source.evidence_tier == "analogical":
        relevance = "analogical"
    else:
        text = _searchable_text(source)
        if any(kw.lower() in text for kw in primary_topics if kw):
            relevance = "direct_topic"
        elif any(kw.lower() in text for kw in adjacent_topics if kw):
            relevance = "adjacent_domain"
        else:
            relevance = "analogical"

    return ClaimProvenance(
        claim_id=source.source_id,
        text=source.title or source.source_id,
        claim_kind="external_methodology",
        source_kind="external_source",
        verification_status="externally_verified",
        evidence_role="methodology_support",
        relevance_class=relevance,  # type: ignore[arg-type]
        confidence=float(source.relevance_score or 0.0),
        source_refs=[
            SourceReference(
                file=source.url or source.title or "external",
                evidence_id=source.source_id,
            ),
        ],
    )


def classify_external_evidence_pack(
    pack: ExternalEvidencePack,
    *,
    primary_topics: list[str],
    adjacent_topics: list[str] | None = None,
    registry: ClaimRegistry | None = None,
) -> ClaimRegistry:
    """Classify every source in the pack and register it.

    Returns the (possibly newly created) registry. Idempotent per
    source_id — calling twice with the same pack overwrites existing
    entries via ``ClaimRegistry.register``.
    """
    if registry is None:
        registry = ClaimRegistry()
    for source in pack.sources:
        registry.register(
            classify_external_source(
                source,
                primary_topics=primary_topics,
                adjacent_topics=adjacent_topics,
            )
        )
    return registry
