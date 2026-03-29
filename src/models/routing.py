"""RFP Routing models — classification, pack selection, and routing report.

The routing architecture classifies each RFP, selects the appropriate
context packs (jurisdiction, domain, client-type), and merges them
into the proposal strategy context.

RFP → Classifier → Pack Selection → Proposal Strategy → Source Book → Engine 2
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import DeckForgeBaseModel


# ──────────────────────────────────────────────────────────────
# RFP Classification
# ──────────────────────────────────────────────────────────────


class RFPClassification(DeckForgeBaseModel):
    """Output of the RFP classifier. Determines pack selection."""

    # Primary classification
    jurisdiction: str = ""  # e.g. "saudi_arabia", "qatar", "uae", "unknown"
    sector: Literal[
        "public_sector", "private_sector", "semi_government", "unknown",
    ] = "unknown"
    client_type: str = ""  # e.g. "ministry", "authority", "private_enterprise"
    domain: str = ""  # e.g. "investment_promotion", "digital_transformation"
    subdomain: str = ""  # e.g. "export_support", "smart_government"
    regulatory_frame: str = ""  # e.g. "vision_2030", "nds_2030", "none_identified"
    evaluator_pattern: str = ""  # e.g. "technical_financial_split", "quality_cost_based"
    proof_types_needed: list[str] = Field(default_factory=list)  # e.g. ["case_studies", "team_cvs"]
    language: str = "ar"  # primary RFP language
    confidence: float = 0.0  # 0.0-1.0

    # Alternate classifications when confidence is low
    alternate_classifications: list[dict] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Pack Schema
# ──────────────────────────────────────────────────────────────


class RegulatoryReference(DeckForgeBaseModel):
    """A single regulatory body or framework reference."""

    name: str  # e.g. "DGA", "NDMO"
    full_name: str = ""  # e.g. "Digital Government Authority"
    relevance: str = ""  # When/why to reference this
    url: str = ""


class CompliancePattern(DeckForgeBaseModel):
    """A compliance pattern typical for this jurisdiction/sector."""

    pattern_name: str  # e.g. "Saudization requirements"
    description: str = ""
    typical_requirements: list[str] = Field(default_factory=list)
    evidence_needed: list[str] = Field(default_factory=list)


class EvaluatorInsight(DeckForgeBaseModel):
    """An evaluator behavior pattern for this jurisdiction/sector."""

    insight: str  # e.g. "Saudi public sector evaluators prioritize local content"
    implication: str = ""  # What this means for the proposal
    recommended_action: str = ""  # What to do about it


class MethodologyPattern(DeckForgeBaseModel):
    """A methodology pattern relevant to this domain."""

    framework: str  # e.g. "TOGAF", "ITIL"
    when_to_use: str = ""
    typical_activities: list[str] = Field(default_factory=list)


class BenchmarkReference(DeckForgeBaseModel):
    """An international benchmark relevant to this domain."""

    organization: str  # e.g. "KOTRA", "Enterprise Singapore"
    country: str = ""
    relevance: str = ""
    key_metrics: list[str] = Field(default_factory=list)


class ContextPack(DeckForgeBaseModel):
    """A structured context pack providing jurisdiction/domain/client intelligence.

    Packs are stored as JSON files and loaded at runtime based on
    RFP classification. Adding a new pack requires only adding a new
    JSON file — no code changes.
    """

    # Identity
    pack_id: str  # e.g. "saudi_public_sector", "digital_transformation"
    pack_type: Literal[
        "jurisdiction", "domain", "client_type", "generic_fallback",
    ] = "jurisdiction"
    pack_name: str = ""
    version: str = "1.0"

    # Content
    regulatory_references: list[RegulatoryReference] = Field(default_factory=list)
    compliance_patterns: list[CompliancePattern] = Field(default_factory=list)
    evaluator_insights: list[EvaluatorInsight] = Field(default_factory=list)
    methodology_patterns: list[MethodologyPattern] = Field(default_factory=list)
    benchmark_references: list[BenchmarkReference] = Field(default_factory=list)

    # Research guidance
    recommended_search_queries: list[str] = Field(default_factory=list)
    recommended_s2_queries: list[str] = Field(default_factory=list)

    # Forbidden assumptions — things NOT to assume for this context
    forbidden_assumptions: list[str] = Field(default_factory=list)

    # Classification keywords for routing (B.2: pack-driven classifier)
    classification_keywords: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict,
    )

    # Localization
    local_terminology: dict[str, str] = Field(default_factory=dict)
    # e.g. {"procurement": "مشتريات", "evaluation committee": "لجنة التقييم"}


# ──────────────────────────────────────────────────────────────
# Routing Report
# ──────────────────────────────────────────────────────────────


class RoutingReport(DeckForgeBaseModel):
    """Persisted routing report showing pack selection and confidence."""

    classification: RFPClassification = Field(default_factory=RFPClassification)

    # Selected packs
    selected_packs: list[str] = Field(default_factory=list)  # pack_id list
    fallback_packs_used: list[str] = Field(default_factory=list)

    # Merge result
    merged_regulatory_refs: int = 0
    merged_compliance_patterns: int = 0
    merged_evaluator_insights: int = 0
    merged_methodology_patterns: int = 0
    merged_benchmark_refs: int = 0
    merged_search_queries: int = 0

    # Warnings
    warnings: list[str] = Field(default_factory=list)

    # Confidence
    routing_confidence: float = 0.0  # overall confidence in pack selection
