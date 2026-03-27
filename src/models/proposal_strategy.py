"""Proposal Strategy models — output of the Proposal Strategist agent.

The ProposalStrategy captures the strategic reasoning layer between
evidence curation and content generation: what evaluators care about,
how SG differentiates, and what evidence supports each win theme.
"""

from typing import Literal

from pydantic import Field

from .common import DeckForgeBaseModel


class EvaluatorPriority(DeckForgeBaseModel):
    """A single evaluator priority inferred from the RFP."""

    priority: str  # what the evaluator cares about
    weight_estimate: float = 0.0  # 0.0-1.0
    evidence_available: Literal["strong", "moderate", "weak", "none"] = "none"
    strategy_note: str = ""  # how to address this priority


class WinTheme(DeckForgeBaseModel):
    """A single win theme with evidence backing."""

    theme: str  # the theme statement
    supporting_evidence: list[str] = Field(default_factory=list)  # CLM-xxxx or EXT-xxx IDs
    differentiator_strength: Literal["unique", "strong", "moderate", "weak"] = "moderate"
    strategy_note: str = ""  # how to deploy this theme in the proposal


class ProposalStrategy(DeckForgeBaseModel):
    """Full proposal strategy — output of the Proposal Strategist agent.

    Bridges evidence curation and content generation by providing
    strategic context: what to emphasize, what to prove, and how
    to position SG against competitors.
    """

    rfp_interpretation: str = ""  # 2-3 paragraphs
    unstated_evaluator_priorities: list[EvaluatorPriority] = Field(default_factory=list)
    scoring_logic_assessment: str = ""
    compliance_requirements: list[str] = Field(default_factory=list)
    win_themes: list[WinTheme] = Field(default_factory=list)  # 3-5, each with evidence
    proposal_thesis: str = ""  # 1 paragraph — the core argument
    risk_if_unchanged: str = ""  # client's risk of not acting
    competitive_positioning: str = ""  # how SG differentiates
    evidence_gaps: list[str] = Field(default_factory=list)  # what we can't prove
    recommended_methodology_approach: str = ""  # high-level, informs assembly plan
