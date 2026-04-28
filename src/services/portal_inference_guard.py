"""Portal inference guard — Slice 5.1.

Decides whether a Source Book should commit to a specific procurement
portal name. The default is the generic Arabic placeholder
``البوابة الإلكترونية المعتمدة`` ("the approved electronic portal");
the extractor only overrides this when a known portal brand appears
in a body / table / submission-clause region.

Two brand sets:

* ``PORTAL_BRANDS`` — names that ARE portals when they appear in a
  scope/clause context (e.g. Etimad / منصة اعتماد).
* ``TEMPLATE_OR_AUTHORITY_BRANDS`` — names that look procurement-y but
  are templates or authorities, NOT portals (e.g. EXPRO, NUPCO).
  These never become a portal name, even in body text, because they
  don't operate the submission portal.

Logo, header, footer, and watermark regions are excluded from
explicit-confidence promotion: a brand seen only in those layouts is
recorded but does not justify naming the portal in the proposal.
"""
from __future__ import annotations

from typing import Literal

from src.models.common import DeckForgeBaseModel


# Brand sets — case-sensitive comparison against the source span text.
PORTAL_BRANDS: set[str] = {
    "Etimad",
    "etimad",
    "اعتماد",
    "منصة اعتماد",
}

TEMPLATE_OR_AUTHORITY_BRANDS: set[str] = {
    "EXPRO",
    "اكسبرو",
    "NUPCO",
    "نوبكو",
}

# Regions where brand presence cannot promote portal confidence.
_LOGO_REGIONS: set[str] = {"logo", "header", "footer", "watermark"}

# Default portal name when nothing explicit is detected.
_DEFAULT_PORTAL_NAME = "البوابة الإلكترونية المعتمدة"


class ExtractedTextSpan(DeckForgeBaseModel):
    """A text span attributed to a region of the source document."""

    text: str
    page: int = 0
    region_type: Literal[
        "header",
        "footer",
        "body",
        "table",
        "logo",
        "watermark",
        "unknown",
    ] = "unknown"


class PortalExtraction(DeckForgeBaseModel):
    """Extractor output describing the portal commitment."""

    portal_name: str = _DEFAULT_PORTAL_NAME
    portal_confidence: Literal[
        "explicit_submission_clause",
        "likely_from_context",
        "unknown_named_portal",
    ] = "unknown_named_portal"
    source_clause: str = ""
    inferred_from_logo: bool = False


def _matches(span_text: str, brands: set[str]) -> str | None:
    """Return the matching brand if any, preferring the longest match."""
    text = span_text or ""
    matched: list[str] = []
    for b in brands:
        if not b:
            continue
        if b in text or b.lower() in text.lower():
            matched.append(b)
    if not matched:
        return None
    return max(matched, key=len)


def extract_portal(
    spans: list[ExtractedTextSpan],
) -> PortalExtraction:
    """Extract a portal commitment from a list of region-tagged spans.

    Rules:
      * any span whose text matches a TEMPLATE_OR_AUTHORITY_BRANDS
        member NEVER produces a portal name — those brands run
        templates and procurement frameworks, not portals;
      * a PORTAL_BRANDS match in body / table / submission-clause
        promotes confidence to ``explicit_submission_clause`` and
        names the portal;
      * a PORTAL_BRANDS match only in logo / header / footer /
        watermark sets ``inferred_from_logo=True`` but leaves the
        confidence at ``unknown_named_portal`` — the proposal must use
        the generic placeholder.
    """
    explicit_match: str | None = None
    explicit_clause: str = ""
    seen_in_logo: bool = False

    for span in spans:
        # Template / authority brands disqualify even body matches —
        # they are not portals regardless of region.
        tba = _matches(span.text, TEMPLATE_OR_AUTHORITY_BRANDS)
        if tba is not None:
            # Recorded but ignored for portal commitment.
            continue

        portal = _matches(span.text, PORTAL_BRANDS)
        if portal is None:
            continue

        if span.region_type in _LOGO_REGIONS:
            seen_in_logo = True
            continue

        # body / table / unknown body-equivalent regions — explicit.
        if explicit_match is None:
            explicit_match = portal
            explicit_clause = span.text

    if explicit_match is not None:
        return PortalExtraction(
            portal_name=explicit_match,
            portal_confidence="explicit_submission_clause",
            source_clause=explicit_clause,
            inferred_from_logo=False,
        )

    return PortalExtraction(
        portal_name=_DEFAULT_PORTAL_NAME,
        portal_confidence="unknown_named_portal",
        source_clause="",
        inferred_from_logo=seen_in_logo,
    )
