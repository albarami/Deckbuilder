"""Blueprint schema with ownership-aware section entries.

This module defines the template-locked blueprint used by the Structure Agent.
The Source Book Writer uses a separate SlideBlueprintEntry defined in
source_book.py (with slide_number, proof_points, etc.) for Section 6 content.
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .common import DeckForgeBaseModel

OwnershipType = Literal["house", "dynamic", "hybrid"]
HouseActionType = Literal["include_as_is", "select_from_pool", "skip"]


class SlideBlueprintEntry(DeckForgeBaseModel):
    """One template-mapped blueprint entry."""

    section_id: str
    section_name: str
    ownership: OwnershipType

    slide_title: str | None = None
    key_message: str | None = None
    bullet_points: list[str] | None = None
    evidence_ids: list[str] | None = None
    visual_guidance: str | None = None

    house_action: HouseActionType | None = None
    pool_selection_criteria: str | None = None

    @model_validator(mode="after")
    def validate_ownership_fields(self) -> SlideBlueprintEntry:
        """Enforce content split for house/dynamic/hybrid entries."""
        has_dynamic_payload = any(
            (
                self.slide_title,
                self.key_message,
                self.bullet_points,
                self.evidence_ids,
                self.visual_guidance,
            )
        )

        if self.ownership == "house":
            if has_dynamic_payload:
                raise ValueError("House entries cannot contain generated content fields.")
            if self.house_action is None:
                raise ValueError("House entries must set house_action.")

        if self.ownership == "dynamic":
            if not has_dynamic_payload:
                raise ValueError("Dynamic entries must include generated content fields.")
            if self.house_action is not None:
                raise ValueError("Dynamic entries cannot set house_action.")
            if self.pool_selection_criteria is not None:
                raise ValueError("Dynamic entries cannot set pool_selection_criteria.")

        if self.ownership == "hybrid":
            if self.house_action is None:
                raise ValueError("Hybrid entries must set house_action for template shell handling.")
            if self.bullet_points or self.evidence_ids or self.visual_guidance:
                raise ValueError(
                    "Hybrid entries may only parameterize title/key message; "
                    "they cannot include full generated content payload."
                )

        return self


class SlideBlueprint(DeckForgeBaseModel):
    """Ordered blueprint document."""

    entries: list[SlideBlueprintEntry]
