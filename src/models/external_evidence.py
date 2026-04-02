"""External evidence models for the Proposal Source Book pipeline.

Produced by the External Research Agent from Semantic Scholar + Perplexity.
"""

from typing import Literal

from pydantic import Field, field_validator

from .common import DeckForgeBaseModel


SupportsCategoryType = Literal[
    "methodology", "market_context", "benchmark", "teaming",
    "governance", "timeline", "service_design", "general",
]


class ExternalSource(DeckForgeBaseModel):
    """A single piece of external evidence (paper, report, benchmark).

    Rich enough that a human consultant can use it directly to write
    proposal sections, and another AI agent can consume it downstream.
    """

    source_id: str  # EXT-001, EXT-002, ...
    provider: Literal["semantic_scholar", "perplexity", "manual"] = "manual"
    title: str
    authors: list[str] = Field(default_factory=list)
    source_type: Literal[
        "academic_paper",
        "industry_report",
        "benchmark",
        "case_study",
        "framework",
        "web_analysis",
    ]
    year: int = 0
    url: str = ""
    abstract: str = ""  # max ~200 words
    query_used: str = ""  # the search query that found this source
    relevance_score: float = 0.0  # 0.0-1.0
    relevance_reason: str = ""  # why this source was selected
    mapped_rfp_theme: str = ""  # which RFP scope area this supports
    key_findings: list[str] = Field(default_factory=list)  # 3-5 bullet points
    raw_excerpt: str = ""  # verbatim excerpt or distilled finding
    how_to_use_in_proposal: str = ""  # actionable guidance for proposal writer
    supports_category: list[SupportsCategoryType] = Field(default_factory=list)

    citation_count: int | None = None  # for S2 papers
    selection_method: str = ""  # "search_hit", "recommendation", "perplexity_synthesis"
    evidence_tier: Literal["primary", "secondary", "analogical"] = "analogical"
    evidence_class: Literal[
        "international_benchmark", "local_public", "evidence_gap",
    ] = "international_benchmark"

    @field_validator("supports_category", mode="before")
    @classmethod
    def _coerce_supports_category(cls, v: list) -> list:
        """Coerce unknown LLM-generated category values to 'general'."""
        allowed = {"methodology", "market_context", "benchmark", "teaming",
                   "governance", "timeline", "service_design", "general"}
        return [cat if cat in allowed else "general" for cat in (v or [])]


class ExternalEvidencePack(DeckForgeBaseModel):
    """Container for all external evidence gathered by the External Research Agent."""

    sources: list[ExternalSource] = Field(default_factory=list)
    search_queries_used: list[str] = Field(default_factory=list)
    # Per-query service mapping: query text → list of services it was sent to
    # e.g. {"query1": ["perplexity"], "query2": ["semantic_scholar"]}
    query_service_map: dict[str, list[str]] = Field(default_factory=dict)
    coverage_assessment: str = ""  # summary of what evidence was/wasn't found
