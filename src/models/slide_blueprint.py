"""Slide Blueprint — structured per-slide content specification.

The Slide Blueprint is produced by the Slide Architect agent after Gate 3
approval. It maps Source Book content to individual slide specifications
with explicit bullet logic, evidence references, and layout guidance.

The SlideBlueprintEntry model lives in source_book.py (Section 6 of the
Source Book). This module defines the SlideBlueprint container that wraps
a list of entries with aggregate metadata.
"""

from pydantic import Field

from .common import DeckForgeBaseModel
from .source_book import SlideBlueprintEntry


class SlideBlueprint(DeckForgeBaseModel):
    """Complete slide blueprint — output of the Slide Architect agent.

    Contains per-slide content specifications (SlideBlueprintEntry) plus
    aggregate metadata for quality validation.

    Fields:
        blueprint_version: Schema version for forward compatibility.
        total_variable_slides: Number of b_variable slides in the blueprint.
        evidence_coverage: Fraction (0.0-1.0) of slides with evidence backing.
        entries: Per-slide content specifications.
    """

    blueprint_version: str = "1.0"
    total_variable_slides: int = 0
    evidence_coverage: float = 0.0
    entries: list[SlideBlueprintEntry] = Field(default_factory=list)
