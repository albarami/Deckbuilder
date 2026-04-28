"""Governance Filler — generates section_06 variable slides.

Section 06 ("Project Governance") defines the governance framework,
steering committee structure, escalation paths, and reporting cadence.

**Model:** Opus 4.7
**Budget:** 2 b_variable slides (fixed by G2 spec)
**Layouts:**
  - Slide 1: layout_heading_and_4_boxes_of_content (inject_multi_body)
  - Slide 2: layout_heading_and_two_content_with_tiltes (inject_multi_body)
**External enrichment:** None (governance is methodology-driven)

G2 schema: GovernanceOutput with GovernanceStructureSlide (3 tiers +
escalation), QAReportingSlide (reporting blocks + quality gates).
All bullet lists are typed (Bullets_2_4, Bullets_3_4, Bullets_2_3).
No free-form text.  No paragraphs.

Unit-tested with mocked LLM.  Integration with live LLM is production-only.
"""

from __future__ import annotations

import json
import logging

from src.models.proposal_manifest import ManifestEntry
from src.services.llm import call_llm

from .base import BaseSectionFiller, SectionFillerInput, make_variable_entry
from .g2_schemas import (
    EscalationBlock,
    GovernanceOutput,
    GovernanceStructureSlide,
    GovernanceTier,
    QAReportingSlide,
    QualityGate,
    ReportingBlock,
)

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-7"

# ── Placeholder index maps ───────────────────────────────────────────
# Derived from catalog_lock_en.json

# layout_heading_and_4_boxes_of_content: 5 placeholders
SLIDE_1_MAP = {
    "title": 0,    # TITLE
    "tier_1": 1,   # OBJECT
    "tier_2": 2,   # OBJECT
    "tier_3": 13,  # OBJECT
    "escalation": 14,  # OBJECT
}

# layout_heading_and_two_content_with_tiltes: 5 placeholders
SLIDE_2_MAP = {
    "title": 0,          # TITLE
    "left_subtitle": 1,  # BODY
    "left_content": 2,   # OBJECT
    "right_subtitle": 3,  # BODY
    "right_content": 4,   # OBJECT
}


# ── System prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior management consultant writing the "Project Governance" \
section of a proposal PRESENTATION.  This section defines HOW the project \
will be managed, governed, and quality-assured.

{governance_context}

You must produce EXACTLY 2 slides:

SLIDE 1 — Governance Structure (GovernanceStructureSlide):
- title: short headline, max 10 words
- tier_1: GovernanceTier with tier_name, members, cadence, 2-4 responsibility bullets
- tier_2: GovernanceTier (same structure)
- tier_3: GovernanceTier (same structure)
- escalation: EscalationBlock with 3-4 escalation trigger bullets

Each tier must have:
  tier_name (max 30 chars), members (max 60 chars), cadence (max 20 chars, REQUIRED),
  responsibilities (2-4 bullets, each max 25 words)

SLIDE 2 — QA & Reporting (QAReportingSlide):
- title: short headline, max 10 words
- left_subtitle: column label (max 30 chars)
- reporting_blocks: 2-4 blocks, each with cadence, report_name, audience, 2-3 bullets
- right_subtitle: column label (max 30 chars)
- quality_gates: 2-4 gates, each with gate_name, 2-3 criteria bullets, sign_off_authority

CRITICAL RULES:
- Every field is a TYPED bullet list — NOT prose paragraphs
- NEVER start a bullet with "Furthermore", "Moreover", "In addition"
- Define clear governance tiers: Steering Committee, Project Board, Working Teams
- Include specific reporting cadence (weekly, bi-weekly, monthly)
- Define escalation paths and decision-making authority
- Do NOT use placeholder text or [brackets]

Output language: {output_language}
"""


# ── Injection data builders ───────────────────────────────────────────


def _format_tier_block(tier: GovernanceTier) -> str:
    """Format a governance tier as structured text for OBJECT placeholder.

    Output:
        TIER_NAME | cadence
        members
        Responsibility 1
        Responsibility 2
    """
    header = f"{tier.tier_name} | {tier.cadence}"
    members = tier.members
    responsibilities = "\n".join(tier.responsibilities.items)
    return f"{header}\n{members}\n{responsibilities}"


def _format_escalation_block(esc: EscalationBlock) -> str:
    """Format escalation block as structured text for OBJECT placeholder."""
    header = esc.tier_name
    triggers = "\n".join(esc.triggers.items)
    return f"{header}\n{triggers}"


def _format_reporting_blocks(blocks: list[ReportingBlock]) -> str:
    """Format reporting blocks as structured text for OBJECT placeholder."""
    parts: list[str] = []
    for block in blocks:
        header = f"{block.report_name} | {block.cadence}"
        audience = f"Audience: {block.audience}"
        items = "\n".join(block.items.items)
        parts.append(f"{header}\n{audience}\n{items}")
    return "\n\n".join(parts)


def _format_quality_gates(gates: list[QualityGate]) -> str:
    """Format quality gates as structured text for OBJECT placeholder."""
    parts: list[str] = []
    for gate in gates:
        header = gate.gate_name
        criteria = "\n".join(gate.criteria.items)
        authority = f"Sign-off: {gate.sign_off_authority}"
        parts.append(f"{header}\n{criteria}\n{authority}")
    return "\n\n".join(parts)


def build_slide_1_injection(
    slide: GovernanceStructureSlide,
) -> dict[str, object]:
    """Build injection_data for layout_heading_and_4_boxes_of_content.

    Injector: inject_multi_body — title as string (renderer reads
    data.get("title", "")), tier blocks in body_contents.
    """
    body_contents: dict[int, str] = {
        SLIDE_1_MAP["tier_1"]: _format_tier_block(slide.tier_1),
        SLIDE_1_MAP["tier_2"]: _format_tier_block(slide.tier_2),
        SLIDE_1_MAP["tier_3"]: _format_tier_block(slide.tier_3),
        SLIDE_1_MAP["escalation"]: _format_escalation_block(slide.escalation),
    }
    return {
        "title": slide.title,
        "body_contents": body_contents,
    }


def build_slide_2_injection(slide: QAReportingSlide) -> dict[str, object]:
    """Build injection_data for layout_heading_and_two_content_with_tiltes.

    Injector: inject_multi_body — title as string (renderer reads
    data.get("title", "")), subtitles and blocks in body_contents.
    """
    body_contents: dict[int, str] = {
        SLIDE_2_MAP["left_subtitle"]: slide.left_subtitle,
        SLIDE_2_MAP["left_content"]: _format_reporting_blocks(
            slide.reporting_blocks,
        ),
        SLIDE_2_MAP["right_subtitle"]: slide.right_subtitle,
        SLIDE_2_MAP["right_content"]: _format_quality_gates(
            slide.quality_gates,
        ),
    }
    return {
        "title": slide.title,
        "body_contents": body_contents,
    }


# ── Filler ────────────────────────────────────────────────────────────


def _build_governance_context(filler_input: SectionFillerInput) -> str:
    """Build governance context from methodology blueprint."""
    parts: list[str] = []

    bp = filler_input.methodology_blueprint
    if bp:
        parts.append(f"Phase count: {bp.phase_count}")
        if bp.governance_touchpoints:
            for phase_id, tier in bp.governance_touchpoints.items():
                parts.append(
                    f"Governance touchpoint {phase_id}: {tier}",
                )
        for phase in bp.phases:
            if phase.governance_tier:
                parts.append(
                    f"Phase {phase.phase_number} ({phase.phase_name_en}): "
                    f"tier={phase.governance_tier}",
                )

    if filler_input.source_pack:
        for doc in filler_input.source_pack.documents[:2]:
            parts.append(
                f"Source [{doc.doc_id}]: {doc.content_text[:5000]}",
            )

    if filler_input.win_themes:
        parts.append(f"Win themes: {', '.join(filler_input.win_themes)}")

    return "\n".join(parts)


class GovernanceFiller(BaseSectionFiller):
    """Generates section_06 governance slides.

    Uses G2 GovernanceOutput schema with typed bullet lists.
    All content is structured — no free-form text.
    """

    section_id = "section_06"
    model_name = MODEL

    async def _generate(
        self, filler_input: SectionFillerInput,
    ) -> list[ManifestEntry]:
        governance_ctx = _build_governance_context(filler_input)

        system = SYSTEM_PROMPT.format(
            governance_context=governance_ctx,
            output_language=filler_input.output_language,
        )

        user_msg = json.dumps({
            "slide_count": 2,
            "output_language": str(filler_input.output_language),
        })

        # Append blueprint guidance from Slide Architect when available
        blueprint_guidance = self._format_blueprint_guidance(filler_input)
        if blueprint_guidance:
            user_msg += "\n\n" + blueprint_guidance

        llm_response = await call_llm(
            model=self.model_name,
            system_prompt=system,
            user_message=user_msg,
            response_model=GovernanceOutput,
            temperature=0.2,
            max_tokens=5000,
        )

        output = llm_response.parsed
        entries: list[ManifestEntry] = []

        # Slide 1 — Governance Structure (4-box)
        entries.append(make_variable_entry(
            asset_id="governance_01",
            semantic_layout_id="layout_heading_and_4_boxes_of_content",
            section_id="section_06",
            injection_data=build_slide_1_injection(output.slide_1_structure),
        ))

        # Slide 2 — QA & Reporting (two-column)
        entries.append(make_variable_entry(
            asset_id="governance_02",
            semantic_layout_id="layout_heading_and_two_content_with_tiltes",
            section_id="section_06",
            injection_data=build_slide_2_injection(
                output.slide_2_qa_reporting,
            ),
        ))

        return entries
