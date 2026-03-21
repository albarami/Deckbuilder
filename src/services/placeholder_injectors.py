"""Phase 11 — Placeholder Injectors.

Semantic-layout-driven injection into existing placeholders only.
No shape creation.  All resolution by semantic layout ID — never raw
slide indices or display names.

Injector functions write proposal-specific content into pre-sanitized
A2 shells and B variable slides.  Each injector is keyed by a layout
family and respects the PlaceholderContract for that layout.

Formatting rules:
  - Bold key phrases where required (first sentence or label)
  - Preserve template formatting unless explicitly needed for fit
  - Inject into existing placeholders only — never create shapes
  - Validate against PlaceholderContract before injection

Layout families covered:
  - Title/heading layouts (content_heading_desc, content_heading_only, etc.)
  - Cover shells (proposal_cover, intro_message)
  - Section dividers (section_divider_01..06)
  - Table of contents (toc_table)
  - Methodology layouts (overview, focused, detail)
  - Case study layouts (detailed, cases)
  - Team layouts (team_two_members)
  - Content box layouts (4boxes, desc_box)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.services.placeholder_contracts import (
    PlaceholderContract,
    validate_placeholders,
)

logger = logging.getLogger(__name__)


# ── Exceptions ──────────────────────────────────────────────────────────


class InjectionError(RuntimeError):
    """Raised when placeholder injection fails."""


# ── Data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InjectedPlaceholder:
    """Record of one placeholder injection."""

    placeholder_idx: int
    placeholder_type: str       # TITLE, BODY, TABLE, etc.
    content_preview: str        # first 80 chars of injected content
    bold_applied: bool = False


@dataclass(frozen=True)
class InjectionResult:
    """Result of injecting content into one slide."""

    semantic_layout_id: str
    injected: tuple[InjectedPlaceholder, ...] = ()
    skipped: tuple[int, ...] = ()       # placeholder indices with no content
    skipped_types: tuple[str, ...] = ()  # parallel to skipped — type per index
    errors: list[str] = field(default_factory=list)


# ── Text formatting helpers ─────────────────────────────────────────────


def _set_text_preserving_format(text_frame: Any, text: str) -> None:
    """Set text in a text frame, preserving the first paragraph's formatting.

    Clears existing runs and writes new text into the first paragraph,
    preserving the paragraph-level formatting (font, size, color, alignment).
    """
    if not text_frame.paragraphs:
        return

    first_para = text_frame.paragraphs[0]

    # Preserve the paragraph's formatting by keeping the pPr element
    # Clear all existing runs
    for run in list(first_para.runs):
        run.text = ""

    # If there's at least one run, use it; otherwise create via the paragraph
    if first_para.runs:
        first_para.runs[0].text = text
    else:
        first_para.text = text


def _set_text_with_bold_lead(text_frame: Any, text: str, bold_chars: int = 0) -> bool:
    """Set text with optional bold formatting on the leading portion.

    Parameters
    ----------
    text_frame : pptx text frame
        Target text frame.
    text : str
        Full text to inject.
    bold_chars : int
        Number of leading characters to bold.  0 = no bold.

    Returns
    -------
    bool
        True if bold was applied.
    """
    if not text_frame.paragraphs:
        return False

    first_para = text_frame.paragraphs[0]

    # Clear existing runs
    for run in list(first_para.runs):
        run.text = ""

    if bold_chars > 0 and bold_chars < len(text):
        bold_part = text[:bold_chars]
        rest_part = text[bold_chars:]

        if first_para.runs:
            first_para.runs[0].text = bold_part
            first_para.runs[0].font.bold = True
        else:
            run = first_para.add_run()
            run.text = bold_part
            run.font.bold = True

        run2 = first_para.add_run()
        run2.text = rest_part
        run2.font.bold = False
        return True
    else:
        if first_para.runs:
            first_para.runs[0].text = text
        else:
            first_para.text = text
        return False


def _find_bold_break(text: str) -> int:
    """Find the position to split text for bold key phrase.

    Bold the first sentence or up to the first colon/dash, including
    the trailing space so the bold region reads naturally.
    Returns 0 if no natural break found.
    """
    # Look for colon separator (e.g. "Key Finding: details here")
    colon_pos = text.find(": ")
    if 0 < colon_pos < 60:
        return colon_pos + 2  # include ": "

    # Look for em-dash separator
    dash_pos = text.find(" — ")
    if 0 < dash_pos < 60:
        return dash_pos + 3

    # Look for first sentence ending
    for end_char in ".!?":
        pos = text.find(end_char)
        if 0 < pos < 80:
            # Include trailing space if present
            if pos + 1 < len(text) and text[pos + 1] == " ":
                return pos + 2
            return pos + 1

    return 0


def _set_table_data(table: Any, rows: list[list[str]]) -> None:
    """Write data into an existing table, filling available cells.

    Does not create new rows or columns.
    """
    for r_idx, row in enumerate(table.rows):
        if r_idx >= len(rows):
            break
        for c_idx, cell in enumerate(row.cells):
            if c_idx >= len(rows[r_idx]):
                break
            cell.text = rows[r_idx][c_idx]


# ── Contract validation wrapper ─────────────────────────────────────────


def _validate_before_inject(
    contract: PlaceholderContract,
    actual_placeholders: dict[int, str],
) -> None:
    """Validate placeholders against contract.  Raise on violation."""
    result = validate_placeholders(contract, actual_placeholders)
    if not result.is_valid:
        details = "; ".join(v.detail for v in result.violations)
        raise InjectionError(
            f"Contract violation for '{contract.semantic_layout_id}': {details}"
        )


# ── Injector: Title/Heading layouts ─────────────────────────────────────


def inject_title_body(
    slide: Any,
    semantic_layout_id: str,
    contract: PlaceholderContract,
    *,
    title: str = "",
    body: str = "",
    bold_body_lead: bool = False,
    object_contents: dict[int, str] | None = None,
) -> InjectionResult:
    """Inject into TITLE + BODY layouts (content_heading_desc, section dividers, etc.).

    Covers: content_heading_desc, section_divider_01..06, methodology_detail,
    layout_heading_description_and_content_box (TITLE + BODY + OBJECT).

    Parameters
    ----------
    object_contents : dict[int, str] | None
        Optional mapping of placeholder index -> text for OBJECT placeholders.
        Phase G extension: enables injection into OBJECT placeholders on
        layouts like layout_heading_description_and_content_box (idx 1).
    """
    actual = _collect_placeholders(slide)
    _validate_before_inject(contract, actual)

    if object_contents is None:
        object_contents = {}
    else:
        object_contents = {int(k): v for k, v in object_contents.items()}

    injected: list[InjectedPlaceholder] = []
    skipped: list[int] = []
    skipped_types: list[str] = []

    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        ph_type = contract.required_placeholders.get(idx, "UNKNOWN")

        if ph_type in ("TITLE", "CENTER_TITLE") and title:
            _set_text_preserving_format(ph.text_frame, title)
            injected.append(InjectedPlaceholder(
                placeholder_idx=idx, placeholder_type=ph_type,
                content_preview=title[:80],
            ))
        elif ph_type == "BODY" and body:
            bold_applied = False
            if bold_body_lead:
                bold_break = _find_bold_break(body)
                bold_applied = _set_text_with_bold_lead(ph.text_frame, body, bold_break)
            else:
                _set_text_preserving_format(ph.text_frame, body)
            injected.append(InjectedPlaceholder(
                placeholder_idx=idx, placeholder_type="BODY",
                content_preview=body[:80], bold_applied=bold_applied,
            ))
        elif ph_type == "OBJECT" and idx in object_contents:
            # Phase G extension: inject text into OBJECT placeholders
            text = object_contents[idx]
            if text:
                _set_text_preserving_format(ph.text_frame, text)
                injected.append(InjectedPlaceholder(
                    placeholder_idx=idx, placeholder_type="OBJECT",
                    content_preview=text[:80],
                ))
            else:
                skipped.append(idx)
                skipped_types.append("OBJECT")
        else:
            skipped.append(idx)
            skipped_types.append(ph_type)

    return InjectionResult(
        semantic_layout_id=semantic_layout_id,
        injected=tuple(injected),
        skipped=tuple(skipped),
        skipped_types=tuple(skipped_types),
    )


# ── Injector: Center title layout ───────────────────────────────────────


def inject_center_title(
    slide: Any,
    semantic_layout_id: str,
    contract: PlaceholderContract,
    *,
    title: str = "",
) -> InjectionResult:
    """Inject into CENTER_TITLE-only layouts (content_heading_only)."""
    actual = _collect_placeholders(slide)
    _validate_before_inject(contract, actual)

    injected: list[InjectedPlaceholder] = []
    skipped: list[int] = []
    skipped_types: list[str] = []

    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        ph_type = contract.required_placeholders.get(idx, "UNKNOWN")

        if ph_type == "CENTER_TITLE" and title:
            _set_text_preserving_format(ph.text_frame, title)
            injected.append(InjectedPlaceholder(
                placeholder_idx=idx, placeholder_type="CENTER_TITLE",
                content_preview=title[:80],
            ))
        else:
            skipped.append(idx)
            skipped_types.append(ph_type)

    return InjectionResult(
        semantic_layout_id=semantic_layout_id,
        injected=tuple(injected),
        skipped=tuple(skipped),
        skipped_types=tuple(skipped_types),
    )


# ── Injector: Proposal cover ────────────────────────────────────────────


def inject_proposal_cover(
    slide: Any,
    contract: PlaceholderContract,
    *,
    subtitle: str = "",
    client_name: str = "",
    date_text: str = "",
) -> InjectionResult:
    """Inject into proposal_cover layout (SUBTITLE + BODY fields)."""
    actual = _collect_placeholders(slide)
    _validate_before_inject(contract, actual)

    injected: list[InjectedPlaceholder] = []
    skipped: list[int] = []
    skipped_types: list[str] = []

    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        ph_type = contract.required_placeholders.get(idx, "UNKNOWN")

        if ph_type == "SUBTITLE" and subtitle:
            _set_text_preserving_format(ph.text_frame, subtitle)
            injected.append(InjectedPlaceholder(
                placeholder_idx=idx, placeholder_type="SUBTITLE",
                content_preview=subtitle[:80],
            ))
        elif ph_type == "BODY" and idx == 10 and client_name:
            _set_text_preserving_format(ph.text_frame, client_name)
            injected.append(InjectedPlaceholder(
                placeholder_idx=idx, placeholder_type="BODY",
                content_preview=client_name[:80],
            ))
        elif ph_type == "BODY" and idx == 11 and date_text:
            _set_text_preserving_format(ph.text_frame, date_text)
            injected.append(InjectedPlaceholder(
                placeholder_idx=idx, placeholder_type="BODY",
                content_preview=date_text[:80],
            ))
        elif ph_type == "PICTURE":
            skipped.append(idx)
            skipped_types.append("PICTURE")
        else:
            skipped.append(idx)
            skipped_types.append(ph_type)

    return InjectionResult(
        semantic_layout_id="proposal_cover",
        injected=tuple(injected),
        skipped=tuple(skipped),
        skipped_types=tuple(skipped_types),
    )


# ── Injector: Table of contents ─────────────────────────────────────────


def inject_toc_table(
    slide: Any,
    contract: PlaceholderContract,
    *,
    title: str = "",
    rows: list[list[str]] | None = None,
) -> InjectionResult:
    """Inject into toc_table layout (TITLE + TABLE)."""
    actual = _collect_placeholders(slide)
    _validate_before_inject(contract, actual)

    injected: list[InjectedPlaceholder] = []
    skipped: list[int] = []
    skipped_types: list[str] = []

    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        ph_type = contract.required_placeholders.get(idx, "UNKNOWN")

        if ph_type == "TITLE" and title:
            _set_text_preserving_format(ph.text_frame, title)
            injected.append(InjectedPlaceholder(
                placeholder_idx=idx, placeholder_type="TITLE",
                content_preview=title[:80],
            ))
        elif ph_type == "TABLE" and rows:
            if ph.has_table:
                _set_table_data(ph.table, rows)
                injected.append(InjectedPlaceholder(
                    placeholder_idx=idx, placeholder_type="TABLE",
                    content_preview=f"{len(rows)} rows",
                ))
            else:
                skipped.append(idx)
                skipped_types.append("TABLE")
        else:
            skipped.append(idx)
            skipped_types.append(ph_type)

    return InjectionResult(
        semantic_layout_id="toc_table",
        injected=tuple(injected),
        skipped=tuple(skipped),
        skipped_types=tuple(skipped_types),
    )


# ── Injector: Multi-body layouts ────────────────────────────────────────


def inject_multi_body(
    slide: Any,
    semantic_layout_id: str,
    contract: PlaceholderContract,
    *,
    title: str = "",
    body_contents: dict[int, str] | None = None,
    bold_leads: bool = False,
) -> InjectionResult:
    """Inject into layouts with multiple BODY placeholders.

    Covers: intro_message, methodology_overview_*, methodology_focused_*,
    case_study_detailed, case_study_cases.

    Parameters
    ----------
    body_contents : dict[int, str]
        Mapping of placeholder index -> text content.
    bold_leads : bool
        If True, apply bold formatting to the key phrase in each body.
    """
    actual = _collect_placeholders(slide)
    _validate_before_inject(contract, actual)

    if body_contents is None:
        body_contents = {}
    else:
        # Coerce keys to int — JSON round-trips (LangGraph state checkpointing,
        # Pydantic serialization) turn int keys into str keys.  Without this,
        # `idx in body_contents` silently fails and all BODY placeholders are
        # treated as BODY_UNUSED, leaving the slide 100% empty.
        body_contents = {int(k): v for k, v in body_contents.items()}

    injected: list[InjectedPlaceholder] = []
    skipped: list[int] = []
    skipped_types: list[str] = []

    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        ph_type = contract.required_placeholders.get(idx, "UNKNOWN")

        if ph_type in ("TITLE", "CENTER_TITLE") and title:
            _set_text_preserving_format(ph.text_frame, title)
            injected.append(InjectedPlaceholder(
                placeholder_idx=idx, placeholder_type=ph_type,
                content_preview=title[:80],
            ))
        elif ph_type == "BODY" and idx in body_contents:
            text = body_contents[idx]
            bold_applied = False
            if bold_leads and text:
                bold_break = _find_bold_break(text)
                bold_applied = _set_text_with_bold_lead(ph.text_frame, text, bold_break)
            elif text:
                _set_text_preserving_format(ph.text_frame, text)
            injected.append(InjectedPlaceholder(
                placeholder_idx=idx, placeholder_type="BODY",
                content_preview=text[:80], bold_applied=bold_applied,
            ))
        elif ph_type == "BODY":
            # BODY placeholder not in body_contents — unused capacity
            # on multi-body layouts (not a required-unfilled error)
            skipped.append(idx)
            skipped_types.append("BODY_UNUSED")
        elif ph_type == "PICTURE":
            skipped.append(idx)
            skipped_types.append("PICTURE")
        elif ph_type == "OBJECT" and idx in body_contents:
            # OBJECT placeholder with content — inject text (Phase G extension).
            # OBJECT placeholders on multi-zone layouts (Understanding, Timeline,
            # Governance) contain text frames that accept structured bullet text.
            text = body_contents[idx]
            if text and text.strip():
                bold_applied = False
                if bold_leads:
                    bold_break = _find_bold_break(text)
                    bold_applied = _set_text_with_bold_lead(ph.text_frame, text, bold_break)
                else:
                    _set_text_preserving_format(ph.text_frame, text)
                injected.append(InjectedPlaceholder(
                    placeholder_idx=idx, placeholder_type="OBJECT",
                    content_preview=text[:80], bold_applied=bold_applied,
                ))
            else:
                skipped.append(idx)
                skipped_types.append("OBJECT")
        elif ph_type in ("OBJECT", "TABLE"):
            # OBJECT/TABLE with no content in body_contents — skip as before
            skipped.append(idx)
            skipped_types.append(ph_type)
        else:
            skipped.append(idx)
            skipped_types.append(ph_type)

    return InjectionResult(
        semantic_layout_id=semantic_layout_id,
        injected=tuple(injected),
        skipped=tuple(skipped),
        skipped_types=tuple(skipped_types),
    )


# ── Injector: Team layout ──────────────────────────────────────────────


def inject_team_members(
    slide: Any,
    contract: PlaceholderContract,
    *,
    member1_name: str = "",
    member1_role: str = "",
    member1_bio: str = "",
    member2_name: str = "",
    member2_role: str = "",
    member2_bio: str = "",
) -> InjectionResult:
    """Inject into team_two_members layout.

    Maps known placeholder indices to member data:
    - idx 14/15/16: member 1 name/role/bio
    - idx 19/20/36: member 2 name/role/bio
    - idx 13/17: pictures (skipped)
    - idx 34: table, idx 1/35: objects (skipped)
    """
    actual = _collect_placeholders(slide)
    _validate_before_inject(contract, actual)

    member_map: dict[int, tuple[str, bool]] = {
        14: (member1_name, True),     # bold name
        15: (member1_role, False),
        16: (member1_bio, False),
        19: (member2_name, True),     # bold name
        20: (member2_role, False),
        36: (member2_bio, False),
    }

    injected: list[InjectedPlaceholder] = []
    skipped: list[int] = []
    skipped_types: list[str] = []

    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        ph_type = contract.required_placeholders.get(idx, "UNKNOWN")

        if idx in member_map:
            text, make_bold = member_map[idx]
            if text:
                if make_bold:
                    _set_text_with_bold_lead(ph.text_frame, text, len(text))
                else:
                    _set_text_preserving_format(ph.text_frame, text)
                injected.append(InjectedPlaceholder(
                    placeholder_idx=idx, placeholder_type=ph_type or "BODY",
                    content_preview=text[:80], bold_applied=make_bold,
                ))
            else:
                skipped.append(idx)
                skipped_types.append(ph_type)
        else:
            skipped.append(idx)
            skipped_types.append(ph_type)

    return InjectionResult(
        semantic_layout_id="team_two_members",
        injected=tuple(injected),
        skipped=tuple(skipped),
        skipped_types=tuple(skipped_types),
    )


# ── Generic injector (dispatch by semantic layout ID) ───────────────────


# Layout family classification for dispatch
_TITLE_BODY_LAYOUTS = frozenset({
    "content_heading_desc",
    "section_divider_01", "section_divider_02", "section_divider_03",
    "section_divider_04", "section_divider_05", "section_divider_06",
    "section_divider_07", "section_divider_08", "section_divider_09",
    "layout_heading_description_and_content_box",
})

_CENTER_TITLE_LAYOUTS = frozenset({
    "content_heading_only",
})

_MULTI_BODY_LAYOUTS = frozenset({
    "intro_message",
    "methodology_overview_3", "methodology_overview_4",
    "methodology_focused_3", "methodology_focused_4",
    "methodology_detail",
    "case_study_detailed", "case_study_cases",
    "content_heading_content",
    "layout_heading_and_4_boxes_of_content",
    "layout_heading_and_two_content_with_tiltes",
    "layout_heading_text_box_and_content",
    "layout_heading_and_subheading",
    "layout_heading_description_and_two_rows_of_content_boxes",
})


def get_layout_family(semantic_layout_id: str) -> str:
    """Classify a semantic layout ID into its injector family.

    Returns
    -------
    str
        One of: "title_body", "center_title", "proposal_cover",
        "toc_table", "team_two_members", "multi_body", "unknown".
    """
    if semantic_layout_id == "proposal_cover":
        return "proposal_cover"
    if semantic_layout_id == "toc_table":
        return "toc_table"
    if semantic_layout_id == "team_two_members":
        return "team_two_members"
    if semantic_layout_id in _TITLE_BODY_LAYOUTS:
        return "title_body"
    if semantic_layout_id in _CENTER_TITLE_LAYOUTS:
        return "center_title"
    if semantic_layout_id in _MULTI_BODY_LAYOUTS:
        return "multi_body"
    return "unknown"


# ── Placeholder collection helper ───────────────────────────────────────


def _collect_placeholders(slide: Any) -> dict[int, str]:
    """Collect actual placeholder indices and types from a slide.

    Returns a dict of idx -> type string compatible with contract validation.
    """
    actual: dict[int, str] = {}
    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        # Determine type from placeholder format
        ph_format_type = ""
        try:
            ph_format_type = str(ph.placeholder_format.type)
        except Exception:
            pass

        # Map python-pptx placeholder types to our contract types
        # Check more specific types first (CENTER_TITLE, SUBTITLE contain "TITLE")
        if "CENTER_TITLE" in ph_format_type.upper():
            actual[idx] = "CENTER_TITLE"
        elif "SUBTITLE" in ph_format_type.upper():
            actual[idx] = "SUBTITLE"
        elif "TITLE" in ph_format_type.upper():
            actual[idx] = "TITLE"
        elif "TABLE" in ph_format_type.upper():
            actual[idx] = "TABLE"
        elif "PICTURE" in ph_format_type.upper():
            actual[idx] = "PICTURE"
        elif "OBJECT" in ph_format_type.upper():
            actual[idx] = "OBJECT"
        elif ph.has_text_frame:
            actual[idx] = "BODY"
        elif ph.has_table:
            actual[idx] = "TABLE"
        else:
            actual[idx] = "BODY"

    return actual
