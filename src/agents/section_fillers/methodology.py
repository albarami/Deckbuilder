"""Methodology Filler — generates section_03 variable slides.

The HIGHEST-VALUE filler.  Uses the MethodologyBlueprint (phases, layouts)
to generate content for methodology_overview, methodology_focused, and
methodology_detail slides.

**Model:** Opus 4.6
**Layouts:** methodology_overview_4, methodology_focused_4, methodology_detail
  (or 3-phase variants)
**External enrichment:** Semantic Scholar for framework references,
  Perplexity for recent best practices (both degrade gracefully)

G2 schema: MethodologyOutput with typed PhaseContent, Bullets_3_5,
Bullets_2_4.  No free-form text.  All bullet items validated at schema
level (25-word max, no essay transitions, count-constrained).

Implements the approved 3/4/5-phase overflow rule:
- 3 grid phases + no overflow → valid 3-phase
- 4 grid phases + no overflow → valid 4-phase
- 4 grid phases + overflow (phase_number=5) → valid 5-phase

Unit-tested with mocked LLM.  Integration with live LLM is production-only.
"""

from __future__ import annotations

import json
import logging

from src.models.proposal_manifest import ManifestEntry
from src.services.llm import call_llm

from .base import BaseSectionFiller, SectionFillerInput, make_variable_entry
from .g2_schemas import (
    MethodologyDetailSlide,
    MethodologyFocusedSlide,
    MethodologyOutput,
    MethodologyOverviewSlide,
)

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"


# ── Placeholder index maps ───────────────────────────────────────────
# These map logical content roles to physical placeholder indices in
# the template's methodology layouts, derived from catalog_lock.

# methodology_overview_4: 13 BODY placeholders
OVERVIEW_4_MAP = {
    "phase_1_title": 41,
    "phase_1_content": 23,
    "phase_2_title": 33,
    "phase_2_content": 35,
    "phase_3_title": 37,
    "phase_3_content": 39,
    "phase_4_title": 42,
    "phase_4_content": 43,
    "subtitle": 13,
    "extra_1": 44,
    "extra_2": 45,
    "extra_3": 46,
    "extra_4": 47,
}

# methodology_overview_3: 10 BODY placeholders
OVERVIEW_3_MAP = {
    "phase_1_title": 41,
    "phase_1_content": 23,
    "phase_2_title": 33,
    "phase_2_content": 35,
    "phase_3_title": 42,
    "phase_3_content": 43,
    "subtitle": 13,
    "extra_1": 44,
    "extra_2": 45,
    "extra_3": 47,
}

# methodology_focused_4: TITLE at 0, 13 BODY placeholders
FOCUSED_4_MAP = {
    "title": 0,
    "phase_1_title": 41,
    "phase_1_content": 23,
    "phase_2_title": 33,
    "phase_2_content": 35,
    "phase_3_title": 37,
    "phase_3_content": 39,
    "phase_4_title": 42,
    "phase_4_content": 43,
    "subtitle": 13,
    "extra_1": 44,
    "extra_2": 45,
    "extra_3": 46,
    "extra_4": 47,
}

# methodology_focused_3: TITLE at 0, 10 BODY placeholders
FOCUSED_3_MAP = {
    "title": 0,
    "phase_1_title": 41,
    "phase_1_content": 23,
    "phase_2_title": 33,
    "phase_2_content": 35,
    "phase_3_title": 42,
    "phase_3_content": 43,
    "subtitle": 13,
    "extra_1": 44,
    "extra_2": 45,
    "extra_3": 47,
}

# methodology_detail: TITLE at 0, 3 distinct BODY placeholders (42, 43, 44)
DETAIL_MAP = {
    "title": 0,
    "activities": 42,
    "deliverables": 43,
    "frameworks": 44,
}


# ── System prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior management consultant writing the "Methodology" section \
of a proposal. This is the MOST IMPORTANT section — it shows the client \
HOW you will deliver the work.

You are writing content for {phase_count} methodology phases.

Phase structure (from the assembly plan):
{phase_structure}

CRITICAL FORMAT RULES — structured data, NOT paragraphs:
- phase_title: max 5 words, e.g., "Discovery & Assessment"
- phase_activities: 3-5 bullet items, each max 25 words
- deliverables: 3-5 bullet items, each max 25 words
- frameworks: 2-4 bullet items, each max 25 words
- NEVER start a bullet with "Furthermore", "Moreover", "In addition", \
"Additionally", "Consequently", "Nevertheless"
- NEVER write continuous prose paragraphs — every field is a bullet list
- Be SPECIFIC to this engagement, not generic methodology boilerplate
- Reference recognized frameworks where relevant (TOGAF, ITIL, PMBOK, \
COBIT, Agile, Lean Six Sigma, etc.)
- Do NOT use placeholder text or [brackets]
- Do NOT invent client names or metrics not in the evidence

{enrichment_context}

Output one overview with {grid_phase_count} phases in the grid, \
{focused_count} focused slides, {detail_count} detail slides\
{overflow_instruction}.

Output language: {output_language}
"""


# ── Enrichment helpers ────────────────────────────────────────────────


def _get_scholar_context(filler_input: SectionFillerInput) -> str:
    """Optionally enrich with Semantic Scholar.  Degrades gracefully."""
    try:
        from src.config.settings import get_settings
        from src.services.semantic_scholar import search_papers

        settings = get_settings()
        api_key = settings.semantic_scholar_api_key
        if not api_key:
            return ""

        sector = ""
        if filler_input.rfp_context and filler_input.rfp_context.scope_items:
            items = filler_input.rfp_context.scope_items[:3]
            sector = " ".join(
                s.description.en or "" for s in items
            )[:100]

        query = f"methodology framework {sector} consulting"
        papers = search_papers(query, api_key=api_key, max_results=3)
        if papers:
            refs = "; ".join(
                f"{p.title} ({p.year}, citations={p.citation_count})"
                for p in papers
            )
            return f"\nAcademic references: {refs}"
    except Exception as exc:
        logger.debug("Semantic Scholar enrichment skipped: %s", exc)
    return ""


def _get_perplexity_context(filler_input: SectionFillerInput) -> str:
    """Optionally enrich with Perplexity.  Degrades gracefully."""
    try:
        from src.config.settings import get_settings
        from src.services.perplexity import search_web

        settings = get_settings()
        api_key = settings.perplexity_api_key.get_secret_value()
        if not api_key:
            return ""

        sector = ""
        if filler_input.rfp_context and filler_input.rfp_context.scope_items:
            sector = (
                filler_input.rfp_context.scope_items[0].description.en or ""
            )

        query = (
            f"Best practices for {sector[:80]} methodology "
            f"consulting engagement 2025"
        )
        result = search_web(query, api_key=api_key, system_context=(
            "Provide concise methodology best practices for a consulting "
            "engagement. Focus on frameworks, phases, and deliverables."
        ))
        if result and result.content:
            return f"\nIndustry best practices: {result.content[:2000]}"
    except Exception as exc:
        logger.debug("Perplexity enrichment skipped: %s", exc)
    return ""


# ── Injection data builders ───────────────────────────────────────────


def _join_bullets(bullet_list: object) -> str:
    """Join a typed bullet list's items with newline separators."""
    return "\n".join(bullet_list.items)  # type: ignore[union-attr]


def build_overview_injection(
    overview: MethodologyOverviewSlide,
    phase_count: int,
) -> dict[str, object]:
    """Build injection_data for methodology_overview layout.

    Maps G2 PhaseContent fields to placeholder indices via body_contents.
    """
    body_contents: dict[int, str] = {}
    phase_map = OVERVIEW_4_MAP if phase_count >= 4 else OVERVIEW_3_MAP

    if overview.subtitle:
        body_contents[phase_map["subtitle"]] = overview.subtitle

    for i, phase in enumerate(overview.phases[:phase_count]):
        title_key = f"phase_{i + 1}_title"
        content_key = f"phase_{i + 1}_content"
        if title_key in phase_map:
            body_contents[phase_map[title_key]] = phase.phase_title
        if content_key in phase_map:
            body_contents[phase_map[content_key]] = _join_bullets(
                phase.phase_activities,
            )

    # Cross-cutting themes → extra slots
    extras = ["extra_1", "extra_2", "extra_3", "extra_4"]
    for i, theme in enumerate(overview.cross_cutting_themes[:4]):
        if extras[i] in phase_map:
            body_contents[phase_map[extras[i]]] = theme

    return {"body_contents": body_contents}


def build_focused_injection(
    focused: MethodologyFocusedSlide,
    phase_count: int,
) -> dict[str, object]:
    """Build injection_data for methodology_focused layout."""
    body_contents: dict[int, str] = {}
    phase_map = FOCUSED_4_MAP if phase_count >= 4 else FOCUSED_3_MAP

    if focused.subtitle:
        body_contents[phase_map["subtitle"]] = focused.subtitle

    for i, phase in enumerate(focused.phases[:phase_count]):
        title_key = f"phase_{i + 1}_title"
        content_key = f"phase_{i + 1}_content"
        if title_key in phase_map:
            body_contents[phase_map[title_key]] = phase.phase_title
        if content_key in phase_map:
            body_contents[phase_map[content_key]] = _join_bullets(
                phase.phase_activities,
            )

    extras = ["extra_1", "extra_2", "extra_3", "extra_4"]
    for i, theme in enumerate(focused.cross_cutting_themes[:4]):
        if extras[i] in phase_map:
            body_contents[phase_map[extras[i]]] = theme

    return {"title": focused.title, "body_contents": body_contents}


def build_detail_injection(
    detail: MethodologyDetailSlide,
) -> dict[str, object]:
    """Build injection_data for methodology_detail layout.

    methodology_detail has 3 distinct BODY placeholders (42, 43, 44).
    Each gets dedicated content: activities, deliverables, frameworks.
    Uses inject_multi_body (body_contents dict).
    """
    body_contents: dict[int, str] = {
        DETAIL_MAP["activities"]: _join_bullets(detail.activities),
        DETAIL_MAP["deliverables"]: _join_bullets(detail.deliverables),
        DETAIL_MAP["frameworks"]: _join_bullets(detail.frameworks),
    }

    return {
        "title": detail.title,
        "body_contents": body_contents,
    }


# ── Filler ────────────────────────────────────────────────────────────


class MethodologyFiller(BaseSectionFiller):
    """Generates section_03 methodology slides.

    Uses G2 MethodologyOutput schema with typed bullet lists.
    Implements 3/4/5-phase overflow rule.
    """

    section_id = "section_03"
    model_name = MODEL

    async def _generate(
        self, filler_input: SectionFillerInput,
    ) -> list[ManifestEntry]:
        bp = filler_input.methodology_blueprint
        if bp is None:
            raise ValueError(
                "MethodologyFiller requires methodology_blueprint in input",
            )

        phase_count = bp.phase_count
        # Grid can hold max 4; phase 5 goes to overflow
        grid_phase_count = min(phase_count, 4)
        has_overflow = phase_count == 5

        phase_structure = "\n".join(
            f"Phase {p.phase_number}: {p.phase_name_en} "
            f"(activities: {', '.join(p.activities[:3])}, "
            f"deliverables: {', '.join(p.deliverables[:3])})"
            for p in bp.phases
        )

        enrichment = _get_scholar_context(filler_input)
        enrichment += _get_perplexity_context(filler_input)

        evidence_parts: list[str] = []
        if filler_input.source_pack:
            for doc in filler_input.source_pack.documents[:3]:
                evidence_parts.append(
                    f"Source [{doc.doc_id}]: {doc.content_text[:5000]}",
                )
        if filler_input.win_themes:
            evidence_parts.append(
                f"Win themes: {', '.join(filler_input.win_themes)}",
            )

        overflow_instruction = (
            ", and 1 phase_5_overflow detail slide for Phase 5"
            if has_overflow else ""
        )

        system = SYSTEM_PROMPT.format(
            phase_count=phase_count,
            grid_phase_count=grid_phase_count,
            focused_count=grid_phase_count,
            detail_count=grid_phase_count,
            phase_structure=phase_structure,
            enrichment_context=enrichment,
            overflow_instruction=overflow_instruction,
            output_language=filler_input.output_language,
        )

        user_msg = json.dumps({
            "phase_count": phase_count,
            "grid_phase_count": grid_phase_count,
            "has_overflow": has_overflow,
            "evidence": "\n\n".join(evidence_parts),
            "output_language": str(filler_input.output_language),
        })

        llm_response = await call_llm(
            model=self.model_name,
            system_prompt=system,
            user_message=user_msg,
            response_model=MethodologyOutput,
            temperature=0.3,
            max_tokens=8000,
        )

        output = llm_response.parsed
        entries: list[ManifestEntry] = []

        # Overview slide
        overview_layout = bp.phases[0].overview_layout if bp.phases else (
            "methodology_overview_4" if grid_phase_count >= 4
            else "methodology_overview_3"
        )
        entries.append(make_variable_entry(
            asset_id="methodology_overview",
            semantic_layout_id=overview_layout,
            section_id="section_03",
            injection_data=build_overview_injection(
                output.overview, grid_phase_count,
            ),
        ))

        # Per-phase focused slides (grid phases only, 1-4)
        for i, focused_slide in enumerate(output.focused_slides):
            if i >= len(bp.phases):
                break
            phase = bp.phases[i]

            for fl in phase.focused_layouts:
                entries.append(make_variable_entry(
                    asset_id=f"methodology_{phase.phase_id}_focused",
                    semantic_layout_id=fl,
                    section_id="section_03",
                    methodology_phase=phase.phase_id,
                    injection_data=build_focused_injection(
                        focused_slide, grid_phase_count,
                    ),
                ))

        # Per-phase detail slides (grid phases only, 1-4)
        for i, detail_slide in enumerate(output.detail_slides):
            if i >= len(bp.phases):
                break
            phase = bp.phases[i]

            for dl in phase.detail_layouts:
                entries.append(make_variable_entry(
                    asset_id=f"methodology_{phase.phase_id}_detail",
                    semantic_layout_id=dl,
                    section_id="section_03",
                    methodology_phase=phase.phase_id,
                    injection_data=build_detail_injection(detail_slide),
                ))

        # Phase 5 overflow detail slide
        if output.phase_5_overflow and has_overflow and len(bp.phases) >= 5:
            phase_5 = bp.phases[4]
            for dl in phase_5.detail_layouts:
                entries.append(make_variable_entry(
                    asset_id=f"methodology_{phase_5.phase_id}_detail",
                    semantic_layout_id=dl,
                    section_id="section_03",
                    methodology_phase=phase_5.phase_id,
                    injection_data=build_detail_injection(
                        output.phase_5_overflow,
                    ),
                ))

        return entries
