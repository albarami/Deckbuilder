"""Numeric commitment detector — Slice 4.2.

Scans client-facing ArtifactSection text for numeric ranges and tries
to resolve each detected commitment against the ClaimRegistry plus the
ProposalOptionRegistry.

Resolution priority:
  1. an ``rfp_fact`` ClaimProvenance whose text contains the canonical
     numeric form (e.g. "5-8" or "12") → ``resolution="rfp_fact"``;
  2. a ``proposal_option`` ClaimProvenance whose linked
     :class:`ProposalOption` has ``approved_for_external_use=True`` and
     whose text contains the canonical form → ``resolution="approved_option"``;
  3. otherwise → ``resolution="unresolved"``.

Internal-only sections (internal_gap_appendix, internal_bid_notes,
evidence_ledger, drafting_notes) are not scanned because numeric
commitments there are not addressed to the client.

The detector normalizes Arabic-Indic digits (٠–٩) to ASCII (0–9) and
treats the Arabic separators ``إلى`` / ``حتى`` and the English
``to`` / ``until`` as range separators. Year ranges (4-digit-4-digit)
are excluded — they are date commitments rather than scope
commitments and would create false positives.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from src.models.claim_provenance import (
    ClaimRegistry,
    ProposalOptionRegistry,
)
from src.models.common import DeckForgeBaseModel
from src.services.artifact_gates import ArtifactSection


_ARABIC_DIGIT_TR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Section types whose numeric content is addressed to the client.
_CLIENT_FACING_SECTION_TYPES: set[str] = {
    "client_facing_body",
    "proof_column",
    "slide_body",
    "slide_proof_points",
}

# A range expression: "5-8", "5–8", "5—8", "5 to 8", "5 إلى 8", "5 حتى 8".
# Both numbers may use ASCII or Arabic-Indic digits.
_RANGE_RE = re.compile(
    r"(?P<lo>[0-9٠-٩]+)\s*"
    r"(?:[-–—]|to|until|إلى|حتى)\s*"
    r"(?P<hi>[0-9٠-٩]+)",
    flags=re.IGNORECASE,
)

# Single-number commitment with a scope-shaping unit. The unit list
# covers contract-duration / scope / cohort / workshop / deliverable
# language in English and Arabic. We only flag a single number when it
# is paired with one of these units — bare numbers in prose are too
# noisy to gate on.
_UNIT_RE = re.compile(
    r"(?P<num>[0-9٠-٩]+)\s+"
    r"(?P<unit>"
    r"months?|weeks?|days?|"
    r"countries|country|sectors?|members?|workshops?|"
    r"hours?|deliverables?|sessions?|trainings?|"
    r"شهر(?:اً|ا)?|أشهر|شهور|"
    r"أسابيع|أسبوع|"
    r"يوم(?:اً|ا)?|أيام|"
    r"دول(?:ة)?|"
    r"قطاع(?:ات)?|"
    r"عضو(?:اً|ا)?|أعضاء|"
    r"ورش(?:ة)?|"
    r"ساع(?:ة|ات)|"
    r"مخرج(?:ات)?"
    r")",
    flags=re.IGNORECASE,
)


def _to_ascii_digits(s: str) -> str:
    return s.translate(_ARABIC_DIGIT_TR)


def _is_year_range(lo: int, hi: int) -> bool:
    """Heuristic: 4-digit numbers in the 1900-2200 band are dates."""
    return 1900 <= lo <= 2200 and 1900 <= hi <= 2200


class NumericCommitment(DeckForgeBaseModel):
    """One scope-shaping numeric range detected in client-facing text."""

    text: str
    canonical: str
    section_path: str
    section_type: str
    resolution: Literal["rfp_fact", "approved_option", "unresolved"] = "unresolved"
    resolved_claim_id: str = ""
    resolved_option_id: str = ""
    notes: str = ""


def _resolve(
    canonical: str,
    claim_registry: ClaimRegistry,
    option_registry: ProposalOptionRegistry,
) -> tuple[str, str, str]:
    """Return (resolution, resolved_claim_id, resolved_option_id)."""
    # Prefer rfp_fact resolutions: these are RFP-side facts, not bid
    # commitments, and they always supersede options.
    for c in claim_registry.rfp_facts:
        if canonical in (c.text or ""):
            return "rfp_fact", c.claim_id, ""

    # Approved proposal options: claim text must mention canonical AND
    # the linked ProposalOption must be approved_for_external_use.
    for c in claim_registry.proposal_options:
        if canonical not in (c.text or ""):
            continue
        option = option_registry.get(c.claim_id)
        if option is not None and option.approved_for_external_use:
            return "approved_option", "", option.option_id

    return "unresolved", "", ""


def detect_numeric_commitments(
    sections: list[ArtifactSection],
    claim_registry: ClaimRegistry,
    option_registry: ProposalOptionRegistry,
) -> list[NumericCommitment]:
    """Detect and resolve numeric commitments across the given sections.

    Only client-facing sections are scanned. Each ``NumericCommitment``
    carries its canonical "lo-hi" form, the section it came from, and a
    resolution status.
    """
    out: list[NumericCommitment] = []
    for section in sections:
        if section.section_type not in _CLIENT_FACING_SECTION_TYPES:
            continue
        text = section.text or ""
        text_for_match = _to_ascii_digits(text)

        # Track ranges first so single-number matches inside them are
        # not double-counted.
        consumed_spans: list[tuple[int, int]] = []
        for m in _RANGE_RE.finditer(text_for_match):
            try:
                lo = int(m.group("lo"))
                hi = int(m.group("hi"))
            except ValueError:
                continue
            if _is_year_range(lo, hi):
                continue
            lo_c, hi_c = (lo, hi) if lo <= hi else (hi, lo)
            canonical = f"{lo_c}-{hi_c}"
            resolution, claim_id, option_id = _resolve(
                canonical, claim_registry, option_registry,
            )
            out.append(NumericCommitment(
                text=m.group(0),
                canonical=canonical,
                section_path=section.section_path,
                section_type=section.section_type,
                resolution=resolution,
                resolved_claim_id=claim_id,
                resolved_option_id=option_id,
            ))
            consumed_spans.append(m.span())

        for m in _UNIT_RE.finditer(text_for_match):
            # Skip if this single-number match falls inside a range
            # expression we already emitted.
            num_start = m.start("num")
            if any(s[0] <= num_start < s[1] for s in consumed_spans):
                continue
            try:
                num = int(m.group("num"))
            except ValueError:
                continue
            unit = m.group("unit")
            canonical = f"{num} {unit}".lower()
            resolution, claim_id, option_id = _resolve(
                canonical, claim_registry, option_registry,
            )
            # Bare numeric fallback: also try just the number so that
            # registry entries expressed in different unit-language
            # (e.g. "12 شهراً" vs "12 months") still resolve.
            if resolution == "unresolved":
                resolution_num, claim_id_num, option_id_num = _resolve(
                    str(num), claim_registry, option_registry,
                )
                if resolution_num != "unresolved":
                    resolution = resolution_num
                    claim_id = claim_id_num
                    option_id = option_id_num
            out.append(NumericCommitment(
                text=m.group(0),
                canonical=canonical,
                section_path=section.section_path,
                section_type=section.section_type,
                resolution=resolution,
                resolved_claim_id=claim_id,
                resolved_option_id=option_id,
            ))
    return out
