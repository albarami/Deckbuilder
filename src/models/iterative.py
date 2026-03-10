"""Iterative slide builder models — 5-turn draft/review/refine cycle."""

from pydantic import Field

from .common import DeckForgeBaseModel


class SlideText(DeckForgeBaseModel):
    """Single slide text from the Draft/Refine agents."""

    slide_number: int
    title: str  # Insight-led headline
    bullets: list[str] = Field(default_factory=list)  # 3-6 bullets
    speaker_notes: str = ""
    target_criterion: str = ""  # RFP criterion addressed
    evidence_level: str = ""  # "sourced" | "general" | "placeholder"
    layout_suggestion: str = ""  # LayoutType hint


class SlideCritique(DeckForgeBaseModel):
    """Per-slide critique from the Review agents."""

    slide_number: int
    score: int  # 1-5
    issues: list[str] = Field(default_factory=list)
    instructions: str = ""  # What to fix


class DeckDraft(DeckForgeBaseModel):
    """Output of Draft Agent (Turn 1) and Refine Agent (Turn 3)."""

    slides: list[SlideText] = Field(default_factory=list)
    turn_number: int = 1
    mode: str = "strict"  # "strict" | "general"


class DeckReview(DeckForgeBaseModel):
    """Output of Review Agent (Turn 2) and Final Review Agent (Turn 4)."""

    critiques: list[SlideCritique] = Field(default_factory=list)
    overall_score: int = 0  # 1-5
    coherence_issues: list[str] = Field(default_factory=list)
    turn_number: int = 2
