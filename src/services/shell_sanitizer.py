"""Phase 10 — A2 Shell Sanitizer.

Before placeholder injectors write proposal-specific content, the
A2 shell must be sanitized.  Sanitization uses the allowlist model
from the catalog lock to determine what stays and what gets cleared.

A2 assets include:
  - 3 cover shells (proposal_cover, intro_message, toc_agenda)
  - 6 section dividers (section_divider_01 .. section_divider_06)

Sanitization rules (fail-closed):
  - Clear non-approved placeholder text (placeholder not on allowlist)
  - Clear non-placeholder text boxes not on preserved-regions allowlist
  - Clear table cell text in non-approved tables
  - Clear speaker notes with forbidden template-example content
  - Clear alt-text / description fields with forbidden content
  - Clear comments / hidden metadata if they contain forbidden content
  - FAIL CLOSED: raise SanitizationError on unknown text-bearing
    elements that are not a recognized sanitization target type

Every cleared element is logged in a SanitizationReport.

Zero-shape-creation guardrail: this module NEVER creates new shapes,
text boxes, or tables.  It only clears existing content.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Exceptions ──────────────────────────────────────────────────────────


class SanitizationError(RuntimeError):
    """Raised when sanitization fails in a way that cannot be recovered."""


# ── Data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClearedElement:
    """Record of a single cleared element during sanitization."""

    shell_id: str
    element_type: str       # "placeholder" | "text_box" | "table" | "speaker_notes" | "alt_text" | "comment" | "hidden_metadata"
    shape_name: str
    reason: str             # why it was cleared
    had_content: bool       # whether it actually had text before clearing


@dataclass(frozen=True)
class SanitizationReport:
    """Complete report from sanitizing one A2 shell slide."""

    shell_id: str
    total_cleared: int
    cleared_by_type: dict[str, int]     # element_type -> count
    cleared_elements: tuple[ClearedElement, ...]
    preserved_count: int                # elements kept per allowlist
    errors: list[str] = field(default_factory=list)


# ── Allowlist loading ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ShellAllowlist:
    """Parsed allowlist for one A2 shell from the catalog lock."""

    shell_id: str
    approved_placeholder_indices: set[int]  # placeholder indices allowed for injection
    preserved_shape_names: set[str]         # non-placeholder shapes to preserve
    preserved_table_names: set[str]         # table shapes to preserve


def _parse_allowlist(shell_id: str, shell_data: dict) -> ShellAllowlist:
    """Parse a single shell's allowlist from catalog lock data."""
    al = shell_data.get("allowlist", {})

    # Approved injection placeholders
    approved_phs = al.get("approved_injection_placeholders", {})
    approved_indices = {int(idx) for idx in approved_phs}

    # Preserved text regions (by shape name)
    preserved_regions = al.get("candidate_preserved_text_regions", [])
    preserved_names = {r["shape_name"] for r in preserved_regions if "shape_name" in r}

    # Preserved tables (by shape name)
    preserved_tables = al.get("candidate_preserved_tables", [])
    preserved_table_names = {t["shape_name"] for t in preserved_tables if "shape_name" in t}

    return ShellAllowlist(
        shell_id=shell_id,
        approved_placeholder_indices=approved_indices,
        preserved_shape_names=preserved_names,
        preserved_table_names=preserved_table_names,
    )


def load_a2_allowlists(
    catalog_lock_path: Path,
) -> dict[str, ShellAllowlist]:
    """Load A2 shell allowlists from the catalog lock.

    Loads from both ``a2_shells`` (cover shells) and ``section_dividers``
    (divider shells).  Returns all 9 A2 asset allowlists.

    Parameters
    ----------
    catalog_lock_path : Path
        Path to catalog_lock_en.json or catalog_lock_ar.json.

    Returns
    -------
    dict[str, ShellAllowlist]
        Allowlists keyed by shell_id.

    Raises
    ------
    SanitizationError
        If catalog lock is missing or has no A2 assets.
    """
    if not catalog_lock_path.exists():
        raise SanitizationError(
            f"Catalog lock not found: {catalog_lock_path}"
        )

    with open(catalog_lock_path, encoding="utf-8") as f:
        lock = json.load(f)

    allowlists: dict[str, ShellAllowlist] = {}

    # ── A2 cover shells (proposal_cover, intro_message, toc_agenda) ──
    a2_shells = lock.get("a2_shells", {})
    for shell_id, shell_data in a2_shells.items():
        allowlists[shell_id] = _parse_allowlist(shell_id, shell_data)

    # ── Section dividers (01..06) ────────────────────────────────────
    section_dividers = lock.get("section_dividers", {})
    for divider_key, divider_data in section_dividers.items():
        # Canonical shell_id: "section_divider_01" etc.
        shell_id = f"section_divider_{divider_key}"
        allowlists[shell_id] = _parse_allowlist(shell_id, divider_data)

    if not allowlists:
        raise SanitizationError(
            "Catalog lock has no A2 shells or section dividers"
        )

    return allowlists


def get_allowlist(
    allowlists: dict[str, ShellAllowlist],
    shell_id: str,
) -> ShellAllowlist:
    """Look up an allowlist by shell ID.  Fail-closed.

    Raises
    ------
    SanitizationError
        If no allowlist exists for this shell ID.
    """
    if shell_id not in allowlists:
        raise SanitizationError(
            f"No allowlist for shell '{shell_id}'"
        )
    return allowlists[shell_id]


# ── Sanitization engine ────────────────────────────────────────────────

# Shape types that the sanitizer knows how to handle.
# Any text-bearing element outside this set triggers fail-closed.
_KNOWN_SHAPE_TYPES = frozenset({
    "placeholder",      # has is_placeholder = True
    "text_frame",       # has_text_frame = True (text boxes, etc.)
    "table",            # has_table = True
    "picture",          # has no text frame and no table (images)
    "connector",        # connectors, lines, etc.
    "group",            # group shapes
    "freeform",         # freeform shapes
    "chart",            # embedded charts
})


def _clear_text_frame(text_frame: Any) -> bool:
    """Clear all text from a pptx text frame.  Returns True if content existed."""
    had_content = False
    for paragraph in text_frame.paragraphs:
        for run in paragraph.runs:
            if run.text.strip():
                had_content = True
            run.text = ""
    return had_content


def _clear_table(table: Any) -> bool:
    """Clear all cell text from a pptx table.  Returns True if content existed."""
    had_content = False
    for row in table.rows:
        for cell in row.cells:
            if cell.text.strip():
                had_content = True
            cell.text = ""
    return had_content


def _is_forbidden_content(text: str) -> bool:
    """Check if text contains forbidden template-example content."""
    if not text.strip():
        return False
    forbidden_markers = [
        "lorem ipsum", "sample text", "click to edit",
        "insert text here", "type here", "add text",
        "example:", "[example", "<example",
    ]
    lower = text.lower()
    return any(marker in lower for marker in forbidden_markers)


def _classify_shape(shape: Any) -> str:
    """Classify a non-placeholder shape into a known type string.

    Returns a type from _KNOWN_SHAPE_TYPES, or "unknown" if the shape
    cannot be classified.
    """
    if shape.is_placeholder:
        return "placeholder"
    if shape.has_text_frame:
        return "text_frame"
    if shape.has_table:
        return "table"

    # Check for common non-text shape types via shape_type or XML tag
    shape_type_name = ""
    try:
        shape_type_name = str(getattr(shape, "shape_type", "")).lower()
    except Exception:
        pass

    # python-pptx MSO_SHAPE_TYPE values
    if "picture" in shape_type_name or "image" in shape_type_name:
        return "picture"
    if "group" in shape_type_name:
        return "group"
    if "freeform" in shape_type_name:
        return "freeform"
    if "connector" in shape_type_name or "line" in shape_type_name:
        return "connector"
    if "chart" in shape_type_name:
        return "chart"

    # Check XML tag for additional classification
    try:
        tag = shape._element.tag.split("}")[-1] if "}" in shape._element.tag else shape._element.tag
        tag_lower = tag.lower()
        if "pic" in tag_lower:
            return "picture"
        if "grpsp" in tag_lower:
            return "group"
        if "cxnsp" in tag_lower:
            return "connector"
    except Exception:
        pass

    return "unknown"


def _sanitize_comments(slide: Any, shell_id: str) -> list[ClearedElement]:
    """Clear comment content with forbidden template-example text.

    In python-pptx, slide comments are accessible via the slide's XML
    part relationships.  We check for comment text and clear forbidden
    content.
    """
    cleared: list[ClearedElement] = []

    try:
        # python-pptx stores comments in slide.part related parts
        slide_element = slide._element
        ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"

        # Check for extLst / comment references in the slide XML
        for ext in slide_element.iter(f"{ns_p}extLst"):
            for child in ext:
                text = child.text or ""
                if text and _is_forbidden_content(text):
                    child.text = ""
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="comment",
                        shape_name="slide_extension",
                        reason="forbidden template-example content in extension",
                        had_content=True,
                    ))

        # Check slide part for comment relationships
        if hasattr(slide, "part") and hasattr(slide.part, "rels"):
            for rel in slide.part.rels.values():
                rel_type = getattr(rel, "reltype", "")
                if "comment" in rel_type.lower():
                    try:
                        target_part = rel.target_part
                        if hasattr(target_part, "blob"):
                            blob_text = target_part.blob.decode("utf-8", errors="ignore")
                            if _is_forbidden_content(blob_text):
                                target_part._blob = b""
                                cleared.append(ClearedElement(
                                    shell_id=shell_id,
                                    element_type="comment",
                                    shape_name="comment_part",
                                    reason="forbidden template-example content in comments",
                                    had_content=True,
                                ))
                    except Exception:
                        pass

    except Exception as exc:
        logger.debug(f"Comment check for {shell_id}: {exc}")

    return cleared


def _sanitize_hidden_metadata(slide: Any, shell_id: str) -> list[ClearedElement]:
    """Clear hidden metadata fields with forbidden template-example content.

    Checks custom XML properties and other metadata stored on the slide.
    """
    cleared: list[ClearedElement] = []

    try:
        slide_element = slide._element
        ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"

        # Check for customerData or similar hidden metadata
        for cust_data in slide_element.iter(f"{ns_p}custDataLst"):
            for child in cust_data:
                text = child.text or ""
                if text and _is_forbidden_content(text):
                    child.text = ""
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="hidden_metadata",
                        shape_name="custDataLst",
                        reason="forbidden template-example content in custom data",
                        had_content=True,
                    ))

        # Check for hidden text in slide properties
        for tag_name in ["hf", "txStyles"]:
            for elem in slide_element.iter(f"{ns_p}{tag_name}"):
                text = "".join(elem.itertext())
                if text and _is_forbidden_content(text):
                    for child in list(elem):
                        elem.remove(child)
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="hidden_metadata",
                        shape_name=tag_name,
                        reason="forbidden template-example content in slide metadata",
                        had_content=True,
                    ))

    except Exception as exc:
        logger.debug(f"Hidden metadata check for {shell_id}: {exc}")

    return cleared


def sanitize_shell(
    slide: Any,
    shell_id: str,
    allowlist: ShellAllowlist,
) -> SanitizationReport:
    """Sanitize an A2 shell slide using its allowlist.

    Clears all non-approved content from the slide while preserving
    approved injection placeholders and allowlisted preserved regions.

    Raises SanitizationError on unknown text-bearing elements that
    are not a recognized sanitization target type (fail-closed).

    Parameters
    ----------
    slide : pptx.slide.Slide
        The cloned A2 shell slide to sanitize.
    shell_id : str
        The semantic shell ID.
    allowlist : ShellAllowlist
        The allowlist for this shell.

    Returns
    -------
    SanitizationReport
        Detailed report of all clearing actions.

    Raises
    ------
    SanitizationError
        If an unknown text-bearing element is encountered.
    """
    cleared: list[ClearedElement] = []
    preserved_count = 0
    errors: list[str] = []

    for shape in slide.shapes:
        shape_name = shape.name or ""

        # ── Placeholders ────────────────────────────────────────
        if shape.is_placeholder:
            ph_idx = shape.placeholder_format.idx
            if ph_idx in allowlist.approved_placeholder_indices:
                # Approved for injection — clear template text so injectors
                # start from blank
                if shape.has_text_frame:
                    had = _clear_text_frame(shape.text_frame)
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="placeholder",
                        shape_name=shape_name,
                        reason=f"approved placeholder idx={ph_idx} cleared for injection",
                        had_content=had,
                    ))
                elif shape.has_table:
                    had = _clear_table(shape.table)
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="table",
                        shape_name=shape_name,
                        reason=f"approved table placeholder idx={ph_idx} cleared for injection",
                        had_content=had,
                    ))
                else:
                    # Picture or other — preserve shape, nothing to clear
                    preserved_count += 1
            else:
                # Non-approved placeholder — clear any text
                if shape.has_text_frame:
                    had = _clear_text_frame(shape.text_frame)
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="placeholder",
                        shape_name=shape_name,
                        reason=f"non-approved placeholder idx={ph_idx}",
                        had_content=had,
                    ))
                else:
                    preserved_count += 1
            continue

        # ── Non-placeholder shapes ──────────────────────────────

        # Check preserved regions allowlist
        if shape_name in allowlist.preserved_shape_names:
            preserved_count += 1
            continue

        # Check preserved tables allowlist
        if shape.has_table:
            if shape_name in allowlist.preserved_table_names:
                preserved_count += 1
                continue
            # Non-approved table — clear
            had = _clear_table(shape.table)
            cleared.append(ClearedElement(
                shell_id=shell_id,
                element_type="table",
                shape_name=shape_name,
                reason="non-approved table outside allowlist",
                had_content=had,
            ))
            continue

        # Non-placeholder text box outside allowlist — clear
        if shape.has_text_frame:
            had = _clear_text_frame(shape.text_frame)
            cleared.append(ClearedElement(
                shell_id=shell_id,
                element_type="text_box",
                shape_name=shape_name,
                reason="text box outside allowlist",
                had_content=had,
            ))
            continue

        # ── Non-text shapes ─────────────────────────────────────
        shape_type = _classify_shape(shape)
        if shape_type == "unknown":
            # FAIL CLOSED: unknown text-bearing element outside allowlist
            raise SanitizationError(
                f"Shell '{shell_id}': unknown shape type for "
                f"'{shape_name}' — cannot determine if text-bearing. "
                f"Fail-closed: shape must be added to allowlist or "
                f"classified as a known type."
            )

        # Known non-text shape (picture, connector, group, etc.)
        preserved_count += 1

    # ── Speaker notes ───────────────────────────────────────────
    if slide.has_notes_slide:
        notes_frame = slide.notes_slide.notes_text_frame
        notes_text = notes_frame.text if notes_frame else ""
        if _is_forbidden_content(notes_text):
            _clear_text_frame(notes_frame)
            cleared.append(ClearedElement(
                shell_id=shell_id,
                element_type="speaker_notes",
                shape_name="notes_text_frame",
                reason="forbidden template-example content in notes",
                had_content=True,
            ))

    # ── Alt-text / description fields ───────────────────────────
    for shape in slide.shapes:
        try:
            desc_elem = shape._element
            cNvPr = None
            for tag in ["nvSpPr", "nvPicPr", "nvGrpSpPr", "nvCxnSpPr"]:
                ns = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
                nv = desc_elem.find(f"{ns}{tag}")
                if nv is not None:
                    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
                    cNvPr = nv.find(f"{ns_a}cNvPr") or nv.find(
                        "{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr"
                    )
                    break

            if cNvPr is not None:
                descr = cNvPr.get("descr", "")
                if descr and _is_forbidden_content(descr):
                    cNvPr.set("descr", "")
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="alt_text",
                        shape_name=shape.name or "",
                        reason="forbidden template-example content in alt-text",
                        had_content=True,
                    ))
        except Exception as exc:
            logger.debug(f"Alt-text check skipped for {shape.name}: {exc}")

    # ── Comments ────────────────────────────────────────────────
    cleared.extend(_sanitize_comments(slide, shell_id))

    # ── Hidden metadata ─────────────────────────────────────────
    cleared.extend(_sanitize_hidden_metadata(slide, shell_id))

    # ── Build report ────────────────────────────────────────────
    by_type: dict[str, int] = {}
    for ce in cleared:
        by_type[ce.element_type] = by_type.get(ce.element_type, 0) + 1

    return SanitizationReport(
        shell_id=shell_id,
        total_cleared=len(cleared),
        cleared_by_type=by_type,
        cleared_elements=tuple(cleared),
        preserved_count=preserved_count,
        errors=errors,
    )


# ── Batch sanitization ─────────────────────────────────────────────────


def sanitize_all_shells(
    slides: dict[str, Any],
    allowlists: dict[str, ShellAllowlist],
) -> dict[str, SanitizationReport]:
    """Sanitize all A2 shell slides.

    Parameters
    ----------
    slides : dict[str, Slide]
        Shell ID → pptx Slide object.
    allowlists : dict[str, ShellAllowlist]
        Shell ID → allowlist.

    Returns
    -------
    dict[str, SanitizationReport]
        Reports keyed by shell ID.

    Raises
    ------
    SanitizationError
        If any shell has no allowlist (fail-closed).
    """
    reports: dict[str, SanitizationReport] = {}
    for shell_id, slide in slides.items():
        allowlist = get_allowlist(allowlists, shell_id)
        reports[shell_id] = sanitize_shell(slide, shell_id, allowlist)
    return reports


# ── Validation ──────────────────────────────────────────────────────────


def validate_sanitization(
    reports: dict[str, SanitizationReport],
) -> list[str]:
    """Validate that sanitization completed without errors.

    Returns a list of error messages (empty if all clean).
    """
    errors: list[str] = []
    for shell_id, report in reports.items():
        if report.errors:
            for err in report.errors:
                errors.append(f"Shell '{shell_id}': {err}")
    return errors
