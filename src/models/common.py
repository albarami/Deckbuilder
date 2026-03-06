"""Common types shared across the DeckForge pipeline."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class DeckForgeBaseModel(BaseModel):
    """
    Strict base model for all DeckForge data structures.
    - extra="forbid": rejects unexpected fields (catches schema drift)
    - validate_assignment=True: validates on field assignment, not just init
    - use_enum_values=True: serializes enums as their string values
    """
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=True,
    )


class BilingualText(DeckForgeBaseModel):
    """Text field supporting English and Arabic."""
    en: str
    ar: str | None = None


class DateRange(DeckForgeBaseModel):
    """Flexible date range — supports YYYY-MM-DD, YYYY-MM, or YYYY."""
    start: str | None = None  # YYYY-MM-DD, YYYY-MM, or YYYY
    end: str | None = None


class ChangeLogEntry(DeckForgeBaseModel):
    """Log entry for tracking modifications to any object."""
    agent: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    description: str
