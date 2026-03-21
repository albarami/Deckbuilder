"""Understanding Filler — generates section_01 variable slides.

Section 01 ("Understanding") demonstrates deep comprehension of the
client's challenge, strategic context, and desired outcomes.

**Model:** Opus 4.6
**Budget:** 3 b_variable slides (fixed by G2 spec)
**Layouts:**
  - Slide 1: layout_heading_and_two_content_with_tiltes (inject_multi_body)
  - Slide 2: layout_heading_and_4_boxes_of_content (inject_multi_body)
  - Slide 3: layout_heading_description_and_content_box (inject_title_body)
**External enrichment:** Perplexity for industry context (graceful degradation)

G2 schema: UnderstandingOutput with TwoColumnSlide, FourBoxSlide,
HeadingDescriptionContentSlide.  All bullet lists are typed (Bullets_3_4,
Bullets_2_3, Bullets_4_6).  No free-form text.  No paragraphs.

Unit-tested with mocked LLM.  Integration with live LLM is production-only.
"""

from __future__ import annotations

import json
import logging

from src.models.proposal_manifest import ManifestEntry
from src.services.llm import call_llm

from .base import BaseSectionFiller, SectionFillerInput, make_variable_entry
from .g2_schemas import (
    FourBoxSlide,
    HeadingDescriptionContentSlide,
    TwoColumnSlide,
    UnderstandingOutput,
)

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"

# ── Placeholder index maps ───────────────────────────────────────────
# Derived from catalog_lock_en.json

# layout_heading_and_two_content_with_tiltes: 5 placeholders
SLIDE_1_MAP = {
    "title": 0,          # TITLE
    "left_subtitle": 1,  # BODY
    "left_evidence": 2,  # OBJECT
    "right_subtitle": 3,  # BODY
    "right_evidence": 4,  # OBJECT
}

# layout_heading_and_4_boxes_of_content: 5 placeholders
SLIDE_2_MAP = {
    "title": 0,    # TITLE
    "box_1": 1,    # OBJECT
    "box_2": 2,    # OBJECT
    "box_3": 13,   # OBJECT
    "box_4": 14,   # OBJECT
}

# layout_heading_description_and_content_box: 3 placeholders
SLIDE_3_MAP = {
    "title": 0,         # TITLE
    "description": 13,  # BODY
    "outcomes": 1,      # OBJECT
}


# ── System prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior management consultant writing the "Understanding" section \
of a proposal PRESENTATION.  This section demonstrates DEEP comprehension \
of the client's challenge — not a restatement of the RFP.

You must produce EXACTLY 3 slides with DISTINCT formats:

SLIDE 1 — Strategic Context (TwoColumnSlide):
- title: short headline, max 10 words
- left_subtitle: column label, max 40 chars (e.g., "Regulatory & Policy Drivers")
- left_evidence: 3-4 bullet items, each max 25 words
- right_subtitle: column label, max 40 chars (e.g., "Operational Challenges")
- right_evidence: 3-4 bullet items, each max 25 words

SLIDE 2 — Core Challenges (FourBoxSlide):
- title: short headline, max 10 words
- box_1 through box_4: each 2-3 bullet items, each max 25 words

SLIDE 3 — Success Definition (HeadingDescriptionContentSlide):
- title: short headline, max 10 words
- description: 1-2 sentences framing text, max 30 words
- outcomes: 4-6 measurable outcome bullets, each max 25 words

CRITICAL RULES:
- Every field is a TYPED bullet list — NOT prose paragraphs
- Each bullet: one concrete, evidence-backed statement
- NEVER start a bullet with "Furthermore", "Moreover", "In addition", \
"Additionally", "Consequently", "Nevertheless"
- Include specific metrics, benchmarks, or evidence references
- Be SPECIFIC to this client and RFP, not generic
- Do NOT use placeholder text or [brackets]
- Do NOT invent client names or metrics not in the evidence

Output language: {output_language}
"""


# ── Injection data builders ───────────────────────────────────────────


def _join_bullets(bullet_list: object) -> str:
    """Join a typed bullet list's items with newline separators."""
    return "\n".join(bullet_list.items)  # type: ignore[union-attr]


def build_slide_1_injection(slide: TwoColumnSlide) -> dict[str, object]:
    """Build injection_data for layout_heading_and_two_content_with_tiltes.

    Injector: inject_multi_body — title as string (renderer reads
    data.get("title", "")), subtitles and evidence in body_contents.
    """
    body_contents: dict[int, str] = {
        SLIDE_1_MAP["left_subtitle"]: slide.left_subtitle,
        SLIDE_1_MAP["left_evidence"]: _join_bullets(slide.left_evidence),
        SLIDE_1_MAP["right_subtitle"]: slide.right_subtitle,
        SLIDE_1_MAP["right_evidence"]: _join_bullets(slide.right_evidence),
    }
    return {
        "title": slide.title,
        "body_contents": body_contents,
    }


def build_slide_2_injection(slide: FourBoxSlide) -> dict[str, object]:
    """Build injection_data for layout_heading_and_4_boxes_of_content.

    Injector: inject_multi_body — title as string (renderer reads
    data.get("title", "")), boxes in body_contents (OBJECT placeholders).
    """
    body_contents: dict[int, str] = {
        SLIDE_2_MAP["box_1"]: _join_bullets(slide.box_1),
        SLIDE_2_MAP["box_2"]: _join_bullets(slide.box_2),
        SLIDE_2_MAP["box_3"]: _join_bullets(slide.box_3),
        SLIDE_2_MAP["box_4"]: _join_bullets(slide.box_4),
    }
    return {
        "title": slide.title,
        "body_contents": body_contents,
    }


def build_slide_3_injection(
    slide: HeadingDescriptionContentSlide,
) -> dict[str, object]:
    """Build injection_data for layout_heading_description_and_content_box.

    Injector: inject_title_body — title, body (description), and
    object_contents (outcomes OBJECT placeholder).
    """
    return {
        "title": slide.title,
        "body": slide.description,
        "object_contents": {SLIDE_3_MAP["outcomes"]: _join_bullets(slide.outcomes)},
    }


# ── Filler ────────────────────────────────────────────────────────────


def _build_evidence_context(filler_input: SectionFillerInput) -> str:
    """Build evidence context string from source pack."""
    parts: list[str] = []

    if filler_input.rfp_context:
        rfp = filler_input.rfp_context
        parts.append(
            f"RFP: {rfp.rfp_name.en if rfp.rfp_name else 'Unknown'}",
        )
        if rfp.mandate:
            parts.append(f"Mandate: {rfp.mandate.en}")
        if rfp.scope_items:
            scope_text = "; ".join(
                s.description.en for s in rfp.scope_items[:10]
                if s.description and s.description.en
            )
            parts.append(f"Scope: {scope_text}")

    if filler_input.source_pack:
        sp = filler_input.source_pack
        for doc in sp.documents[:5]:
            parts.append(
                f"Source [{doc.doc_id}] {doc.title}: "
                f"{doc.content_text[:10_000]}",
            )
        if sp.projects:
            proj_text = "; ".join(
                f"{p.project_name} ({p.client}, {p.sector})"
                for p in sp.projects[:10]
            )
            parts.append(f"Relevant projects: {proj_text}")

    if filler_input.win_themes:
        parts.append(f"Win themes: {', '.join(filler_input.win_themes)}")

    return "\n\n".join(parts)


def _build_perplexity_context(filler_input: SectionFillerInput) -> str:
    """Optionally enrich with Perplexity web search.  Degrades gracefully."""
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
            f"Industry trends and challenges for {sector[:100]} in 2025-2026"
        )
        result = search_web(query, api_key=api_key, system_context=(
            "Provide concise industry context for a management consulting "
            "proposal. Focus on strategic challenges and trends."
        ))
        if result and result.content:
            return f"\n\nIndustry context (web search):\n{result.content[:3000]}"
    except Exception as exc:
        logger.debug("Perplexity enrichment skipped: %s", exc)

    return ""


class UnderstandingFiller(BaseSectionFiller):
    """Generates section_01 understanding slides.

    Uses G2 UnderstandingOutput schema with 3 distinct slide types.
    All content is typed bullet lists — no free-form text.
    """

    section_id = "section_01"
    model_name = MODEL

    async def _generate(
        self, filler_input: SectionFillerInput,
    ) -> list[ManifestEntry]:
        system = SYSTEM_PROMPT.format(
            output_language=filler_input.output_language,
        )

        evidence = _build_evidence_context(filler_input)
        perplexity_ctx = _build_perplexity_context(filler_input)

        user_msg = json.dumps({
            "evidence": evidence + perplexity_ctx,
            "slide_count": 3,
            "output_language": str(filler_input.output_language),
            "win_themes": filler_input.win_themes,
        })

        llm_response = await call_llm(
            model=self.model_name,
            system_prompt=system,
            user_message=user_msg,
            response_model=UnderstandingOutput,
            temperature=0.3,
            max_tokens=5000,
        )

        output = llm_response.parsed
        entries: list[ManifestEntry] = []

        # Slide 1 — Strategic Context (two-column)
        entries.append(make_variable_entry(
            asset_id="understanding_01",
            semantic_layout_id="layout_heading_and_two_content_with_tiltes",
            section_id="section_01",
            injection_data=build_slide_1_injection(
                output.slide_1_strategic_context,
            ),
        ))

        # Slide 2 — Core Challenges (4-box)
        entries.append(make_variable_entry(
            asset_id="understanding_02",
            semantic_layout_id="layout_heading_and_4_boxes_of_content",
            section_id="section_01",
            injection_data=build_slide_2_injection(
                output.slide_2_core_challenges,
            ),
        ))

        # Slide 3 — Success Definition (heading + description + content box)
        entries.append(make_variable_entry(
            asset_id="understanding_03",
            semantic_layout_id="layout_heading_description_and_content_box",
            section_id="section_01",
            injection_data=build_slide_3_injection(
                output.slide_3_success_definition,
            ),
        ))

        return entries
