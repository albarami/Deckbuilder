"""External-methodology classifier — Slice 3.1 + Slice 3.5 wiring.

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

Slice 3.5 adds ``register_external_methodology`` — the pipeline-wiring
helper that classifies a pack against routing-derived domain labels,
registers every source into a ClaimRegistry, and builds an
EvidenceCoverageReport with one requirement per primary domain.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.models.claim_provenance import (
    ClaimProvenance,
    ClaimRegistry,
    SourceReference,
)
from src.models.external_evidence import ExternalEvidencePack, ExternalSource

_PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"


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


# ── Slice 3.5: pipeline wiring helper ─────────────────────────────────


def _read_pack_domain_keywords(domain_id: str) -> list[str]:
    """Read flat domain keywords from src/packs/<domain_id>.json.

    Reads the same field used by the routing classifier
    (``classification_keywords.domain[<domain_id>]``) so the topical
    decisions in the classifier and the coverage builder stay aligned
    with routing's own scoring.
    """
    if not domain_id:
        return []
    path = _PACKS_DIR / f"{domain_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return list(
        data.get("classification_keywords", {})
        .get("domain", {})
        .get(domain_id, [])
    )


def register_external_methodology(
    pack: ExternalEvidencePack,
    registry: ClaimRegistry,
    *,
    primary_domains: list[str],
    secondary_domains: list[str] | None = None,
    minimum_direct_sources: int = 2,
) -> "EvidenceCoverageReport":
    """Slice 3.5 wiring step.

    1. Classify every source in ``pack`` against the union of keywords
       drawn from ``primary_domains`` (treated as ``direct_topic`` source
       material) and ``secondary_domains`` (``adjacent_domain``).
    2. Register every classified source into ``registry``. RFP facts and
       internal_company_claims in the registry are NOT touched.
    3. Build an EvidenceCoverageReport with one requirement per primary
       domain, using that domain's keyword list and the supplied
       ``minimum_direct_sources`` threshold.

    The helper is intended to run inside the pipeline's external
    evidence stage so that downstream nodes — and the final artifact
    gate — see a fully-populated registry and coverage report.
    """
    # Local import keeps artifact_gates as the single owner of the
    # coverage data structures while the classifier remains a pure
    # service module.
    from src.services.artifact_gates import (
        CoverageTopic,
        EvidenceCoverageReport,
        build_evidence_coverage_report,
    )

    secondary_domains = secondary_domains or []

    primary_keywords: list[str] = []
    for d in primary_domains:
        primary_keywords.extend(_read_pack_domain_keywords(d))
    adjacent_keywords: list[str] = []
    for d in secondary_domains:
        adjacent_keywords.extend(_read_pack_domain_keywords(d))

    classify_external_evidence_pack(
        pack,
        primary_topics=primary_keywords,
        adjacent_topics=adjacent_keywords,
        registry=registry,
    )

    topics: list[CoverageTopic] = []
    for d in primary_domains:
        kws = _read_pack_domain_keywords(d)
        topics.append(CoverageTopic(
            name=d,
            keywords=kws if kws else [d],
            minimum_direct_sources=minimum_direct_sources,
        ))

    if not topics:
        # No required topics → trivially passing report.
        return EvidenceCoverageReport(requirements=[])

    return build_evidence_coverage_report(registry, topics=topics)
