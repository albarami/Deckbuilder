"""Why SG Filler — generates section_02 supplementary variable slides.

Section 02 ("Why Strategic Gears") is primarily A1 clones (institutional),
but may have 0-2 supplementary b_variable slides tailored to the RFP.

**Model:** Opus 4.6
**Budget:** 0-2 b_variable slides (from SlideBudgeter)
**Layouts:** content_heading_desc (narrative)
**External enrichment:** None (uses SourcePack evidence only)

When slide_count is 0, the filler returns an empty list (no-op).

Unit-tested with mocked LLM.  Integration with live LLM is production-only.
"""

from __future__ import annotations

import json
import logging

from src.models.common import DeckForgeBaseModel
from src.models.proposal_manifest import ManifestEntry
from src.services.llm import call_llm

from .base import BaseSectionFiller, SectionFillerInput, make_variable_entry

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"


# ── LLM output model ─────────────────────────────────────────────────


class WhySGSlide(DeckForgeBaseModel):
    """One Why SG supplementary slide."""

    slide_title: str
    slide_body: str


class WhySGOutput(DeckForgeBaseModel):
    """Structured output from the Why SG filler LLM call."""

    slides: list[WhySGSlide]


# ── System prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are writing supplementary "Why Strategic Gears" content for a \
proposal.  The main "Why SG" section uses institutional slides (A1 \
clones).  Your job is to produce {slide_count} ADDITIONAL slides that \
tailor the "Why SG" message to THIS SPECIFIC RFP.

Focus on:
- Relevant past projects that match the client's sector and scope
- Specific team capabilities aligned with this engagement
- Differentiators that matter for THIS client (not generic strengths)
- Evidence-backed claims using the source documents provided

Rules:
- Write in professional consulting language
- Be SPECIFIC — reference real projects and people from the evidence
- Each slide has a title and body (2-3 paragraphs)
- Do NOT use placeholder text or [brackets]
- Do NOT invent projects or people not in the evidence
- Do NOT repeat what the institutional A1 slides already cover

Output exactly {slide_count} slides.
"""


# ── Filler ────────────────────────────────────────────────────────────


def _build_evidence_context(filler_input: SectionFillerInput) -> str:
    """Build evidence context for Why SG tailoring."""
    parts: list[str] = []

    if filler_input.rfp_context:
        rfp = filler_input.rfp_context
        parts.append(f"RFP: {rfp.rfp_name.en if rfp.rfp_name else 'Unknown'}")
        if rfp.mandate:
            parts.append(f"Mandate: {rfp.mandate.en}")

    if filler_input.source_pack:
        sp = filler_input.source_pack
        if sp.projects:
            for proj in sp.projects[:10]:
                parts.append(
                    f"Project: {proj.project_name} "
                    f"(client={proj.client}, sector={proj.sector}, "
                    f"outcomes={', '.join(proj.outcomes[:3])})"
                )
        if sp.people:
            for person in sp.people[:10]:
                parts.append(
                    f"Person: {person.name} ({person.current_role}), "
                    f"expertise={', '.join(person.domain_expertise[:3])}, "
                    f"certs={', '.join(person.certifications[:3])}"
                )

    if filler_input.win_themes:
        parts.append(f"Win themes: {', '.join(filler_input.win_themes)}")

    return "\n\n".join(parts)


class WhySGFiller(BaseSectionFiller):
    """Generates section_02 supplementary Why SG slides."""

    section_id = "section_02"
    model_name = MODEL

    async def _generate(
        self, filler_input: SectionFillerInput,
    ) -> list[ManifestEntry]:
        # No-op when budget is 0
        if filler_input.slide_count == 0:
            return []

        evidence = _build_evidence_context(filler_input)

        system = SYSTEM_PROMPT.format(
            slide_count=filler_input.slide_count,
        )

        user_msg = json.dumps({
            "evidence": evidence,
            "slide_count": filler_input.slide_count,
            "output_language": filler_input.output_language,
            "win_themes": filler_input.win_themes,
        })

        # Append blueprint guidance from Slide Architect when available
        blueprint_guidance = self._format_blueprint_guidance(filler_input)
        if blueprint_guidance:
            user_msg += "\n\n" + blueprint_guidance

        llm_response = await call_llm(
            model=self.model_name,
            system_prompt=system,
            user_message=user_msg,
            response_model=WhySGOutput,
            temperature=0.3,
            max_tokens=3000,
        )

        entries: list[ManifestEntry] = []
        for i, slide in enumerate(llm_response.parsed.slides):
            entries.append(make_variable_entry(
                asset_id=f"why_sg_{i + 1:02d}",
                semantic_layout_id="content_heading_desc",
                section_id="section_02",
                injection_data={
                    "title": slide.slide_title,
                    "body": slide.slide_body,
                },
            ))

        return entries
