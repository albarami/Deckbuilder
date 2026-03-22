"""Timeline Filler — generates section_04 variable slides.

Section 04 ("Timeline & Deliverables") presents the project timeline,
milestones, deliverables schedule, and expected outcomes.

**Model:** Opus 4.6
**Budget:** 2 b_variable slides (fixed by G2 spec)
**Layouts:**
  - Slide 1: layout_heading_and_4_boxes_of_content (inject_multi_body)
  - Slide 2: layout_heading_and_two_content_with_tiltes (inject_multi_body)
**External enrichment:** None (timeline is fully evidence-driven)

G2 schema: TimelineOutput with TimelineOverviewSlide (4 TimelinePhaseBlock),
MilestonesSlide (2 MilestoneColumn).  All bullet lists are typed
(Bullets_2_3, BulletList).  No free-form text.  No paragraphs.

Timeline content is grounded in the MethodologyBlueprint's phase
structure and deliverables linkage.

Unit-tested with mocked LLM.  Integration with live LLM is production-only.
"""

from __future__ import annotations

import json
import logging

from src.models.proposal_manifest import ManifestEntry
from src.services.llm import call_llm

from .base import BaseSectionFiller, SectionFillerInput, make_variable_entry
from .g2_schemas import (
    MilestonesSlide,
    TimelineOutput,
    TimelineOverviewSlide,
    TimelinePhaseBlock,
)

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"

# ── Placeholder index maps ───────────────────────────────────────────
# Derived from catalog_lock_en.json

# layout_heading_and_4_boxes_of_content: 5 placeholders
SLIDE_1_MAP = {
    "title": 0,    # TITLE
    "box_1": 1,    # OBJECT
    "box_2": 2,    # OBJECT
    "box_3": 13,   # OBJECT
    "box_4": 14,   # OBJECT
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
You are a senior management consultant writing the "Timeline & Deliverables" \
section of a proposal PRESENTATION.  This section shows the client WHEN \
things happen and WHAT they receive at each milestone.

{methodology_context}

You must produce EXACTLY 2 slides:

SLIDE 1 — Timeline Overview (TimelineOverviewSlide):
- title: short headline, max 10 words
- box_1 through box_4: each a TimelinePhaseBlock with:
  - phase_number (1-5), phase_name (max 40 chars), week_range (max 20 chars)
  - key_activities: 2-3 bullet items, each max 25 words
- All 4 boxes must have DISTINCT phase numbers

SLIDE 2 — Milestones & Deliverables (MilestonesSlide):
- title: short headline, max 10 words
- left_column: subtitle (max 30 chars) + 2-6 deliverable bullets
- right_column: subtitle (max 30 chars) + 2-6 deliverable bullets

CRITICAL RULES:
- Every field is a TYPED bullet list — NOT prose paragraphs
- NEVER start a bullet with "Furthermore", "Moreover", "In addition"
- Include concrete durations (weeks/months), not vague timeframes
- Reference specific phases from the methodology section
- Include decision gates and milestone markers
- Do NOT use placeholder text or [brackets]
- Do NOT invent dates not derivable from the evidence

Output language: {output_language}
"""


# ── Injection data builders ───────────────────────────────────────────


def _format_timeline_block(block: TimelinePhaseBlock) -> str:
    """Format a timeline phase block as structured text for OBJECT placeholder.

    Output:
        Phase Name | Weeks X-Y
        Activity 1
        Activity 2
    """
    header = f"{block.phase_name} | {block.week_range}"
    activities = "\n".join(block.key_activities.items)
    return f"{header}\n{activities}"


def build_slide_1_injection(
    slide: TimelineOverviewSlide,
) -> dict[str, object]:
    """Build injection_data for layout_heading_and_4_boxes_of_content.

    Injector: inject_multi_body — title as string (renderer reads
    data.get("title", "")), timeline blocks in body_contents.
    """
    body_contents: dict[int, str] = {
        SLIDE_1_MAP["box_1"]: _format_timeline_block(slide.box_1),
        SLIDE_1_MAP["box_2"]: _format_timeline_block(slide.box_2),
        SLIDE_1_MAP["box_3"]: _format_timeline_block(slide.box_3),
        SLIDE_1_MAP["box_4"]: _format_timeline_block(slide.box_4),
    }
    return {
        "title": slide.title,
        "body_contents": body_contents,
    }


def _join_bullets(bullet_list: object) -> str:
    """Join a typed bullet list's items with newline separators."""
    return "\n".join(bullet_list.items)  # type: ignore[union-attr]


def build_slide_2_injection(slide: MilestonesSlide) -> dict[str, object]:
    """Build injection_data for layout_heading_and_two_content_with_tiltes.

    Injector: inject_multi_body — title as string (renderer reads
    data.get("title", "")), subtitles and deliverables in body_contents.
    """
    body_contents: dict[int, str] = {
        SLIDE_2_MAP["left_subtitle"]: slide.left_column.subtitle,
        SLIDE_2_MAP["left_content"]: _join_bullets(
            slide.left_column.deliverables,
        ),
        SLIDE_2_MAP["right_subtitle"]: slide.right_column.subtitle,
        SLIDE_2_MAP["right_content"]: _join_bullets(
            slide.right_column.deliverables,
        ),
    }
    return {
        "title": slide.title,
        "body_contents": body_contents,
    }


# ── Filler ────────────────────────────────────────────────────────────


def _build_methodology_context(filler_input: SectionFillerInput) -> str:
    """Build methodology context for timeline grounding."""
    parts: list[str] = []

    bp = filler_input.methodology_blueprint
    if bp:
        parts.append(f"Timeline span: {bp.timeline_span or 'TBD'}")
        parts.append(f"Phase count: {bp.phase_count}")
        for phase in bp.phases:
            deliverables = ", ".join(phase.deliverables[:5]) or "TBD"
            parts.append(
                f"Phase {phase.phase_number} ({phase.phase_name_en}): "
                f"activities={', '.join(phase.activities[:3])}, "
                f"deliverables={deliverables}",
            )
        if bp.deliverables_linkage:
            for phase_id, deliverable_ids in bp.deliverables_linkage.items():
                parts.append(
                    f"Linkage {phase_id}: {', '.join(deliverable_ids)}",
                )

    if filler_input.source_pack:
        for doc in filler_input.source_pack.documents[:2]:
            parts.append(
                f"Source [{doc.doc_id}]: {doc.content_text[:5000]}",
            )

    if filler_input.win_themes:
        parts.append(f"Win themes: {', '.join(filler_input.win_themes)}")

    return "\n".join(parts)


class TimelineFiller(BaseSectionFiller):
    """Generates section_04 timeline slides.

    Uses G2 TimelineOutput schema with typed bullet lists.
    All content is structured — no free-form text.
    """

    section_id = "section_04"
    model_name = MODEL

    async def _generate(
        self, filler_input: SectionFillerInput,
    ) -> list[ManifestEntry]:
        methodology_ctx = _build_methodology_context(filler_input)

        system = SYSTEM_PROMPT.format(
            methodology_context=methodology_ctx,
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
            response_model=TimelineOutput,
            temperature=0.2,
            max_tokens=4000,
        )

        output = llm_response.parsed
        entries: list[ManifestEntry] = []

        # Slide 1 — Timeline Overview (4-box)
        entries.append(make_variable_entry(
            asset_id="timeline_01",
            semantic_layout_id="layout_heading_and_4_boxes_of_content",
            section_id="section_04",
            injection_data=build_slide_1_injection(output.slide_1_overview),
        ))

        # Slide 2 — Milestones & Deliverables (two-column)
        entries.append(make_variable_entry(
            asset_id="timeline_02",
            semantic_layout_id="layout_heading_and_two_content_with_tiltes",
            section_id="section_04",
            injection_data=build_slide_2_injection(output.slide_2_milestones),
        ))

        return entries
