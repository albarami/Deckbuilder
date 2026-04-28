"""Introduction Filler — generates section_00 intro message slide.

Section 00 ("Introduction Message") is a single-slide engagement card
with structured fields: title, client name, scope, and 4 attributes
(duration, sector, geography, service line).

**Model:** Opus 4.7
**Budget:** 1 b_variable slide (fixed)
**Layout:** intro_message — 7 placeholders (1 TITLE + 6 BODY)
**Renderability:** RENDERABLE_NOW — inject_multi_body handles all

No external enrichment.  All fields derived from RFP context.

Unit-tested with mocked LLM.  Integration with live LLM is production-only.
"""

from __future__ import annotations

import json
import logging

from src.models.proposal_manifest import ManifestEntry
from src.services.llm import call_llm

from .base import BaseSectionFiller, SectionFillerInput, make_variable_entry
from .g2_schemas import IntroMessageOutput, IntroMessageSlide

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-7"

# ── Placeholder index map ────────────────────────────────────────────────
# intro_message: 7 placeholders — derived from catalog_lock_en.json
INTRO_MAP = {
    "title": 0,          # TITLE
    "client_name": 1,    # BODY
    "scope_line": 13,    # BODY
    "attr_duration": 14,  # BODY
    "attr_sector": 15,    # BODY
    "attr_geography": 16,  # BODY
    "attr_service_line": 17,  # BODY
}


# ── System prompt ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior management consultant producing the Introduction Message \
slide for a proposal PRESENTATION.  This is the FIRST slide after the cover \
— a structured engagement card, NOT a paragraph.

Extract from the RFP context:
- A concise engagement title (max 12 words)
- The client's full organization name
- A one-line scope statement (max 15 words)
- Duration (e.g., "16 weeks")
- Sector (e.g., "Government / ICT")
- Geography (e.g., "KSA - Riyadh")
- Service line (e.g., "Digital Transformation Advisory")

CRITICAL RULES:
- Every field is REQUIRED — no empty strings
- No placeholder text, no [brackets], no TBD
- Derive all values from the provided evidence
- Title may be up to 12 words (engagement names are longer)
- scope_line max 15 words — sharp and specific
- Each attribute max 30 characters
- If output_language is "ar", write title, client_name, scope_line in Arabic
- Attribute fields may contain numerals with Arabic text in AR mode

Output language: {output_language}
"""


# ── Injection data builder ───────────────────────────────────────────────


def build_intro_injection(slide: IntroMessageSlide) -> dict[str, object]:
    """Build injection_data for intro_message layout.

    Maps each IntroMessageSlide field to its placeholder index
    via body_contents dict (inject_multi_body).
    """
    body_contents: dict[int, str] = {
        INTRO_MAP["client_name"]: slide.client_name,
        INTRO_MAP["scope_line"]: slide.scope_line,
        INTRO_MAP["attr_duration"]: slide.attr_duration,
        INTRO_MAP["attr_sector"]: slide.attr_sector,
        INTRO_MAP["attr_geography"]: slide.attr_geography,
        INTRO_MAP["attr_service_line"]: slide.attr_service_line,
    }
    return {
        "title": slide.title,
        "body_contents": body_contents,
    }


# ── Filler ───────────────────────────────────────────────────────────────


class IntroductionFiller(BaseSectionFiller):
    """Generates section_00 introduction message slide."""

    section_id = "section_00"
    model_name = MODEL

    async def _generate(
        self, filler_input: SectionFillerInput,
    ) -> list[ManifestEntry]:
        evidence_parts: list[str] = []

        if filler_input.rfp_context:
            rfp = filler_input.rfp_context
            if rfp.rfp_name:
                evidence_parts.append(
                    f"RFP: {rfp.rfp_name.en or rfp.rfp_name.ar or ''}",
                )
            if rfp.mandate:
                evidence_parts.append(
                    f"Mandate: {rfp.mandate.en or rfp.mandate.ar or ''}",
                )
            if rfp.scope_items:
                scope_text = "; ".join(
                    s.description.en or s.description.ar or ""
                    for s in rfp.scope_items[:10]
                    if s.description
                )
                evidence_parts.append(f"Scope: {scope_text}")

        if filler_input.win_themes:
            evidence_parts.append(
                f"Win themes: {', '.join(filler_input.win_themes)}",
            )

        system = SYSTEM_PROMPT.format(
            output_language=filler_input.output_language,
        )

        user_msg = json.dumps({
            "evidence": "\n\n".join(evidence_parts),
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
            response_model=IntroMessageOutput,
            temperature=0.2,
            max_tokens=1500,
        )

        output = llm_response.parsed
        slide = output.slide

        return [make_variable_entry(
            asset_id="intro_message",
            semantic_layout_id="intro_message",
            section_id="section_00",
            injection_data=build_intro_injection(slide),
        )]
