"""External evidence models for the Proposal Source Book pipeline.

Produced by the External Research Agent from Semantic Scholar + Perplexity.
"""

from typing import Literal

from pydantic import Field

from .common import DeckForgeBaseModel


class ExternalSource(DeckForgeBaseModel):
    """A single piece of external evidence (paper, report, benchmark)."""

    source_id: str  # EXT-001, EXT-002, ...
    title: str
    source_type: Literal[
        "academic_paper",
        "industry_report",
        "benchmark",
        "case_study",
        "framework",
    ]
    year: int = 0
    url: str = ""
    abstract: str = ""  # max ~200 words
    relevance_score: float = 0.0  # 0.0-1.0
    relevance_reason: str = ""
    key_findings: list[str] = Field(default_factory=list)  # 3-5 bullet points


class ExternalEvidencePack(DeckForgeBaseModel):
    """Container for all external evidence gathered by the External Research Agent."""

    sources: list[ExternalSource] = Field(default_factory=list)
    search_queries_used: list[str] = Field(default_factory=list)
    coverage_assessment: str = ""  # summary of what evidence was/wasn't found
