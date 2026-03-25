"""Slide models — used across Structure, Content, QA, and Design agents."""

from typing import Any, Literal

from pydantic import Field

from .common import ChangeLogEntry, DeckForgeBaseModel
from .enums import LayoutType, SensitivityTag


class ChartSpec(DeckForgeBaseModel):
    """
    Chart specification for DATA_CHART slides.
    Colors are NOT specified here — inherited from template theme.
    """
    type: Literal["bar", "line", "pie", "doughnut", "radar", "scatter"]
    title: str
    x_axis: dict | None = None  # {"label": str, "values": list}
    y_axis: dict | None = None  # {"label": str, "values": list}
    legend: bool = False
    note: str = ""  # e.g., "Colors inherited from template theme — do not specify"


class BodyContent(DeckForgeBaseModel):
    """Structured body content for a slide."""
    text_elements: list[str] = Field(default_factory=list)  # Bullet points / text blocks
    chart_data: dict | None = None  # Optional raw data for charts


class SlideObject(DeckForgeBaseModel):
    """
    Complete slide representation used throughout the pipeline.

    - Structure Agent: populates title, layout_type, report_section_ref, content_guidance, source_claims
    - Content Agent: populates body_content, speaker_notes, chart_spec, source_refs
    - QA Agent: validates all fields
    - Design Agent: renders to PPTX

    source_claims: claim IDs assigned by Structure Agent (from the report)
    source_refs: complete union of ALL claim IDs supporting body + notes (populated by Content Agent)
    No inline [Ref:] tags in body_content or speaker_notes — refs are structural metadata only.
    """
    slide_id: str  # S-NNN
    title: str  # Insight-led headline
    key_message: str = ""
    layout_type: LayoutType
    body_content: BodyContent | None = None
    chart_spec: ChartSpec | None = None
    source_claims: list[str] = Field(default_factory=list)  # CLM-NNNN — from Structure Agent
    source_refs: list[str] = Field(default_factory=list)  # CLM-NNNN — complete union from Content Agent
    report_section_ref: str = ""  # Section of approved report this derives from
    rfp_criterion_ref: str | None = None  # Evaluation criterion addressed
    speaker_notes: str = ""  # No Free Facts applies
    sensitivity_tags: list[SensitivityTag] = Field(default_factory=list)
    content_guidance: str = ""  # Structural only: claim IDs + layout instructions, no factual wording
    change_history: list[ChangeLogEntry] = Field(default_factory=list)
    manifest_asset_id: str | None = None  # Provenance: manifest entry asset_id this slide was built for


class SlideOutline(DeckForgeBaseModel):
    """Output of the Structure Agent — ordered list of slide outlines."""
    slides: list[SlideObject]
    slide_count: int = 0
    weight_allocation: dict[str, Any] = Field(default_factory=dict)


class WrittenSlides(DeckForgeBaseModel):
    """Output of the Content Agent — fully written slides."""
    slides: list[SlideObject]
    notes: str | None = None  # Issues found during writing
